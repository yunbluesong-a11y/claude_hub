"""
git_sync.py — git add + commit + push
"""
import subprocess
from webapp.config import BASE_DIR


def git_status() -> dict:
    """git status 요약"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10,
        )
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        return {
            "success": True,
            "changes": len(lines),
            "files": lines[:50],  # 최대 50개만
            "clean": len(lines) == 0,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_sync(message: str = None) -> dict:
    """git add + commit + push"""
    if not message:
        message = "[claude-hub-webapp] 데이터 동기화"

    steps = []
    try:
        # git add
        r = subprocess.run(
            ["git", "add", "-A"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=30,
        )
        steps.append({"step": "git add", "success": r.returncode == 0, "output": r.stdout + r.stderr})

        # 변경사항 확인
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10,
        )
        if not status.stdout.strip():
            return {"success": True, "message": "변경사항 없음", "steps": steps}

        # git commit
        r = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=30,
        )
        steps.append({"step": "git commit", "success": r.returncode == 0, "output": r.stdout + r.stderr})
        if r.returncode != 0:
            return {"success": False, "error": "commit 실패", "steps": steps}

        # git push
        r = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=60,
        )
        steps.append({"step": "git push", "success": r.returncode == 0, "output": r.stdout + r.stderr})

        return {
            "success": r.returncode == 0,
            "message": "동기화 완료" if r.returncode == 0 else "push 실패",
            "steps": steps,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "steps": steps}
