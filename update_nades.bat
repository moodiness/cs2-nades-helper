@echo off
setlocal

set "REPO_ZIP=https://github.com/FNScence/CSAFAP-config-package/archive/refs/heads/main.zip"
set "SOURCE_PATH=CSAFAP-config-package-main\csafap\csgo\annotations\local"
set "TMP_DIR=%TEMP%\nades-helper-update"
set "ZIP_PATH=%TMP_DIR%\source.zip"
set "EXTRACT_DIR=%TMP_DIR%\extract"

if exist "%TMP_DIR%" rmdir /s /q "%TMP_DIR%"
mkdir "%TMP_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%REPO_ZIP%' -OutFile '%ZIP_PATH%'"
if errorlevel 1 goto error

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP_PATH%' -DestinationPath '%EXTRACT_DIR%' -Force"
if errorlevel 1 goto error

if not exist "%EXTRACT_DIR%\%SOURCE_PATH%" (
    echo Source folder not found: %EXTRACT_DIR%\%SOURCE_PATH%
    goto error
)

if exist "nades" rmdir /s /q "nades"
xcopy "%EXTRACT_DIR%\%SOURCE_PATH%" "nades\" /e /i /y
if errorlevel 1 goto error

echo Nades updated successfully.
goto end

:error
echo Failed to update nades.
exit /b 1

:end
pause
