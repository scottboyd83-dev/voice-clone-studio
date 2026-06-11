#!/bin/sh
# One-time setup for Phase 3 fine-tuning: GPT-SoVITS in an isolated venv.
# Requires: git, uv, cmake (brew install cmake).
set -e
cd "$(dirname "$0")/.."

[ -d third_party/GPT-SoVITS ] || git clone --depth 1 https://github.com/RVC-Boss/GPT-SoVITS third_party/GPT-SoVITS

cd third_party/GPT-SoVITS
[ -d .venv ] || uv venv --python 3.10 .venv
uv pip install -p .venv/bin/python -r requirements.txt
uv pip install -p .venv/bin/python "torchcodec==0.10"  # audio decoding; 0.10 pairs with torch 2.10

# macOS: forked DataLoader workers deadlock — force single-process loading
# (num_workers=0 also requires prefetch_factor=None and persistent_workers=False)
sed -i '' 's/        num_workers=5,/        num_workers=0,/; s/        persistent_workers=True,/        persistent_workers=False,/; s/        prefetch_factor=3,/        prefetch_factor=None,/' GPT_SoVITS/s2_train.py
sed -i '' 's/num_workers=max(self.num_workers, 12),/num_workers=self.num_workers,/; s/prefetch_factor=16,/prefetch_factor=None,/; s/            persistent_workers=True,/            persistent_workers=False,/' GPT_SoVITS/AR/data/data_module.py

# NLTK data for English G2P
.venv/bin/python -c "
import nltk
for r in ['averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng', 'cmudict', 'punkt']:
    nltk.download(r, download_dir='.venv/nltk_data')
"

# v2 pretrained base models (~3GB) from HF
cd ../..
uv run python - <<'EOF'
from huggingface_hub import snapshot_download
snapshot_download(
    "lj1995/GPT-SoVITS",
    local_dir="third_party/GPT-SoVITS/GPT_SoVITS/pretrained_models",
    allow_patterns=["gsv-v2final-pretrained/*", "chinese-hubert-base/*", "chinese-roberta-wwm-ext-large/*"],
)
print("GPT-SoVITS setup complete")
EOF
