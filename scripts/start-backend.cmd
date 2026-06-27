@echo off
setlocal
cd /d "%~dp0..\backend"
if not exist ".env" copy ".env.example" ".env" >nul
uv run uvicorn foundry.main:app --reload
endlocal
