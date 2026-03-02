#!/bin/bash
# Full test workflow - run from music-agent/ with .env in project root
# No jq required - uses Python for JSON parsing

set -e
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

BEARER=${BEARER_TOKEN:?BEARER_TOKEN required in .env}
BASE=${BASE_URL:-http://localhost:8000}
BASE=${BASE%/}

echo "1. Health check..."
curl -s "$BASE/health"

echo -e "\n\n2. Submit job..."
RESP=$(curl -s -X POST "$BASE/v1/song" \
  -H "Authorization: Bearer $BEARER" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test","transcript":"A witch flying away","style":"K-indie, hopeful"}')
JOB_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])" <<< "$RESP")
echo "Job ID: $JOB_ID"

echo -e "\n3. Long poll until done..."
while true; do
  RESULT=$(curl -s -H "Authorization: Bearer $BEARER" \
    "$BASE/v1/song/$JOB_ID?wait=60")
  STATUS=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" <<< "$RESULT")
  echo "  Status: $STATUS"
  [ "$STATUS" = "done" ] && break
  if [ "$STATUS" = "error" ]; then
    python3 -c "import json,sys; d=json.load(sys.stdin); print('Error:', d.get('error','unknown'))" <<< "$RESULT"
    exit 1
  fi
done

echo -e "\n4. Download audio..."
AUDIO_URL=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('audio_url',''))" <<< "$RESULT")
OUTFILE="test_${JOB_ID:0:8}.mp3"
curl -s -H "Authorization: Bearer $BEARER" -o "$OUTFILE" "$AUDIO_URL"
echo "Saved: $OUTFILE"
ls -la "$OUTFILE"
