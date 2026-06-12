#!/bin/sh
# One-time setup for Phase 4 speech-to-speech: Seed-VC in an isolated venv.
# Requires: git, uv.
set -e
cd "$(dirname "$0")/.."

[ -d third_party/seed-vc ] || git clone --depth 1 https://github.com/Plachtaa/seed-vc third_party/seed-vc

cd third_party/seed-vc
[ -d .venv ] || uv venv --python 3.10 .venv

# Minimal deps for SeedVCWrapper (upstream requirements-mac.txt pins nightly
# torch and pulls GUI/eval extras we don't use). Stable torch supports MPS.
uv pip install -p .venv/bin/python \
  "torch==2.10.*" "torchaudio==2.10.*" \
  "transformers==4.46.3" "librosa==0.10.2" "numpy==1.26.4" "scipy==1.13.1" \
  "munch==4.0.0" "einops==0.8.0" "descript-audio-codec==1.0.0" "pydub==0.25.1" \
  "soundfile==0.12.1" "huggingface-hub>=0.28.1" pyyaml tqdm

# macOS: wrapper compares torch.device to the string "mps", so the float64->
# float32 F0 cast never runs and singing mode crashes (MPS has no float64)
sed -i '' 's/if self.device == "mps":/if self.device.type == "mps":/' seed_vc_wrapper.py

# Pre-download all checkpoints (~4GB) so the first conversion doesn't stall.
# load_custom_model_from_hf uses cache_dir=./checkpoints; whisper/bigvgan use
# the default HF cache, which the worker pins to ./checkpoints/hf_cache.
HF_HUB_CACHE=checkpoints/hf_cache .venv/bin/python - <<'EOF'
from huggingface_hub import hf_hub_download, snapshot_download

for f in ["DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth",
          "config_dit_mel_seed_uvit_whisper_small_wavenet.yml",
          "DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema.pth",
          "config_dit_mel_seed_uvit_whisper_base_f0_44k.yml"]:
    hf_hub_download("Plachta/Seed-VC", f, cache_dir="./checkpoints")
hf_hub_download("funasr/campplus", "campplus_cn_common.bin", cache_dir="./checkpoints")
hf_hub_download("lj1995/VoiceConversionWebUI", "rmvpe.pt", cache_dir="./checkpoints")

snapshot_download("openai/whisper-small",
                  allow_patterns=["config.json", "model.safetensors",
                                  "preprocessor_config.json", "tokenizer*", "*.txt"])
for repo in ["nvidia/bigvgan_v2_22khz_80band_256x", "nvidia/bigvgan_v2_44khz_128band_512x"]:
    snapshot_download(repo, allow_patterns=["config.json", "bigvgan_generator.pt"])
print("Seed-VC setup complete")
EOF
