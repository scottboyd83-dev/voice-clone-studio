"""Ingest uploaded audio files into training takes.

Unlike Studio recordings, an uploaded clip has no known transcript and may be
long. Each file is therefore converted to a clean 32kHz mono working copy,
silence-split into utterance-sized segments, Whisper-transcribed to recover the
text, quality-checked, and stored as takes (script_id = UPLOAD_SCRIPT_ID).

From there the normal "Build dataset" -> "Fine-tune" flow applies unchanged: the
dataset builder re-normalizes and re-transcribes each take, and for uploads that
comparison acts as a self-consistency filter (garbled/unstable segments fall
below the 0.6 threshold and are dropped).
"""

import json
import re
import subprocess
import threading
import time
from pathlib import Path

from . import audio, db, engine, quality
from .paths import TAKES_DIR

UPLOAD_SCRIPT_ID = -1   # sentinel: this take came from an upload, not a script prompt
MIN_SEG = 2.0           # drop segments shorter than this — too little to train on
MAX_SEG = 14.0          # hard cap; GPT-SoVITS trains on short utterances
TARGET_SEG = 9.0        # accumulate speech up to ~this length before cutting
SILENCE_DB = -30        # silencedetect noise floor
SILENCE_MIN = 0.35      # min silence duration (s) to count as a boundary
BRIDGE_GAP = 0.8        # merge speech spans separated by a gap shorter than this
PAD = 0.1               # padding added to each side of a cut to avoid clipping words

_status = {"state": "idle", "progress": 0.0, "message": "", "added": 0, "files": []}
_lock = threading.Lock()


def status() -> dict:
    return dict(_status)


def start_ingest(files: list[tuple[Path, str]]) -> None:
    """Begin processing already-saved temp files [(path, original_name), ...]."""
    with _lock:
        if _status["state"] == "running":
            raise RuntimeError("An upload is already being processed")
        _status.update(state="running", progress=0.0, message="Starting…",
                       added=0, files=[name for _, name in files])
    threading.Thread(target=_run, args=(files,), daemon=True).start()


def _run(files: list[tuple[Path, str]]) -> None:
    total = 0
    try:
        for i, (path, name) in enumerate(files):
            _status.update(progress=i / len(files), message=f"Processing {name}…")
            try:
                total += _process_file(path, name)
            finally:
                path.unlink(missing_ok=True)
            _status.update(added=total)
        if total == 0:
            raise RuntimeError("No usable speech segments found — check the audio isn't silent or too noisy")
        _status.update(state="done", progress=1.0, added=total,
                       message=f"Added {total} segment(s) to your takes")
    except Exception as e:
        # Drop any temp files we never reached.
        for path, _ in files:
            path.unlink(missing_ok=True)
        _status.update(state="error", message=str(e))


def _process_file(src: Path, name: str) -> int:
    work = src.with_name(src.stem + ".work.wav")
    audio.to_wav(src, work, sample_rate=32000)  # mono 32k — accurate seeking + matches training input
    try:
        segments = _detect_speech_segments(work)
        added = 0
        for j, (start, end) in enumerate(segments):
            _status.update(message=f"{name}: segment {j + 1}/{len(segments)} (transcribe)")
            if _ingest_segment(work, start, end):
                added += 1
                _status.update(added=_status["added"] + 1)
        return added
    finally:
        work.unlink(missing_ok=True)


def _ingest_segment(work: Path, start: float, end: float) -> bool:
    take_id = db.new_id()
    wav = TAKES_DIR / f"{take_id}.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(work),
             "-ss", f"{max(0.0, start - PAD):.3f}", "-to", f"{end + PAD:.3f}",
             "-ac", "1", "-ar", "32000", "-c:a", "pcm_s16le", str(wav)],
            check=True, capture_output=True,
        )
        text = engine.transcribe(wav).strip()
        if not text:  # unintelligible segment — skip
            wav.unlink(missing_ok=True)
            return False
        metrics = quality.analyze(wav)
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO takes (id, script_id, text, duration_secs, metrics, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (take_id, UPLOAD_SCRIPT_ID, text, metrics["duration_secs"],
                 json.dumps(metrics), db.now()),
            )
        return True
    except Exception:
        wav.unlink(missing_ok=True)
        return False  # one bad segment shouldn't abort the whole file


def _detect_speech_segments(wav: Path) -> list[tuple[float, float]]:
    """Silence-split into [start, end] speech spans, each ~MIN_SEG..MAX_SEG seconds."""
    dur = audio.duration_secs(wav)
    proc = subprocess.run(
        ["ffmpeg", "-i", str(wav),
         "-af", f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]

    # Pair silences (a trailing silence_start with no end runs to EOF).
    silences = sorted((s, ends[i] if i < len(ends) else dur) for i, s in enumerate(starts))

    # Speech spans = the gaps between silences across [0, dur].
    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in silences:
        if s > cursor:
            speech.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < dur:
        speech.append((cursor, dur))
    if not speech:  # no silence detected → treat the whole file as one span
        speech = [(0.0, dur)]

    # Greedily merge consecutive spans up to TARGET, flushing as we go.
    merged: list[tuple[float, float]] = []
    seg_start = seg_end = None
    for s, e in speech:
        if seg_start is None:
            seg_start, seg_end = s, e
        elif (e - seg_start) <= MAX_SEG and (s - seg_end) <= BRIDGE_GAP:
            seg_end = e
        else:
            merged.append((seg_start, seg_end))
            seg_start, seg_end = s, e
        if (seg_end - seg_start) >= TARGET_SEG:
            merged.append((seg_start, seg_end))
            seg_start = seg_end = None
    if seg_start is not None:
        merged.append((seg_start, seg_end))

    # Hard-split any over-long span into even chunks; drop anything too short.
    out: list[tuple[float, float]] = []
    for s, e in merged:
        length = e - s
        if length <= MAX_SEG:
            if length >= MIN_SEG:
                out.append((s, e))
            continue
        n = int(length // MAX_SEG) + 1
        step = length / n
        for k in range(n):
            out.append((s + k * step, s + (k + 1) * step))
    return out
