@echo off
echo ==============================================================================
echo Project ByteClass: Launching Edge Web Client (Vite + React PWA)
echo ==============================================================================
echo Web Client URL: http://127.0.0.1:5173
echo.
cd client
npm run dev -- --host 127.0.0.1 --port 5173
pause
