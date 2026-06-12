#!/bin/zsh
# Voice Clone Studio — one-click installer for Apple Silicon Macs.
# Double-click this file in Finder. It installs the tooling, downloads the
# app + voice engines (~6GB), and puts a launcher on your Desktop.
set -e

REPO="https://github.com/scottboyd83-dev/voice-clone-studio.git"
DEST="$HOME/voice-clone-studio"

banner() { echo; echo "━━━ $1"; echo; }

banner "Voice Clone Studio installer"

# ---- Apple Silicon only ----
if [ "$(uname -m)" != "arm64" ]; then
  echo "Sorry — this app needs an Apple Silicon Mac (M1 or later)."
  echo "This machine reports: $(uname -m)"
  exit 1
fi

# ---- Xcode Command Line Tools (provides git) ----
if ! xcode-select -p >/dev/null 2>&1; then
  banner "Installing Apple's command-line tools (a dialog will pop up)"
  xcode-select --install || true
  echo "Finish the dialog that appeared, then double-click this installer again."
  exit 0
fi

# ---- Homebrew ----
if ! command -v brew >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/brew ]; then
  banner "Installing Homebrew (you'll be asked for your Mac password)"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$(/opt/homebrew/bin/brew shellenv)"

banner "Installing ffmpeg, cmake, node and uv"
brew install ffmpeg cmake node uv

# ---- Get the code ----
if [ -d "$DEST/.git" ]; then
  banner "Updating existing copy in $DEST"
  git -C "$DEST" pull --ff-only
else
  banner "Downloading Voice Clone Studio to $DEST"
  git clone "$REPO" "$DEST"
fi
cd "$DEST"

# ---- Engines (the long part: ~6GB of model downloads) ----
banner "Setting up the fine-tuning engine (GPT-SoVITS, ~3GB) — grab a coffee"
./scripts/setup_gptsovits.sh

banner "Setting up the voice changer (Seed-VC, ~3GB)"
./scripts/setup_seedvc.sh

banner "Installing the interface"
(cd frontend && npm install)

# ---- App in /Applications ----
banner "Creating Voice Clone Studio in your Applications folder"
./scripts/make_app.sh

banner "Done!"
echo "Open 'Voice Clone Studio' from Applications, Launchpad or Spotlight."
echo "First speech generation downloads one more model (~1.4GB), one time only."
echo
echo "Everything you record stays on this Mac. Clone your own voice — or only"
echo "voices whose owners have said yes."
