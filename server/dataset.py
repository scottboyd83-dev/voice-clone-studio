"""Dataset builder: kept takes -> training-ready GPT-SoVITS dataset.

Per take: loudness-normalize to 32kHz mono, transcribe with Whisper, and verify
the transcript against the script the user read. Mismatches below 0.6 are
excluded (misread/garbled), 0.6-0.85 are flagged for review but included.
Output: data/datasets/<id>/wavs/*.wav + filelist.list (path|speaker|EN|text).
"""

import json
import subprocess
import threading
import time
from difflib import SequenceMatcher

from . import audio, db, engine
from .paths import DATASETS_DIR, TAKES_DIR

_status = {"state": "idle", "progress": 0.0, "message": "", "manifest": None}
_start_lock = threading.Lock()


def status() -> dict:
    return dict(_status)


def start_build(speaker: str = "scott") -> None:
    with _start_lock:
        if _status["state"] == "running":
            raise RuntimeError("A dataset build is already running")
        _status.update(state="running", progress=0.0, message="Starting…", manifest=None)
    threading.Thread(target=_build, args=(speaker,), daemon=True).start()


def _norm(text: str) -> str:
    return " ".join("".join(c.lower() if c.isalnum() or c.isspace() else " " for c in text).split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _build(speaker: str) -> None:
    try:
        with db.connect() as conn:
            takes = [dict(r) for r in conn.execute(
                "SELECT * FROM takes WHERE status='kept' ORDER BY created_at").fetchall()]
        if not takes:
            raise RuntimeError("No kept takes — record some prompts first")

        ds_id = time.strftime("%Y%m%d-%H%M%S")
        out = DATASETS_DIR / ds_id
        wavs = out / "wavs"
        wavs.mkdir(parents=True)

        items, flagged, excluded = [], [], []
        total_secs = 0.0
        for i, take in enumerate(takes):
            _status.update(progress=i / len(takes),
                           message=f"Processing take {i + 1}/{len(takes)} (normalize + verify)")
            src = TAKES_DIR / f"{take['id']}.wav"
            if not src.exists():
                continue
            dst = wavs / f"{take['id']}.wav"
            # Loudness-normalize; 32kHz mono matches GPT-SoVITS training input.
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-af", "loudnorm=I=-18:TP=-2:LRA=11",
                 "-ar", "32000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                check=True, capture_output=True,
            )
            heard = engine.transcribe(dst)
            score = _similarity(take["text"], heard)
            with db.connect() as conn:
                conn.execute("UPDATE takes SET verify_score=?, verify_text=? WHERE id=?",
                             (score, heard, take["id"]))
            if score < 0.6:
                dst.unlink()
                excluded.append({"id": take["id"], "text": take["text"], "heard": heard,
                                 "score": round(score, 2)})
                continue
            if score < 0.85:
                flagged.append({"id": take["id"], "text": take["text"], "heard": heard,
                                "score": round(score, 2)})
            dur = audio.duration_secs(dst)
            total_secs += dur
            items.append({"file": dst.name, "text": take["text"],
                          "duration_secs": round(dur, 2), "score": round(score, 2)})

        if not items:
            raise RuntimeError("All takes were excluded by verification — re-record and retry")

        with open(out / "filelist.list", "w") as f:
            for it in items:
                f.write(f"wavs/{it['file']}|{speaker}|EN|{it['text']}\n")

        manifest = {
            "id": ds_id,
            "speaker": speaker,
            "path": str(out),
            "segments": len(items),
            "total_secs": round(total_secs, 1),
            "flagged": flagged,
            "excluded": excluded,
            "created_at": time.time(),
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        _status.update(state="done", progress=1.0,
                       message=f"Dataset ready: {len(items)} segments, "
                               f"{total_secs / 60:.1f} min", manifest=manifest)
    except Exception as e:
        _status.update(state="error", message=str(e))


def latest_manifest() -> dict | None:
    builds = sorted(DATASETS_DIR.glob("*/manifest.json"))
    if not builds:
        return None
    return json.loads(builds[-1].read_text())
