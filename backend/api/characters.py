from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.db_models import Character
from backend.models.schemas import CharacterCreate, CharacterUpdate, CharacterOut

router = APIRouter(prefix="/api", tags=["characters"])


@router.get("/stories/{story_id}/characters", response_model=list[CharacterOut])
async def list_characters(story_id: int, db: AsyncSession = Depends(get_db)):
    chars = (await db.execute(
        select(Character).where(Character.story_id == story_id)
    )).scalars().all()
    return chars


@router.post("/stories/{story_id}/characters", response_model=CharacterOut)
async def create_character(story_id: int, body: CharacterCreate, db: AsyncSession = Depends(get_db)):
    char = Character(story_id=story_id, **body.model_dump())
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char


@router.put("/characters/{char_id}", response_model=CharacterOut)
async def update_character(char_id: int, body: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, char_id)
    if not char:
        raise HTTPException(404, "Character not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(char, k, v)
    await db.commit()
    await db.refresh(char)
    return char


@router.delete("/characters/{char_id}")
async def delete_character(char_id: int, db: AsyncSession = Depends(get_db)):
    char = await db.get(Character, char_id)
    if not char:
        raise HTTPException(404, "Character not found")
    await db.delete(char)
    await db.commit()
    return {"ok": True}
