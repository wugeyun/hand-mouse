@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "DEFAULT_VENV=.venv312"
set "CONFIG_FILE=.hand-mouse-windows.conf"
set "MODEL_PATH=src\hand_mouse\models\hand_landmarker.task"
set "PYTHON_CMD="
set "VENV_DIR="
set "VENV_PY="
set "DEPLOY=1"

if exist "%CONFIG_FILE%" (
    set "CANDIDATE_DIR="
    set /p "CANDIDATE_DIR="<"%CONFIG_FILE%"
    if defined CANDIDATE_DIR if exist "!CANDIDATE_DIR!\Scripts\python.exe" (
        "!CANDIDATE_DIR!\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 (
            echo A completed Windows deployment was found: !CANDIDATE_DIR!
            call :ask_yes "Skip deployment and use this environment"
            if not errorlevel 1 (
                set "VENV_DIR=!CANDIDATE_DIR!"
                set "VENV_PY=!VENV_DIR!\Scripts\python.exe"
                set "DEPLOY=0"
            )
        )
    )
)

if "%DEPLOY%"=="1" (
    call :deploy
    if errorlevel 1 goto :failed
)

echo Running tests...
"%VENV_PY%" -m pytest
if errorlevel 1 (
    echo Tests failed. Live mouse control will not start.
    goto :failed
)

call :ask_yes "All tests passed. Start live mouse control now"
if errorlevel 1 (
    echo Tests passed. Live mode was not started.
    goto :done
)

echo Starting live mode. Press Ctrl+C to stop.
"%VENV_PY%" run_hand_mouse.py --live --no-preview
set "RUN_RESULT=%ERRORLEVEL%"
if not "%RUN_RESULT%"=="0" goto :failed
goto :done

:deploy
call :find_python
if not defined PYTHON_CMD (
    echo No supported Python 3.10+ interpreter was found.
    echo Choose a Python version to install:
    echo   1^) Python 3.12 ^(recommended^)
    echo   2^) Python 3.11
    echo   3^) Python 3.10
    set "INSTALL_VERSION="
    set /p "INSTALL_VERSION=Choice [default 3.12]: "
    if not defined INSTALL_VERSION set "INSTALL_VERSION=3.12"
    if "!INSTALL_VERSION!"=="1" set "INSTALL_VERSION=3.12"
    if "!INSTALL_VERSION!"=="2" set "INSTALL_VERSION=3.11"
    if "!INSTALL_VERSION!"=="3" set "INSTALL_VERSION=3.10"
    if not "!INSTALL_VERSION!"=="3.12" if not "!INSTALL_VERSION!"=="3.11" if not "!INSTALL_VERSION!"=="3.10" (
        echo Unsupported Python selection: !INSTALL_VERSION!
        exit /b 1
    )
    where winget >nul 2>&1
    if errorlevel 1 (
        echo winget is not available. Install Python from https://www.python.org/downloads/windows/ and run this script again.
        start "" "https://www.python.org/downloads/windows/"
        exit /b 1
    )
    echo Installing Python !INSTALL_VERSION! with winget...
    winget install --id Python.Python.!INSTALL_VERSION! -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 exit /b 1
    call :find_python
)
if not defined PYTHON_CMD (
    echo A supported Python interpreter is still unavailable.
    exit /b 1
)

echo Using Python %PYTHON_CMD%
set /p "VENV_DIR=Virtual environment directory [default %DEFAULT_VENV%]: "
if not defined VENV_DIR set "VENV_DIR=%DEFAULT_VENV%"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

set "USE_EXISTING=0"
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "USE_EXISTING=1"
)

if "%USE_EXISTING%"=="0" (
    if exist "%VENV_DIR%" (
        echo The selected environment is missing or uses an unsupported Python version.
        call :ask_yes "Reinitialize %VENV_DIR% with the selected Python"
        if errorlevel 1 exit /b 1
    )
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b 1
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
echo Installing project and test dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VENV_PY%" -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1

if not exist "%MODEL_PATH%" (
    echo Bundled model is missing: %MODEL_PATH%
    exit /b 1
)
"%VENV_PY%" -c "from hand_mouse.tracker import resolve_model_path; print('Model:', resolve_model_path(None))"
if errorlevel 1 exit /b 1

> "%CONFIG_FILE%" echo %VENV_DIR%
exit /b 0

:find_python
set "PYTHON_CMD="
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD (
    py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.11"
)
if not defined PYTHON_CMD (
    py -3.10 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.10"
)
if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
exit /b 0

:ask_yes
:ask_yes_loop
set "ANSWER="
set /p "ANSWER=%~1 [Y/n]: "
if not defined ANSWER exit /b 0
if /i "%ANSWER%"=="y" exit /b 0
if /i "%ANSWER%"=="yes" exit /b 0
if /i "%ANSWER%"=="n" exit /b 1
if /i "%ANSWER%"=="no" exit /b 1
echo Please enter Y or N.
goto :ask_yes_loop

:failed
echo.
echo The automated run did not complete successfully.
pause
exit /b 1

:done
echo.
echo Finished.
pause
exit /b 0
