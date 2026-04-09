"""
run.py — 서버 진입점 (uvicorn 실행)
"""
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

import uvicorn
from webapp.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run(
        "webapp.app:app",
        host=HOST,
        port=PORT,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )
