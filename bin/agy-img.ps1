# agy-img - headless image gen via agy (generate_image / Nano Banana)
# Success: exit 0; last stdout line IMAGE_PATH: <absolute path>
# Failure: non-zero; reason on stderr
# NOTE: no param() block — PowerShell would eat --ref as a named parameter.
$ErrorActionPreference = 'Stop'
function Write-Err([string]$m) { [Console]::Error.WriteLine($m) }

function Show-Help {
  @(
    'agy-img - headless image gen via agy (generate_image / Nano Banana)'
    ''
    'Usage:'
    '  agy-img "prompt" -o <path> [--ref <img> ...] [--ratio 1:1|16:9|9:16|4:3|3:4|2:3|3:2] [--name <slug>] [--chromakey green|magenta] [--canvas <N>]'
    ''
    'Options:'
    '  -o, --output <path>        Output image path (required)'
    '  --ref <path>               Reference image for img2img / style / edit (repeatable)'
    '  --ratio <ratio>            Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2 (default: 1:1)'
    '  --name <slug>              Base filename hint'
    '  -k, --chromakey <color>    Optional post-process chromakey cutout: green or magenta'
    '  --canvas <N>               Square canvas size in pixels when using --chromakey (e.g. 64, 96, 128, 256)'
    '  --model <model>            Driver model for agy (default: gemini-3.8-flash-low)'
    '  --timeout <sec>            Timeout in seconds (default: 180)'
    ''
    'Env:'
    '  AGY_IMG_MODEL              driver model (default: gemini-3.8-flash-low)'
    '  AGY_IMG_TIMEOUT            timeout seconds (default: 180)'
    '  AGY_IMG_LOCK_WAIT          seconds to wait for single-instance lock (default: 60)'
    '  AGY_IMG_AGY                path to agy.exe (optional)'
    ''
    'Notes:'
    '  --ref may repeat; paths must exist (exit 64 if missing).'
    '  Driver model only schedules; drawing uses agy native generate_image.'
    '  Includes orphan lock auto-recovery and 1 auto-retry on recoverable failures.'
  ) | ForEach-Object { Write-Output $_ }
}

$argv = [System.Collections.Generic.List[string]]::new()
foreach ($a in $args) { [void]$argv.Add([string]$a) }

if ($argv.Count -eq 0 -or $argv[0] -in @('-h', '--help', '/?', '-Help', '-help')) {
  Show-Help
  exit 0
}

function Take-Flag([string]$long, [string]$short) {
  for ($i = 0; $i -lt $argv.Count; $i++) {
    $a = $argv[$i]
    if ($a -eq $long -or ($short -and ($a -eq $short -or $a -eq "-$short"))) {
      if ($i + 1 -ge $argv.Count) { throw "flag $a requires a value" }
      $v = $argv[$i + 1]
      $argv.RemoveAt($i + 1); $argv.RemoveAt($i)
      return $v
    }
    if ($a.StartsWith("$long=")) {
      $v = $a.Substring($long.Length + 1)
      $argv.RemoveAt($i)
      return $v
    }
  }
  return $null
}

$Prompt = $null
$Output = $null
$Ratio = '1:1'
$Name = $null
$Chromakey = $null
$Canvas = $null
$Model = $(if ($env:AGY_IMG_MODEL) { $env:AGY_IMG_MODEL } else { 'gemini-3.8-flash-low' })
$TimeoutSec = $(if ($env:AGY_IMG_TIMEOUT) { [int]$env:AGY_IMG_TIMEOUT } else { 180 })
$RefPaths = [System.Collections.Generic.List[string]]::new()

try {
  $o2 = Take-Flag '--output' 'o'; if ($o2) { $Output = $o2 }
  $r2 = Take-Flag '--ratio' $null; if ($r2) { $Ratio = $r2 }
  $n2 = Take-Flag '--name' $null; if ($n2) { $Name = $n2 }
  $m2 = Take-Flag '--model' $null; if ($m2) { $Model = $m2 }
  $t2 = Take-Flag '--timeout' $null; if ($t2) { $TimeoutSec = [int]$t2 }
  $k2 = Take-Flag '--chromakey' 'k'; if ($k2) { $Chromakey = $k2.ToLowerInvariant() }
  $c2 = Take-Flag '--canvas' $null
  if ($c2) {
    if ($c2 -notmatch '^\d+$' -or [int]$c2 -le 0) {
      throw "--canvas must be a positive integer, got '$c2'"
    }
    $Canvas = [int]$c2
  }
  while ($true) {
    $rf = Take-Flag '--ref' $null
    if (-not $rf) { break }
    [void]$RefPaths.Add($rf)
  }
} catch {
  Write-Err "error: $($_.Exception.Message)"; exit 64
}

