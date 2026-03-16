"""MiniMax Lyrics and Music Generation API client."""
import json
import logging
import asyncio
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

LYRICS_URL = "https://api.minimax.io/v1/lyrics_generation"
MUSIC_URL = "https://api.minimax.io/v1/music_generation"
LYRICS_TIMEOUT = 300.0  # MiniMax lyrics can be slow; 120s was too short
TIMEOUT = 600.0
MAX_RETRIES = 2
RETRY_DELAY = 5.0


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_settings().MINIMAX_API_KEY}",
    }


async def generate_lyrics(prompt: str) -> str:
    """
    Generate full song lyrics from transcript/prompt.
    Returns lyrics string with structure tags.
    """
    payload = {"mode": "write_full_song", "prompt": prompt}
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=LYRICS_TIMEOUT) as client:
                r = await client.post(LYRICS_URL, json=payload, headers=_headers())
                r.raise_for_status()
                data = r.json()
                break
        except httpx.ReadTimeout as e:
            last_err = e
            if attempt < MAX_RETRIES:
                logger.warning("MiniMax lyrics timeout (attempt %d/%d), retrying in %.0fs", attempt + 1, MAX_RETRIES + 1, RETRY_DELAY)
                await asyncio.sleep(RETRY_DELAY)
            else:
                raise
        except Exception:
            raise
    else:
        if last_err:
            raise last_err

    for path in [("data", "lyrics"), ("lyrics",), ("data", "text")]:
        cur: Any = data
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, str) and cur.strip():
            return cur

    raise RuntimeError(
        "Could not extract lyrics from response: "
        + json.dumps(data, indent=2, ensure_ascii=False)
    )


async def generate_music(lyrics: str, style_prompt: str) -> dict[str, Any]:
    """
    Generate music from lyrics and style.
    Returns dict with audio_url (str) and duration_ms (int, optional).
    """
    payload = {
        "model": "music-2.5",
        "prompt": style_prompt,
        "lyrics": lyrics,
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 128000,
            "format": "mp3",
        },
        "output_format": "url",
    }
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(MUSIC_URL, json=payload, headers=_headers())
                r.raise_for_status()
                result = r.json()
                break
        except httpx.ReadTimeout as e:
            last_err = e
            if attempt < MAX_RETRIES:
                logger.warning("MiniMax music timeout (attempt %d/%d), retrying in %.0fs", attempt + 1, MAX_RETRIES + 1, RETRY_DELAY)
                await asyncio.sleep(RETRY_DELAY)
            else:
                raise
        except Exception:
            raise
    else:
        if last_err:
            raise last_err

    data = (result or {}).get("data")
    if data is None:
        data = {}
    audio = data.get("audio")

    if not audio:
        base_resp = (result or {}).get("base_resp", {})
        err_msg = base_resp.get("status_msg") or "No audio returned"
        raise RuntimeError(
            f"{err_msg}: " + json.dumps(result, indent=2, ensure_ascii=False)
        )

    extra = (result or {}).get("extra_info") or {}
    duration_ms = extra.get("music_duration")

    return {
        "audio_url": audio if isinstance(audio, str) and audio.startswith("http") else "",
        "duration_ms": duration_ms,
    }
