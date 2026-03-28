@echo off
REM Double-click this file (or run from this folder) so Flask starts in the right directory.
cd /d "%~dp0"
echo.
echo Starting Abjad app from: %CD%
echo Open: http://127.0.0.1:5050/category-page
echo.
python app.py
pause
