@echo off
chcp 65001 >nul
echo ========================================
echo   claude-hub 웹앱 시작
echo ========================================
echo.

cd /d "%~dp0.."

:: 의존성 확인
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [설치] 필요한 패키지를 설치합니다...
    pip install -r webapp\requirements.txt
    echo.
)

:: 서버 시작
echo [시작] http://localhost:8000
echo [토큰] claude-hub-2026
echo [중지] Ctrl+C
echo.
python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000 --reload --reload-dir webapp

pause
