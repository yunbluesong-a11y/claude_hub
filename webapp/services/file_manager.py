"""
file_manager.py — 파일 저장, 경로 관리
"""
import shutil
from pathlib import Path
from webapp.config import RAW_DIR, PROJECTS_DIR


def ensure_case_dirs(client_id: str, case_slug: str):
    """사건 관련 디렉토리 일괄 생성"""
    dirs = [
        RAW_DIR / client_id / case_slug,
        PROJECTS_DIR / client_id / case_slug / "summaries",
        PROJECTS_DIR / client_id / case_slug / "index",
        PROJECTS_DIR / client_id / case_slug / "outputs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    # 의뢰인 README
    client_readme = PROJECTS_DIR / client_id / "README.md"
    if not client_readme.exists():
        client_readme.parent.mkdir(parents=True, exist_ok=True)
        client_readme.write_text(f"# {client_id}\n\n의뢰인 정보\n", encoding="utf-8")


def save_uploaded_file(file_bytes: bytes, filename: str, client_id: str, case_slug: str) -> Path:
    """업로드 파일을 raw/ 디렉토리에 저장"""
    target_dir = RAW_DIR / client_id / case_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    # 동일 파일명 존재 시 번호 추가
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        i = 1
        while target_path.exists():
            target_path = target_dir / f"{stem}_{i}{suffix}"
            i += 1
    target_path.write_bytes(file_bytes)
    return target_path


def get_file_size_str(size_bytes: int) -> str:
    """파일 크기를 읽기 좋은 문자열로"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def get_raw_files(client_id: str, case_slug: str) -> list:
    """사건의 raw 파일 목록"""
    raw_dir = RAW_DIR / client_id / case_slug
    if not raw_dir.exists():
        return []
    files = []
    for f in sorted(raw_dir.rglob("*")):
        if f.is_file() and not f.name.startswith("."):
            files.append({
                "name": f.name,
                "path": str(f.relative_to(RAW_DIR.parent)),
                "size": get_file_size_str(f.stat().st_size),
                "size_bytes": f.stat().st_size,
                "suffix": f.suffix.lower(),
            })
    return files
