#!/bin/sh
# Start backend + frontend; Ctrl-C stops both.
cd "$(dirname "$0")"
uv run uvicorn server.app:app --port 8000 &
BACK=$!
trap 'kill $BACK' EXIT INT TERM
cd frontend && npm run dev
