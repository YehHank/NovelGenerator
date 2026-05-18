@echo off
echo ========================================
echo   NovelGenerator - 開發模式
echo ========================================
echo.
echo   後端: http://127.0.0.1:8000
echo   前端: http://127.0.0.1:5173 (有 HMR)
echo.

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Start backend
start "NovelGenerator Backend" cmd /c "cd /d %~dp0 && if exist .venv\Scripts\activate.bat (call .venv\Scripts\activate.bat) && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

REM Start frontend dev server
cd frontend
call npm run dev
