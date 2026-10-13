@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "FlowGuard" pythonw -m flowguard
) else (
  start "FlowGuard" python -m flowguard
)
