@echo off
echo ========================================================
echo  PostgreSQL Database Migration Safety Checker
echo ========================================================
echo.

set "VENV_EXE=C:\Users\harsh\OneDrive\Desktop\migration_datasest\venv\Scripts\python.exe"

if exist "%VENV_EXE%" (
    set "PY_EXE=%VENV_EXE%"
) else (
    set "PY_EXE=python"
)

echo Using Python binary: %PY_EXE%
echo.
echo [1/2] Starting FastAPI Backend on http://localhost:8000 ...
start /B "" "%PY_EXE%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

timeout /t 2 >nul

echo [2/2] Launching Streamlit Dashboard on http://localhost:8501 ...
"%PY_EXE%" -m streamlit run frontend/app.py
pause
