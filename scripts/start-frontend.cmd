@echo off
setlocal
cd /d "%~dp0..\frontend"
if not exist ".env.local" copy ".env.local.example" ".env.local" >nul
if not exist "node_modules" call npm.cmd install
call npm.cmd run dev
endlocal
