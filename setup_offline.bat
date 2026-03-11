@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ============================================================
echo  AI Friend -- Offline Setup
echo  Python 3.10  ^|  CUDA 12.1  ^|  RTX 3050
echo ============================================================
echo.

:: ─────────────────────────────────────────────────────────────
:: Verified version matrix  (all constraints checked)
::
::  torch            2.4.1+cu121   CUDA 12.1; satisfies diffusers torch>=2.4 req
::  torchvision      0.19.1+cu121  must match torch 2.4.1
::  torchaudio       2.4.1+cu121   must match torch 2.4.1
::  diffusers        0.29.2        dropped cached_download; escapes hub version gap
::  huggingface_hub  0.24.6        has is_offline_mode (transformers 4.43 needs it);
::                                 no cached_download (diffusers 0.29 no longer uses it)
::  transformers     4.43.4        needs hub>=0.23.2 -- 0.24.6 satisfies this
::  tokenizers       0.19.1        transformers 4.43.x needs >=0.19
::  safetensors      0.4.3         transformers 4.43.x needs >=0.4.1
::  accelerate       0.32.1        diffusers 0.29 needs >=0.26.0; aligns with torch 2.4
::  numpy            1.26.4        torch 2.4.x hard-requires numpy<2.0
::  pillow           10.3.0        no conflicts
::  fastapi          0.111.0       pydantic v2 compatible
::  uvicorn          0.29.0        matches fastapi 0.111
::  pydantic         2.7.1         fastapi 0.111 fully supports v2
::  requests         2.31.0        no conflicts
::  python-dotenv    1.0.1         no conflicts
::
::  Models:
::  SD model : Realistic_Vision_V6.0_B1_noVAE  (~2 GB, photorealistic)
::             noVAE edition REQUIRES external VAE for proper faces
::  VAE      : stabilityai/sd-vae-ft-mse  (~335 MB)
::             fixes blurry/distorted faces -- biggest face quality fix
::  LLM      : llama3:latest
::             must use full tag -- plain "llama3" causes 500 errors
:: ─────────────────────────────────────────────────────────────

set OLLAMA_MODEL=llama3:latest
set SD_MODEL_ID=SG161222/Realistic_Vision_V6.0_B1_noVAE
set SD_MODEL_PATH=models\realistic
set VAE_MODEL_ID=stabilityai/sd-vae-ft-mse
set VAE_MODEL_PATH=models\vae

:: ─────────────────────────────────────────────
:: Step 1 -- Check Python 3.10
:: ─────────────────────────────────────────────
echo [Step 1] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.10 from https://www.python.org/downloads/release/python-3100/
    echo Tick "Add Python to PATH" during install.
    pause & exit /b 1
)
for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set PY_VER=%%a
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do set PY_MAJOR_MINOR=%%a.%%b
if "%PY_MAJOR_MINOR%" neq "3.10" (
    echo ERROR: Python 3.10.x required, found %PY_VER%.
    echo Download from https://www.python.org/downloads/release/python-3100/
    pause & exit /b 1
)
echo Python %PY_VER% -- OK

:: ─────────────────────────────────────────────
:: Step 2 -- Virtual environment
:: ─────────────────────────────────────────────
echo.
echo [Step 2] Setting up virtual environment...
if not exist venv (
    python -m venv venv
    if errorlevel 1 ( echo ERROR: venv creation failed. & pause & exit /b 1 )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists -- skipping.
)
call venv\Scripts\activate
if errorlevel 1 ( echo ERROR: Could not activate venv. & pause & exit /b 1 )

:: ─────────────────────────────────────────────
:: Step 3 -- Upgrade pip + build tools
:: ─────────────────────────────────────────────
echo.
echo [Step 3] Upgrading pip and build tools...
python -m pip install --upgrade pip setuptools wheel --quiet
echo Done.

