@echo off
rem Fetch Open-Meteo forecasts into MongoDB (weather_forcasting). Extra args are passed through, e.g. --dry-run
cd /d "%~dp0"
if not exist logs mkdir logs
".venv\Scripts\python.exe" -X utf8 src\09_fetch_forecast.py %* >> logs\fetch_forecast.log 2>&1
