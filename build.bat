@echo off
title Build CookBook2026
cd /d "%~dp0"

echo.
echo =============================================
echo   CookBook2026  ^|  ShashevPro Build
echo =============================================
echo.

set PYARMOR=C:\Users\Andrey\AppData\Local\Programs\Python\Python311\Scripts\pyarmor.exe
set PYARMOR_CC=C:\Users\Andrey\.pyarmor\clang.exe

set no_proxy=*
set NO_PROXY=*
set PIP_NO_PROXY=*

:: -------------------------------------------------------
:: venv
:: -------------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [*] Creating venv...
    python -m venv venv
    if errorlevel 1 ( echo [ERROR] Failed to create venv & pause & exit /b 1 )
)
call venv\Scripts\activate.bat

echo [*] Upgrading pip...
python -m pip install --upgrade pip --no-warn-script-location >nul 2>&1
pip install PySocks --no-warn-script-location >nul 2>&1

echo [*] Installing PyQt6...
pip install PyQt6 --no-warn-script-location
if errorlevel 1 ( echo [ERROR] PyQt6 failed & pause & exit /b 1 )

echo [*] Installing SQLAlchemy...
pip install sqlalchemy --no-warn-script-location
if errorlevel 1 ( echo [ERROR] SQLAlchemy failed & pause & exit /b 1 )

echo [*] Installing PyInstaller 6.11 (max supported by PyArmor 9.x)...
pip install "pyinstaller==6.11.0" --force-reinstall --no-warn-script-location
if errorlevel 1 ( echo [ERROR] PyInstaller 6.11 failed & pause & exit /b 1 )

echo [*] Installing PyArmor...
pip install pyarmor --no-warn-script-location
if errorlevel 1 ( echo [ERROR] PyArmor failed & pause & exit /b 1 )

echo [OK] All dependencies installed

:: -------------------------------------------------------
:: Clean ALL old artifacts including obfuscated folder
:: -------------------------------------------------------
echo [*] Cleaning old builds...
if exist "dist\CookBook2026.exe"  del /f /q "dist\CookBook2026.exe"
if exist "build"                  rmdir /s /q "build"
if exist "dist_pyarmor"           rmdir /s /q "dist_pyarmor"
if exist "CookBook2026.spec"      del /f /q "CookBook2026.spec"

:: =======================================================
:: PRE-STEP - ensure __init__.py exists in subpackages
::            PyArmor needs them to treat folders as packages
::            and preserve the directory structure in output
:: =======================================================
if not exist "database\__init__.py" (
    echo. > "database\__init__.py"
    echo [*] Created database\__init__.py
)
if not exist "gui\__init__.py" (
    echo. > "gui\__init__.py"
    echo [*] Created gui\__init__.py
)

:: =======================================================
:: STEP 1 - PyArmor BCC: obfuscate ALL .py source files
::          Output goes to dist_pyarmor/ with same structure
::          dist_pyarmor/main.py        <- obfuscated
::          dist_pyarmor/database/      <- obfuscated
::          dist_pyarmor/gui/           <- obfuscated
::          dist_pyarmor/pyarmor_runtime_XXXXX/  <- runtime
:: =======================================================
echo.
echo [1/3] PyArmor BCC obfuscation...
echo.

%PYARMOR% gen --enable-bcc -O dist_pyarmor ^
    main.py ^
    database ^
    gui

if errorlevel 1 (
    echo [ERROR] PyArmor BCC failed.
    pause & exit /b 1
)

:: Verify obfuscation produced the right files
if not exist "dist_pyarmor\main.py" (
    echo [ERROR] dist_pyarmor\main.py not found after obfuscation!
    pause & exit /b 1
)
if not exist "dist_pyarmor\database" (
    echo [ERROR] dist_pyarmor\database\ not found after obfuscation!
    pause & exit /b 1
)
if not exist "dist_pyarmor\gui" (
    echo [ERROR] dist_pyarmor\gui\ not found after obfuscation!
    pause & exit /b 1
)
echo [OK] BCC done. Obfuscated files verified in dist_pyarmor\

:: =======================================================
:: STEP 2 - Generate .spec file
::          make_spec.py points ALL app paths to dist_pyarmor/
::          so PyInstaller picks up OBFUSCATED code only
:: =======================================================
echo.
echo [2/3] Writing PyInstaller spec...
python make_spec.py
if errorlevel 1 ( echo [ERROR] make_spec.py failed & pause & exit /b 1 )

:: =======================================================
:: STEP 3 - PyInstaller builds exe from obfuscated sources
::          Runs from project ROOT (not dist_pyarmor)
::          spec uses absolute paths to dist_pyarmor/
:: =======================================================
echo.
echo [3/3] Building exe from obfuscated sources...
echo.

pyinstaller CookBook2026.spec --noconfirm

if errorlevel 1 (
    echo [ERROR] PyInstaller failed
    echo Check: build\CookBook2026\warn-CookBook2026.txt
    pause & exit /b 1
)

:: -------------------------------------------------------
:: Post-build
:: -------------------------------------------------------
if exist "dist\CookBook2026.exe" (
    echo.
    if exist "icon.ico" (
        copy /y "icon.ico" "dist\icon.ico" >nul
        echo [*] icon.ico  -> dist\icon.ico  OK
    )
    if exist "C:\Windows\Fonts\arial.ttf" (
        copy /y "C:\Windows\Fonts\arial.ttf" "dist\arial.ttf" >nul
        echo [*] arial.ttf -> dist\arial.ttf  OK
    )
    echo.
    echo =============================================
    echo   BUILD SUCCESS
    echo   dist\CookBook2026.exe
    echo =============================================
    echo.
    explorer dist
) else (
    echo.
    echo =============================================
    echo   BUILD FAILED - see errors above
    echo   build\CookBook2026\warn-CookBook2026.txt
    echo =============================================
)

echo.
pause
