@echo off
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0pstack-command-shim.ps1" ship-pr %*
exit /b %ERRORLEVEL%
