"""Fine-tuning orchestration: dataset -> GPT-SoVITS v2 voice.

Replicates the GPT-SoVITS webui pipeline without the webui:
  1. 1-get-text.py      (phonemes + BERT features)
  2. 2-get-hubert-wav32k.py (SSL features)
  3. 3-get-semantic.py  (semantic tokens via pretrained s2G)
  4. s2_train.py        (SoVITS — the vocal timbre model)
  5. s1_train.py        (GPT — the prosody/delivery model)
  6. register the fine-tuned voice in the library

Each stage shells into the isolated GPT-SoVITS venv (CPU training on Apple
Silicon — slow but supported). Logs land in data/finetune/<job>/logs/.
"""

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import yaml

from . import audio, db, gsv
from .paths import DATA, DATASETS_DIR, VOICES_DIR

FINETUNE_DIR = DATA / "finetune"
MODELS_DIR = DATA / "models"

_status = {"state": "idle", "stage": None, "progress": 0.0, "message": "",
           "job_id": None, "voice_id": None}
_start_lock = threading.Lock()

STAGES = ["preprocess_text", "preprocess_ssl", "preprocess_semantic",
          "train_sovits", "train_gpt", "register"]


def status() -> dict:
    s = dict(_status)
    s["log_tail"] = _log_tail()
    return s


