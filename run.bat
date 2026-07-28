@echo off
chcp 65001 >nul 2>&1
title PDF Translator

echo Starting PDF Translator...
echo Opening http://localhost:5000 in your browser...

REM Open browser automatically after 2 seconds delay
start "" cmd /c "timeout /t 2 >nul && start http://localhost:5000"

REM Run python app
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe app.py
) else (
    python app.py
)

pause
