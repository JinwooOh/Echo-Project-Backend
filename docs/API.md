# Music Agent API Reference

REST API for generating music from transcript text. The service accepts transcript and style from clients (e.g. Raspberry Pi), generates lyrics and music via MiniMax, and serves the resulting audio.

**Base URL:** `http://<host>:8000` (default port 8000)

---

## Authentication

All endpoints except `GET /health` require a Bearer token:

```
Authorization: Bearer <BEARER_TOKEN>
```

Set `BEARER_TOKEN` in `.env` on the server. Clients must use the same token.

---

## Endpoints

### GET /health

Health check. No authentication required.

**Request:**
```http
GET /health HTTP/1.1
Host: localhost:8000
```

**Response:** `200 OK`
```json
{
  "ok": true
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

### POST /v1/song

Submit a new song generation job. The job is queued and processed asynchronously.

**Request:**
```http
POST /v1/song HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
Content-Type: application/json

{
  "device_id": "pi-zero-1",
  "transcript": "A witch flying away into the night sky",
  "style": "K-indie, hopeful, spring, gentle guitar"
}
```

**Request body:**

| Field       | Type   | Required | Description                                      |
|-------------|--------|----------|--------------------------------------------------|
| device_id   | string | Yes      | Device identifier (e.g. pi-zero-1)              |
| transcript  | string | Yes      | Text from speech-to-text (theme/idea for lyrics) |
| style       | string | Yes      | Music style and vibe (e.g. genre, mood, instruments) |

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_url": "/v1/song/550e8400-e29b-41d4-a716-446655440000"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/v1/song \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pi-zero-1",
    "transcript": "A witch flying away into the night sky",
    "style": "K-indie, hopeful, spring, gentle guitar"
  }'
```

---

### GET /v1/song/{job_id}

Get the status of a song generation job. Poll this endpoint until `status` is `done` or `error`.

**Request:**
```http
GET /v1/song/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "generating_music",
  "lyrics": null,
  "audio_url": null,
  "duration_seconds": null,
  "error": null
}
```

**Response fields:**

| Field            | Type    | Description                                              |
|------------------|---------|----------------------------------------------------------|
| job_id           | string  | Job UUID                                                 |
| status           | string  | Current pipeline stage (see below)                      |
| lyrics           | string? | Generated lyrics (available when done or partial)        |
| audio_url        | string? | Absolute URL to download audio (only when status=done)   |
| duration_seconds| float?  | Audio duration in seconds (when available)               |
| error            | string? | Error message (only when status=error)                   |

**Status values:**

| Status           | Description                          |
|------------------|--------------------------------------|
| writing_lyrics   | Generating lyrics from transcript    |
| generating_music | Creating music from lyrics           |
| downloading     | Downloading audio from MiniMax       |
| archiving       | Copying to NAS (if enabled)          |
| done            | Job completed successfully          |
| error            | Job failed (see `error` field)        |

**Response (done):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "lyrics": "[Verse]\n달빛 아래 낡은 빗자루가...",
  "audio_url": "http://localhost:8000/out/550e8400-e29b-41d4-a716-446655440000.mp3",
  "duration_seconds": 113.2,
  "error": null
}
```

**Response (error):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "lyrics": null,
  "audio_url": null,
  "duration_seconds": null,
  "error": "insufficient balance"
}
```

**Error response:** `404 Not Found` when job does not exist
```json
{
  "error": "Job not found",
  "code": "not_found"
}
```

**Example:**
```bash
curl -H "Authorization: Bearer your-secret-token" \
  http://localhost:8000/v1/song/550e8400-e29b-41d4-a716-446655440000
```

---

### GET /out/{filename}

Download the generated audio file. Filename must be `{job_id}.mp3` or `{job_id}.wav`.

**Request:**
```http
GET /out/550e8400-e29b-41d4-a716-446655440000.mp3 HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:** `200 OK`
- **Content-Type:** `audio/mpeg` (mp3) or `audio/wav` (wav)
- **Body:** Binary audio data

**Error responses:**
- `400 Bad Request` – Invalid filename
- `404 Not Found` – File does not exist (job not done or failed)

**Example:**
```bash
curl -H "Authorization: Bearer your-secret-token" \
  -o song.mp3 \
  http://localhost:8000/out/550e8400-e29b-41d4-a716-446655440000.mp3
```

---

## Typical Client Flow

1. **Submit job:** `POST /v1/song` with `device_id`, `transcript`, `style`
2. **Poll status:** `GET /v1/song/{job_id}` every 5–10 seconds
3. **Download audio:** When `status` is `done`, fetch from `audio_url` or `GET /out/{job_id}.mp3`

**Example (bash):**
```bash
# 1. Submit
RESP=$(curl -s -X POST http://localhost:8000/v1/song \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"pi","transcript":"A witch flying away","style":"K-indie, hopeful"}')
JOB_ID=$(echo $RESP | jq -r '.job_id')

# 2. Poll until done
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $BEARER_TOKEN" \
    "http://localhost:8000/v1/song/$JOB_ID" | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "error" ] && exit 1
  sleep 5
done

# 3. Download
curl -H "Authorization: Bearer $BEARER_TOKEN" \
  -o song.mp3 "http://localhost:8000/out/$JOB_ID.mp3"
```

---

## Error Codes

| Code         | HTTP | Description                    |
|--------------|------|--------------------------------|
| auth_missing | 401  | Missing Authorization header   |
| auth_invalid | 401  | Invalid Bearer token          |
| not_found    | 404  | Job or file not found         |
| invalid_filename | 400 | Invalid filename for /out/    |

---

## Request ID

Responses include `X-Request-ID` for tracing. Clients may send `X-Request-ID` in requests; otherwise one is generated.
