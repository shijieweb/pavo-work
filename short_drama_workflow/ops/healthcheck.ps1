<#
.SYNOPSIS
    healthcheck.ps1 —— 探活 8777 / 8787 / 8788 三端口
.DESCRIPTION
    对 8777(studio) / 8787(proxy) / 8788(board) 三端口各发一次
    GET http://127.0.0.1:<port>/api/projects -TimeoutSec 5，
    按 HTTP 200 判 UP 并打印耗时(ms)，否则 DOWN。
    零 AGNES 额度：仅进程/端口探活，不调任何生成 API。
.EXAMPLE
    .\healthcheck.ps1
    .\healthcheck.ps1 -Ports 8777,8787
#>

[CmdletBinding()]
param(
    [int[]]$Ports = @(8777, 8787, 8788),
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$LABELS = @{
    8777 = "studio"
    8787 = "proxy "
    8788 = "board "
}

$allUp = $true
foreach ($port in $Ports) {
    $label = if ($LABELS.ContainsKey($port)) { $LABELS[$port] } else { "svc" }
    $uri = "http://${HostName}:${port}/api/projects"
    $t0 = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $r = Invoke-WebRequest -Uri $uri -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        $t0.Stop()
        $ms = $t0.ElapsedMilliseconds
        if ($r.StatusCode -eq 200) {
            Write-Host ("{0,5} {1}: UP ({2} ms)" -f $port, $label, $ms) -ForegroundColor Green
        } else {
            $allUp = $false
            Write-Host ("{0,5} {1}: DOWN (HTTP {2})" -f $port, $label, $r.StatusCode) -ForegroundColor Red
        }
    } catch {
        $t0.Stop()
        $allUp = $false
        $msg = $_.Exception.Message -replace "`n.*", ""
        Write-Host ("{0,5} {1}: DOWN ({2})" -f $port, $label, $msg) -ForegroundColor Red
    }
}

if ($allUp) {
    Write-Host ("`n✅ 全部探测端口 UP") -ForegroundColor Green
    exit 0
} else {
    Write-Host ("`n⚠ 存在 DOWN 端口") -ForegroundColor Yellow
    exit 1
}

