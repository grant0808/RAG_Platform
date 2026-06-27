@echo off
setlocal
cd /d "%~dp0.."
echo == Backend tests ==
cd backend
uv run pytest
if errorlevel 1 exit /b %errorlevel%
uv run ruff check src tests
if errorlevel 1 exit /b %errorlevel%
echo == Frontend checks ==
cd ..\frontend
call npm.cmd run lint
if errorlevel 1 exit /b %errorlevel%
call npm.cmd run build
if errorlevel 1 exit /b %errorlevel%
endlocal
