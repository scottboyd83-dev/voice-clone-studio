from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VOICES_DIR = DATA / "voices"
GENERATIONS_DIR = DATA / "generations"
TAKES_DIR = DATA / "takes"
DATASETS_DIR = DATA / "datasets"
DB_PATH = DATA / "studio.db"

for d in (VOICES_DIR, GENERATIONS_DIR, TAKES_DIR, DATASETS_DIR):
    d.mkdir(parents=True, exist_ok=True)
