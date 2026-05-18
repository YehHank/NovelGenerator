from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.db_models import PlotHook, HookStatus
from backend.models.schemas import PlotHookCreate, PlotHookUpdate, PlotHookOut

router = APIRouter(prefix="/api", tags=["hooks"])


@router.get("/stories/{story_id}/hooks", response_model=list[PlotHookOut])
async def list_hooks(story_id: int, status: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(PlotHook).where(PlotHook.story_id == story_id)
    if status:
        q = q.where(PlotHook.status == HookStatus(status))
    hooks = (await db.execute(q)).scalars().all()
    return hooks


@router.post("/stories/{story_id}/hooks", response_model=PlotHookOut)
async def create_hook(story_id: int, body: PlotHookCreate, db: AsyncSession = Depends(get_db)):
    hook = PlotHook(
        story_id=story_id,
        description=body.description,
        planted_episode=body.planted_episode,
        status=HookStatus(body.status),
    )
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return hook


@router.put("/hooks/{hook_id}", response_model=PlotHookOut)
async def update_hook(hook_id: int, body: PlotHookUpdate, db: AsyncSession = Depends(get_db)):
    hook = await db.get(PlotHook, hook_id)
    if not hook:
        raise HTTPException(404, "Hook not found")
    if body.description is not None:
        hook.description = body.description
    if body.status is not None:
        hook.status = HookStatus(body.status)
    await db.commit()
    await db.refresh(hook)
    return hook


@router.delete("/hooks/{hook_id}")
async def delete_hook(hook_id: int, db: AsyncSession = Depends(get_db)):
    hook = await db.get(PlotHook, hook_id)
    if not hook:
        raise HTTPException(404, "Hook not found")
    await db.delete(hook)
    await db.commit()
    return {"ok": True}
