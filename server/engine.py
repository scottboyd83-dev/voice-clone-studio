"""Lazy-loaded F5-TTS engine. One model instance, inference serialized by a lock
(MPS doesn't benefit from concurrent inference and 24GB favours one resident model)."""

import threading
from dataclasses import dataclass
from pathlib import Path

_lock = threading.Lock()
_model = None


@dataclass
class GenSettings:
    speed: float = 1.0          # 0.5–2.0
    nfe_step: int = 32          # quality vs speed: 16 fast, 32 default, 64 best
    cfg_strength: float = 2.0   # adherence to reference voice: 1.0–4.0
    seed: int | None = None     # None = random; actual seed returned for reproducibility
    remove_silence: bool = False


def _get_model():
    global _model
    if _model is None:
        from f5_tts.api import F5TTS  # deferred: heavy import + checkpoint download
        _model = F5TTS()  # auto-selects MPS on Apple Silicon
    return _model


def warmup() -> None:
    """Load the model ahead of the first request."""
    with _lock:
        _get_model()


def is_loaded() -> bool:
    return _model is not None


def transcribe(ref_wav: Path) -> str:
    with _lock:
        return _get_model().transcribe(str(ref_wav), language="en").strip()


def generate(ref_wav: Path, ref_text: str, text: str, settings: GenSettings, out_wav: Path) -> int:
    """Synthesize `text` in the cloned voice. Returns the seed actually used."""
    with _lock:
        model = _get_model()
        model.infer(
            ref_file=str(ref_wav),
            ref_text=ref_text,
            gen_text=text,
            speed=settings.speed,
            nfe_step=settings.nfe_step,
            cfg_strength=settings.cfg_strength,
            seed=settings.seed,
            remove_silence=settings.remove_silence,
            file_wave=str(out_wav),
        )
        return model.seed