# first remaining positional = prompt; reject unknown flags
$positionals = [System.Collections.Generic.List[string]]::new()
foreach ($a in @($argv)) {
  if ($a -like '-*') {
    Write-Err "error: unknown flag: $a"
    exit 64
  }
  [void]$positionals.Add($a)
}
if ($positionals.Count -gt 0) {
  $Prompt = ($positionals -join ' ').Trim()
}

if (-not $Prompt) {
  Write-Err 'error: prompt required. Example: agy-img "a red cube" -o .\out.png'
  exit 64
}
if (-not $Output) {
  Write-Err 'error: -o / --output path required'
  exit 64
}
$validRatios = @('1:1', '16:9', '9:16', '4:3', '3:4', '2:3', '3:2')
if ($Ratio -notin $validRatios) {
  Write-Err "error: invalid --ratio '$Ratio' (use $($validRatios -join '|'))"
  exit 64
}
if ($Chromakey -and ($Chromakey -notin @('green', 'magenta'))) {
  Write-Err "error: invalid --chromakey '$Chromakey' (must be 'green' or 'magenta')"
  exit 64
}

$ResolvedRefs = [System.Collections.Generic.List[string]]::new()
foreach ($rp in $RefPaths) {
  if ([string]::IsNullOrWhiteSpace($rp)) {
    Write-Err 'error: --ref requires a non-empty path'
    exit 64
  }
  try {
    $abs = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($rp)
  } catch {
    Write-Err "error: --ref path invalid: $rp"
    exit 64
  }
  if (-not (Test-Path -LiteralPath $abs -PathType Leaf)) {
    Write-Err "error: --ref file not found: $abs"
    exit 64
  }
  [void]$ResolvedRefs.Add((Resolve-Path -LiteralPath $abs).Path)
}

$agy = $env:AGY_IMG_AGY
if (-not $agy) {
  $cmd = Get-Command agy -ErrorAction SilentlyContinue
  if ($cmd) { $agy = $cmd.Source }
}
if (-not $agy -or -not (Test-Path -LiteralPath $agy)) {
  $fallback = Join-Path $env:LOCALAPPDATA 'agy\bin\agy.exe'
  if (Test-Path -LiteralPath $fallback) { $agy = $fallback }
}
if (-not $agy -or -not (Test-Path -LiteralPath $agy)) {
  Write-Err 'error: agy not installed (agy.exe not on PATH). Install Antigravity CLI first.'
  exit 127
}

$authOk = $false
if ($env:ANTIGRAVITY_API_KEY) { $authOk = $true }
elseif (Test-Path (Join-Path $env:USERPROFILE '.gemini\antigravity-cli')) { $authOk = $true }
elseif (Test-Path (Join-Path $env:USERPROFILE '.gemini\oauth_creds.json')) { $authOk = $true }
if (-not $authOk) {
  Write-Err 'error: agy not logged in. Run `agy` once interactively, or set ANTIGRAVITY_API_KEY.'
  exit 1
}

