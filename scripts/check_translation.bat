@echo off
cd /d "%~dp0\.."
if "%~1"=="" (
  echo Usage: scripts\check_translation.bat original.nds
  exit /b 1
)
uv run python tools\check_translation.py "%~1"
