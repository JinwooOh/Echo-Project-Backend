#!/usr/bin/env python3
"""Smoke test: submit a job, poll until done, download audio."""
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

BEARER_TOKEN = os.getenv("BEARER_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

if not BEARER_TOKEN:
    print("BEARER_TOKEN not set in .env")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}", "Content-Type": "application/json"}


def main() -> int:
    # 1. Submit job
    print("Submitting job...")
    r = httpx.post(
        f"{BASE_URL}/v1/song",
        json={
            "device_id": "smoke-test",
            "transcript": "A witch flying away into the night sky, saying goodbye to the forest",
            "style": "K-indie, hopeful, spring, gentle guitar",
        },
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    job_id = data["job_id"]
    print(f"Job created: {job_id}")

    # 2. Long poll until done or error (wait=60 holds up to 60s per request)
    print("Long polling for completion...")
    while True:
        r = httpx.get(
            f"{BASE_URL}/v1/song/{job_id}",
            params={"wait": 60},
            headers=HEADERS,
            timeout=70,
        )
        r.raise_for_status()
        status_data = r.json()
        status = status_data["status"]
        print(f"  Status: {status}")
        if status == "done":
            break
        if status == "error":
            print(f"  Error: {status_data.get('error', 'unknown')}")
            return 1

    # 3. Download audio
    audio_url = status_data.get("audio_url")
    if not audio_url:
        print("No audio_url in response")
        return 1
    print(f"Downloading from {audio_url}...")
    r = httpx.get(audio_url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    out_path = f"smoke_test_{job_id[:8]}.mp3"
    with open(out_path, "wb") as f:
        f.write(r.content)
    print(f"Saved to {out_path} ({len(r.content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
