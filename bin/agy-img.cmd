@echo off
setlocal
REM Execute agy-img.ps1 with pwsh if available, fallback to powershell
where pwsh >nul 2>nul
if %ERRORLEVEL% equ 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0agy-img.ps1" %*
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0agy-img.ps1" %*
)
exit /b %ERRORLEVEL%
