import json
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import audio, db, dataset, engine, finetune, gsv, quality, seedvc
from .paths import CONVERSIONS_DIR, GENERATIONS_DIR, TAKES_DIR, VOICES_DIR
from .scripts_corpus import SCRIPTS

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
        audio.to_wav(tmp_path, ref_wav)
        tmp_path.unlink()

        duration = audio.duration_secs(ref_wav)
        if duration < 3:
            raise HTTPException(400, "Reference clip too short — record at least 3 seconds.")
        if duration > audio.MAX_REF_SECONDS:
            # F5-TTS paces output by the reference's chars-per-second, so the
            # transcript must match the audio exactly. After trimming, the
            # provided transcript no longer does — discard it and re-transcribe.
            trimmed = voice_dir / "reference_trimmed.wav"
            audio.to_wav(ref_wav, trimmed, max_seconds=audio.MAX_REF_SECONDS)
            trimmed.replace(ref_wav)
            ref_text = ""

        # No transcript (or trimmed) -> auto-transcribe (first call downloads Whisper).
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
        "engine": row["engine"],
        "model": row["model"],
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
    # GPT-SoVITS sampling (ignored by the F5 engine)
    top_k: int = Field(default=5, ge=1, le=100)
    top_p: float = Field(default=1.0, ge=0.05, le=1.0)
    temperature: float = Field(default=1.0, ge=0.05, le=2.0)


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
        if voice["engine"] == "gptsovits":
            used_seed = gsv.generate(voice, req.text, req.speed, req.seed, out_wav,
                                     top_k=req.top_k, top_p=req.top_p,
                                     temperature=req.temperature)
        else:
            used_seed = engine.generate(ref_wav, voice["ref_text"], req.text, settings, out_wav)
    except Exception as e:
        out_wav.unlink(missing_ok=True)
        raise HTTPException(500, f"Generation failed: {e}")

    duration = audio.duration_secs(out_wav)
    settings_json = json.dumps({
        "speed": req.speed, "nfe_step": req.nfe_step, "cfg_strength": req.cfg_strength,
        "seed": req.seed, "remove_silence": req.remove_silence,
        "top_k": req.top_k, "top_p": req.top_p, "temperature": req.temperature,
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


# ---------- speech-to-speech conversion (Seed-VC) ----------

@app.get("/api/convert/status")
def convert_status():
    return {"installed": seedvc.is_installed(), "state": seedvc.state()}


@app.post("/api/convert/warmup")
def convert_warmup():
    if not seedvc.is_installed():
        raise HTTPException(409, "Seed-VC is not installed — run scripts/setup_seedvc.sh")
    threading.Thread(target=seedvc.ensure_running, daemon=True).start()
    return {"ok": True}


@app.post("/api/convert")
def convert(
    voice_id: str = Form(...),
    diffusion_steps: int = Form(25),
    length_adjust: float = Form(1.0),
    f0_condition: bool = Form(False),
    auto_f0_adjust: bool = Form(True),
    pitch_shift: int = Form(0),
    audio_file: UploadFile = File(...),
):
    voice = get_voice(voice_id)
    target_wav = VOICES_DIR / voice_id / "reference.wav"
    if not target_wav.exists():
        raise HTTPException(404, "Reference audio missing for this voice")
    if not 1 <= diffusion_steps <= 100:
        raise HTTPException(400, "diffusion_steps must be 1-100")
    if not 0.5 <= length_adjust <= 2.0:
        raise HTTPException(400, "length_adjust must be 0.5-2.0")
    if not -24 <= pitch_shift <= 24:
        raise HTTPException(400, "pitch_shift must be -24..24 semitones")

    conv_id = db.new_id()
    source_wav = CONVERSIONS_DIR / f"{conv_id}_source.wav"
    out_wav = CONVERSIONS_DIR / f"{conv_id}.wav"
    try:
        suffix = Path(audio_file.filename or "source").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            tmp_path = Path(tmp.name)
        # 44.1k keeps full bandwidth for the singing (f0) path's 44.1k output
        audio.to_wav(tmp_path, source_wav, sample_rate=44100)
        tmp_path.unlink()

        src_secs = audio.duration_secs(source_wav)
        if src_secs < 1:
            raise HTTPException(400, "Source clip too short — need at least 1 second of speech.")
        if src_secs > 300:
            raise HTTPException(400, "Source clip too long — keep it under 5 minutes.")

        seedvc.convert(
            source_wav, target_wav, out_wav,
            diffusion_steps=diffusion_steps, length_adjust=length_adjust,
            f0_condition=f0_condition, auto_f0_adjust=auto_f0_adjust,
            pitch_shift=pitch_shift,
        )

        settings_json = json.dumps({
            "diffusion_steps": diffusion_steps, "length_adjust": length_adjust,
            "f0_condition": f0_condition, "auto_f0_adjust": auto_f0_adjust,
            "pitch_shift": pitch_shift,
        })
        source_name = Path(audio_file.filename).name if audio_file.filename else "recording"
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO conversions (id, voice_id, source_name, settings, duration_secs, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (conv_id, voice_id, source_name, settings_json,
                 audio.duration_secs(out_wav), db.now()),
            )
        return get_conversion(conv_id)
    except HTTPException:
        source_wav.unlink(missing_ok=True)
        out_wav.unlink(missing_ok=True)
        raise
    except Exception as e:
        source_wav.unlink(missing_ok=True)
        out_wav.unlink(missing_ok=True)
        raise HTTPException(500, f"Conversion failed: {e}")


def _conv_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "voice_id": row["voice_id"],
        "source_name": row["source_name"],
        "settings": json.loads(row["settings"]),
        "duration_secs": row["duration_secs"],
        "created_at": row["created_at"],
    }


@app.get("/api/conversions")
def list_conversions(voice_id: str | None = None):
    q = "SELECT * FROM conversions"
    args: tuple = ()
    if voice_id:
        q += " WHERE voice_id=?"
        args = (voice_id,)
    q += " ORDER BY created_at DESC LIMIT 200"
    with db.connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [_conv_row_to_dict(r) for r in rows]


@app.get("/api/conversions/{conv_id}")
def get_conversion(conv_id: str):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM conversions WHERE id=?", (conv_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Conversion not found")
    return _conv_row_to_dict(row)


