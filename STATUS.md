# Voice Clone Studio — Project Status

> Handoff doc for resuming the build. Last updated: 2026-06-12 (end of Phase 3).
> Owner: Scott. Goal: local, private, ElevenLabs-class voice cloning of Scott's own
> voice on an M4 Pro 24GB Mac. English only. 100% on-device.

## How to run

```sh
./run.sh                        # backend :8000 (FastAPI/uv) + frontend :5173 (Vite)
./scripts/setup_gptsovits.sh    # one-time Phase 3 setup — ALREADY DONE on this machine
```

## Completed work

| Phase | Status | Commit |
|---|---|---|
| 1 — Instant cloning (F5-TTS) + generation UI | ✅ done, verified | `b6ee3f0` |
| Fix: rushed-speech bug (transcript/audio mismatch) | ✅ | `5e6a3ab` |
| 2 — Recording studio + dataset pipeline | ✅ done, verified | `9cc744a` |
| 3 — GPT-SoVITS fine-tuning + inference | ✅ done, verified end-to-end | `7fe947e` |
| 4 — Speech-to-speech (Seed-VC) + polish | ⬜ not started | — |

All verification was end-to-end through the real API (synthetic test data, cleaned up
afterwards). Current voice library: "Scott" (instant), "Test Voice" (F5 sample clip).

## Architecture

```
server/  (FastAPI, managed by uv, Python 3.11)
  app.py      all routes: voices, generate, history, studio takes, dataset, train
  engine.py   F5-TTS instant cloning — lazy singleton, MPS, serialized by lock
  gsv.py      GPT-SoVITS integration: paths + api_v2 inference server on :9880 (MPS)
  finetune.py training orchestration: preprocess (text/SSL/semantic) → s2_train →
              s1_train → register voice; subprocesses into the isolated gsv venv
  dataset.py  kept takes → loudnorm 32kHz mono → Whisper-verify (exclude <0.6,
              flag <0.85) → GPT-SoVITS filelist.list (path|scott|EN|text) + manifest
  quality.py  per-take gating: clipping %, SNR estimate, level → pass/warn/fail
  scripts_corpus.py  90 prompts (50 Harvard + questions/expressive/numbers/passages)
  db.py       SQLite (data/studio.db): voices (engine='f5'|'gptsovits', model JSON),
              generations, takes
frontend/  (React + Vite, dark studio aesthetic, no router — tab state in App.jsx)
  Voices · Studio · Train · Generate · History
data/      (gitignored) voices/, takes/, datasets/, finetune/, models/, generations/
third_party/GPT-SoVITS/  (gitignored; reproduced by scripts/setup_gptsovits.sh)
  .venv = isolated py3.10 + torch 2.10; v2 pretrained models downloaded (~3GB)
```

Key flows:
- **Instant voice**: 8-12s reference + matching transcript → F5-TTS zero-shot.
  CRITICAL INVARIANT: ref transcript must exactly match ref audio (F5-TTS paces
  output by reference chars-per-second). Clips >12s are trimmed + re-transcribed.
- **Fine-tuned voice**: Studio takes → dataset build → Train tab → ~3-5h CPU train
  (8 SoVITS + 15 GPT epochs for ~10min data) → voice registered with engine
  'gptsovits', weights under data/models/<job>/, generation proxied to api_v2.

## macOS gotchas (hard-won; all baked into scripts/setup_gptsovits.sh)

1. GPT-SoVITS prepare/train scripts need `PYTHONPATH=<repo>:<repo>/GPT_SoVITS` (finetune.py sets it)
2. Forked DataLoader workers deadlock on macOS → patched num_workers=0,
   prefetch_factor=None, persistent_workers=False in s2_train.py + AR/data/data_module.py
3. English G2P needs NLTK data (downloaded into the gsv venv)
4. torchaudio 2.11 decodes via torchcodec — must be **0.10** to pair with torch 2.10,
   and api_v2 needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (gsv.py sets it)

## Outstanding tasks

**Scott (human, blocking the first real fine-tune):**
- [ ] Record dataset in Studio tab (~10-15 min of kept takes; 90 prompts ≈ most of it)
- [ ] Build dataset, then start fine-tune from Train tab (overnight)
- [ ] A/B fine-tuned vs instant voice in Generate

**Phase 4 (next build phase):**
- [ ] Speech-to-speech voice changer via Seed-VC (zero-shot VC, no training):
      record/upload any speech → convert to a library voice. New tab or Generate mode.
- [ ] Polish: GPT-SoVITS settings exposure (top_k/top_p/temperature sliders for
      fine-tuned voices), checkpoint comparison (train saves intermediate epochs —
      let user A/B them), better long-text progress feedback during generation.

**Known rough edges (non-blocking):**
- Training/dataset job state is in-memory — a backend restart mid-train loses status
  tracking (the subprocess dies with it). Fine for overnight runs; could persist jobs.
- GPT-SoVITS api_v2 stays resident (~2GB RAM) after first fine-tuned generation;
  no idle shutdown yet.
- `nfe_step`/`cfg_strength` sliders are hidden for fine-tuned voices but speed/seed
  work; GPT-SoVITS-native sampling knobs not yet exposed.
- F5-TTS auto-transcribe path (uploads without transcript) downloads Whisper
  (~1.6GB, transformers) on first use — already cached on this machine.

## Recommended next steps (in order)

1. Scott records his dataset + runs the first real overnight fine-tune (no code needed)
2. Evaluate the result; if quality disappoints, first levers: more/cleaner data,
   then epoch tuning (SoVITS 8→12, GPT 15→20)
3. Build Phase 4 (Seed-VC speech-to-speech) — same pattern as GPT-SoVITS:
   isolated venv under third_party/, setup script, server module, tab
4. Polish list above

## Verification habits used so far (keep doing this)

Synthesize test audio with the F5 engine itself for pipeline tests (e.g. generate a
script prompt's text, upload as a take) — and always delete synthetic
voices/takes/datasets afterwards so Scott's real data stays clean.
