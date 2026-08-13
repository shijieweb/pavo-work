# check_wip.ps1 - WIP 机械检查：统计 board 项目在途任务数（进行中+待验证+已验证），超阈值红卡拦截
# T-20260812-05 (O4 board 机械闸门)
# 用法: .\check_wip.ps1 [-ProjectId 19] [-Limit 3] [-Owner 阿编]
# 退出码: 0=放行(WIP PASS)  1=红卡拦截(WIP 超限)/服务异常
# 零 AGNES 额度（纯 board API 调用）
# 注意：文件必须保存为 UTF-8 with BOM（PowerShell 5.1 按 ANSI 解析无 BOM 文件会乱码）

param(
    [int]$ProjectId = 19,
    [int]$Limit = 3,
    [string]$Owner = ""
)

$ErrorActionPreference = "Stop"

# 仓库根 = 脚本上溯两级 (ops/ -> short_drama_workflow/ -> 仓库根)
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$EnvFile = Join-Path $RepoRoot "shared_board\.env"

# ---- 读 BOARD_TOKEN（shared_board/.env）----
$token = $null
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*BOARD_TOKEN=(.+)$') { $token = $matches[1].Trim() }
    }
}
if (-not $token) {
    Write-Host "[ERROR] $EnvFile 未找到 BOARD_TOKEN" -ForegroundColor Red
    exit 1
}

# ---- 拉 board 任务树 ----
# 关键：curl.exe 输出是 UTF-8 字节流，直接进 PowerShell 管道会被按 ANSI(GBK) 解码导致
# 中文乱码 + JSON 结构破坏。所以输出到临时文件，再用 .NET 显式按 UTF-8 读取。
$url = "http://127.0.0.1:8788/api/tasks?project_id=$ProjectId"
$tmpFile = Join-Path $env:TEMP ("board_tasks_" + $ProjectId + "_" + $PID + ".json")
try {
    & curl.exe -s -H "X-Agent: 阿编" -H "X-Board-Token: $token" $url -o $tmpFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] curl.exe 退出码 $LASTEXITCODE（board 服务不可达 127.0.0.1:8788）" -ForegroundColor Red
        Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
        exit 1
    }
    $jsonText = [System.IO.File]::ReadAllText($tmpFile, [System.Text.Encoding]::UTF8)
    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
    $tasks = $jsonText | ConvertFrom-Json
} catch {
    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
    Write-Host "[ERROR] board 服务不可达 (http://127.0.0.1:8788): $_" -ForegroundColor Red
    exit 1
}
if ($null -eq $tasks) {
    Write-Host "[ERROR] board 返回空响应（服务未起或 project_id 无效）" -ForegroundColor Red
    exit 1
}

# ---- 统计在途（进行中 + 待验证 + 已验证）----
$wipStates = @("进行中", "待验证", "已验证")
$wip = @($tasks | Where-Object {
    $wipStates -contains $_.status -and ($Owner -eq "" -or $_.author -eq $Owner)
})
$n = $wip.Count

# ---- 判定 ----
if ($n -le $Limit) {
    Write-Host "[OK] WIP PASS ($n/$Limit)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[FAIL] WIP 超限 ($n/$Limit)" -ForegroundColor Red
    $wip | ForEach-Object { Write-Host "  - $($_.title)" -ForegroundColor Yellow }
    exit 1
}
