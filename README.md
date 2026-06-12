# Voice Clone Studio

Local, private voice cloning — ElevenLabs-style features, everything on-device.
**F5-TTS** for instant cloning (MPS), **GPT-SoVITS v2** for fine-tuned
professional-grade clones, and **Seed-VC** for speech-to-speech voice changing,
all on Apple Silicon.

## Run

```sh
./run.sh
```

One-time setups for the optional engines:

```sh
./scripts/setup_gptsovits.sh   # fine-tuning: clones GPT-SoVITS, isolated venv, ~3GB models (needs brew install cmake)
./scripts/setup_seedvc.sh      # voice changer: clones Seed-VC, isolated venv, ~3GB checkpoints
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
4. **Generate** tab → type text, tune sliders (speed / quality / voice adherence —
   or top-k / top-p / temperature for fine-tuned voices), hit Generate.
5. **Convert** tab → record or upload any speech and re-render it in a library voice.
   No transcript needed; pacing and emotion carry through. Singing mode for vocals.
6. **History** tab → every take with its exact settings; lock a seed to reproduce one.

Notes:
- First generation after startup loads the model (~30s; first ever run downloads ~1.4GB).
- First conversion loads the Seed-VC worker (~1 min); later ones run in seconds.
- Reference clips are trimmed to 12s — F5-TTS works best with short, clean references.
- Uploads without a transcript are auto-transcribed (first time downloads Whisper).

## Layout

- `server/` — FastAPI backend: `engine.py` (F5-TTS), `finetune.py` + `gsv.py`
  (GPT-SoVITS training/inference), `seedvc.py` (voice conversion), `dataset.py`,
  `quality.py`, `app.py` (routes)
- `frontend/` — React + Vite studio UI
- `data/` — voices, generations, takes, datasets, conversions, trained models (gitignored)
- `third_party/GPT-SoVITS/`, `third_party/seed-vc/` — isolated engine checkouts
  (gitignored; reproduced by the setup scripts)

## Roadmap

- Checkpoint comparison (A/B intermediate training epochs), long-text progress
  feedback, persistent train-job state, idle engine shutdown
