@echo off
cd /d "%~dp0\.."
if "%~1"=="" (
  echo Usage: scripts\build_rom.bat original.nds
  exit /b 1
)
uv run python tools\build_release.py "%~1"
