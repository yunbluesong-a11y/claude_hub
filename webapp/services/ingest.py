"""
ingest.py — 기존 scripts/ 호출 래퍼
비동기 처리를 위해 subprocess로 실행
"""
import subprocess
import sys
from pathlib import Path
from webapp.config import SCRIPTS_DIR, BASE_DIR, INGEST_TIMEOUT


def run_ingest(client_id: str, case_slug: str) -> dict:
    """
    scripts/ingest.py를 subprocess로 실행.
    작은 트랜잭션 단위로 처리되므로 WAL 모드에서 안전.
    """
    script = SCRIPTS_DIR / "ingest.py"
    if not script.exists():
        return {"success": False, "error": "ingest.py 스크립트가 없습니다.", "output": ""}

    try:
        result = subprocess.run(
            [sys.executable, str(script), f"{client_id}/{case_slug}"],
            capture_output=True,
            text=True,
            timeout=INGEST_TIMEOUT,
            cwd=str(BASE_DIR),
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"ingest 타임아웃 ({INGEST_TIMEOUT}초 초과)", "output": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "output": ""}


def classify_file_type(filename: str) -> str:
    """파일 확장자로 유형 판별"""
    ext = Path(filename).suffix.lower()
    type_map = {
        ".xlsx": "xlsx", ".xls": "xlsx", ".csv": "csv",
        ".pdf": "pdf",
        ".docx": "docx", ".doc": "docx",
        ".jpg": "image", ".jpeg": "image", ".png": "image",
        ".gif": "image", ".bmp": "image", ".tiff": "image",
        ".tif": "image", ".webp": "image", ".heic": "image",
        ".mp4": "video", ".avi": "video", ".mov": "video",
        ".mkv": "video", ".wmv": "video",
    }
    return type_map.get(ext, "other")
