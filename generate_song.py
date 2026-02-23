import os
import json
import time
import binascii
import argparse
import requests
from dotenv import load_dotenv

# -------------------------
# Setup
# -------------------------
load_dotenv()

API_KEY = os.getenv("MINIMAX_API_KEY")
if not API_KEY:
    raise SystemExit("❌ Missing MINIMAX_API_KEY in .env")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

LYRICS_URL = "https://api.minimax.io/v1/lyrics_generation"
MUSIC_URL  = "https://api.minimax.io/v1/music_generation"


# -------------------------
# MiniMax helpers
# -------------------------
def generate_lyrics(prompt: str) -> str:
    payload = {
        "mode": "write_full_song",
        "prompt": prompt,
    }

    r = requests.post(LYRICS_URL, json=payload, headers=HEADERS, timeout=120)
    r.raise_for_status()
    data = r.json()

    # Try common response paths
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

    raise RuntimeError(
        "❌ Could not extract lyrics from response:\n"
        + json.dumps(data, indent=2, ensure_ascii=False)
    )


def generate_music(
    lyrics: str,
    style_prompt: str,
    output_format: str = "url",
) -> dict:
    payload = {
        "model": "music-2.5",
        "prompt": style_prompt,
        "lyrics": lyrics,
        "audio_setting": {
            "sample_rate": 44100,
            # "bitrate": 256000,
            "bitrate": 128000,
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


def load_lyrics_from_file(path: str) -> str:
    """Load lyrics string from an output file (e.g. outputs/20260223_043458_lyrics.txt)."""
    with open(path, encoding="utf-8") as f:
        return f.read()


# -------------------------
# Input handling
# -------------------------
def get_input_interactive():
    print("\n🎵 MiniMax Music Generator (Interactive Mode)")
    print("-------------------------------------------")
    prompt = input("✏️  Enter a lyric idea / theme:\n> ").strip()

    style = input(
        "\n🎼 Enter style / vibe "
        "(e.g. 'K-indie, hopeful, spring, gentle guitar'):\n> "
    ).strip()

    return prompt, style


def parse_args():
    parser = argparse.ArgumentParser(description="Generate music via MiniMax")
    parser.add_argument("--prompt", help="Lyric idea / theme")
    parser.add_argument("--style", help="Music style / vibe")
    parser.add_argument(
        "--lyrics-file",
        help="Path to existing lyrics file (e.g. outputs/20260223_043458_lyrics.txt). Skips lyrics generation.",
    )
    return parser.parse_args()


# -------------------------
# Main
# -------------------------
def main():
    args = parse_args()

    os.makedirs("outputs", exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    if args.lyrics_file:
        print(f"▶ Loading lyrics from: {args.lyrics_file}")
        lyrics = load_lyrics_from_file(args.lyrics_file)
        lyrics_path = args.lyrics_file
        if args.style:
            style = args.style
        else:
            style = input("\n🎼 Enter style / vibe (e.g. 'K-indie, hopeful, spring'):\n> ").strip()
    else:
        if args.prompt and args.style:
            prompt = args.prompt
            style = args.style
            print("▶ Using CLI input")
        else:
            prompt, style = get_input_interactive()

        print("\n📝 Generating lyrics...")
        lyrics = generate_lyrics(prompt)

        lyrics_path = f"outputs/{ts}_lyrics.txt"
        with open(lyrics_path, "w", encoding="utf-8") as f:
            f.write(lyrics)

        print(f"✔ Lyrics saved: {lyrics_path}")

    print("\n🎶 Generating music...")
    result = generate_music(
        lyrics=lyrics,
        style_prompt=style,
        output_format="url",
    )

    meta_path = f"outputs/{ts}_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Handle null/None result or data (e.g. API errors like "insufficient balance")
    data = (result or {}).get("data")
    if data is None:
        data = {}
    audio = data.get("audio")

    if not audio:
        base_resp = (result or {}).get("base_resp", {})
        err_msg = base_resp.get("status_msg") or "No audio returned"
        raise RuntimeError(
            f"❌ {err_msg}\n"
            + json.dumps(result, indent=2, ensure_ascii=False)
        )

    out_mp3 = f"outputs/{ts}.mp3"

    if audio.startswith("http"):
        download_file(audio, out_mp3)
    else:
        audio_bytes = binascii.unhexlify(audio)
        with open(out_mp3, "wb") as f:
            f.write(audio_bytes)

    print(f"🎧 Audio saved: {out_mp3}")
    print("\n✅ Done!")


if __name__ == "__main__":
    main()



