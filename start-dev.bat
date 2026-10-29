@echo off
setlocal

start "SolarScope Backend Server" cmd /k "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
start "SolarScope Frontend Client" cmd /k "npm --prefix frontend run dev"

echo SolarScope full-stack application started.
echo Backend API: http://127.0.0.1:8000/docs
echo Frontend UI: http://localhost:5173
echo Press any key to exit this launcher window.
pause

