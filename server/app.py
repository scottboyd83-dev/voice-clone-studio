import json
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import audio, db, engine
from .paths import GENERATIONS_DIR, VOICES_DIR

app = FastAPI(title="Voice Clone Studio")

# Dev: vite runs on :5173, API on :8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()


# ---------- status / warmup ----------

@app.get("/api/status")
def status():
    return {"model_loaded": engine.is_loaded()}


@app.post("/api/warmup")
def warmup():
    # Load in a background thread so the request returns immediately;
    # generation requests queue behind the engine lock until it's ready.
    threading.Thread(target=engine.warmup, daemon=True).start()
    return {"ok": True}


# ---------- voices ----------

@app.post("/api/voices")
def create_voice(
    name: str = Form(...),
    description: str = Form(""),
    ref_text: str = Form(""),
    audio_file: UploadFile = File(...),
):
    voice_id = db.new_id()
    voice_dir = VOICES_DIR / voice_id
    voice_dir.mkdir(parents=True)
    try:
        # Stash upload (webm from MediaRecorder, or any format) then convert.
        suffix = Path(audio_file.filename or "ref").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            tmp_path = Path(tmp.name)
        ref_wav = voice_dir / "reference.wav"
        audio.to_wav(tmp_path, ref_wav, max_seconds=audio.MAX_REF_SECONDS)
        tmp_path.unlink()

        if duration := audio.duration_secs(ref_wav):
            if duration < 3:
                raise HTTPException(400, "Reference clip too short — record at least 3 seconds.")

        # No transcript provided -> auto-transcribe (first call downloads Whisper).
        ref_text = ref_text.strip() or engine.transcribe(ref_wav)

        with db.connect() as conn:
            conn.execute(
                "INSERT INTO voices (id, name, description, ref_text, created_at) VALUES (?,?,?,?,?)",
                (voice_id, name.strip(), description.strip(), ref_text, db.now()),
            )
        return get_voice(voice_id)
    except HTTPException:
        shutil.rmtree(voice_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(voice_dir, ignore_errors=True)
        raise HTTPException(500, f"Failed to create voice: {e}")


def _voice_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "ref_text": row["ref_text"],
        "created_at": row["created_at"],
    }


@app.get("/api/voices")
def list_voices():
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM voices ORDER BY created_at DESC").fetchall()
    return [_voice_row_to_dict(r) for r in rows]


@app.get("/api/voices/{voice_id}")
def get_voice(voice_id: str):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM voices WHERE id=?", (voice_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Voice not found")
    return _voice_row_to_dict(row)


@app.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: str):
    with db.connect() as conn:
        gen_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM generations WHERE voice_id=?", (voice_id,)).fetchall()]
        deleted = conn.execute("DELETE FROM voices WHERE id=?", (voice_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Voice not found")
    shutil.rmtree(VOICES_DIR / voice_id, ignore_errors=True)
    for gid in gen_ids:
        (GENERATIONS_DIR / f"{gid}.wav").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/voices/{voice_id}/reference")
def voice_reference_audio(voice_id: str):
    path = VOICES_DIR / voice_id / "reference.wav"
    if not path.exists():
        raise HTTPException(404, "Reference audio not found")
    return FileResponse(path, media_type="audio/wav")


# ---------- generation ----------

class GenerateRequest(BaseModel):
    voice_id: str
    text: str = Field(min_length=1, max_length=20000)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    nfe_step: int = Field(default=32, ge=8, le=64)
    cfg_strength: float = Field(default=2.0, ge=1.0, le=4.0)
    seed: int | None = None
    remove_silence: bool = False


@app.post("/api/generate")
def generate(req: GenerateRequest):
    voice = get_voice(req.voice_id)
    ref_wav = VOICES_DIR / req.voice_id / "reference.wav"
    if not ref_wav.exists():
        raise HTTPException(404, "Reference audio missing for this voice")

    gen_id = db.new_id()
    out_wav = GENERATIONS_DIR / f"{gen_id}.wav"
    settings = engine.GenSettings(
        speed=req.speed, nfe_step=req.nfe_step, cfg_strength=req.cfg_strength,
        seed=req.seed, remove_silence=req.remove_silence,
    )
    try:
        used_seed = engine.generate(ref_wav, voice["ref_text"], req.text, settings, out_wav)
    except Exception as e:
        out_wav.unlink(missing_ok=True)
        raise HTTPException(500, f"Generation failed: {e}")

    duration = audio.duration_secs(out_wav)
    settings_json = json.dumps({
        "speed": req.speed, "nfe_step": req.nfe_step, "cfg_strength": req.cfg_strength,
        "seed": req.seed, "remove_silence": req.remove_silence,
    })
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO generations (id, voice_id, text, settings, seed, duration_secs, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (gen_id, req.voice_id, req.text, settings_json, used_seed, duration, db.now()),
        )
    return get_generation(gen_id)


def _gen_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "voice_id": row["voice_id"],
        "text": row["text"],
        "settings": json.loads(row["settings"]),
        "seed": row["seed"],
        "duration_secs": row["duration_secs"],
        "created_at": row["created_at"],
    }


@app.get("/api/generations")
def list_generations(voice_id: str | None = None):
    q = "SELECT * FROM generations"
    args: tuple = ()
    if voice_id:
        q += " WHERE voice_id=?"
        args = (voice_id,)
    q += " ORDER BY created_at DESC LIMIT 200"
    with db.connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [_gen_row_to_dict(r) for r in rows]


@app.get("/api/generations/{gen_id}")
def get_generation(gen_id: str):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM generations WHERE id=?", (gen_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Generation not found")
    return _gen_row_to_dict(row)


@app.get("/api/generations/{gen_id}/audio")
def generation_audio(gen_id: str, format: str = "wav"):
    wav = GENERATIONS_DIR / f"{gen_id}.wav"
    if not wav.exists():
        raise HTTPException(404, "Audio not found")
    if format == "mp3":
        mp3 = GENERATIONS_DIR / f"{gen_id}.mp3"
        if not mp3.exists():
            audio.wav_to_mp3(wav, mp3)
        return FileResponse(mp3, media_type="audio/mpeg", filename=f"{gen_id}.mp3")
    return FileResponse(wav, media_type="audio/wav", filename=f"{gen_id}.wav")


@app.delete("/api/generations/{gen_id}")
def delete_generation(gen_id: str):
    with db.connect() as conn:
        deleted = conn.execute("DELETE FROM generations WHERE id=?", (gen_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Generation not found")
    (GENERATIONS_DIR / f"{gen_id}.wav").unlink(missing_ok=True)
    (GENERATIONS_DIR / f"{gen_id}.mp3").unlink(missing_ok=True)
    return {"ok": True}
