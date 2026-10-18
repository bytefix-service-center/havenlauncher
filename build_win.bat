@echo off
chcp 65001 >nul
setlocal
rem ====================================================================
rem  Сборка Haven Lands Launcher.exe и установщика (Windows x64)
rem    build_win.bat                  - обычная сборка
rem    set VERSION=1.2.0 & build_win.bat   - задать версию
rem  Нужно: Python 3.11 (64-bit) и Inno Setup 6 (для установщика)
rem ====================================================================
cd /d "%~dp0"

set "APP_NAME=Haven Lands Launcher"
if "%VERSION%"=="" set "VERSION=1.0.0"
if "%PYTHON%"=="" set "PYTHON=py -3.11"
set "PF86=%ProgramFiles(x86)%"

if not exist assets\icon.ico (
  echo Нет assets\icon.ico - выполните: python tools\make_assets.py
  exit /b 1
)

echo ==^> 1/3  Окружение Python
%PYTHON% -m venv .venv
if errorlevel 1 goto :fail
call .venv\Scripts\activate
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail

echo ==^> 2/3  Сборка "%APP_NAME%.exe"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean --windowed --name "%APP_NAME%" --icon assets\icon.ico --add-data "ui;ui" --collect-all webview --collect-all pythonnet --collect-all clr_loader --collect-all certifi --hidden-import clr main.py
if errorlevel 1 goto :fail
if not exist "dist\%APP_NAME%\%APP_NAME%.exe" goto :fail

echo ==^> 3/3  Установщик
set "ISCC="
for %%P in ("%PF86%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if "%ISCC%"=="" goto :noinno
"%ISCC%" /Qp /DMyAppVersion=%VERSION% installer\HavenLandsLauncher.iss
if errorlevel 1 goto :fail

echo.
echo Готово:
echo   dist\%APP_NAME%\%APP_NAME%.exe   - программа без установки
echo   dist\Haven-Lands-Launcher-Setup-%VERSION%.exe   - установщик
exit /b 0

:noinno
echo.
echo Программа собрана: dist\%APP_NAME%\%APP_NAME%.exe
echo Inno Setup 6 не найден, поэтому установщик не создан.
echo Скачайте его на https://jrsoftware.org/isdl.php и запустите build_win.bat ещё раз.
exit /b 0

:fail
echo.
echo ОШИБКА сборки - смотрите сообщения выше.
exit /b 1
