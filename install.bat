@echo off
setlocal

if not exist "env\Scripts\python.exe" (
    python -m venv env
)

"env\Scripts\python.exe" -m pip install -r requirements.txt

pause
