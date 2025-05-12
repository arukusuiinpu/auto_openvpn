@echo off

>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if %errorlevel% NEQ 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

call pip install requests
call pip install bs4
call pip install datetime
call pip install socket
call pip install pycountry

echo Done!

start "" "control (OPEN ME TO CHECK).cmd"

EXIT