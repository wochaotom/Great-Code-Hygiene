$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$gitDir = Join-Path $repoRoot ".git"
$hooksDir = Join-Path $gitDir "hooks"

if (-not (Test-Path $gitDir -PathType Container)) {
    throw "not a git repository root: $repoRoot"
}

New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null

$preCommit = @'
#!/bin/sh
powershell -NoProfile -ExecutionPolicy Bypass -File tools/hooks/pre-commit.ps1
'@

$prePush = @'
#!/bin/sh
powershell -NoProfile -ExecutionPolicy Bypass -File tools/hooks/pre-push.ps1
'@

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path $hooksDir "pre-commit"), $preCommit, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $hooksDir "pre-push"), $prePush, $utf8NoBom)

Write-Host "Installed local hooks into $hooksDir"
