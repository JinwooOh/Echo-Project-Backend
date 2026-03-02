# Full Test Workflow

End-to-end testing for the Music Agent backend.

---

## Prerequisites

1. **Environment**
   ```bash
   cd music-agent
   source .venv/bin/activate
   ```

2. **`.env` configured**
   - `BEARER_TOKEN` – for API auth
   - `MINIMAX_API_KEY` – for lyrics + music generation
   - `BASE_URL` – e.g. `http://localhost:8000` (used in `audio_url`)

3. **Server running**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

---

## Step 1: Health Check

```bash
curl http://localhost:8000/health
```

**Expected:** `{"ok":true}`

---

## Step 2: Verify MiniMax API Key (Optional)

Uses minimal MiniMax credits to check auth and balance.

```bash
python test_api_key.py
```

**Expected:**
- ✔ Key valid, lyrics OK
- ✔ Key valid, music OK

If you see `1008 insufficient balance`, add credits at [MiniMax Audio Subscription](https://platform.minimax.io/subscribe/audio-subscription).

---

## Step 3: Submit a Song Job

```bash
curl -X POST http://localhost:8000/v1/song \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test-device",
    "transcript": "A witch flying away into the night sky",
    "style": "K-indie, hopeful, spring, gentle guitar"
  }'
```

**Expected:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_url": "/v1/song/550e8400-e29b-41d4-a716-446655440000"
}
```

Save `job_id` for the next steps.

---

## Step 4: Check Status (Immediate)

```bash
JOB_ID="<paste-job-id-here>"

curl -H "Authorization: Bearer $BEARER_TOKEN" \
  "http://localhost:8000/v1/song/$JOB_ID"
```

**Expected (in progress):**
```json
{
  "job_id": "...",
  "status": "writing_lyrics",
  "lyrics": null,
  "audio_url": null,
  "duration_seconds": null,
  "error": null
}
```

Status values: `writing_lyrics` → `generating_music` → `downloading` → `archiving` → `done`

---

## Step 5: Long Poll Until Done

Hold the request for up to 60 seconds; returns as soon as the job finishes.

```bash
RESULT=$(curl -s -H "Authorization: Bearer $BEARER_TOKEN" \
  "http://localhost:8000/v1/song/$JOB_ID?wait=60")

echo $RESULT | jq .
STATUS=$(echo $RESULT | jq -r '.status')
echo "Status: $STATUS"
```

If `status` is not `done` or `error`, call again (job may still be running).

---

## Step 6: Download Audio (When Done)

```bash
AUDIO_URL=$(echo $RESULT | jq -r '.audio_url')
curl -H "Authorization: Bearer $BEARER_TOKEN" \
  -o song.mp3 "$AUDIO_URL"

# Verify
file song.mp3
# song.mp3: Audio file with ID3 version 2.4.0
```

---

## Full Bash Script (Copy-Paste)

```bash
#!/bin/bash
# Full test workflow - run from music-agent/ with .env loaded

set -e
source .env 2>/dev/null || true

BEARER=${BEARER_TOKEN:?BEARER_TOKEN required}
BASE=${BASE_URL:-http://localhost:8000}
BASE=${BASE%/}

echo "1. Health check..."
curl -s "$BASE/health" | jq .

echo -e "\n2. Submit job..."
RESP=$(curl -s -X POST "$BASE/v1/song" \
  -H "Authorization: Bearer $BEARER" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test","transcript":"A witch flying away","style":"K-indie, hopeful"}')
JOB_ID=$(echo $RESP | jq -r '.job_id')
echo "Job ID: $JOB_ID"

echo -e "\n3. Long poll until done..."
while true; do
  RESULT=$(curl -s -H "Authorization: Bearer $BEARER" \
    "$BASE/v1/song/$JOB_ID?wait=60")
  STATUS=$(echo $RESULT | jq -r '.status')
  echo "  Status: $STATUS"
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "error" ] && echo $RESULT | jq '.error' && exit 1
done

echo -e "\n4. Download audio..."
AUDIO_URL=$(echo $RESULT | jq -r '.audio_url')
curl -s -H "Authorization: Bearer $BEARER" -o "test_${JOB_ID:0:8}.mp3" "$AUDIO_URL"
echo "Saved: test_${JOB_ID:0:8}.mp3"
ls -la "test_${JOB_ID:0:8}.mp3"
```

---

## Python Smoke Test

```bash
python scripts/smoke_test.py
```

Submits a job, long polls until done, downloads audio.

## Bash Full Test

```bash
./scripts/full_test.sh
```

Runs the full workflow (health → submit → long poll → download). Requires `.env` with `BEARER_TOKEN`. No `jq` needed.

---

## Error Cases

| Scenario | Response |
|----------|----------|
| Missing auth | `401` |
| Invalid job_id | `404` `{"error":"Job not found","code":"not_found"}` |
| Job failed | `status: "error"`, `error: "<message>"` |
| Invalid filename on /out/ | `400` |

---

## Typical Timing

- Lyrics generation: ~30–60 seconds
- Music generation: ~60–120 seconds
- Download: ~5–10 seconds  
- **Total:** ~2–4 minutes per song
