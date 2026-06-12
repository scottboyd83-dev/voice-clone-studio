"""Seed-VC conversion worker. Runs inside third_party/seed-vc/.venv with
cwd=third_party/seed-vc; the backend (server/seedvc.py) talks to it over a
JSON-lines protocol: one request object per stdin line, one response per
stdout line. Models load once at startup and stay resident.
"""

import json
import os
import sys

# Keep every checkpoint under the seed-vc tree, and let MPS fall back to CPU
# for the few ops it lacks. Must be set before torch/transformers import.
os.environ.setdefault("HF_HUB_CACHE", os.path.join(os.getcwd(), "checkpoints", "hf_cache"))
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# Protocol replies go to the real stdout; library chatter (model loading,
# tqdm, etc.) is shunted to stderr so it can't corrupt the JSON stream.
protocol_out = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)

# Script lives in scripts/, so cwd (the seed-vc repo) isn't on sys.path.
sys.path.insert(0, os.getcwd())

import soundfile as sf  # noqa: E402
from seed_vc_wrapper import SeedVCWrapper  # noqa: E402


def reply(obj: dict) -> None:
    protocol_out.write(json.dumps(obj) + "\n")
    protocol_out.flush()


def main() -> None:
    wrapper = SeedVCWrapper()
    reply({"event": "ready"})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        try:
            f0 = bool(req.get("f0_condition", False))
            gen = wrapper.convert_voice(
                source=req["source"],
                target=req["target"],
                diffusion_steps=int(req.get("diffusion_steps", 25)),
                length_adjust=float(req.get("length_adjust", 1.0)),
                inference_cfg_rate=float(req.get("inference_cfg_rate", 0.7)),
                f0_condition=f0,
                auto_f0_adjust=bool(req.get("auto_f0_adjust", True)),
                pitch_shift=int(req.get("pitch_shift", 0)),
                stream_output=False,
            )
            # convert_voice contains yields, so even with stream_output=False it
            # is a generator; the audio comes back as the StopIteration value.
            audio = None
            try:
                next(gen)
            except StopIteration as stop:
                audio = stop.value
            if audio is None:
                raise RuntimeError("conversion produced no audio")
            sr = 44100 if f0 else 22050
            sf.write(req["output"], audio, sr)
            reply({"event": "done", "id": req.get("id"), "sr": sr})
        except Exception as e:  # report and keep serving
            reply({"event": "error", "id": req.get("id"), "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
