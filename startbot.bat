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
curl -sf http://localhost:11434/ >nul 2>&1
if not errorlevel 1 (
    echo Ollama already running -- OK.
    goto :ollama_ready
)

echo Starting Ollama...
start /b "" ollama serve >> "%TEMP%\ollama.log" 2>&1
echo Waiting for Ollama to be ready...
set /a i=0

:wait_loop
set /a i+=1
curl -sf http://localhost:11434/ >nul 2>&1
if not errorlevel 1 goto :ollama_started
if %i% geq 15 goto :ollama_failed
echo   Waiting... (%i%/15)
timeout /t 2 /nobreak >nul
goto :wait_loop

:ollama_failed
echo ERROR: Ollama did not start in time. Check %TEMP%\ollama.log for details.
pause
exit /b 1

:ollama_started
echo Ollama started -- OK.

:ollama_ready

:: ── Activate venv and start FastAPI ──────────────────────────
echo Starting FastAPI on http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo.
call venv\Scripts\activate
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload

endlocal
