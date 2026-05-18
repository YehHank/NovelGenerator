import logging
import re
import subprocess
from typing import AsyncGenerator

import aiohttp
import opencc

from pathlib import Path
from backend.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# OpenCC：繁簡轉換（Fish Audio 建議送簡體）
# ============================================================

_cc_t2s = opencc.OpenCC('t2s')   # 繁體 → 簡體

# 補充 OpenCC t2s 未收錄的字符
_T2S_EXTRA = str.maketrans({
    "牠": "它",
    "著": "着",
    "裡": "里",
    "祇": "只",
    "儘": "尽",
    "剋": "克",
    "鍾": "钟",
    "噁": "恶",
    "覈": "核",
})


def _t2s(text: str) -> str:
    """繁體轉簡體，補充 OpenCC t2s 未收錄的字符。"""
    return _cc_t2s.convert(text).translate(_T2S_EXTRA)


def _normalize_mp3_file(source_path: Path, target_path: Path) -> None:
    """Re-encode concatenated MP3 fragments into a single valid MP3 file."""
    normalized_path = target_path.with_name(f"{target_path.stem}.normalized{target_path.suffix}")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(normalized_path),
        ],
        check=True,
    )
    normalized_path.replace(target_path)


def ensure_valid_mp3_file(path: Path) -> None:
    """Repair old cached MP3 files that were created by raw byte concatenation."""
    if not path.exists():
        return

    try:
        probe = subprocess.run(
            ["ffprobe", "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not found; skip MP3 validation for %s", path)
        return

    if "invalid concatenated file detected" not in (probe.stderr or "").lower():
        return

    logger.info("Repairing invalid cached MP3: %s", path)
    try:
        _normalize_mp3_file(path, path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("Failed to repair cached MP3 %s: %s", path, exc)


# 句子/子句結束標點（含逗號，讓 TTS 逐段播放）
SENTENCE_END = re.compile(r'[,，!?。！？…；;：:]+\s*')


def _split_sentences(text: str) -> list[str]:
    """依句末標點逐句分割。"""
    parts = re.split(r'(?<=[。！？…\n])\s*', text)
    return [p.strip() for p in parts if p.strip()]


async def _tts_fishaudio(session: aiohttp.ClientSession, text: str) -> bytes:
    """呼叫 Fish Audio TTS API，回傳 MP3 bytes。"""
    simplified = _t2s(text).strip() or text
    payload = {
        "text": simplified,
        "chunk_length": settings.fishaudio_chunk_length,
        "format": "mp3",
        "mp3_bitrate": 64,
        "references": [],
        "reference_id": settings.fishaudio_reference_id or None,
        "seed": None,
        "use_memory_cache": settings.fishaudio_memory_cache,
        "normalize": True,
        "streaming": False,
        "max_new_tokens": settings.fishaudio_max_new_tokens,
        "top_p": 0.7,
        "repetition_penalty": 1.1,
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {settings.fishaudio_api_key}"}
    async with session.post(
        settings.fishaudio_url,
        json=payload,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as r:
        if r.status != 200:
            raise RuntimeError(f"FishAudio {r.status}: {await r.text()}")
        return await r.read()


async def stream_speech(text: str, episode_id: int) -> AsyncGenerator[bytes, None]:
    """逐句呼叫 TTS，每句完成後立即 yield MP3 資料；全部完成後存盤快取。"""
    audio_dir = settings.audio_dir
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / f"episode_{episode_id}.mp3"
    raw_path = audio_dir / f"episode_{episode_id}.raw.mp3"

    sentences = _split_sentences(text) or [text]
    all_chunks: list[bytes] = []

    async with aiohttp.ClientSession() as session:
        for sentence in sentences:
            mp3_bytes = await _tts_fishaudio(session, sentence)
            yield mp3_bytes
            all_chunks.append(mp3_bytes)

    # 存盤，供下次直接 FileResponse。先輸出原始拼接檔，再重整成合法單一 MP3。
    raw_path.write_bytes(b"".join(all_chunks))
    try:
        _normalize_mp3_file(raw_path, out_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("Failed to normalize MP3 cache %s: %s", out_path, exc)
        raw_path.replace(out_path)
    else:
        raw_path.unlink(missing_ok=True)

    logger.info(f"TTS audio cached: {out_path}")