:: ─────────────────────────────────────────────
:: Step 4 -- Wipe previously installed conflicting
::           packages so pip cannot reuse cached
::           broken/mismatched versions.
::           Safe to run even on a fresh venv.
:: ─────────────────────────────────────────────
echo.
echo [Step 4] Removing any conflicting existing packages...
pip uninstall torch torchvision torchaudio ^
    diffusers transformers huggingface_hub ^
    tokenizers safetensors accelerate ^
    -y --quiet >nul 2>&1
echo Done (errors above are harmless if packages did not exist).

:: ─────────────────────────────────────────────
:: Step 5 -- PyTorch 2.4.1 + CUDA 12.1
::           Install as ONE call so torch/torchvision/
::           torchaudio versions stay in lock-step.
::           Must come before all other ML packages.
:: ─────────────────────────────────────────────
echo.
echo [Step 5] Installing PyTorch 2.4.1 (CUDA 12.1) -- ~2.5 GB...
pip install ^
    torch==2.4.1+cu121 ^
    torchvision==0.19.1+cu121 ^
    torchaudio==2.4.1+cu121 ^
    --index-url https://download.pytorch.org/whl/cu121 ^
    --quiet
if errorlevel 1 ( echo ERROR: PyTorch install failed. & pause & exit /b 1 )
echo PyTorch 2.4.1+cu121 installed.

:: ─────────────────────────────────────────────
:: Step 6 -- Verify CUDA is visible to PyTorch
:: ─────────────────────────────────────────────
echo.
echo [Step 6] Verifying CUDA...
python -c "import torch; c=torch.cuda.is_available(); print('  CUDA available :', c); print('  GPU            :', torch.cuda.get_device_name(0) if c else 'None -- will fall back to CPU'); print('  Torch version  :', torch.__version__)"
if errorlevel 1 ( echo WARNING: CUDA check failed -- server will use CPU mode. )

:: ─────────────────────────────────────────────
:: Step 7 -- ML dependencies
::           ORDER IS CRITICAL:
::             numpy/pillow     -- no upstream ML deps
::             huggingface_hub  -- must be pinned BEFORE transformers/diffusers
::                                 so pip cannot pull a newer incompatible version
::             tokenizers       -- transformers hard dep, must precede transformers
::             safetensors      -- transformers hard dep, must precede transformers
::             transformers     -- must precede diffusers
::             accelerate       -- must precede diffusers
::             diffusers        -- installed last, all deps already satisfied
:: ─────────────────────────────────────────────
echo.
echo [Step 7] Installing ML dependencies (strict order)...

echo   [7a] numpy, pillow...
pip install numpy==1.26.4 pillow==10.3.0 --quiet
if errorlevel 1 ( echo ERROR: numpy/pillow failed. & pause & exit /b 1 )

echo   [7b] huggingface_hub 0.24.6 (pinned -- do NOT upgrade)...
pip install huggingface_hub==0.24.6 --quiet
if errorlevel 1 ( echo ERROR: huggingface_hub failed. & pause & exit /b 1 )

echo   [7c] tokenizers, safetensors...
pip install tokenizers==0.19.1 safetensors==0.4.3 --quiet
if errorlevel 1 ( echo ERROR: tokenizers/safetensors failed. & pause & exit /b 1 )

echo   [7d] transformers...
pip install transformers==4.43.4 --quiet
if errorlevel 1 ( echo ERROR: transformers failed. & pause & exit /b 1 )

echo   [7e] accelerate...
pip install accelerate==0.32.1 --quiet
if errorlevel 1 ( echo ERROR: accelerate failed. & pause & exit /b 1 )

echo   [7f] diffusers...
pip install diffusers==0.29.2 --quiet
if errorlevel 1 ( echo ERROR: diffusers failed. & pause & exit /b 1 )

echo   ML dependencies installed.

:: ─────────────────────────────────────────────
:: Step 8 -- Web / API stack
:: ─────────────────────────────────────────────
echo.
echo [Step 8] Installing API dependencies...
pip install ^
    pydantic==2.7.1 ^
    fastapi==0.111.0 ^
    uvicorn==0.29.0 ^
    requests==2.31.0 ^
    python-dotenv==1.0.1 ^
    --quiet