@app.get("/api/conversions/{conv_id}/audio")
def conversion_audio(conv_id: str, which: str = "output"):
    name = f"{conv_id}_source.wav" if which == "source" else f"{conv_id}.wav"
    path = CONVERSIONS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Audio not found")
    return FileResponse(path, media_type="audio/wav", filename=name)


@app.delete("/api/conversions/{conv_id}")
def delete_conversion(conv_id: str):
    with db.connect() as conn:
        deleted = conn.execute("DELETE FROM conversions WHERE id=?", (conv_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Conversion not found")
    (CONVERSIONS_DIR / f"{conv_id}.wav").unlink(missing_ok=True)
    (CONVERSIONS_DIR / f"{conv_id}_source.wav").unlink(missing_ok=True)
    return {"ok": True}


# ---------- recording studio ----------

@app.get("/api/studio/scripts")
def studio_scripts():
    with db.connect() as conn:
        counts = dict(conn.execute(
            "SELECT script_id, COUNT(*) FROM takes WHERE status='kept' GROUP BY script_id"
        ).fetchall())
    return [
        {"script_id": i, "category": cat, "text": text, "takes": counts.get(i, 0)}
        for i, (cat, text) in enumerate(SCRIPTS)
    ]


def _take_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "script_id": row["script_id"],
        "text": row["text"],
        "duration_secs": row["duration_secs"],
        "metrics": json.loads(row["metrics"]) if row["metrics"] else None,
        "verify_score": row["verify_score"],
        "verify_text": row["verify_text"],
        "created_at": row["created_at"],
    }


@app.post("/api/studio/takes")
def create_take(script_id: int = Form(...), audio_file: UploadFile = File(...)):
    if not 0 <= script_id < len(SCRIPTS):
        raise HTTPException(400, "Unknown script")
    take_id = db.new_id()
    wav = TAKES_DIR / f"{take_id}.wav"
    try:
        suffix = Path(audio_file.filename or "take").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            tmp_path = Path(tmp.name)
        audio.to_wav(tmp_path, wav)
        tmp_path.unlink()
        metrics = quality.analyze(wav)
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO takes (id, script_id, text, duration_secs, metrics, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (take_id, script_id, SCRIPTS[script_id][1], metrics["duration_secs"],
                 json.dumps(metrics), db.now()),
            )
        return get_take(take_id)
    except HTTPException:
        wav.unlink(missing_ok=True)
        raise
    except Exception as e:
        wav.unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to save take: {e}")


@app.get("/api/studio/takes")
def list_takes(script_id: int | None = None):
    q = "SELECT * FROM takes WHERE status='kept'"
    args: tuple = ()
    if script_id is not None:
        q += " AND script_id=?"
        args = (script_id,)
    q += " ORDER BY created_at DESC"
    with db.connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [_take_row_to_dict(r) for r in rows]


@app.get("/api/studio/takes/{take_id}")
def get_take(take_id: str):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM takes WHERE id=?", (take_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Take not found")
    return _take_row_to_dict(row)


