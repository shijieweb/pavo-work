Start-Process python -ArgumentList "C:\Users\67972\.qclaw\workspace-agent-16a3f8bf\meeting_system\diag_join.py" -WorkingDirectory "C:\Users\67972\.qclaw\workspace-agent-16a3f8bf\meeting_system" -NoNewWindow -PassThru | Select-Object Id
Start-Sleep -Seconds 15
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*diag_join*" } | Format-Table ProcessId -AutoSize
