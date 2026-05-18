from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.db_models import Story, Episode
from backend.models.schemas import StoryCreate, StoryUpdate, StoryOut

router = APIRouter(prefix="/api/stories", tags=["stories"])


@router.post("", response_model=StoryOut)
async def create_story(body: StoryCreate, db: AsyncSession = Depends(get_db)):
    story = Story(**body.model_dump())
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return {**story.__dict__, "episode_count": 0}


@router.get("", response_model=list[StoryOut])
async def list_stories(db: AsyncSession = Depends(get_db)):
    stories = (await db.execute(select(Story).order_by(Story.created_at.desc()))).scalars().all()
    result = []
    for s in stories:
        count = (await db.execute(
            select(func.count(Episode.id)).where(Episode.story_id == s.id)
        )).scalar() or 0
        result.append({**s.__dict__, "episode_count": count})
    return result


@router.get("/{story_id}", response_model=StoryOut)
async def get_story(story_id: int, db: AsyncSession = Depends(get_db)):
    story = await db.get(Story, story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    count = (await db.execute(
        select(func.count(Episode.id)).where(Episode.story_id == story_id)
    )).scalar() or 0
    return {**story.__dict__, "episode_count": count}


@router.put("/{story_id}", response_model=StoryOut)
async def update_story(story_id: int, body: StoryUpdate, db: AsyncSession = Depends(get_db)):
    story = await db.get(Story, story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(story, k, v)
    await db.commit()
    await db.refresh(story)
    count = (await db.execute(
        select(func.count(Episode.id)).where(Episode.story_id == story_id)
    )).scalar() or 0
    return {**story.__dict__, "episode_count": count}


@router.delete("/{story_id}")
async def delete_story(story_id: int, db: AsyncSession = Depends(get_db)):
    story = await db.get(Story, story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    await db.delete(story)
    await db.commit()
    return {"ok": True}
