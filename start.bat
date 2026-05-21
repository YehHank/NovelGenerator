@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   NovelGenerator - 無限疊代小說生成器
echo ========================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo [INFO] 未找到 .env，從 .env.example 複製...
    copy .env.example .env
    echo [INFO] 請編輯 .env 設定你的 LLM 端點和 API Key
    echo.
)

REM Create data directory
if not exist "data" mkdir data

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 找不到 Python，請先安裝 Python 3.10+
    pause
    exit /b 1
)

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] 偵測到 .venv，啟用虛擬環境...
    call .venv\Scripts\activate.bat
) else (
    echo [INFO] 未偵測到 .venv，使用系統 Python
)

REM Install Python dependencies
echo [1/4] 安裝 Python 依賴...
pip install -r requirements.txt -q

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 找不到 Node.js，請先安裝 Node.js 18+
    pause
    exit /b 1
)

REM Install frontend dependencies
echo [2/4] 安裝前端依賴...
cd frontend
call npm install --silent
echo [3/4] 建構前端...
call npm run build
cd ..

REM Start backend (serves frontend from dist/)
echo [4/4] 啟動伺服器...
echo.
echo   開啟瀏覽器前往 http://127.0.0.1:8000
echo   按 Ctrl+C 停止伺服器
echo.
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
