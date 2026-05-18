from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    # LLM
    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "default"

    # TTS (Fish Audio)
    tts_enabled: bool = True
    fishaudio_url: str = "http://localhost:8080/v1/tts"
    fishaudio_api_key: str = ""
    fishaudio_reference_id: str = ""
    fishaudio_chunk_length: int = 200
    fishaudio_memory_cache: str = "on"
    fishaudio_max_new_tokens: int = 256

    # Generation
    context_full_episodes: int = 3
    context_summary_episodes: int = 20
    max_tokens: int = 4096
    temperature: float = 0.8

    # Database (PostgreSQL)
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "n8n_user"
    postgres_password: str = "n8n_secure_password"
    postgres_db: str = "novelgenerator"

    # Paths
    data_dir: Path = Path(__file__).parent.parent / "data"

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


settings = Settings()