@app.get("/api/studio/takes/{take_id}/audio")
def take_audio(take_id: str):
    path = TAKES_DIR / f"{take_id}.wav"
    if not path.exists():
        raise HTTPException(404, "Take audio not found")
    return FileResponse(path, media_type="audio/wav")


@app.delete("/api/studio/takes/{take_id}")
def delete_take(take_id: str):
    with db.connect() as conn:
        deleted = conn.execute("DELETE FROM takes WHERE id=?", (take_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Take not found")
    (TAKES_DIR / f"{take_id}.wav").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/studio/stats")
def studio_stats():
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(duration_secs),0) AS secs, "
            "COUNT(DISTINCT script_id) AS scripts FROM takes WHERE status='kept'"
        ).fetchone()
    return {"takes": row["n"], "total_secs": row["secs"],
            "scripts_covered": row["scripts"], "scripts_total": len(SCRIPTS)}


# ---------- dataset ----------

@app.post("/api/dataset/build")
def dataset_build():
    try:
        dataset.start_build()
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.get("/api/dataset/status")
def dataset_status():
    s = dataset.status()
    if s["state"] == "idle":
        s["manifest"] = dataset.latest_manifest()
    return s


@app.get("/api/datasets")
def list_datasets():
    out = []
    for mf in sorted(dataset.DATASETS_DIR.glob("*/manifest.json"), reverse=True):
        out.append(json.loads(mf.read_text()))
    return out


# ---------- fine-tuning ----------

class TrainRequest(BaseModel):
    dataset_id: str
    voice_name: str = Field(min_length=1, max_length=80)
    sovits_epochs: int = Field(default=8, ge=1, le=25)
    gpt_epochs: int = Field(default=15, ge=1, le=50)


@app.post("/api/train")
def train_start(req: TrainRequest):
    try:
        job_id = finetune.start(req.dataset_id, req.voice_name.strip(),
                                req.sovits_epochs, req.gpt_epochs)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"job_id": job_id}


@app.get("/api/train/status")
def train_status():
    return finetune.status()


@app.delete("/api/generations/{gen_id}")
def delete_generation(gen_id: str):
    with db.connect() as conn:
        deleted = conn.execute("DELETE FROM generations WHERE id=?", (gen_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Generation not found")
    (GENERATIONS_DIR / f"{gen_id}.wav").unlink(missing_ok=True)
    (GENERATIONS_DIR / f"{gen_id}.mp3").unlink(missing_ok=True)
    return {"ok": True}
