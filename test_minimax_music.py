import os
import json
import time
import binascii
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MINIMAX_API_KEY")
if not API_KEY:
    raise SystemExit("Missing MINIMAX_API_KEY in environment/.env")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

LYRICS_URL = "https://api.minimax.io/v1/lyrics_generation"
MUSIC_URL  = "https://api.minimax.io/v1/music_generation"


def generate_lyrics(prompt: str) -> str:
    payload = {"mode": "write_full_song", "prompt": prompt}
    r = requests.post(LYRICS_URL, json=payload, headers=HEADERS, timeout=120)
    r.raise_for_status()
    data = r.json()

    # The guide shows printing response.text; response schema may evolve.
    # Try common fields first, otherwise dump for inspection.
    for path in [("data", "lyrics"), ("lyrics",), ("data", "text")]:
        cur = data
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, str) and cur.strip():
            return cur

    raise RuntimeError(f"Could not find lyrics field. Response:\n{json.dumps(data, indent=2)}")


def generate_music(lyrics: str, prompt: str, output_format: str = "url") -> dict:
    payload = {
        "model": "music-2.5",
        "prompt": prompt,
        "lyrics": lyrics,
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "mp3",
        },
        "output_format": output_format,  # "url" or "hex"
    }
    r = requests.post(MUSIC_URL, json=payload, headers=HEADERS, timeout=600)
    r.raise_for_status()
    return r.json()


def download_file(url: str, out_path: str):
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def main():
    os.makedirs("outputs", exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    theme = "A hopeful indie song about winter melting into spring"
    style = "Indie, hopeful, springtime, gentle drums, warm guitar, uplifting vocals"

    # Step 1 (optional): generate lyrics
    print("Generating lyrics...")
    lyrics = generate_lyrics(theme)
    lyrics_path = f"outputs/{ts}_lyrics.txt"
    with open(lyrics_path, "w", encoding="utf-8") as f:
        f.write(lyrics)
    print(f"Saved lyrics: {lyrics_path}")

    # Step 2: generate music (url output is easiest to handle)
    print("Generating music...")
    result = generate_music(lyrics=lyrics, prompt=style, output_format="url")

    meta_path = f"outputs/{ts}_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Saved meta: {meta_path}")

    audio = result.get("data", {}).get("audio")
    if not audio:
        raise RuntimeError(f"No data.audio found. Response:\n{json.dumps(result, indent=2)}")

    out_mp3 = f"outputs/{ts}.mp3"

    # If output_format=url, `audio` should be a URL (expires ~24h per docs)
    # If output_format=hex, `audio` is hex-encoded bytes.
    if audio.startswith("http://") or audio.startswith("https://"):
        print("Downloading audio from URL...")
        download_file(audio, out_mp3)
        print(f"Saved audio: {out_mp3}")
    else:
        print("Decoding hex audio...")
        audio_bytes = binascii.unhexlify(audio)
        with open(out_mp3, "wb") as f:
            f.write(audio_bytes)
        print(f"Saved audio: {out_mp3}")

    print("Done.")


if __name__ == "__main__":
    main()