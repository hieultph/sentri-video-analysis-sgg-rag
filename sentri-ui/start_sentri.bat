@echo off
REM Sentri System Startup Script
REM Run this to start the Sentri camera monitoring system

echo ================================================
echo           SENTRI SYSTEM STARTUP
echo ================================================
echo.

REM Activate conda environment
echo [1/4] Activating conda environment 'agno-env'...
call conda activate agno-env
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate conda environment 'agno-env'
    echo Please ensure conda is installed and 'agno-env' environment exists
    echo Create environment with: conda create -n agno-env python=3.10
    pause
    exit /b 1
)
echo.

echo [2/4] Checking Python installation...
python --version
echo.

REM Check if bcrypt is installed
echo [3/4] Checking bcrypt installation...
python -c "import bcrypt" >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: bcrypt not installed. Installing now...
    pip install bcrypt
    echo.
)

REM Initialize database if needed
echo [4/4] Initializing database...
python db_setup.py
if %errorlevel% neq 0 (
    echo ERROR: Database initialization failed
    pause
    exit /b 1
)
echo.

echo ================================================
echo        STARTING SENTRI SERVER
echo ================================================
echo.
echo Server will start on: http://localhost:7777
echo.
echo Open your browser and navigate to:
echo   http://localhost:7777/static/register.html
echo.
echo Press Ctrl+C to stop the server
echo ================================================
echo.

REM Start the server
python app.py

pause
