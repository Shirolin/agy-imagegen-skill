@echo off
setlocal
REM Execute scripts\engine.py using python or py directly (Thin Adapter)
set "SCRIPT_PATH=%~dp0..\scripts\engine.py"

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "%SCRIPT_PATH%" %*
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py "%SCRIPT_PATH%" %*
    exit /b %ERRORLEVEL%
)

echo [ERROR] Python not found on PATH. Please install Python 3.10+ >&2
exit /b 1
