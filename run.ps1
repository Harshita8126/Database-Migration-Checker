# PowerShell launcher for Migration Safety Checker

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " PostgreSQL Database Migration Safety Checker" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# Detect Python Environment
$customVenv = "C:\Users\harsh\OneDrive\Desktop\migration_datasest\venv\Scripts\python.exe"
if (Test-Path $customVenv) {
    $pythonExe = $customVenv
} else {
    $pythonExe = "python"
}

Write-Host "`nUsing Python binary: $pythonExe" -ForegroundColor Yellow

Write-Host "`n[1/2] Starting FastAPI Backend on http://localhost:8000..." -ForegroundColor Cyan
Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" -WindowStyle Minimized

Start-Sleep -Seconds 2

Write-Host "[2/2] Launching Streamlit Dashboard on http://localhost:8501..." -ForegroundColor Green
& $pythonExe -m streamlit run frontend/app.py
