"""Pydantic schemas for API requests and responses."""
from enum import Enum
from pydantic import BaseModel, Field


class JobStatusEnum(str, Enum):
    """Job pipeline status."""

    WRITING_LYRICS = "writing_lyrics"
    GENERATING_MUSIC = "generating_music"
    DOWNLOADING = "downloading"
    ARCHIVING = "archiving"
    DONE = "done"
    ERROR = "error"


class SongRequest(BaseModel):
    """Request body for POST /v1/song."""

    device_id: str = Field(..., min_length=1, description="Device identifier (e.g. pi-zero-1)")
    transcript: str = Field(..., min_length=1, description="Transcript from Pi STT")
    style: str = Field(..., min_length=1, description="Music style from Pi")


class SongResponse(BaseModel):
    """Response for POST /v1/song."""

    job_id: str
    status_url: str


class JobStatus(BaseModel):
    """Response for GET /v1/song/{job_id}."""

    job_id: str
    status: JobStatusEnum
    lyrics: str | None = None
    audio_url: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
