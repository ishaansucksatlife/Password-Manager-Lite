@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================================
echo     Password Manager - Setup Script
echo ==========================================================
echo.

:: --- Locate MySQL ---
set "MYSQL_CMD=C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
if not exist "!MYSQL_CMD!" (
    where mysql >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Could not find mysql.exe
        pause
        exit /b 1
    ) else (
        set "MYSQL_CMD=mysql"
    )
)
echo Using MySQL: !MYSQL_CMD!
echo.

:: --- Virtual environment ---
set /p CREATE_VENV="Create/update virtual environment? (y/n, default y): "
if "!CREATE_VENV!"=="" set CREATE_VENV=y
if /i "!CREATE_VENV!"=="y" (
    echo Creating virtual environment 'password'...
    if not exist "password\" (
        python -m venv password
    ) else (
        echo Virtual environment already exists.
    )
    echo.
)

echo Activating virtual environment...
call password\Scripts\activate

:: --- Dependencies ---
set /p INSTALL_DEPS="Install/update dependencies? (y/n, default y): "
if "!INSTALL_DEPS!"=="" set INSTALL_DEPS=y
if /i "!INSTALL_DEPS!"=="y" (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo.
)

:: --- MySQL credentials ---
echo.
echo Enter MySQL connection details:
set /p MYSQL_USER="MySQL username (default: root): "
if "!MYSQL_USER!"=="" set MYSQL_USER=root
set /p MYSQL_PASS="MySQL password for !MYSQL_USER!: "

echo.
echo Testing connection...
"!MYSQL_CMD!" -u %MYSQL_USER% -p"%MYSQL_PASS%" -e "SELECT 1;" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Connection failed. Please check credentials.
    pause
    exit /b 1
)
echo Connection successful.
echo.

:: --- Create config.json ---
(
    echo {
    echo     "host": "localhost",
    echo     "user": "%MYSQL_USER%",
    echo     "password": "%MYSQL_PASS%",
    echo     "database": "password_manager"
    echo }
) > config.json
echo [OK] config.json created.
echo.

:: --- Build SQL file (without index handling) ---
set "SQL_FILE=setup.sql"

echo( CREATE DATABASE IF NOT EXISTS password_manager; > "%SQL_FILE%"
echo( USE password_manager; >> "%SQL_FILE%"
echo( CREATE TABLE IF NOT EXISTS master ( >> "%SQL_FILE%"
echo(     id INT PRIMARY KEY DEFAULT 1, >> "%SQL_FILE%"
echo(     master_password VARCHAR(255) NOT NULL, >> "%SQL_FILE%"
echo(     pin VARCHAR(10), >> "%SQL_FILE%"
echo(     trusted_until VARCHAR(20) >> "%SQL_FILE%"
echo( ); >> "%SQL_FILE%"
echo( CREATE TABLE IF NOT EXISTS entries ( >> "%SQL_FILE%"
echo(     id INT AUTO_INCREMENT PRIMARY KEY, >> "%SQL_FILE%"
echo(     service VARCHAR(255) NOT NULL, >> "%SQL_FILE%"
echo(     username VARCHAR(255) NOT NULL, >> "%SQL_FILE%"
echo(     password TEXT NOT NULL, >> "%SQL_FILE%"
echo(     notes TEXT, >> "%SQL_FILE%"
echo(     is_favorite INT DEFAULT 0 >> "%SQL_FILE%"
echo( ); >> "%SQL_FILE%"

:: --- Remove duplicate rows (keep smallest id) ---
echo( -- Remove duplicate rows >> "%SQL_FILE%"
echo( DELETE t1 FROM entries t1 >> "%SQL_FILE%"
echo( INNER JOIN entries t2 >> "%SQL_FILE%"
echo( WHERE t1.id ^> t2.id >> "%SQL_FILE%"
echo( AND t1.service = t2.service >> "%SQL_FILE%"
echo( AND t1.username = t2.username; >> "%SQL_FILE%"

echo [OK] SQL file created: %SQL_FILE%
echo.

:: --- Run the main schema SQL ---
echo Running schema setup...
"!MYSQL_CMD!" -u %MYSQL_USER% -p"%MYSQL_PASS%" < "%SQL_FILE%"

if errorlevel 1 (
    echo [ERROR] Schema setup failed.
    echo The SQL file is available as: %SQL_FILE%
    echo You can run it manually: mysql -u %MYSQL_USER% -p < %SQL_FILE%
    pause
    exit /b 1
)

del "%SQL_FILE%" 2>nul
echo [SUCCESS] Database tables and initial data created.
echo.

:: --- Handle the unique index separately (compatible with all MySQL versions) ---
echo Adding unique index on (service, username)...
"!MYSQL_CMD!" -u %MYSQL_USER% -p"%MYSQL_PASS%" -e "ALTER TABLE password_manager.entries DROP INDEX idx_service_username;" 2>nul
"!MYSQL_CMD!" -u %MYSQL_USER% -p"%MYSQL_PASS%" -e "ALTER TABLE password_manager.entries ADD UNIQUE INDEX idx_service_username (service, username);"
if errorlevel 1 (
    echo [ERROR] Failed to create the unique index.
    pause
    exit /b 1
)
echo [OK] Unique index created.

echo.
echo ==========================================================
echo Setup completed successfully!
echo.
echo You can now run: run.bat
echo ==========================================================
pause