"""Seed-VC integration: speech-to-speech voice conversion via a persistent
worker subprocess (scripts/seedvc_worker.py) in the isolated seed-vc venv.
Models load once on first use (~1 min) and stay resident."""

import json
import subprocess
import threading
from pathlib import Path

from .paths import DATA, ROOT

SVC_ROOT = ROOT / "third_party" / "seed-vc"
SVC_PY = SVC_ROOT / ".venv" / "bin" / "python"
WORKER = ROOT / "scripts" / "seedvc_worker.py"
WORKER_LOG = DATA / "seedvc_worker.log"

_proc: subprocess.Popen | None = None
_lock = threading.Lock()
_state = "idle"  # idle | loading | ready


def is_installed() -> bool:
    return SVC_PY.exists()


def state() -> str:
    if _proc is not None and _proc.poll() is not None:
        return "idle"  # worker died
    return _state


def _start_worker() -> None:
    """Spawn the worker and block until its models are loaded."""
    global _proc, _state
    if not is_installed():
        raise RuntimeError("Seed-VC is not installed — run scripts/setup_seedvc.sh")
    _state = "loading"
    log = open(WORKER_LOG, "a")
    _proc = subprocess.Popen(
        [str(SVC_PY), str(WORKER)],
        cwd=SVC_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=log, text=True, bufsize=1,
    )
    line = _proc.stdout.readline()  # blocks through model load
    if not line or json.loads(line).get("event") != "ready":
        _state = "idle"
        _proc.kill()
        _proc = None
        raise RuntimeError(f"Seed-VC worker failed to start — see {WORKER_LOG}")
    _state = "ready"


def ensure_running() -> None:
    with _lock:
        if _proc is None or _proc.poll() is not None:
            _start_worker()


def convert(source: Path, target: Path, out_wav: Path, *, diffusion_steps: int = 25,
            length_adjust: float = 1.0, inference_cfg_rate: float = 0.7,
            f0_condition: bool = False, auto_f0_adjust: bool = True,
            pitch_shift: int = 0) -> None:
    """Convert the speech in `source` to the voice of `target`."""
    ensure_running()
    req = {
        "source": str(source), "target": str(target), "output": str(out_wav),
        "diffusion_steps": diffusion_steps, "length_adjust": length_adjust,
        "inference_cfg_rate": inference_cfg_rate, "f0_condition": f0_condition,
        "auto_f0_adjust": auto_f0_adjust, "pitch_shift": pitch_shift,
    }
    with _lock:
        _proc.stdin.write(json.dumps(req) + "\n")
        _proc.stdin.flush()
        line = _proc.stdout.readline()
    if not line:
        raise RuntimeError(f"Seed-VC worker died mid-conversion — see {WORKER_LOG}")
    resp = json.loads(line)
    if resp.get("event") != "done":
        raise RuntimeError(resp.get("error", "unknown Seed-VC error"))
