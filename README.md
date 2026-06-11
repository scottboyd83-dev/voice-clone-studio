# Voice Clone Studio

Local, private voice cloning — ElevenLabs-style features, everything on-device.
**F5-TTS** for instant cloning (MPS) and **GPT-SoVITS v2** for fine-tuned
professional-grade clones, both on Apple Silicon.

## Run

```sh
./run.sh
```

For fine-tuning (Phase 3), one-time setup first (needs `brew install cmake`):

```sh
./scripts/setup_gptsovits.sh   # clones GPT-SoVITS, isolated venv, ~3GB pretrained models
```

Then open http://localhost:5173. Or run the pieces manually:

```sh
uv run uvicorn server.app:app --port 8000   # backend
cd frontend && npm run dev                   # frontend
```

## Use

1. **Voices** tab → *New Voice* → read the on-screen script (~10s) or upload a clean clip.
2. **Studio** tab → read prompts past the quality gate, then *Build dataset* (aim 10-15 min).
3. **Train** tab → pick the dataset, start a fine-tune (CPU, plan for overnight). A
   ★ fine-tuned voice appears in the library when done.
4. **Generate** tab → type text, tune sliders (speed / quality / voice adherence), hit Generate.
5. **History** tab → every take with its exact settings; lock a seed to reproduce one.

Notes:
- First generation after startup loads the model (~30s; first ever run downloads ~1.4GB).
- Reference clips are trimmed to 12s — F5-TTS works best with short, clean references.
- Uploads without a transcript are auto-transcribed (first time downloads Whisper).

## Layout

- `server/` — FastAPI backend: `engine.py` (F5-TTS), `finetune.py` + `gsv.py`
  (GPT-SoVITS training/inference), `dataset.py`, `quality.py`, `app.py` (routes)
- `frontend/` — React + Vite studio UI
- `data/` — voices, generations, takes, datasets, trained models (gitignored)
- `third_party/GPT-SoVITS/` — isolated training framework (gitignored; see setup script)

## Roadmap

- **Phase 4** — speech-to-speech voice changer (Seed-VC), polish
