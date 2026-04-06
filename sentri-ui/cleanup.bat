@echo off
echo ==========================================
echo SENTRI DATA CLEANUP UTILITY
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "app.py" (
    echo ERROR: This doesn't appear to be the Sentri project directory
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

echo Choose cleanup option:
echo.
echo [1] Interactive cleanup (recommended)
echo [2] Quick cleanup (immediate, no confirmation)
echo [3] Cancel
echo.

set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" (
    echo.
    echo Starting interactive cleanup...
    python clear_data.py
) else if "%choice%"=="2" (
    echo.
    echo WARNING: This will immediately delete all data!
    set /p confirm="Type 'YES' to proceed: "
    if /i "!confirm!"=="YES" (
        python quick_clear_data.py --force
    ) else (
        echo Operation cancelled
    )
) else if "%choice%"=="3" (
    echo Operation cancelled
) else (
    echo Invalid choice
)

echo.
pause