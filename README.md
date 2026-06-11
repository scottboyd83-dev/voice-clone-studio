# Voice Clone Studio

Local, private voice cloning — ElevenLabs-style features, everything on-device.
Built around **F5-TTS** (instant cloning) running on Apple Silicon (MPS).

## Run

```sh
./run.sh
```

Then open http://localhost:5173. Or run the pieces manually:

```sh
uv run uvicorn server.app:app --port 8000   # backend
cd frontend && npm run dev                   # frontend
```

## Use

1. **Voices** tab → *New Voice* → read the on-screen script (~10s) or upload a clean clip.
2. **Generate** tab → type text, tune sliders (speed / quality / voice adherence), hit Generate.
3. **History** tab → every take with its exact settings; lock a seed to reproduce one.

Notes:
- First generation after startup loads the model (~30s; first ever run downloads ~1.4GB).
- Reference clips are trimmed to 12s — F5-TTS works best with short, clean references.
- Uploads without a transcript are auto-transcribed (first time downloads Whisper).

## Layout

- `server/` — FastAPI backend: `engine.py` (lazy F5-TTS), `app.py` (routes), `db.py` (SQLite)
- `frontend/` — React + Vite studio UI
- `data/` — voices, generations, and the SQLite DB (gitignored, local-only)

## Roadmap

- **Phase 2** — recording studio: guided scripts, quality checks (SNR/clipping), dataset pipeline (mlx-whisper transcription, VAD segmentation)
- **Phase 3** — fine-tuning with GPT-SoVITS for professional-grade similarity
- **Phase 4** — speech-to-speech voice changer (Seed-VC), polish
