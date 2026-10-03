@echo off
setlocal
REM Execute scripts\chromakey.py using python or py
set "SCRIPT_DIR=%~dp0..\scripts\chromakey.py"

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "%SCRIPT_DIR%" %*
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py "%SCRIPT_DIR%" %*
    exit /b %ERRORLEVEL%
)

echo [ERROR] Python not found on PATH. Please install Python 3.10+ >&2
exit /b 1
