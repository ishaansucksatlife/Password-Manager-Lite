@echo off
echo Starting Password Manager...
echo.

call password\Scripts\activate.bat

if errorlevel 1 (
    echo Failed to activate virtual environment.
    echo Make sure the environment "password" exists in the root folder.
    pause
    exit /b 1
)

python main.py
pause