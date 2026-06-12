# Voice Clone Studio — Project Status

> Handoff doc for resuming the build. Last updated: 2026-06-12 (end of Phase 4).
> Owner: Scott. Goal: local, private, ElevenLabs-class voice cloning of Scott's own
> voice on an M4 Pro 24GB Mac. English only. 100% on-device.

## How to run

```sh
./run.sh                        # backend :8000 (FastAPI/uv) + frontend :5173 (Vite)
./scripts/setup_gptsovits.sh    # one-time Phase 3 setup — ALREADY DONE on this machine
./scripts/setup_seedvc.sh       # one-time Phase 4 setup — ALREADY DONE on this machine
```

## Completed work

| Phase | Status | Commit |
|---|---|---|
| 1 — Instant cloning (F5-TTS) + generation UI | ✅ done, verified | `b6ee3f0` |
| Fix: rushed-speech bug (transcript/audio mismatch) | ✅ | `5e6a3ab` |
| 2 — Recording studio + dataset pipeline | ✅ done, verified | `9cc744a` |
| 3 — GPT-SoVITS fine-tuning + inference | ✅ done, verified end-to-end | `7fe947e` |
| 4 — Speech-to-speech (Seed-VC) + sampling-knob polish | ✅ done, verified end-to-end | — |

All verification was end-to-end through the real API (synthetic test data, cleaned up
afterwards). Current voice library: "Scott" (instant), "Test Voice" (F5 sample clip).

Phase 4 verification notes: speech conversion (22.05kHz) and singing/f0 conversion
(44.1kHz) both verified via `/api/convert` against the example clips in the seed-vc
repo; cold first conversion ~60s (worker model load), warm conversions ~10s for a
10s clip. F5 generation re-verified unaffected by the new sampling fields.

## Architecture

```
server/  (FastAPI, managed by uv, Python 3.11)
  app.py      all routes: voices, generate, convert, history, studio takes, dataset, train
  engine.py   F5-TTS instant cloning — lazy singleton, MPS, serialized by lock
  gsv.py      GPT-SoVITS integration: paths + api_v2 inference server on :9880 (MPS);
              generate() takes top_k/top_p/temperature
  seedvc.py   Seed-VC speech-to-speech: persistent JSON-lines worker subprocess
              (scripts/seedvc_worker.py in the seed-vc venv); models load on first
              conversion and stay resident; idle | loading | ready state
  finetune.py training orchestration: preprocess (text/SSL/semantic) → s2_train →
              s1_train → register voice; subprocesses into the isolated gsv venv
  dataset.py  kept takes → loudnorm 32kHz mono → Whisper-verify (exclude <0.6,
              flag <0.85) → GPT-SoVITS filelist.list (path|scott|EN|text) + manifest
  quality.py  per-take gating: clipping %, SNR estimate, level → pass/warn/fail
  scripts_corpus.py  90 prompts (50 Harvard + questions/expressive/numbers/passages)
  db.py       SQLite (data/studio.db): voices (engine='f5'|'gptsovits', model JSON),
              generations, takes, conversions
frontend/  (React + Vite, dark studio aesthetic, no router — tab state in App.jsx)
  Voices · Studio · Train · Generate · Convert · History
data/      (gitignored) voices/, takes/, datasets/, finetune/, models/, generations/,
           conversions/ (<id>.wav output + <id>_source.wav input)
third_party/GPT-SoVITS/  (gitignored; reproduced by scripts/setup_gptsovits.sh)
  .venv = isolated py3.10 + torch 2.10; v2 pretrained models downloaded (~3GB)
third_party/seed-vc/     (gitignored; reproduced by scripts/setup_seedvc.sh)
  .venv = isolated py3.10 + stable torch 2.10 (upstream pins nightly; not needed);
  ~3GB checkpoints under checkpoints/ (DiT base + f0, whisper-small, 2× BigVGAN,
  campplus, RMVPE). Upstream repo is archived (Nov 2025) — pinned, fine.
```

