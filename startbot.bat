@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo  AI Friend -- Starting
echo ============================================================
echo.

:: ── Check Ollama is running ───────────────────────────────────
echo Checking Ollama service...
tasklist /fi "imagename eq ollama.exe" 2>nul | findstr /i "ollama.exe" >nul
if errorlevel 1 (
    echo Starting Ollama...
    start /b ollama serve
    timeout /t 3 /nobreak >nul
) else (
    echo Ollama already running -- OK.
)

:: ── Activate venv and start FastAPI ──────────────────────────
echo Starting FastAPI on http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo.
call venv\Scripts\activate
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload

endlocal