if errorlevel 1 ( echo ERROR: API dependencies failed. & pause & exit /b 1 )
echo   API dependencies installed.

:: TTS -- uncomment when ready to wire up to an endpoint:
:: pip install TTS==0.22.0 --quiet

:: ─────────────────────────────────────────────
:: Step 9 -- Full import smoke-test
::           Catches version conflicts before
::           wasting time on model downloads.
:: ─────────────────────────────────────────────
echo.
echo [Step 9] Smoke-testing all imports...
python -c "import torch, diffusers, transformers, accelerate, huggingface_hub; import fastapi, uvicorn, dotenv; print('  torch:           ', torch.__version__); print('  diffusers:       ', diffusers.__version__); print('  transformers:    ', transformers.__version__); print('  huggingface_hub: ', huggingface_hub.__version__); print('  accelerate:      ', accelerate.__version__); print('  fastapi:         ', fastapi.__version__); c=torch.cuda.is_available(); print('  CUDA ready:      ', c); print('All imports OK.')"
if errorlevel 1 (
    echo ERROR: Import smoke-test failed -- fix errors above before continuing.
    pause & exit /b 1
)

:: ─────────────────────────────────────────────
:: Step 10 -- Ollama check
::            Uses full tag "llama3:latest" --
::            plain "llama3" causes 500 errors
::            because Ollama stores it with the tag.
:: ─────────────────────────────────────────────
echo.
echo [Step 10] Checking Ollama...

:: 1. Check if the Ollama executable is installed
where ollama >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama not found. Download from https://ollama.com/download
    pause & exit /b 1
)
echo   Ollama executable found.

:: 2. Check if the Ollama background service is actually running
ollama list >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama service is not running.
    echo Please start Ollama ^(search for it in your Start Menu or run 'ollama serve' in another terminal^) and try again.
    pause & exit /b 1
)

:: 3. Check for the specific model using the variable safely
ollama list | findstr /i /c:"%OLLAMA_MODEL%" >nul
if errorlevel 1 (
    echo Pulling "%OLLAMA_MODEL%" - requires internet and is approx 4.7 GB...
    ollama pull %OLLAMA_MODEL%
    if errorlevel 1 ( echo ERROR: Ollama pull failed. & pause & exit /b 1 )
    echo Ollama model ready.
) else (
    echo Ollama model "%OLLAMA_MODEL%" already present -- skipping.
)

:: 4. Verify Ollama API responds correctly with the full model tag
echo Verifying Ollama API...
python -c "import requests; r=requests.post('http://localhost:11434/api/generate', json={'model':'%OLLAMA_MODEL%','prompt':'hi','stream':False}, timeout=30); r.raise_for_status(); print('  Ollama API -- OK')"
if errorlevel 1 (
    echo ERROR: Ollama API test failed.
    echo Make sure the background service is running properly.
    pause & exit /b 1
)

:: ─────────────────────────────────────────────
:: Step 11 -- Realistic Vision SD model
::            noVAE edition -- requires the VAE
::            in Step 12 for proper face quality.
::            Checks model_index.json not the folder.
:: ─────────────────────────────────────────────
echo.
echo [Step 11] Checking Realistic Vision model...
if not exist "%SD_MODEL_PATH%\model_index.json" (
    echo Downloading Realistic Vision V6 to %SD_MODEL_PATH%\ - ~2 GB...
    python -c "from diffusers import StableDiffusionPipeline; pipe = StableDiffusionPipeline.from_pretrained('%SD_MODEL_ID%'); pipe.save_pretrained(r'%SD_MODEL_PATH%'); print('SD model saved.')"
    if errorlevel 1 ( echo ERROR: SD model download failed. & pause & exit /b 1 )
    echo Realistic Vision model downloaded.
) else (
    echo Realistic Vision model already present -- skipping.
)

