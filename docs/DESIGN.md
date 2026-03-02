# Music Agent Design Notes

## Data Workflow

```
Raspberry Pi (device)
  1. Captures audio
  2. STT (on-device API) → transcript
  3. Sends transcript + genre → backend

Backend (this VM)
  4. Receives transcript + genre
  5. Generate lyrics (MiniMax)
  6. Generate music (MiniMax, genre → style_prompt)
  7. Store audio, expose HTTP URL
  8. Pi waits via long polling

Raspberry Pi
  9. Receives response when job done (long poll returns)
  10. Fetches audio via HTTP URL
  11. Plays audio
```

---

## Long Polling

Instead of short polling every 5–10 seconds, the Pi uses **long polling** to reduce round-trips and get notified as soon as the job completes.

### How it works

1. Pi sends `GET /v1/song/{job_id}?wait=60` after submitting the job.
2. Backend holds the request open and checks job status every 1–2 seconds.
3. If the job finishes → respond immediately with full status (including `audio_url`).
4. If `wait` seconds elapse without completion → respond with current status.
5. Pi checks the response: if `status` is `done` or `error`, stop; otherwise call the same endpoint again.

### Endpoint

```
GET /v1/song/{job_id}?wait=60
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `wait` | int | 0 | Max seconds to hold the request. `0` = return immediately (backward compatible). |

### Pi flow

```
POST /v1/song  →  job_id
loop:
  GET /v1/song/{job_id}?wait=60
  if status in (done, error): break
  # else: still processing, loop again
fetch audio_url and play
```

### Implementation

- If `wait=0` or omitted: same as today (immediate response).
- If `wait>0`: poll job status every 1–2 seconds until done or timeout, then respond.
