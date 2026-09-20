@echo off
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0pstack-command-shim.ps1" watch-pr %*
exit /b %ERRORLEVEL%
