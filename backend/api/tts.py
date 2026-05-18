from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.db_models import Episode
from backend.services.tts_service import ensure_valid_mp3_file, stream_speech

router = APIRouter(prefix="/api", tags=["tts"])


@router.get("/episodes/{episode_id}/audio")
async def get_episode_audio(episode_id: int, db: AsyncSession = Depends(get_db)):
    if not settings.tts_enabled:
        raise HTTPException(400, "TTS is disabled")

    ep = await db.get(Episode, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    out_path = Path(settings.audio_dir) / f"episode_{episode_id}.mp3"

    # 已快取：直接回傳檔案
    if out_path.exists():
        ensure_valid_mp3_file(out_path)
        return FileResponse(out_path, media_type="audio/mpeg", filename=f"episode_{episode_id}.mp3")

    # 逐句串流，同時在背景存盤
    ep.audio_path = str(out_path)
    await db.commit()

    return StreamingResponse(
        stream_speech(ep.content, episode_id),
        media_type="audio/mpeg",
    )

