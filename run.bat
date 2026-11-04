@echo off
REM Starts the S1-mini service on port 9220 (syncs .venv with uv on each run). The first start downloads the weights (about 1.5 GB).
REM LABEL: S1-mini Service
REM DESCRIPTION: Shared HTTP service that runs S1-mini on the CPU for every project.

cd /d "%~dp0"

uv sync
if errorlevel 1 (
    echo uv sync failed. Install uv: winget install astral-sh.uv
    pause
    exit /b 1
)
call .venv\Scripts\activate

python src/app.py
pause