def _log_tail(lines: int = 25) -> list[str]:
    job_id = _status.get("job_id")
    stage = _status.get("stage")
    if not job_id or not stage:
        return []
    log = FINETUNE_DIR / job_id / "logs" / f"{stage}.log"
    if not log.exists():
        return []
    try:
        return log.read_text(errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def start(dataset_id: str, voice_name: str, sovits_epochs: int = 8, gpt_epochs: int = 15) -> str:
    with _start_lock:
        if _status["state"] == "running":
            raise RuntimeError("A fine-tune is already running")
        if not gsv.is_installed():
            raise RuntimeError("GPT-SoVITS is not installed — run setup first")
        if not (DATASETS_DIR / dataset_id / "filelist.list").exists():
            raise RuntimeError(f"Dataset {dataset_id} not found")
        job_id = time.strftime("%Y%m%d-%H%M%S")
        _status.update(state="running", stage=STAGES[0], progress=0.0,
                       message="Starting fine-tune…", job_id=job_id, voice_id=None)
    threading.Thread(target=_run, args=(job_id, dataset_id, voice_name,
                                        sovits_epochs, gpt_epochs), daemon=True).start()
    return job_id


def _stage(idx: int, message: str) -> None:
    _status.update(stage=STAGES[idx], progress=idx / len(STAGES), message=message)


def _run_script(job: Path, stage: str, args: list[str], env_extra: dict) -> None:
    env = os.environ.copy()
    # scripts import from both the repo root (tools.*) and GPT_SoVITS/ (text.*, AR.*)
    env["PYTHONPATH"] = f"{gsv.GSV_ROOT}:{gsv.GSV_ROOT / 'GPT_SoVITS'}"
    env.update({"version": "v2", "is_half": "False", "_CUDA_VISIBLE_DEVICES": "0",
                "i_part": "0", "all_parts": "1", "hz": "25hz"})
    env.update({k: str(v) for k, v in env_extra.items()})
    logs = job / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / f"{stage}.log", "w") as log:
        proc = subprocess.run([str(gsv.GSV_PY), "-s", *args], cwd=gsv.GSV_ROOT,
                              env=env, stdout=log, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise RuntimeError(f"{stage} failed (exit {proc.returncode}) — see {logs}/{stage}.log")


def _run(job_id: str, dataset_id: str, voice_name: str,
         sovits_epochs: int, gpt_epochs: int) -> None:
    try:
        dataset = DATASETS_DIR / dataset_id
        inp_text = dataset / "filelist.list"
        inp_wav_dir = dataset / "wavs"
        job = FINETUNE_DIR / job_id
        opt = job / "exp"          # GPT-SoVITS experiment dir
        opt.mkdir(parents=True, exist_ok=True)
        weights_sovits = MODELS_DIR / job_id / "sovits"
        weights_gpt = MODELS_DIR / job_id / "gpt"
        weights_sovits.mkdir(parents=True, exist_ok=True)
        weights_gpt.mkdir(parents=True, exist_ok=True)
        exp_name = "voice"

        common = {"inp_text": inp_text, "inp_wav_dir": inp_wav_dir,
                  "exp_name": exp_name, "opt_dir": opt}

        # ---- 1: text/BERT ----
        _stage(0, "Extracting phonemes and text features…")
        _run_script(job, STAGES[0], ["GPT_SoVITS/prepare_datasets/1-get-text.py"],
                    {**common, "bert_pretrained_dir": gsv.BERT_DIR})
        part = opt / "2-name2text-0.txt"
        if not part.exists() or not part.read_text().strip():
            raise RuntimeError("Text preprocessing produced no output")
        part.rename(opt / "2-name2text.txt")

        # ---- 2: SSL features ----
        _stage(1, "Extracting speech features (HuBERT)…")
        _run_script(job, STAGES[1], ["GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py"],
                    {**common, "cnhubert_base_dir": gsv.HUBERT_DIR})

        # ---- 3: semantic tokens ----
        _stage(2, "Extracting semantic tokens…")
        _run_script(job, STAGES[2], ["GPT_SoVITS/prepare_datasets/3-get-semantic.py"],
                    {**common, "pretrained_s2G": gsv.PRETRAIN_S2G,
                     "s2config_path": "GPT_SoVITS/configs/s2.json"})
        part = opt / "6-name2semantic-0.tsv"
        if not part.exists():
            raise RuntimeError("Semantic preprocessing produced no output")
        merged = "item_name\tsemantic_audio\n" + part.read_text().strip("\n") + "\n"
        (opt / "6-name2semantic.tsv").write_text(merged)
        part.unlink()

        # ---- 4: SoVITS training ----
        _stage(3, f"Training SoVITS (timbre) — {sovits_epochs} epochs on CPU, this is the long part…")
        with open(gsv.GSV_ROOT / "GPT_SoVITS" / "configs" / "s2.json") as f:
            s2 = json.load(f)
        s2["train"].update(fp16_run=False, batch_size=2, epochs=sovits_epochs,
                           text_low_lr_rate=0.4, pretrained_s2G=str(gsv.PRETRAIN_S2G),
                           pretrained_s2D=str(gsv.PRETRAIN_S2D), if_save_latest=True,
                           if_save_every_weights=True,
                           save_every_epoch=max(1, sovits_epochs // 2),
                           gpu_numbers="0", grad_ckpt=False, lora_rank=32)
        s2["model"]["version"] = "v2"
        s2["data"]["exp_dir"] = s2["s2_ckpt_dir"] = str(opt)
        s2["save_weight_dir"] = str(weights_sovits)
        s2["name"] = exp_name
        s2["version"] = "v2"
        (opt / "logs_s2_v2").mkdir(exist_ok=True)
        s2_cfg = job / "s2_config.json"
        s2_cfg.write_text(json.dumps(s2))
        _run_script(job, STAGES[3], ["GPT_SoVITS/s2_train.py", "--config", str(s2_cfg)], {})
        sovits_weights = _newest(weights_sovits, "*.pth")

        # ---- 5: GPT training ----
        _stage(4, f"Training GPT (prosody) — {gpt_epochs} epochs on CPU…")
        with open(gsv.GSV_ROOT / "GPT_SoVITS" / "configs" / "s1longer-v2.yaml") as f:
            s1 = yaml.safe_load(f)
        s1["train"].update(batch_size=2, epochs=gpt_epochs,
                           save_every_n_epoch=max(1, gpt_epochs // 3),
                           if_save_every_weights=True, if_save_latest=True, if_dpo=False,
                           half_weights_save_dir=str(weights_gpt), exp_name=exp_name)
        s1["train"]["precision"] = "32"
        s1["data"]["num_workers"] = 0  # forked DataLoader workers deadlock on macOS
        s1["pretrained_s1"] = str(gsv.PRETRAIN_S1)
        s1["train_semantic_path"] = str(opt / "6-name2semantic.tsv")
        s1["train_phoneme_path"] = str(opt / "2-name2text.txt")
        s1["output_dir"] = str(opt / "logs_s1_v2")
        s1_cfg = job / "s1_config.yaml"
        s1_cfg.write_text(yaml.dump(s1, default_flow_style=False))
        _run_script(job, STAGES[4], ["GPT_SoVITS/s1_train.py", "--config_file", str(s1_cfg)], {})
        gpt_weights = _newest(weights_gpt, "*.ckpt")

        # ---- 6: register voice ----
        _stage(5, "Registering fine-tuned voice…")
        voice_id = _register_voice(voice_name, dataset, dataset_id,
                                   gpt_weights, sovits_weights)
        _status.update(state="done", progress=1.0, voice_id=voice_id,
                       message=f"Fine-tune complete — voice “{voice_name}” is ready")
    except Exception as e:
        _status.update(state="error", message=str(e))


def _newest(directory: Path, pattern: str) -> Path:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        raise RuntimeError(f"No trained weights found in {directory}")
    return files[-1]


def _register_voice(name: str, dataset: Path, dataset_id: str,
                    gpt_weights: Path, sovits_weights: Path) -> str:
    # Prompt clip must be 3-10s for GPT-SoVITS inference; pick the one nearest 6s.
    best, best_text = None, None
    for line in (dataset / "filelist.list").read_text().splitlines():
        rel, _spk, _lang, text = line.split("|", 3)
        wav = dataset / rel
        if not wav.exists():
            continue
        dur = audio.duration_secs(wav)
        if 3 <= dur <= 10 and (best is None or abs(dur - 6) < abs(best[1] - 6)):
            best, best_text = (wav, dur), text
    if best is None:
        raise RuntimeError("No 3-10s clip in dataset to use as inference prompt")

    voice_id = db.new_id()
    voice_dir = VOICES_DIR / voice_id
    voice_dir.mkdir(parents=True)
    prompt_wav = voice_dir / "reference.wav"
    shutil.copyfile(best[0], prompt_wav)
    model = {"gpt_path": str(gpt_weights), "sovits_path": str(sovits_weights),
             "prompt_wav": str(prompt_wav), "prompt_text": best_text}
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO voices (id, name, description, ref_text, engine, model, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (voice_id, name, f"Fine-tuned (GPT-SoVITS v2) from dataset {dataset_id}",
             best_text, "gptsovits", json.dumps(model), db.now()),
        )
    return voice_id