Key flows:
- **Instant voice**: 8-12s reference + matching transcript → F5-TTS zero-shot.
  CRITICAL INVARIANT: ref transcript must exactly match ref audio (F5-TTS paces
  output by reference chars-per-second). Clips >12s are trimmed + re-transcribed.
- **Fine-tuned voice**: Studio takes → dataset build → Train tab → ~3-5h CPU train
  (8 SoVITS + 15 GPT epochs for ~10min data) → voice registered with engine
  'gptsovits', weights under data/models/<job>/, generation proxied to api_v2.
- **Voice changer**: any speech (record/upload, ≤5 min) + target voice's
  reference.wav → Seed-VC zero-shot conversion. Works for both instant and
  fine-tuned voices (every voice dir has reference.wav). Source stored at 44.1kHz
  so singing mode keeps full bandwidth. SeedVCWrapper.convert_voice is a generator
  even with stream_output=False — audio comes back as StopIteration.value
  (handled in scripts/seedvc_worker.py).

## macOS gotchas (hard-won; all baked into the setup scripts)

1. GPT-SoVITS prepare/train scripts need `PYTHONPATH=<repo>:<repo>/GPT_SoVITS` (finetune.py sets it)
2. Forked DataLoader workers deadlock on macOS → patched num_workers=0,
   prefetch_factor=None, persistent_workers=False in s2_train.py + AR/data/data_module.py
3. English G2P needs NLTK data (downloaded into the gsv venv)
4. torchaudio 2.11 decodes via torchcodec — must be **0.10** to pair with torch 2.10,
   and api_v2 needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (gsv.py sets it)
5. Seed-VC: `seed_vc_wrapper.py` compares `self.device == "mps"` (torch.device vs
   str → always False), so the float64→float32 F0 cast is skipped and singing mode
   crashes on MPS. Patched to `self.device.type == "mps"` by setup_seedvc.sh.
   Worker also sets `PYTORCH_ENABLE_MPS_FALLBACK=1` and pins HF_HUB_CACHE into the
   seed-vc tree.

## Outstanding tasks

**Scott (human, blocking the first real fine-tune):**
- [ ] Record dataset in Studio tab (~10-15 min of kept takes; 90 prompts ≈ most of it)
- [ ] Build dataset, then start fine-tune from Train tab (overnight)
- [ ] A/B fine-tuned vs instant voice in Generate

**Remaining polish (no phase assigned):**
- [ ] Checkpoint comparison — train saves intermediate epochs; let user A/B them
- [ ] Better long-text progress feedback during generation
- [ ] Persist training/dataset job state (in-memory now — backend restart mid-train
      loses status tracking; the subprocess dies with it. Fine for overnight runs.)
- [ ] Idle shutdown for resident engines (api_v2 ~2GB and the Seed-VC worker ~3-4GB
      stay loaded after first use)

**Known rough edges (non-blocking):**
- F5 auto-transcribe path (uploads without transcript) downloads Whisper
  (~1.6GB, transformers) on first use — already cached on this machine.
- Conversion is a synchronous request (~1s of processing per second of audio);
  a 5-min clip holds the HTTP request for a few minutes. Acceptable locally.

## Recommended next steps (in order)

1. Scott records his dataset + runs the first real overnight fine-tune (no code needed)
2. Evaluate the result; if quality disappoints, first levers: more/cleaner data,
   then epoch tuning (SoVITS 8→12, GPT 15→20)
3. Try the Convert tab on real speech (e.g. a voice memo → "Scott")
4. Polish list above

## Verification habits used so far (keep doing this)

Synthesize test audio with the F5 engine itself for pipeline tests (e.g. generate a
script prompt's text, upload as a take) — and always delete synthetic
voices/takes/datasets/conversions afterwards so Scott's real data stays clean.
