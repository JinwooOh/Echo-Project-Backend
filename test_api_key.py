#!/usr/bin/env python3
"""Quick test of MiniMax API key - verifies auth and reports per-service status."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MINIMAX_API_KEY")
if not API_KEY:
    print("❌ MINIMAX_API_KEY not found in .env")
    exit(1)

# Mask key for display
masked = API_KEY[:8] + "..." + API_KEY[-4:] if len(API_KEY) > 12 else "***"
print(f"Testing key: {masked}\n")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

# Status code meanings
CODES = {
    0: "success",
    1002: "rate limit",
    1004: "auth failed",
    1008: "insufficient balance",
    1026: "invalid params",
    2049: "invalid API key",
}


def test_endpoint(name: str, url: str, payload: dict) -> dict | None:
    """Make request, return parsed JSON or None on HTTP error."""
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=60)
        data = r.json() if r.content else {}
        base = data.get("base_resp", {})
        code = base.get("status_code", -1)
        msg = base.get("status_msg", "")
        return {"code": code, "msg": msg, "data": data, "http": r.status_code}
    except requests.exceptions.RequestException as e:
        return {"code": -1, "msg": str(e), "data": None, "http": getattr(e.response, "status_code", None)}


def main():
    # 1. Lyrics (text credits) - minimal request
    print("1. Lyrics API (text credits)...")
    res = test_endpoint(
        "lyrics",
        "https://api.minimax.io/v1/lyrics_generation",
        {"mode": "write_full_song", "prompt": "test"},
    )
    code = res["code"]
    if code == 0:
        print("   ✔ Key valid, lyrics OK (text credits available)")
    elif code in (1004, 2049):
        print("   ✗ Auth failed - check API key")
        exit(1)
    elif code == 1008:
        print("   ⚠ Key valid, but insufficient text credits")
    else:
        print(f"   ? {CODES.get(code, code)}: {res['msg']}")

    # 2. Music (audio credits) - minimal request
    print("\n2. Music API (audio credits)...")
    res = test_endpoint(
        "music",
        "https://api.minimax.io/v1/music_generation",
        {
            "model": "music-2.5",
            "prompt": "test",
            "lyrics": "[Verse]\ntest line",
            "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
            "output_format": "url",
        },
    )
    code = res["code"]
    if code == 0:
        print("   ✔ Key valid, music OK (audio credits available)")
    elif code in (1004, 2049):
        print("   ✗ Auth failed - check API key")
    elif code == 1008:
        print("   ⚠ Key valid, but insufficient audio credits")
        print("   → Subscribe at: https://platform.minimax.io/subscribe/audio-subscription")
    else:
        print(f"   ? {CODES.get(code, code)}: {res['msg']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
