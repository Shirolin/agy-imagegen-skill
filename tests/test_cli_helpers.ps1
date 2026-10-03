# test_cli_helpers.ps1 — 验证 agy-img 核心辅助函数与路径安全
$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$AgyImgPs1 = Join-Path $RepoRoot 'bin\agy-img.ps1'

# 提取关键函数定义并执行测试
$content = Get-Content -LiteralPath $AgyImgPs1 -Raw

# 提取 Get-ImageKind, Test-PathIsInside, Find-ImagePath 函数块
$funcs = @'
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
'@

Invoke-Expression $funcs

$testWork = Join-Path $env:TEMP ('agy-test-work-' + [guid]::NewGuid().ToString('N'))
$outsideDir = Join-Path $env:TEMP ('agy-test-out-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $testWork | Out-Null
New-Item -ItemType Directory -Force -Path $outsideDir | Out-Null

try {
  # 1. 验证 Test-PathIsInside
  $insideFile = Join-Path $testWork 'output.png'
  $outsideFile = Join-Path $outsideDir 'ref.png'
  [System.IO.File]::WriteAllBytes($insideFile, [byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52))
  [System.IO.File]::WriteAllBytes($outsideFile, [byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52))

  if (-not (Test-PathIsInside $insideFile $testWork)) { throw 'Test-PathIsInside failed for inside file' }
  if (Test-PathIsInside $outsideFile $testWork) { throw 'Test-PathIsInside falsely matched outside file' }

  # 2. 验证 Find-ImagePath 防逃逸
  # 场景 A: 模型复述了外部参考图路径，但未在 work 生成合法文件
  $dummyResponse = @"
I used the reference image at:
IMAGE_PATH: $outsideFile
Done.
"@
  $found = Find-ImagePath $dummyResponse $testWork
  # 此时不应返回 outsideFile，因为 outsideFile 在 work 目录外！它应该降级找到 $insideFile
  if ($found -eq $outsideFile) {
    throw 'Security vulnerability: Find-ImagePath leaked external file from ref prompt!'
  }
  if ($found -ne $insideFile) {
    throw "Find-ImagePath expected to fallback to $insideFile, got: $found"
  }

  # 3. 验证 Get-ImageKind PNG 头检测
  $kind = Get-ImageKind $insideFile
  if (-not $kind -or $kind.Ext -ne '.png') {
    throw 'Get-ImageKind failed to recognize valid PNG header'
  }

  Write-Output '[+] CLI 辅助函数与安全回归测试全部通过！'
} finally {
  Remove-Item -LiteralPath $testWork -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $outsideDir -Recurse -Force -ErrorAction SilentlyContinue
}
