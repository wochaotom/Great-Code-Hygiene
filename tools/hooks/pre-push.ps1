$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

function Invoke-Checked {
    param([string[]] $Command)
    Write-Host "> $($Command -join ' ')"
    & $Command[0] @($Command[1..($Command.Count - 1)])
    if ($LASTEXITCODE -ne 0) {
        throw "command failed: $($Command -join ' ')"
    }
}

Invoke-Checked @("git", "diff", "--check")
Invoke-Checked @(
    "python",
    "code-hygiene-compounder/scripts/source_audit_plan.py",
    "--skill-root",
    "code-hygiene-compounder",
    "--context-index",
    "--out",
    "code-hygiene-compounder/references/context-index.json",
    "--check"
)
Invoke-Checked @("python", "code-hygiene-compounder/scripts/validate_package.py", "--repo-root", ".")
Invoke-Checked @("python", "code-hygiene-compounder/scripts/guardrail_check.py", "--skill-root", "code-hygiene-compounder")
Invoke-Checked @("python", "code-hygiene-compounder/scripts/pass100_runner.py", "list", "--suite", "code-hygiene-compounder/references/eval-prompts.md")
Invoke-Checked @("python", "code-hygiene-compounder/scripts/fixture_runner.py", "--fixtures", "code-hygiene-compounder/fixtures", "validate", "--suite", "code-hygiene-compounder/references/eval-prompts.md")
Invoke-Checked @("python", "code-hygiene-compounder/scripts/fixture_runner.py", "--fixtures", "code-hygiene-compounder/fixtures", "baseline")
