@echo off
REM Telegram Multi Account Broadcaster - Windows Startup Script
REM This script creates a virtual environment, installs dependencies, and starts the application

echo ========================================
echo Telegram Multi Account Broadcaster
echo Starting Application...
echo ========================================

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Python is not installed or not in PATH
        echo Please install Python 3.12+ from https://www.python.org/
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo Installing dependencies...
pip install -q --upgrade pip
pip install -q -r requirements.txt

if errorlevel 1 (
    echo Error installing dependencies
    pause
    exit /b 1
)

REM Create necessary directories
if not exist "app/sessions" mkdir app/sessions
if not exist "app/logs" mkdir app/logs
if not exist "app/database" mkdir app/database
if not exist "app/static/uploads" mkdir app/static/uploads

REM Initialize database
echo Initializing database...
python -c "from app.models import init_db; init_db()"

echo.
echo ========================================
echo Starting Flask Application...
echo ========================================
echo.
echo Application will open in your browser shortly...
echo Press Ctrl+C to stop the server
echo.

REM Start Flask application
python app.py

pause
