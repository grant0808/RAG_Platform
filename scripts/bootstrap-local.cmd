@echo off
setlocal
cd /d "%~dp0..\backend"
if not exist ".env" copy ".env.example" ".env" >nul
uv sync
uv run foundry-local bootstrap
endlocal
