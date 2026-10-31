@echo off
echo ==============================================================================
echo Project ByteClass: Launching Full System (Backend + Web Client)
echo ==============================================================================
echo 1. Starting Backend Server on http://127.0.0.1:8000
start "ByteClass Backend" cmd /k ".\venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload"

echo 2. Starting Frontend Web Client on http://127.0.0.1:5173
start "ByteClass Web Client" cmd /k "cd client && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo Both services are now running!
echo Open your browser to: http://127.0.0.1:5173
echo.
timeout /t 3 >nul
start http://127.0.0.1:5173
