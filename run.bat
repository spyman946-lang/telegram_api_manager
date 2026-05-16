@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Создание виртуального окружения...
    python -m venv .venv
    if errorlevel 1 (
        echo Ошибка: не найден Python. Установите с https://www.python.org/
        pause
        exit /b 1
    )
    set "PY=%~dp0.venv\Scripts\python.exe"
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Ошибка установки зависимостей.
        pause
        exit /b 1
    )
)

"%PY%" main.py
if errorlevel 1 (
    echo.
    echo Программа завершилась с ошибкой. См. error.log
    pause
    exit /b 1
)
