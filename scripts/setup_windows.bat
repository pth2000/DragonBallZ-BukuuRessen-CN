@echo off
cd /d "%~dp0\.."
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is required: https://docs.astral.sh/uv/getting-started/installation/
  exit /b 1
)
uv sync --frozen
if errorlevel 1 exit /b %errorlevel%
echo.
echo Environment ready. Run: uv run python tools\fetch_fonts.py
