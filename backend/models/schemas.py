from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Story ──
class StoryCreate(BaseModel):
    title: str
    genre: str = ""
    world_setting: str = ""
    writing_style: str = ""
    auto_generate: bool = False
    auto_interval_sec: int = 300


class StoryUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    world_setting: Optional[str] = None
    writing_style: Optional[str] = None
    auto_generate: Optional[bool] = None
    auto_interval_sec: Optional[int] = None


class StoryOut(BaseModel):
    id: int
    title: str
    genre: str
    world_setting: str
    writing_style: str
    auto_generate: bool
    auto_interval_sec: int
    created_at: datetime
    episode_count: int = 0

    model_config = {"from_attributes": True}


# ── Episode ──
class EpisodeOut(BaseModel):
    id: int
    story_id: int
    episode_number: int
    title: str
    content: str
    summary: str
    direction_hint: str
    audio_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    direction_hint: str = ""


# ── Character ──
class CharacterCreate(BaseModel):
    name: str
    description: str = ""
    current_state: dict = {}
    traits: dict = {}
    relationship_map: dict = {}


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    current_state: Optional[dict] = None
    traits: Optional[dict] = None
    relationship_map: Optional[dict] = None


class CharacterOut(BaseModel):
    id: int
    story_id: int
    name: str
    description: str
    current_state: dict
    traits: dict
    relationship_map: dict

    model_config = {"from_attributes": True}


# ── PlotHook ──
class PlotHookCreate(BaseModel):
    description: str
    planted_episode: int = 0
    status: str = "active"


class PlotHookUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None


class PlotHookOut(BaseModel):
    id: int
    story_id: int
    description: str
    planted_episode: int
    referenced_episodes: list
    status: str

    model_config = {"from_attributes": True}


# ── Settings (runtime) ──
class SettingsOut(BaseModel):
    llm_base_url: str
    llm_model: str
    tts_enabled: bool
    fishaudio_url: str
    fishaudio_reference_id: str
    fishaudio_chunk_length: int
    fishaudio_memory_cache: str
    fishaudio_max_new_tokens: int
    context_full_episodes: int
    context_summary_episodes: int
    max_tokens: int
    temperature: float


class SettingsUpdate(BaseModel):
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    tts_enabled: Optional[bool] = None
    fishaudio_url: Optional[str] = None
    fishaudio_api_key: Optional[str] = None
    fishaudio_reference_id: Optional[str] = None
    fishaudio_chunk_length: Optional[int] = None
    fishaudio_memory_cache: Optional[str] = None
    fishaudio_max_new_tokens: Optional[int] = None
    context_full_episodes: Optional[int] = None
    context_summary_episodes: Optional[int] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
