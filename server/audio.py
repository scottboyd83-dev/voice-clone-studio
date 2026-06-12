"""Audio helpers: format conversion and reference-clip preparation via ffmpeg."""

import subprocess
from pathlib import Path

# F5-TTS works best with reference clips under ~12s, mono.
MAX_REF_SECONDS = 12


def to_wav(src: Path, dst: Path, *, mono: bool = True, max_seconds: float | None = None,
           sample_rate: int = 24000) -> None:
    """Convert any audio file (webm/m4a/mp3/...) to PCM wav (24kHz default)."""
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sample_rate), "-c:a", "pcm_s16le", str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)


def duration_secs(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def wav_to_mp3(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-b:a", "192k", str(dst)],
        check=True, capture_output=True,
    )
