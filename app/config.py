"""Environment-based configuration."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load config from env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BEARER_TOKEN: str
    MINIMAX_API_KEY: str
    DATA_DIR: Path = Path("./data")
    ARCHIVE_ENABLED: bool = False
    ARCHIVE_PATH: Path = Path("/mnt/nas/music-agent")
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BASE_URL: str = "http://localhost:8000"  # For absolute audio_url in responses


def get_settings() -> Settings:
    """Return validated settings."""
    return Settings()
