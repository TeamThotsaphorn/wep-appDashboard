@echo off
rem Re-export MongoDB data for the web app (docs/data) and push it to GitHub Pages.
cd /d "%~dp0"
".venv\Scripts\python.exe" -X utf8 src\11_export_web_data.py || exit /b 1
git add docs/data
git diff --cached --quiet && (echo No data changes. & exit /b 0)
git commit -m "Update web data snapshot" || exit /b 1
git push
