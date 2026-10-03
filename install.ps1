# install.ps1 — agy-imagegen-skill entry point for Windows
#
# Usage:
#   .\install.ps1                    # Standard setup: add bin to PATH, link to ~/.gemini/config/skills/
#   .\install.ps1 -dev               # Developer mode: symlink skills
#   .\install.ps1 -uninstall         # Remove PATH entry and symlinks

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SkillRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-Python {
    foreach ($candidate in 'python', 'python3', 'py') {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
    }
    return $null
}

$Python = Find-Python
if (-not $Python) {
    [Console]::Error.WriteLine('[ERROR] Python 3.10+ is required but not found on PATH.')
    exit 1
}

$installPy = Join-Path $SkillRoot 'scripts\install.py'
& $Python $installPy @args
exit $LASTEXITCODE