:: ─────────────────────────────────────────────
:: Step 12 -- VAE model  *** NEW ***
::            The Realistic Vision model is the
::            noVAE edition -- it NEEDS this external
::            VAE to produce sharp, non-distorted faces.
::            Without it faces look melted/asymmetric.
::            stabilityai/sd-vae-ft-mse is the standard
::            VAE for SD 1.5 based realistic models.
::            ~335 MB download.
:: ─────────────────────────────────────────────
echo.
echo [Step 12] Checking VAE model (required for sharp faces)...
if not exist "%VAE_MODEL_PATH%\config.json" (
    echo Downloading VAE to %VAE_MODEL_PATH%\ - ~335 MB...
    python -c "from diffusers import AutoencoderKL; vae = AutoencoderKL.from_pretrained('%VAE_MODEL_ID%'); vae.save_pretrained(r'%VAE_MODEL_PATH%'); print('VAE saved.')"
    if errorlevel 1 ( echo ERROR: VAE download failed. & pause & exit /b 1 )
    echo VAE downloaded.
) else (
    echo VAE already present -- skipping.
)

:: ─────────────────────────────────────────────
:: Step 13 -- backend\.env
::            Always overwrite -- stale/missing
::            .env caused multiple errors throughout
::            development (wrong MODEL_NAME, SD_PATH).
::            Now includes VAE_PATH for face fix.
:: ─────────────────────────────────────────────
echo.
echo [Step 13] Writing backend\.env...
(
    echo BASE_URL=http://127.0.0.1:8000
    echo OLLAMA_URL=http://localhost:11434/api/generate
    echo MODEL_NAME=llama3:latest
    echo SD_PATH=models/realistic
    echo VAE_PATH=models/vae
) > backend\.env
echo backend\.env written:
type backend\.env

:: ─────────────────────────────────────────────
:: Step 14 -- ai-friend\.env  (React)
::            Only create if missing -- user may
::            have a customised API URL.
:: ─────────────────────────────────────────────
echo.
echo [Step 14] Creating ai-friend\.env...
if not exist "ai-friend\.env" (
    echo REACT_APP_API_URL=http://127.0.0.1:8000 > ai-friend\.env
    echo ai-friend\.env created.
) else (
    echo ai-friend\.env already exists -- skipping.
)

:: ─────────────────────────────────────────────
:: Step 15 -- npm install inside ai-friend\
:: ─────────────────────────────────────────────
echo.
echo [Step 15] Installing React dependencies in ai-friend\...
where npm >nul 2>&1
if errorlevel 1 (
    echo WARNING: npm not found -- skipping React install.
    echo Install Node.js 18+ from https://nodejs.org then run:
    echo   cd ai-friend ^&^& npm install ^&^& npm install @mui/icons-material
) else (
    cd ai-friend
    echo   Running npm install...
    npm install --silent
    echo   Installing MUI icons...
    npm install @mui/icons-material --silent
    cd ..
    echo   React dependencies installed.
)

:: ─────────────────────────────────────────────
:: Done
:: ─────────────────────────────────────────────
echo.
echo ============================================================
echo  Setup complete!
echo.
echo  Python packages:
echo    torch            2.4.1+cu121
echo    diffusers        0.29.2
echo    huggingface_hub  0.24.6  ^<-- do NOT pip upgrade this
echo    transformers     4.43.4
echo    accelerate       0.32.1
echo    numpy            1.26.4
echo    fastapi          0.111.0  /  uvicorn 0.29.0
echo    pydantic         2.7.1
echo.
echo  Models downloaded:
echo    LLM : llama3:latest          (Ollama)
echo    SD  : Realistic Vision V6    (models\realistic\)
echo    VAE : sd-vae-ft-mse          (models\vae\)
echo.
echo  IMPORTANT: Do NOT run "pip install --upgrade" on this venv.
echo  huggingface_hub is intentionally pinned at 0.24.6.
echo  Upgrading it will break diffusers and transformers imports.
echo.
echo  To start the app:
echo    Terminal 1:  startbot.bat
echo    Terminal 2:  cd ai-friend ^&^& npm start
echo ============================================================
pause
endlocal
