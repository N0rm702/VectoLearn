@echo off
echo ==============================================================================
echo Project ByteClass: Launching Backend Engine (FastAPI + LangChain)
echo ==============================================================================
echo Python Virtual Environment: .\venv\Scripts\python.exe
echo Backend URL: http://127.0.0.1:8000
echo.
.\venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
pause
