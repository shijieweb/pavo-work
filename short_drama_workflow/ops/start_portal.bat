@echo off
REM ============================================================
REM start_portal.bat - 8787 unified portal autostart (T-20260813-04b)
REM Managed python absolute path. Auto-restart on crash.
REM Registered via schtasks onlogon -> survives agent session end.
REM ============================================================
cd /d C:\Users\67972\WorkBuddy\workbuddy
if not exist logs mkdir logs

:loop
echo [%date% %time%] portal starting... >> logs\portal_service.log 2>&1
"C:\Users\67972\.workbuddy\binaries\python\versions\3.13.12\python.exe" agnes_proxy.py >> logs\portal_service.log 2>&1
echo [%date% %time%] portal exited, restart in 3s... >> logs\portal_service.log 2>&1
timeout /t 3 /nobreak >nul
goto loop
