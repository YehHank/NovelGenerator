import hashlib
import json
import logging
import re
import shutil
import subprocess
from typing import AsyncGenerator

import aiohttp
import asyncio
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

# 最小合併字數：若片段字數少於此值，會與後續片段合併再送 TTS
MIN_CHUNK_CHARS = 10


def _has_speakable_text(text: str) -> bool:
    """判斷文字是否含有可發音內容（非純標點/符號）。"""
    return bool(re.search(r'[\w\u4e00-\u9fff\u3400-\u4dbf]', text))


def _split_sentences(text: str) -> list[str]:
    """依句末標點逐句分割，過濾純標點片段。"""
    parts = re.split(r'(?<=[。！？…\n])\s*', text)
    return [p.strip() for p in parts if p.strip() and _has_speakable_text(p)]


async def _tts_fishaudio(session: aiohttp.ClientSession, text: str) -> bytes:
    """呼叫 Fish Audio TTS API，回傳 MP3 bytes。包含簡單重試機制以降低 transient 網路失敗影響。"""
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

    max_retries = 3
    backoff_base = 0.5
    for attempt in range(1, max_retries + 1):
        try:
            async with session.post(
                settings.fishaudio_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                if r.status != 200:
                    raise RuntimeError(f"FishAudio {r.status}: {await r.text()}")
                return await r.read()
        except (aiohttp.ClientConnectorError, asyncio.TimeoutError, OSError) as exc:
            logger.warning(
                "TTS request attempt %d/%d failed: %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt == max_retries:
                raise
            await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))


def _segments_dir(audio_dir: Path, episode_id: int) -> Path:
    return audio_dir / f"episode_{episode_id}_segments"


def _segment_manifest_path(seg_dir: Path) -> Path:
    return seg_dir / "manifest.json"


def _load_segment_manifest(seg_dir: Path, text_hash: str, total: int) -> dict:
    """載入分段 manifest；若 hash 或總數不符則視為無效。"""
    manifest_path = _segment_manifest_path(seg_dir)
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("text_hash") == text_hash and manifest.get("total") == total:
                return manifest
        except (json.JSONDecodeError, KeyError):
            pass
    return {"text_hash": text_hash, "total": total, "completed": []}


def _save_segment_manifest(seg_dir: Path, manifest: dict) -> None:
    _segment_manifest_path(seg_dir).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )


async def stream_speech(text: str, episode_id: int) -> AsyncGenerator[bytes, None]:
    """逐句呼叫 TTS，支援中斷續傳：已生成的分段會暫存，重新請求時從中斷點繼續。"""
    audio_dir = settings.audio_dir
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / f"episode_{episode_id}.mp3"
    raw_path = audio_dir / f"episode_{episode_id}.raw.mp3"

    sentences = _split_sentences(text) or [text]

    # 將過短的片段（< MIN_CHUNK_CHARS）與後續片段合併，避免一次送出非常短的文字
    chunks: list[str] = []
    cur: str = ""
    for s in sentences:
        if not cur:
            cur = s
            continue

        if len(cur.strip()) < MIN_CHUNK_CHARS:
            sep = "" if cur.endswith(("\n", " ")) else " "
            cur = cur + sep + s
        else:
            chunks.append(cur)
            cur = s

    if cur:
        chunks.append(cur)

    total = len(chunks)
    text_hash = hashlib.md5(text.encode()).hexdigest()

    # 建立分段暫存目錄
    seg_dir = _segments_dir(audio_dir, episode_id)
    seg_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_segment_manifest(seg_dir, text_hash, total)
    completed_indices: set[int] = set(manifest.get("completed", []))

    all_chunks: list[bytes] = []

    async with aiohttp.ClientSession() as session:
        for idx, chunk in enumerate(chunks):
            seg_file = seg_dir / f"{idx:04d}.mp3"

            if idx in completed_indices and seg_file.exists():
                mp3_bytes = seg_file.read_bytes()
                logger.debug("TTS chunk %d/%d loaded from cache", idx + 1, total)
            else:
                mp3_bytes = await _tts_fishaudio(session, chunk)
                seg_file.write_bytes(mp3_bytes)
                completed_indices.add(idx)
                manifest["completed"] = sorted(completed_indices)
                _save_segment_manifest(seg_dir, manifest)
                logger.debug("TTS chunk %d/%d generated", idx + 1, total)

            yield mp3_bytes
            all_chunks.append(mp3_bytes)

    # 全部完成：合併為最終檔案
    raw_path.write_bytes(b"".join(all_chunks))
    try:
        _normalize_mp3_file(raw_path, out_path)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("Failed to normalize MP3 cache %s: %s", out_path, exc)
        raw_path.replace(out_path)
    else:
        raw_path.unlink(missing_ok=True)

    # 清理分段暫存
    shutil.rmtree(seg_dir, ignore_errors=True)

    logger.info(f"TTS audio cached: {out_path}")

