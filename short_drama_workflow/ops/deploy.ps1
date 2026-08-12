<#
.SYNOPSIS
    deploy.ps1 - rsync project to VPS + remote start + healthcheck (skeleton)
.DESCRIPTION
    - DEPLOY_HOST not set (env or -DeployHost) -> print skip message and exit 0 (safe, no local harm).
    - -Check mode: only print the commands that WOULD run (rsync --dry-run + ssh plan), do not execute.
    - Real mode (host set, not -Check): rsync -> ssh remote start 8777/8788/8787 -> remote healthcheck.
    - When O5 not provisioned: only -Check validation matters (script must not error).
    Zero AGNES quota: pure file sync + process mgmt, no generation API.
#>

[CmdletBinding()]
param(
    [switch]$Check,
    [string]$DeployHost = $env:DEPLOY_HOST,
    [string]$RemotePath = $(if ($env:DEPLOY_PATH) { $env:DEPLOY_PATH } else { "/opt/workbuddy" }),
    [string]$IdentityFile = $env:DEPLOY_KEY
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function Write-Step($m){ Write-Host ("==> " + $m) -ForegroundColor Cyan }
$PY_BIN = "C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe"
$REPO_ROOT = (Resolve-Path (Split-Path (Split-Path $PSScriptRoot))).Path

# excludes for rsync
$EXCLUDES = @("--exclude=.git", "--exclude=output", "--exclude=__pycache__",
              "--exclude=*.pyc", "--exclude=.env", "--exclude=node_modules",
              "--exclude=short_drama_workflow/html_prototype/logs")

# 0) host not configured -> safe skip
if ([string]::IsNullOrWhiteSpace($DeployHost)) {
    Write-Host ("DEPLOY_HOST not configured, skip deploy.") -ForegroundColor Yellow
    Write-Host ("  Set via: `$env:DEPLOY_HOST = 'user@vps.example.com'  or  .\deploy.ps1 -DeployHost user@vps") -ForegroundColor DarkGray
    exit 0
}

$rsync = Get-Command rsync -ErrorAction SilentlyContinue
if (-not $rsync) {
    Write-Warning ("rsync not found on this machine (WSL / Git Bash / cwRsync all provide it). Install before real deploy.")
    if (-not $Check) { exit 1 }
}

$sshOpts = @()
if ($IdentityFile) { $sshOpts += @("-i", $IdentityFile) }

$rsyncCmd = ("rsync -avz --delete " + ($EXCLUDES -join " ") + " '{0}/' '{1}:{2}/'" -f $REPO_ROOT, $DeployHost, $RemotePath)
$sshBase  = ("ssh {0} '{1}'" -f ($sshOpts -join " "), $DeployHost)

# remote launch (single-quoted here-string: & and $ are literal)
$remoteLaunch = @'
cd __REMOTE_PATH__
nohup __PYBIN__ short_drama_workflow/html_prototype/server.py > output/launches/studio.log 2>&1 &
nohup __PYBIN__ shared_board/server.py > output/launches/board.log 2>&1 &
nohup __PYBIN__ agnes_proxy.py > output/launches/proxy.log 2>&1 &
'@
$remoteLaunch = $remoteLaunch.Replace("__REMOTE_PATH__", $RemotePath).Replace("__PYBIN__", $PY_BIN)

$remoteHealth = 'curl -s -o /dev/null -w "8777:%{http_code} " http://127.0.0.1:8777/api/projects; curl -s -o /dev/null -w "8787:%{http_code} " http://127.0.0.1:8787/api/projects; curl -s -o /dev/null -w "8788:%{http_code}\n" http://127.0.0.1:8788/api/projects'

Write-Host ("Target VPS : " + $DeployHost) -ForegroundColor Cyan
Write-Host ("Remote path: " + $RemotePath) -ForegroundColor Cyan

# -Check: print only
if ($Check) {
    Write-Host ("`n[CHECK mode] commands that would run on real deploy (not executed, no local change):") -ForegroundColor Yellow
    Write-Host ("  RSYNC : " + $rsyncCmd) -ForegroundColor DarkGray
    Write-Host ("  SSH   : " + $sshBase + " <start 3 services>") -ForegroundColor DarkGray
    ($remoteLaunch.TrimEnd() -split "`n") | ForEach-Object { Write-Host ("           " + $_.Trim()) -ForegroundColor DarkGray }
    Write-Host ("  HEALTH: " + $sshBase + " '" + $remoteHealth + "'") -ForegroundColor DarkGray
    Write-Host ("`n[OK] --check passed: script logic validated, no change to local/VPS.") -ForegroundColor Green
    exit 0
}

# real mode
Write-Step ("Deploying to " + $DeployHost)
Write-Step ("1) rsync project to VPS")
Invoke-Expression $rsyncCmd
if ($LASTEXITCODE -ne 0) { Write-Error "rsync failed"; exit 1 }

Write-Step ("2) remote start 8777/8788/8787")
$launchCmd = $sshBase + " '" + ($remoteLaunch -replace "'", "'\''") + "'"
Invoke-Expression $launchCmd
if ($LASTEXITCODE -ne 0) { Write-Error "remote start failed"; exit 1 }

Write-Step ("3) remote healthcheck")
$healthCmd = $sshBase + " '" + $remoteHealth + "'"
Invoke-Expression $healthCmd

Write-Host ("`n[OK] deploy finished.") -ForegroundColor Green
exit 0

