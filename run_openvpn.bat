@echo off
setlocal

set "BASE=%1"
set "CONFIG=%ORIGINAL_USERPROFILE%\OpenVPN\config\%BASE%\%BASE%.ovpn"
set "LOGFILE=%ORIGINAL_USERPROFILE%\OpenVPN\log\openvpn_%BASE%.log"
set "OVPN_EXE=C:\Program Files\OpenVPN\bin\openvpn.exe"

powershell -NoProfile -Command ^
    "& '%OVPN_EXE%' --config '%CONFIG%' --connect-timeout 10 --connect-retry-max 1 --mute-replay-warnings 2>&1 | Tee-Object -FilePath '%LOGFILE%'"

endlocal
EXIT