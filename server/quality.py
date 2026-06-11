"""Per-take audio quality analysis: clipping, level, and an SNR estimate.

SNR is estimated frame-wise: the quietest frames approximate the noise floor,
the loudest approximate speech. Crude but reliable for pass/warn/fail gating.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

FRAME_SECS = 0.03


def analyze(path: Path) -> dict:
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    duration = len(data) / sr

    peak = float(np.abs(data).max()) if len(data) else 0.0
    clip_pct = float((np.abs(data) > 0.985).mean() * 100)

    n = int(sr * FRAME_SECS)
    nframes = max(1, len(data) // n)
    rms = np.sqrt((data[: nframes * n].reshape(nframes, n) ** 2).mean(axis=1)) + 1e-9
    noise_rms = float(np.percentile(rms, 10))
    speech_rms = float(np.percentile(rms, 90))
    snr_db = float(20 * np.log10(speech_rms / noise_rms))
    speech_db = float(20 * np.log10(speech_rms))

    issues: list[str] = []
    level = "pass"

    def flag(severity: str, msg: str):
        nonlocal level
        issues.append(msg)
        order = {"pass": 0, "warn": 1, "fail": 2}
        if order[severity] > order[level]:
            level = severity

    if duration < 1.5:
        flag("fail", "Too short — speak the full prompt.")
    if peak < 0.02:
        flag("fail", "Almost silent — check the microphone input.")
    if clip_pct > 1.0:
        flag("fail", f"Clipping on {clip_pct:.1f}% of samples — lower input gain or back off the mic.")
    elif clip_pct > 0.1:
        flag("warn", "Slight clipping detected — consider lowering input gain.")
    if snr_db < 14:
        flag("fail", f"Very noisy ({snr_db:.0f} dB SNR) — find a quieter spot.")
    elif snr_db < 25:
        flag("warn", f"Background noise audible ({snr_db:.0f} dB SNR).")
    if speech_db < -30 and peak >= 0.02:
        flag("warn", "Quiet recording — move closer to the mic or raise gain.")

    return {
        "duration_secs": round(duration, 2),
        "peak": round(peak, 3),
        "clip_pct": round(clip_pct, 3),
        "snr_db": round(snr_db, 1),
        "speech_db": round(speech_db, 1),
        "level": level,
        "issues": issues,
    }