$outRequested = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
$outDir = Split-Path -Parent $outRequested
if (-not $outDir) { $outDir = (Get-Location).Path; $outRequested = Join-Path $outDir $Output }
if (-not (Test-Path -LiteralPath $outDir)) {
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$AddDirs = [System.Collections.Generic.List[string]]::new()
[void]$AddDirs.Add($outDir)
foreach ($rr in $ResolvedRefs) {
  $d = Split-Path -Parent $rr
  if ($d -and -not $AddDirs.Contains($d)) { [void]$AddDirs.Add($d) }
}

function Get-ImageKind([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { return $null }
  $fi = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
  if (-not $fi -or $fi.Length -lt 16) { return $null }
  $len = $fi.Length
  $hdr = New-Object byte[] 16
  $fs = $null
  try {
    $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $read = $fs.Read($hdr, 0, 16)
    if ($read -lt 12) { return $null }
  } catch {
    return $null
  } finally {
    if ($fs) { $fs.Dispose() }
  }

  if ($hdr[0] -eq 0x89 -and $hdr[1] -eq 0x50 -and $hdr[2] -eq 0x4E -and $hdr[3] -eq 0x47) {
    return @{ Ext = '.png'; Len = $len }
  }
  if ($hdr[0] -eq 0xFF -and $hdr[1] -eq 0xD8) {
    return @{ Ext = '.jpg'; Len = $len }
  }
  if ($hdr[0] -eq 0x52 -and $hdr[1] -eq 0x49 -and $hdr[2] -eq 0x46 -and $hdr[3] -eq 0x46 -and
      $hdr[8] -eq 0x57 -and $hdr[9] -eq 0x45 -and $hdr[10] -eq 0x42 -and $hdr[11] -eq 0x50) {
    return @{ Ext = '.webp'; Len = $len }
  }
  return $null
}

function Test-PathIsInside([string]$candidate, [string]$parentDir) {
  try {
    $targetFull = [System.IO.Path]::GetFullPath($candidate)
    $parentFull = [System.IO.Path]::GetFullPath($parentDir)
    if (-not $parentFull.EndsWith([System.IO.Path]::DirectorySeparatorChar.ToString())) {
      $parentFull += [System.IO.Path]::DirectorySeparatorChar
    }
    return $targetFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)
  } catch {
    return $false
  }
}

function Find-ImagePath([string]$text, [string]$dir) {
  $src = $null
  if ($text) {
    foreach ($line in ($text -split "`r?`n")) {
      if ($line -match '^\s*IMAGE_PATH:\s*(.+)\s*$') {
        $cand = $Matches[1].Trim().Trim('"').Trim("'")
        if ((Test-Path -LiteralPath $cand) -and (Test-PathIsInside $cand $dir)) {
          $src = $cand
          break
        }
      }
    }
    if (-not $src) {
      $matches = [regex]::Matches($text, '(?i)([A-Za-z]:\\[^\s"'']+\.(?:png|jpe?g|webp)|/[^\s"'']+\.(?:png|jpe?g|webp))')
      foreach ($m in $matches) {
        $cand = $m.Groups[1].Value
        if ((Test-Path -LiteralPath $cand) -and (Test-PathIsInside $cand $dir)) {
          $src = $cand
          break
        }
      }
    }
  }
  if ((-not $src -or -not (Test-Path -LiteralPath $src)) -and (Test-Path -LiteralPath $dir)) {
    $f = Get-ChildItem -LiteralPath $dir -File -Recurse -Include *.png,*.jpg,*.jpeg,*.webp -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) { $src = $f.FullName }
  }
  return $src
}

function Resolve-OutputPath([string]$requested, $kind) {
  $curExt = [System.IO.Path]::GetExtension($requested).ToLowerInvariant()
  $want = $kind.Ext
  $jpegOk = ($want -eq '.jpg' -and $curExt -in @('.jpg', '.jpeg'))
  if ($jpegOk -or ($curExt -eq $want)) { return $requested }
  return ([System.IO.Path]::ChangeExtension($requested, $want))
}

