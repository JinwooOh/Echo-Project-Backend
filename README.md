# Music Agent Backend Service

Production-grade FastAPI backend that accepts transcript text from a Raspberry Pi, generates lyrics and music via MiniMax APIs, stores/serves audio, optionally archives to NAS, and exposes a simple HTTP API with bearer-token auth.

**API Reference:** [docs/API.md](docs/API.md) · **Design notes:** [docs/DESIGN.md](docs/DESIGN.md) · **Test workflow:** [docs/TEST_WORKFLOW.md](docs/TEST_WORKFLOW.md)

## Requirements

- Python 3.11+
- MiniMax API key (Audio Subscription for music generation)

## Setup

1. Clone or copy the project to your Ubuntu VM.

2. Create virtual environment and install dependencies:

```bash
cd music-agent
python3 -m venv .venv
source .venv/bin/activate  # or .venv/bin/activate on Linux
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
# Edit .env: BEARER_TOKEN, MINIMAX_API_KEY, BASE_URL (for Pi to reach VM)
```

4. Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Tailscale Binding

To bind only to the Tailscale interface (e.g. `100.x.x.x`):

```bash
# Find your Tailscale IP
ip addr show tailscale0

# Run with that host
uvicorn app.main:app --host 100.x.x.x --port 8000
```

Or use Tailscale as the default route so the service listens on all interfaces.

## Run 24/7 (survives SSH disconnect)

Install as a systemd service on your Proxmox VM (or any Linux host):

```bash
cd /path/to/Echo-Project-Backend   # or music-agent
sudo ./install-service.sh
# Or: sudo ./install-service.sh echo /home/echo/music-agent

sudo systemctl start music-agent
sudo systemctl status music-agent
```

The backend will:
- Start automatically on VM boot
- Restart on crash (RestartSec=5)
- Keep running when you close your Mac SSH session

## API Endpoints

### GET /health

No auth. Returns `{"ok": true}`.

```bash
curl http://localhost:8000/health
```

### POST /v1/song

Submit a song job. Auth: `Authorization: Bearer <TOKEN>`.

```bash
curl -X POST http://localhost:8000/v1/song \
  -H "Authorization: Bearer your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"pi-zero-1","transcript":"A witch flying away into the night sky","style":"K-indie, hopeful, spring, gentle guitar"}'
```

Response:

```json
{"job_id":"uuid-here","status_url":"/v1/song/uuid-here"}
```

### GET /v1/song/{job_id}

Poll job status. Auth required.

```bash
curl -H "Authorization: Bearer your-secret-token" \
  http://localhost:8000/v1/song/<job_id>
```

Response (running):

```json
{"job_id":"...","status":"writing_lyrics","lyrics":null,"audio_url":null,"duration_seconds":null,"error":null}
```

Response (done):

```json
{"job_id":"...","status":"done","lyrics":"[Verse]\n...","audio_url":"http://.../out/<job_id>.mp3","duration_seconds":113.2,"error":null}
```

### GET /out/{job_id}.mp3

Download generated audio. Auth required.

```bash
curl -H "Authorization: Bearer your-secret-token" \
  -o song.mp3 \
  http://localhost:8000/out/<job_id>.mp3
```

## Smoke Test

```bash
# Set BEARER_TOKEN and BASE_URL in .env
python scripts/smoke_test.py
```
