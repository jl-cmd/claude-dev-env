@echo off
setlocal
for /f "delims=" %%P in ('pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0caller-window-pid.ps1"') do set CALLER_PID=%%P
if "%CALLER_PID%"=="" (
    echo [cursor-agents-continue-caller] Failed to resolve caller PID.
    exit /b 1
)
call "%~dp0cursor-agents-continue.cmd" %CALLER_PID% --start-on
endlocal