function Invoke-AgyOnce([string]$agyPath, [string]$model, [int]$timeoutSec, [string]$promptBody, [string]$work, [string[]]$extraDirs) {
  $timeoutArg = "${timeoutSec}s"
  $addParts = New-Object System.Collections.Generic.List[string]
  [void]$addParts.Add("--add-dir `"$($work.TrimEnd('\'))`"")
  foreach ($d in ($extraDirs | Select-Object -Unique)) {
    if ($d) { [void]$addParts.Add("--add-dir `"$($d.TrimEnd('\'))`"") }
  }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $agyPath
  $psi.Arguments = "--model $model --dangerously-skip-permissions $($addParts -join ' ') --print-timeout $timeoutArg"
  $psi.UseShellExecute = $false
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $psi.WorkingDirectory = $work
  $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  [void]$proc.Start()

  # 异步读取 stdout 和 stderr，防止管道填满导致 WaitForExit 死锁
  $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
  $stderrTask = $proc.StandardError.ReadToEndAsync()

  $proc.StandardInput.Write($promptBody)
  $proc.StandardInput.Close()

  $finished = $proc.WaitForExit(($timeoutSec + 20) * 1000)
  if (-not $finished) {
    try { $proc.Kill() } catch {}
    return @{ Ok = $false; Recoverable = $true; Code = 124; Error = "agy timed out after ${timeoutSec}s"; Response = ''; Stderr = ''; Src = $null; Work = $work }
  }

  $response = $stdoutTask.GetAwaiter().GetResult()
  $stderrTxt = $stderrTask.GetAwaiter().GetResult()
  $rc = $proc.ExitCode
  $src = Find-ImagePath $response $work
  if (-not $src -or -not (Test-Path -LiteralPath $src)) {
    $msg = if ($rc -ne 0) { "agy failed (exit $rc). $($stderrTxt.Trim())" } else { 'could not parse image path from agy output (no IMAGE_PATH / no image file under work dir).' }
    $isRecoverable = ($rc -eq 0 -or $rc -eq 124)
    return @{ Ok = $false; Recoverable = $isRecoverable; Code = $(if ($rc -ne 0) { $rc } else { 2 }); Error = $msg; Response = $response; Stderr = $stderrTxt; Src = $null; Work = $work }
  }
  $kind = Get-ImageKind $src
  if (-not $kind) {
    $len = if (Test-Path -LiteralPath $src) { (Get-Item -LiteralPath $src).Length } else { 0 }
    return @{ Ok = $false; Recoverable = $true; Code = 2; Error = "resolved path is not a real image ($src, $len bytes)."; Response = $response; Stderr = $stderrTxt; Src = $src; Work = $work }
  }
  return @{ Ok = $true; Recoverable = $false; Code = 0; Error = ''; Response = $response; Stderr = $stderrTxt; Src = $src; Kind = $kind; Work = $work }
}

# --- Single instance lock with orphan-process recovery ---
$lockWait = 60
if ($env:AGY_IMG_LOCK_WAIT) { $lockWait = [int]$env:AGY_IMG_LOCK_WAIT }
$lockPath = Join-Path $env:TEMP 'agy-img.single.lock'
$lockStream = $null
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$lastLockError = ''

while ($sw.Elapsed.TotalSeconds -lt $lockWait) {
  try {
    $lockStream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $lockBytes = [System.Text.Encoding]::UTF8.GetBytes("pid=$PID ts=$(Get-Date -Format o)`n")
    $lockStream.SetLength(0)
    $lockStream.Write($lockBytes, 0, $lockBytes.Length)
    $lockStream.Flush()
    break
  } catch [System.IO.IOException] {
    $lastLockError = $_.Exception.Message
    # 尝试探查占用锁的 pid
    try {
      if (Test-Path -LiteralPath $lockPath) {
        $fsRead = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $sr = [System.IO.StreamReader]::new($fsRead)
        $content = $sr.ReadToEnd()
        $sr.Dispose()
        if ($content -match 'pid=(\d+)') {
          $holderPid = [int]$Matches[1]
          $holderProc = Get-Process -Id $holderPid -ErrorAction SilentlyContinue
          if (-not $holderProc) {
            # 持有进程已死亡，尝试清除残留锁文件
            try { [System.IO.File]::Delete($lockPath) } catch {}
          }
        }
      }
    } catch {}
    Start-Sleep -Milliseconds 300
  } catch {
    # 非并发冲突异常直接报告退出
    Write-Err "error: cannot create lock file ($lockPath): $($_.Exception.Message)"
    exit 1
  }
}

if (-not $lockStream) {
  Write-Err "error: agy-img busy (another instance holds the lock after ${lockWait}s: $lastLockError). Set AGY_IMG_LOCK_WAIT to wait longer."
  exit 75
}

try {
  $nameClause = if ($Name) { " Save the image with base name `"$Name`"." } else { '' }

  $refBlock = ''
  if ($ResolvedRefs.Count -gt 0) {
    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add('Reference images (MUST pass these absolute paths as ImagePaths / reference inputs to generate_image for img2img or edit — do NOT only describe them in text):')
    $i = 1
    foreach ($rr in $ResolvedRefs) {
      [void]$lines.Add("$i. $rr")
      $i++
    }
    [void]$lines.Add('When calling generate_image, include every listed path as image/reference inputs. Preserve subject identity and key visual traits from the references while applying the edit description below.')
    $refBlock = ($lines -join "`n") + "`n`n"
  }

  $attempt = 0
  $maxAttempts = 2
  $last = $null

  while ($attempt -lt $maxAttempts) {
    $attempt++
    $work = Join-Path $env:TEMP ('agy-img-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $work | Out-Null

    $modeLine = if ($ResolvedRefs.Count -gt 0) {
      'Use your built-in generate_image tool (Nano Banana / Imagen) in image-to-image / edit mode with the reference ImagePaths below.'
    } else {
      'Use your built-in generate_image tool (Nano Banana / Imagen) to create an image. Do not describe the image in prose instead of generating it.'
    }

    $promptBody = @"
$modeLine

$refBlock`Description / edit instruction: $Prompt
Aspect ratio: $Ratio.$nameClause
Write the output file under this absolute directory (create if needed): $work

After generate_image succeeds, you MUST end your entire reply with exactly one line in this format (no quotes, no markdown, nothing after it):
IMAGE_PATH: <absolute path to the generated image file>

The IMAGE_PATH line is required for the calling wrapper.
"@

    if ($attempt -gt 1) {
      Write-Err "retry: recoverable failure on attempt 1 ($($last.Error)); retrying once..."
      Start-Sleep -Seconds 2
    }

    $last = Invoke-AgyOnce -agyPath $agy -model $Model -timeoutSec $TimeoutSec -promptBody $promptBody -work $work -extraDirs ($AddDirs.ToArray())

    if ($last.Ok) { break }

    if ($attempt -lt $maxAttempts -and $last.Recoverable) {
      try { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue } catch {}
      continue
    }
    break
  }

  if (-not $last.Ok) {
    Write-Err ("error: " + $last.Error)
    if ($last.Stderr) { Write-Err $last.Stderr.Trim() }
    Write-Err ("debug work dir: " + $last.Work)
    exit $last.Code
  }

  $rawOutput = Resolve-OutputPath -requested $outRequested -kind $last.Kind
  try {
    Copy-Item -LiteralPath $last.Src -Destination $rawOutput -Force
  } catch {
    Write-Err "error: failed to copy image to output path: $($_.Exception.Message)"
    Write-Err ("debug work dir: " + $last.Work)
    exit 1
  }

  if ($rawOutput -ne $outRequested -and (Test-Path -LiteralPath $outRequested)) {
    try {
      $stale = Get-ImageKind $outRequested
      if (-not $stale) { Remove-Item -LiteralPath $outRequested -Force -ErrorAction SilentlyContinue }
    } catch {}
  }

  $finalImage = $rawOutput

  # Optional post-process chromakey
  if ($Chromakey) {
    $scriptDir = Split-Path -Parent $PSScriptRoot
    $chromaPy = Join-Path $scriptDir 'scripts\chromakey.py'
    if (-not (Test-Path -LiteralPath $chromaPy)) {
      $cmd = Get-Command chromakey -ErrorAction SilentlyContinue
      if ($cmd) { $chromaPy = $cmd.Source }
    }

    if (-not (Test-Path -LiteralPath $chromaPy)) {
      Write-Err "error: chromakey tool not found (scripts/chromakey.py). Cannot perform requested chromakey."
      exit 1
    }

    $pyCmd = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'py' }
    $targetPng = [System.IO.Path]::ChangeExtension($rawOutput, '.png')
    
    $pyArgs = [System.Collections.Generic.List[string]]::new()
    [void]$pyArgs.Add($chromaPy)
    [void]$pyArgs.Add($rawOutput)
    [void]$pyArgs.Add('-o')
    [void]$pyArgs.Add($targetPng)
    [void]$pyArgs.Add('--bg')
    [void]$pyArgs.Add($Chromakey)
    if ($Canvas) {
      [void]$pyArgs.Add('--canvas')
      [void]$pyArgs.Add($Canvas.ToString())
    }

    $chromaRes = & $pyCmd @pyArgs 2>&1
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $targetPng)) {
      Write-Err "error: chromakey post-processing failed (exit code $LASTEXITCODE):"
      Write-Err ($chromaRes -join "`n")
      exit $(if ($LASTEXITCODE -ne 0) { $LASTEXITCODE } else { 1 })
    }

    $finalImage = $targetPng
  }

  $clean = ($last.Response -split "`r?`n" | Where-Object { $_ -notmatch '^\s*IMAGE_PATH:\s*' }) -join "`n"
  if ($clean.Trim()) { Write-Output $clean.TrimEnd() }
  Write-Output ("IMAGE_PATH: " + $finalImage)

  try { Remove-Item -LiteralPath $last.Work -Recurse -Force -ErrorAction SilentlyContinue } catch {}
  exit 0
}
finally {
  if ($lockStream) {
    try { $lockStream.Close() } catch {}
    try { $lockStream.Dispose() } catch {}
  }
}
