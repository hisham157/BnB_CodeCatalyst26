@echo off
setlocal
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo Backend environment is missing. Follow the setup instructions in README.md.
  exit /b 1
)
"%~dp0backend\.venv\Scripts\python.exe" "%~dp0backend\run.py" %*
exit /b %errorlevel%
