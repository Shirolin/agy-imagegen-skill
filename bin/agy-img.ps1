# agy-img.ps1 — PowerShell Thin Adapter delegating to scripts/engine.py
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnginePy = Join-Path (Split-Path -Parent $ScriptDir) 'scripts\engine.py'

function Find-Python {
    foreach ($cand in 'python', 'python3', 'py') {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            return $cand
        }
    }
    return $null
}

$Python = Find-Python
if (-not $Python) {
    [Console]::Error.WriteLine('[ERROR] Python 3.10+ is required but not found on PATH.')
    exit 1
}

& $Python $EnginePy @args
exit $LASTEXITCODE
