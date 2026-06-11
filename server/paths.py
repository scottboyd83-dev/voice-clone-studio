from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VOICES_DIR = DATA / "voices"
GENERATIONS_DIR = DATA / "generations"
DB_PATH = DATA / "studio.db"

for d in (VOICES_DIR, GENERATIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)
