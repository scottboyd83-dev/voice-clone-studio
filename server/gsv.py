"""GPT-SoVITS integration: paths, the api_v2 inference server (managed as a
subprocess on :9880), and generation for fine-tuned voices."""

import json
import os
import random
import socket
import subprocess
import threading
import time
from pathlib import Path

import requests

from .paths import DATA, ROOT

GSV_ROOT = ROOT / "third_party" / "GPT-SoVITS"
GSV_PY = GSV_ROOT / ".venv" / "bin" / "python"
PRETRAINED = GSV_ROOT / "GPT_SoVITS" / "pretrained_models"
BERT_DIR = PRETRAINED / "chinese-roberta-wwm-ext-large"
HUBERT_DIR = PRETRAINED / "chinese-hubert-base"
PRETRAIN_S2G = PRETRAINED / "gsv-v2final-pretrained" / "s2G2333k.pth"
PRETRAIN_S2D = PRETRAINED / "gsv-v2final-pretrained" / "s2D2333k.pth"
PRETRAIN_S1 = PRETRAINED / "gsv-v2final-pretrained" / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"

PORT = 9880
BASE = f"http://127.0.0.1:{PORT}"
INFER_LOG = DATA / "gsv_api.log"

_proc: subprocess.Popen | None = None
_loaded = {"gpt": None, "sovits": None}
_lock = threading.Lock()


def is_installed() -> bool:
    return GSV_PY.exists() and PRETRAIN_S2G.exists()


def _infer_yaml() -> Path:
    """Inference config: v2 weights, MPS (fp32) on Apple Silicon."""
    path = DATA / "gsv_infer.yaml"
    path.write_text(
        "custom:\n"
        f"  bert_base_path: {BERT_DIR}\n"
        f"  cnhuhbert_base_path: {HUBERT_DIR}\n"
        "  device: mps\n"
        "  is_half: false\n"
        f"  t2s_weights_path: {PRETRAIN_S1}\n"
        "  version: v2\n"
        f"  vits_weights_path: {PRETRAIN_S2G}\n"
    )
    return path


def _port_open() -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def ensure_running(timeout: float = 180) -> None:
    """Start api_v2 if it isn't up; first start loads models (~30-60s)."""
    global _proc
    with _lock:
        if _port_open():
            return
        log = open(INFER_LOG, "a")
        env = os.environ.copy()
        # torchcodec dlopens ffmpeg dylibs; point it at the homebrew install
        env["DYLD_FALLBACK_LIBRARY_PATH"] = "/opt/homebrew/lib"
        _proc = subprocess.Popen(
            [str(GSV_PY), "-s", "api_v2.py", "-a", "127.0.0.1", "-p", str(PORT),
             "-c", str(_infer_yaml())],
            cwd=GSV_ROOT, stdout=log, stderr=subprocess.STDOUT, env=env,
        )
        _loaded["gpt"] = _loaded["sovits"] = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _port_open():
                return
            if _proc.poll() is not None:
                raise RuntimeError(f"GPT-SoVITS server exited — see {INFER_LOG}")
            time.sleep(1)
        raise RuntimeError("GPT-SoVITS server did not come up in time")


def _set_weights(gpt_path: str, sovits_path: str) -> None:
    if _loaded["gpt"] != gpt_path:
        r = requests.get(f"{BASE}/set_gpt_weights", params={"weights_path": gpt_path}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"set_gpt_weights failed: {r.text}")
        _loaded["gpt"] = gpt_path
    if _loaded["sovits"] != sovits_path:
        r = requests.get(f"{BASE}/set_sovits_weights", params={"weights_path": sovits_path}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"set_sovits_weights failed: {r.text}")
        _loaded["sovits"] = sovits_path


def generate(voice: dict, text: str, speed: float, seed: int | None, out_wav: Path) -> int:
    """Synthesize with a fine-tuned voice. Returns the seed used."""
    model = json.loads(voice["model"])
    ensure_running()
    with _lock:
        _set_weights(model["gpt_path"], model["sovits_path"])
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    r = requests.post(f"{BASE}/tts", json={
        "text": text,
        "text_lang": "en",
        "ref_audio_path": model["prompt_wav"],
        "prompt_text": model["prompt_text"],
        "prompt_lang": "en",
        "speed_factor": speed,
        "seed": seed,
        "media_type": "wav",
        "text_split_method": "cut5",
        "batch_size": 1,
    }, timeout=600)
    if r.status_code != 200:
        raise RuntimeError(f"GPT-SoVITS tts failed: {r.text[:300]}")
    out_wav.write_bytes(r.content)
    return seed
