$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python 3.11+ is required. Install it from https://www.python.org/downloads/windows/"
    exit 1
}

$PythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
& $PythonCmd --version
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "FlowGuard check complete. No external Python packages are required."
Write-Host "Optional local AI: install Ollama, then run: ollama pull qwen3.5:4b"
Write-Host "Start the app with: .\run_flowguard.ps1"
