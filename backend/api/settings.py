from fastapi import APIRouter
from backend.config import settings
from backend.models.schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_settings():
    return SettingsOut(
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        tts_enabled=settings.tts_enabled,
        fishaudio_url=settings.fishaudio_url,
        fishaudio_reference_id=settings.fishaudio_reference_id,
        fishaudio_chunk_length=settings.fishaudio_chunk_length,
        fishaudio_memory_cache=settings.fishaudio_memory_cache,
        fishaudio_max_new_tokens=settings.fishaudio_max_new_tokens,
        context_full_episodes=settings.context_full_episodes,
        context_summary_episodes=settings.context_summary_episodes,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )


@router.put("", response_model=SettingsOut)
async def update_settings(body: SettingsUpdate):
    for k, v in body.model_dump(exclude_unset=True).items():
        if hasattr(settings, k):
            object.__setattr__(settings, k, v)
    return await get_settings()
