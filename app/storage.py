"""File paths, download, and archive operations."""
import json
import logging
import shutil
from pathlib import Path

import httpx

from app.config import get_settings
from app.models import JobStatusEnum

logger = logging.getLogger(__name__)


def get_data_dir() -> Path:
    """Return base data directory."""
    return get_settings().DATA_DIR


def get_jobs_dir() -> Path:
    """Return jobs directory."""
    return get_data_dir() / "jobs"


def get_out_dir() -> Path:
    """Return output directory for audio and metadata."""
    return get_data_dir() / "out"


def get_job_path(job_id: str) -> Path:
    """Return path to job JSON file."""
    return get_jobs_dir() / f"{job_id}.json"


def get_audio_path(job_id: str) -> Path:
    """Return path to audio file (mp3)."""
    return get_out_dir() / f"{job_id}.mp3"


def get_metadata_path(job_id: str) -> Path:
    """Return path to metadata JSON file."""
    return get_out_dir() / f"{job_id}.json"


async def download_audio(url: str, path: Path) -> None:
    """Stream download audio from URL to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=600) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)


async def archive_job(job_id: str) -> str:
    """
    Copy audio and metadata to archive path if enabled.
    Returns 'ok', 'skipped', or 'failed'.
    """
    settings = get_settings()
    if not settings.ARCHIVE_ENABLED:
        return "skipped"

    archive_path = settings.ARCHIVE_PATH
    audio_path = get_audio_path(job_id)
    metadata_path = get_metadata_path(job_id)

    if not audio_path.exists() or not metadata_path.exists():
        logger.warning("job_id=%s archive skipped: audio or metadata missing", job_id)
        return "skipped"

    try:
        archive_path.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio_path, archive_path / f"{job_id}.mp3")
        shutil.copy2(metadata_path, archive_path / f"{job_id}.json")
        return "ok"
    except OSError as e:
        logger.warning("job_id=%s archive failed: %s", job_id, e)
        return "failed"
