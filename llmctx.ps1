#!/usr/bin/env pwsh
# llmctx.ps1 — Windows convenience wrapper around llmctx.py.
# Finds a Python interpreter and forwards all arguments to llmctx.py.
#
#   .\llmctx.ps1                     # current dir -> context.md
#   .\llmctx.ps1 C:\dev\app app.md   # a project   -> app.md
#   .\llmctx.ps1 . --redact

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'llmctx.py'

if (-not (Test-Path $script)) {
    Write-Error "llmctx.py not found next to this script ($script)."
    exit 1
}

$python = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}

if (-not $python) {
    Write-Error @'
Python 3.8+ was not found on PATH.
Install it from https://www.python.org/downloads/ or the Microsoft Store,
then re-run this script.
'@
    exit 1
}

& $python $script @args
exit $LASTEXITCODE
