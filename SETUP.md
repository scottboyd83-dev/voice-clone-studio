# Setting up Voice Clone Studio on a new Mac

The easy way: download `install/Install Voice Clone Studio.command` from this
repo, double-click it in Finder, and follow the prompts. It does everything
below for you and puts a "Voice Clone Studio" launcher on your Desktop.

> First time opening it, macOS may warn about an unidentified developer —
> right-click the file → Open → Open.

## What you need

- A Mac with **Apple Silicon** (M1 or later) — the engines run on the GPU via MPS
- **16GB+ RAM** recommended (24GB to fine-tune comfortably)
- **~20GB free disk** (the voice engines download ~6GB of models)
- A microphone (built-in is fine; a headset is better)

## Manual setup (what the installer automates)

```sh
# 1. Tooling (skip anything you already have)
xcode-select --install                # git + compilers (GUI prompt)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg cmake node uv

# 2. Get the code
git clone https://github.com/scottboyd83-dev/voice-clone-studio.git
cd voice-clone-studio

# 3. One-time engine setup (downloads ~6GB of models; takes a while)
./scripts/setup_gptsovits.sh          # fine-tuning engine
./scripts/setup_seedvc.sh             # voice-changer engine

# 4. Frontend deps
cd frontend && npm install && cd ..

# 5. Run it
./run.sh                              # then open http://localhost:5173
```

The first text-to-speech generation downloads the F5-TTS model (~1.4GB) and
the first upload-without-transcript downloads Whisper (~1.6GB) — both one-time.

## Where your data lives

Everything — recordings, voices, trained models, generated audio — stays in
the `data/` folder on your machine. Nothing is uploaded anywhere, ever.

## A note on ethics

This app is built for cloning **your own voice**, or the voice of someone who
has explicitly consented. Don't clone people without their permission.
