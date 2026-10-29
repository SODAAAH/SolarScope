Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm --prefix frontend run dev"

Write-Host "SolarScope full-stack application started." -ForegroundColor Green
Write-Host "Backend API: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "Frontend UI: http://localhost:5173" -ForegroundColor Yellow

