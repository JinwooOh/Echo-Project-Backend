"""Job manager, persistence, and background worker."""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.models import JobStatusEnum
from app.storage import (
    archive_job as do_archive,
    download_audio,
    get_audio_path,
    get_job_path,
    get_jobs_dir,
    get_metadata_path,
    get_out_dir,
)
from app import minimax


logger = logging.getLogger(__name__)

# In-process queue and worker
_queue: asyncio.Queue[dict] | None = None
_worker_task: asyncio.Task | None = None


def _ensure_dirs() -> None:
    """Create data/jobs and data/out directories."""
    get_jobs_dir().mkdir(parents=True, exist_ok=True)
    get_out_dir().mkdir(parents=True, exist_ok=True)


def _load_job(job_id: str) -> dict | None:
    """Load job JSON from disk."""
    path = get_job_path(job_id)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("job_id=%s load failed: %s", job_id, e)
        return None


def _save_job(job_id: str, data: dict) -> None:
    """Atomically write job JSON."""
    path = get_job_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.rename(path)


def create_job(device_id: str, transcript: str, style: str) -> str:
    """Create job, persist, enqueue. Returns job_id."""
    _ensure_dirs()
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "job_id": job_id,
        "device_id": device_id,
        "transcript": transcript,
        "style": style,
        "status": JobStatusEnum.WRITING_LYRICS.value,
        "lyrics": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "audio_path": None,
        "duration_seconds": None,
        "archive_status": None,
    }
    _save_job(job_id, data)
    _queue.put_nowait(data)
    return job_id


def get_job(job_id: str) -> dict | None:
    """Load job by ID."""
    return _load_job(job_id)


def update_job(job_id: str, **kwargs: object) -> None:
    """Update job fields and persist."""
    data = _load_job(job_id)
    if data is None:
        return
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data.update(kwargs)
    _save_job(job_id, data)


async def _worker() -> None:
    """Process jobs from queue one at a time."""
    global _queue
    if _queue is None:
        return
    while True:
        try:
            job_data = await _queue.get()
            job_id = job_data["job_id"]
            logger.info("job_id=%s processing started", job_id)
            try:
                # 1. writing_lyrics
                update_job(job_id, status=JobStatusEnum.WRITING_LYRICS.value)
                lyrics = await minimax.generate_lyrics(job_data["transcript"])
                update_job(job_id, lyrics=lyrics, status=JobStatusEnum.GENERATING_MUSIC.value)

                # 2. generating_music
                result = await minimax.generate_music(lyrics, job_data["style"])
                audio_url = result.get("audio_url", "")
                duration_ms = result.get("duration_ms")
                duration_seconds = duration_ms / 1000.0 if duration_ms else None


                update_job(job_id, status=JobStatusEnum.DOWNLOADING.value)

                # 3. downloading
                audio_path = get_audio_path(job_id)
                await download_audio(audio_url, audio_path)
                update_job(
                    job_id,
                    audio_path=str(audio_path),
                    duration_seconds=duration_seconds,
                    status=JobStatusEnum.ARCHIVING.value,
                )

                # 4. archiving
                archive_status = await do_archive(job_id)
                update_job(job_id, archive_status=archive_status, status=JobStatusEnum.DONE.value)

                # 5. metadata JSON
                meta_path = get_metadata_path(job_id)
                meta_data = {
                    "job_id": job_id,
                    "device_id": job_data["device_id"],
                    "transcript": job_data["transcript"],
                    "style": job_data["style"],
                    "lyrics": lyrics,
                    "duration_seconds": duration_seconds,
                    "created_at": job_data["created_at"],
                }
                meta_path.parent.mkdir(parents=True, exist_ok=True)
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)

                logger.info("job_id=%s done", job_id)
            except Exception as e:
                logger.exception("job_id=%s error: %s", job_id, e)
                update_job(
                    job_id,
                    status=JobStatusEnum.ERROR.value,
                    error=str(e),
                )
            finally:
                _queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("worker error: %s", e)


def start_worker() -> None:
    """Start background worker task."""
    global _queue, _worker_task
    _ensure_dirs()
    _queue = asyncio.Queue()
    _worker_task = asyncio.create_task(_worker())
    logger.info("worker started")


async def stop_worker() -> None:
    """Cancel worker and drain queue."""
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    logger.info("worker stopped")
