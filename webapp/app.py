"""
app.py — FastAPI 앱 정의
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import time

from webapp.config import AUTH_TOKEN, RAW_DIR
from webapp.services.db import init_master_db
from webapp.routers import clients, cases, evidence, documents, system

# ── FastAPI 앱 ──────────────────────────────────────────────────────

app = FastAPI(
    title="claude-hub",
    description="의뢰인·사건·증거 관리 웹앱",
    version="1.0.0",
)


# ── 보안 미들웨어 (Bearer 토큰) ────────────────────────────────────

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """간단한 Bearer 토큰 인증"""
    # 정적 파일, health 체크는 인증 제외
    path = request.url.path
    if path in ("/", "/health", "/favicon.ico") or path.startswith("/static"):
        return await call_next(request)

    # API 요청은 토큰 확인
    if path.startswith("/api"):
        # health, login은 인증 없이
        if path in ("/api/health", "/api/login"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        token = request.query_params.get("token", "")

        if auth == f"Bearer {AUTH_TOKEN}" or token == AUTH_TOKEN:
            return await call_next(request)

        # 쿠키 기반 인증 (로그인 후)
        if request.cookies.get("auth_token") == AUTH_TOKEN:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "인증이 필요합니다. Bearer 토큰을 제공해주세요."}
        )

    return await call_next(request)


# ── 에러 핸들러 ────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=404, content={"detail": "요청한 리소스를 찾을 수 없습니다.", "path": request.url.path})
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.exception_handler(422)
async def validation_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": "입력값이 올바르지 않습니다.", "errors": str(exc)}
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}
    )


# ── 라우터 등록 ────────────────────────────────────────────────────

app.include_router(clients.router)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(documents.router)
app.include_router(system.router)


# ── 파일 미리보기 엔드포인트 ────────────────────────────────────────

@app.get("/api/preview/{client_id}/{case_slug}/{filename:path}")
async def preview_file(client_id: str, case_slug: str, filename: str):
    """증거 파일 미리보기 (PDF는 브라우저 뷰어, 이미지는 직접 표시)"""
    file_path = RAW_DIR / client_id / case_slug / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    suffix = file_path.suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".bmp": "image/bmp", ".webp": "image/webp",
        ".tiff": "image/tiff", ".tif": "image/tiff",
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)


# ── 로그인 API ─────────────────────────────────────────────────────

from pydantic import BaseModel

class LoginRequest(BaseModel):
    token: str

@app.post("/api/login")
async def login(data: LoginRequest):
    """토큰으로 로그인 → 쿠키 설정"""
    if data.token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="토큰이 올바르지 않습니다.")
    response = JSONResponse(content={"message": "로그인 성공"})
    response.set_cookie(
        key="auth_token",
        value=AUTH_TOKEN,
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30일
        samesite="lax",
    )
    return response


# ── 정적 파일 & SPA ────────────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")


# ── 시작 시 DB 초기화 ──────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_master_db()
    print("[claude-hub] 웹앱 시작 완료")
