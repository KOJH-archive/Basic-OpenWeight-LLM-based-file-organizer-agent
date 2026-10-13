$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir
$Python = if (Get-Command pythonw -ErrorAction SilentlyContinue) { "pythonw" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "pyw" }
Start-Process -FilePath $Python -ArgumentList "-m", "flowguard" -WorkingDirectory $ProjectDir -WindowStyle Hidden
