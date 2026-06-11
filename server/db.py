import sqlite3
import time
import uuid

from .paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS voices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    ref_text TEXT NOT NULL,
    engine TEXT NOT NULL DEFAULT 'f5',   -- f5 (instant) | gptsovits (fine-tuned)
    model TEXT,                          -- JSON weight/prompt paths for gptsovits
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS takes (
    id TEXT PRIMARY KEY,
    script_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    duration_secs REAL,
    metrics TEXT,                    -- JSON from quality.analyze
    status TEXT DEFAULT 'kept',      -- kept | discarded
    verify_score REAL,               -- transcript match 0-1, set during dataset build
    verify_text TEXT,                -- what Whisper heard
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    voice_id TEXT NOT NULL REFERENCES voices(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    settings TEXT NOT NULL,          -- JSON: speed, nfe_step, cfg_strength, seed, remove_silence
    seed INTEGER,                    -- actual seed used (resolved if random)
    duration_secs REAL,
    created_at REAL NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # migrate pre-Phase-3 databases
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(voices)")}
        if "engine" not in cols:
            conn.execute("ALTER TABLE voices ADD COLUMN engine TEXT NOT NULL DEFAULT 'f5'")
            conn.execute("ALTER TABLE voices ADD COLUMN model TEXT")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> float:
    return time.time()
