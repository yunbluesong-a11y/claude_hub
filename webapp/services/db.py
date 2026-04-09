"""
db.py — SQLite 연결 관리 (WAL 모드)
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from webapp.config import MASTER_DB, DB_DIR


# ── master.sqlite 스키마 정의 ──────────────────────────────────────

MASTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contact TEXT,
    address TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    case_slug TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'civil',
    case_number TEXT,
    court TEXT,
    opponent TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(client_id, case_slug),
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    case_slug TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    file_type TEXT,
    file_path TEXT,
    submitted INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    case_slug TEXT NOT NULL,
    title TEXT NOT NULL,
    doc_type TEXT,
    file_path TEXT,
    version INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS transactions_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT UNIQUE,
    client_id TEXT,
    case_slug TEXT,
    source_file TEXT,
    row_count INTEGER,
    columns TEXT,
    date_range_start TEXT,
    date_range_end TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    case_slug TEXT NOT NULL,
    source_file TEXT NOT NULL,
    file_type TEXT,
    page_number INTEGER,
    content TEXT,
    keywords TEXT
);

CREATE TABLE IF NOT EXISTS image_ocr (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    case_slug TEXT NOT NULL,
    source_file TEXT NOT NULL,
    ocr_text TEXT,
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
"""


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    """WAL 모드로 SQLite 연결 생성"""
    if db_path is None:
        db_path = MASTER_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db(db_path: Path = None):
    """컨텍스트 매니저로 DB 연결 관리"""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_master_db():
    """master.sqlite 초기화 (테이블 없으면 생성)"""
    MASTER_DB.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(MASTER_SCHEMA)
    print(f"[DB] master.sqlite 초기화 완료: {MASTER_DB}")


def dict_from_row(row: sqlite3.Row) -> dict:
    """sqlite3.Row를 dict로 변환"""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list:
    """sqlite3.Row 목록을 dict 리스트로 변환"""
    return [dict(r) for r in rows]
