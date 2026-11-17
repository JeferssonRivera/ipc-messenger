@echo off
REM IPC Messenger - Universidad Simon Bolivar
cd /d "%~dp0"
py -m pip install -r requirements.txt --quiet 2>nul || python -m pip install -r requirements.txt --quiet
py main.py 2>nul || python main.py
pause
