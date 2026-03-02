"""FastAPI application for Music Agent backend."""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import verify_bearer
from app.config import get_settings
from app.jobs import create_job, get_job, start_worker, stop_worker
from app.models import JobStatus, JobStatusEnum, SongRequest, SongResponse


# --- Structured logging ---
class JsonFormatter(logging.Formatter):
    """JSON log formatter with request_id and job_id in extra."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "job_id"):
            log_obj["job_id"] = record.job_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging() -> None:
    """Configure structured JSON logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


# --- Request ID middleware ---
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add request_id to state and logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    start_worker()
    yield
    await stop_worker()


app = FastAPI(title="Music Agent", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)


# --- Routes ---
@app.get("/health")
async def health() -> dict:
    """Health check, no auth."""
    return {"ok": True}


@app.post("/v1/song", response_model=SongResponse)
async def post_song(
    body: SongRequest,
    _: None = Depends(verify_bearer),
) -> SongResponse:
    """Submit a new song job."""
    job_id = create_job(
        device_id=body.device_id,
        transcript=body.transcript,
        style=body.style,
    )
    settings = get_settings()
    return SongResponse(
        job_id=job_id,
        status_url=f"/v1/song/{job_id}",
    )


def _build_job_status_response(job_id: str, job: dict) -> JobStatus:
    """Build JobStatus from job dict."""
    status_val = job.get("status", "error")
    lyrics = job.get("lyrics")
    error = job.get("error")
    duration_seconds = job.get("duration_seconds")
    audio_url = None
    if status_val == JobStatusEnum.DONE.value and job.get("audio_path"):
        base = get_settings().BASE_URL.rstrip("/")
        audio_url = f"{base}/out/{job_id}.mp3"
    return JobStatus(
        job_id=job_id,
        status=JobStatusEnum(status_val),
        lyrics=lyrics,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        error=error,
    )


@app.get("/v1/song/{job_id}", response_model=None)
async def get_song_status(
    job_id: str,
    wait: int = Query(0, ge=0, le=120, description="Max seconds to hold request (long polling)"),
    _: None = Depends(verify_bearer),
):
    """Get job status. Use ?wait=60 for long polling."""
    job = get_job(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Job not found", "code": "not_found"},
        )

    # Long polling: hold until done/error or timeout
    if wait > 0:
        check_interval = 1
        elapsed = 0
        while elapsed < wait:
            job = get_job(job_id)
            if job is None:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Job not found", "code": "not_found"},
                )
            status_val = job.get("status", "error")
            if status_val in (JobStatusEnum.DONE.value, JobStatusEnum.ERROR.value):
                return _build_job_status_response(job_id, job)
            await asyncio.sleep(check_interval)
            elapsed += check_interval

    return _build_job_status_response(job_id, job)


@app.get("/out/{filename}", response_model=None)
async def get_audio(
    filename: str,
    _: None = Depends(verify_bearer),
) -> FileResponse | JSONResponse:
    """Serve generated audio file."""
    if not filename.endswith(".mp3") and not filename.endswith(".wav"):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid filename", "code": "invalid_filename"},
        )
    job_id = filename.removesuffix(".mp3").removesuffix(".wav")
    if not job_id or ".." in filename or "/" in filename:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid filename", "code": "invalid_filename"},
        )
    path = Path(get_settings().DATA_DIR) / "out" / filename
    if not path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "File not found", "code": "not_found"},
        )
    media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
    return FileResponse(path, media_type=media_type)
