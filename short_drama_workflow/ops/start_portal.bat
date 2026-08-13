@echo off
REM ============================================================
REM start_portal.bat - 8787 unified portal bootstrap (T-20260813-04b, rev2)
REM FIX (2026-08-13): schtasks onlogon + interactive task gets Ctrl+C
REM when the triggering session ends, killing the python child.
REM -> Use Start-Process to spawn python as an INDEPENDENT process;
REM    this bat exits immediately, task completes, portal survives.
REM Registered via schtasks AgnesPortal (onlogon).
REM ============================================================
cd /d C:\Users\67972\WorkBuddy\workbuddy
if not exist logs mkdir logs
echo [%date% %time%] bootstrap start >> logs\portal_service.log 2>&1
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Users\67972\.workbuddy\binaries\python\versions\3.13.12\python.exe' -ArgumentList 'agnes_proxy.py' -WorkingDirectory 'C:\Users\67972\WorkBuddy\workbuddy' -WindowStyle Hidden"
echo [%date% %time%] bootstrap done (python detached) >> logs\portal_service.log 2>&1
