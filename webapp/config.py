"""
config.py — 웹앱 설정
"""
import os
from pathlib import Path

# claude_hub 루트 경로 (환경변수로 오버라이드 가능)
BASE_DIR = Path(os.environ.get("CLAUDE_HUB_ROOT", Path(__file__).parent.parent))

# DB 경로
MASTER_DB = BASE_DIR / "db" / "master.sqlite"
LEGACY_DB_DIR = BASE_DIR / "db" / "legacy"
DB_DIR = BASE_DIR / "db"

# 디렉토리
RAW_DIR = BASE_DIR / "raw"
PROJECTS_DIR = BASE_DIR / "projects"
SCRIPTS_DIR = BASE_DIR / "scripts"
SESSIONS_DIR = BASE_DIR / "sessions"

# 서버
HOST = os.environ.get("WEBAPP_HOST", "0.0.0.0")
PORT = int(os.environ.get("WEBAPP_PORT", "8000"))

# 보안 — Bearer 토큰 (환경변수 또는 기본값)
# 프로덕션에서는 반드시 환경변수로 설정할 것
AUTH_TOKEN = os.environ.get("WEBAPP_AUTH_TOKEN", "claude-hub-2026")

# 파일 업로드 제한
MAX_UPLOAD_SIZE_MB = 200
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ingest 타임아웃 (초)
INGEST_TIMEOUT = 300
