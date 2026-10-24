@echo off
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0dudu.py" %*
) else (
  python "%~dp0dudu.py" %*
)
