@echo off
REM Startup script for TrialSync ETL Web Server (Windows)

echo Starting TrialSync ETL Web Server...

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Dependencies not installed. Installing...
    pip install -r requirements.txt
)

REM Check if .env file exists
if not exist ".env" (
    echo Warning: .env file not found.
    if exist ".env.example" (
        echo Please copy .env.example to .env and configure it.
    )
)

REM Start the server
echo Starting server on http://localhost:8000
echo Web UI: http://localhost:8000/ui
echo API Docs: http://localhost:8000/docs
echo Press Ctrl+C to stop
echo.

uvicorn src.web.api:app --reload --host 0.0.0.0 --port 8000

