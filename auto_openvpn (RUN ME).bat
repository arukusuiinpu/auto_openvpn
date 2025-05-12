@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

set "ORIGINAL_USERPROFILE=%USERPROFILE%"

>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if %errorlevel% NEQ 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

:START

rmdir /S /Q "%ORIGINAL_USERPROFILE%\OpenVPN\config\"

set "CONDITION_FILE=%TEMP%\vpn_condition.flag"
echo true > "%CONDITION_FILE%"

python ./downloader.py list --silent=true

REM 1) Iterate every .ovpn URL printed by the Python script
for /f "usebackq delims=" %%U in (`python ./downloader.py list`) do (
    if not exist "%ORIGINAL_USERPROFILE%\OpenVPN\blacklist.txt" type nul > "%ORIGINAL_USERPROFILE%\OpenVPN\blacklist.txt"
    if not exist "%ORIGINAL_USERPROFILE%\OpenVPN\log\" mkdir "%ORIGINAL_USERPROFILE%\OpenVPN\log\"
    
    if exist "%CONDITION_FILE%" (
        for /f %%C in ('type "%CONDITION_FILE%"') do set "condition=%%C"
        if "!condition!" == "true" (
            findstr /C:"%%U" "%ORIGINAL_USERPROFILE%\OpenVPN\blacklist.txt" >nul
            if !errorlevel! equ 0 (
                echo %%U is blacklisted as not working! Skipping...
            ) else (
    	        REM 2) Download it
    	        python downloader.py download "%%U"
	        
    	        REM 3) Derive the base name (strip path and extension)
    	        for %%F in ("%%~nxU") do set "BASE=%%~nF"
	        
       	        REM 4) Launch OpenVPN in background
                start "OpenVPN Connection" "run_openvpn.bat" !BASE!
                
                REM 5) Check the log file for successful connection message
	        python downloader.py check "!BASE!" "%%U" --timeout="2h"
            )
        )
    )
)

echo Reloading available VPNs list...
goto :START

:END
ENDLOCAL