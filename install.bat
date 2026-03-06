@echo off
echo ============================================
echo   Dashboard123 - Installation
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo.
    echo Please install Python 3.10 or later from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, check the box that says
    echo   "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

:: Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)
echo.

:: Activate venv and install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo.
echo [OK] All dependencies installed.
echo.

:: Set up .env file
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [OK] Created .env file from template.
        echo.
        echo ============================================
        echo   NEXT STEP: Configure your P123 API keys
        echo ============================================
        echo.
        echo Open the .env file in a text editor and replace
        echo the placeholder values with your Portfolio123
        echo API credentials:
        echo.
        echo   P123_API_ID=your_actual_api_id
        echo   P123_API_KEY=your_actual_api_key
        echo.
        echo You can find your API keys at:
        echo   https://www.portfolio123.com/sv/account-settings/dataminer-api
        echo.
    )
) else (
    echo [OK] .env file already exists.
)

echo ============================================
echo   Installation complete!
echo ============================================
echo.
echo To start Dashboard123, run:
echo   run.bat
echo.
pause
