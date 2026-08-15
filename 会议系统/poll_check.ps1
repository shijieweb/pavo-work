# temp polling script
Start-Sleep -Seconds 8
$d = Invoke-WebRequest -Uri "http://localhost:5000/api/room/meeting/messages?since=0" -UseBasicParsing | ConvertFrom-Json
Write-Host "PHASE: $($d.phase)"
Write-Host "COUNT: $($d.messages.Count)"
$d.messages | ForEach-Object { Write-Host "$($_.seq) $($_.from.name) | $($_.content.Substring(0, [Math]::Min(70, $_.content.Length)))" }
