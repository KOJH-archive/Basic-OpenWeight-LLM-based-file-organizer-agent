$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir
$Python = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
& $Python -m unittest discover -s tests -v
exit $LASTEXITCODE
