import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from backend.config import settings
from backend.database import async_session, get_db
from backend.db_models import Episode, Story
from backend.models.schemas import EpisodeOut, GenerateRequest
from backend.services.story_service import generate_episode

router = APIRouter(prefix="/api", tags=["episodes"])
logger = logging.getLogger(__name__)


@router.get("/stories/{story_id}/episodes", response_model=list[EpisodeOut])
async def list_episodes(story_id: int, db: AsyncSession = Depends(get_db)):
    eps = (await db.execute(
        select(Episode)
        .where(Episode.story_id == story_id)
        .order_by(Episode.episode_number)
    )).scalars().all()
    return eps


@router.get("/episodes/{episode_id}", response_model=EpisodeOut)
async def get_episode(episode_id: int, db: AsyncSession = Depends(get_db)):
    ep = await db.get(Episode, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    return ep


@router.post("/stories/{story_id}/episodes/generate", response_model=EpisodeOut)
async def generate_ep(story_id: int, body: GenerateRequest, db: AsyncSession = Depends(get_db)):
    try:
        episode, _, _fin = await generate_episode(db, story_id, body.direction_hint, stream=False)
        return episode
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/stories/{story_id}/episodes/generate/stream")
async def generate_ep_stream(story_id: int, body: GenerateRequest):
    """SSE streaming endpoint for episode generation."""
    async with async_session() as db:
        story = await db.get(Story, story_id)
        if not story:
            raise HTTPException(404, f"Story {story_id} not found")

    async def event_stream():
        async with async_session() as db:
            try:
                episode, content_gen, finalize = await generate_episode(db, story_id, body.direction_hint, stream=True)

                meta = {"episode_id": episode.id, "episode_number": episode.episode_number}
                yield f"data: {json.dumps(meta)}\n\n"

                chunks: list[str] = []

                async for chunk in content_gen:
                    chunks.append(chunk)
                    payload = json.dumps({"content": chunk}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

                await finalize("".join(chunks))
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as exc:
                await db.rollback()
                logger.exception("Streaming episode generation failed for story %s", story_id)
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
