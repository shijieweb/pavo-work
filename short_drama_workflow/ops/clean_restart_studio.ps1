<#
.SYNOPSIS
    clean_restart_studio.ps1 - 干净重启 8777 工作台（studio 后端）
.DESCRIPTION
    固化历史踩坑点：8777 脏重启导致端口假占用 / 残留进程互相抢端口。
    做法（复刻 agnes_proxy._launch_studio）：
      1. 用 Get-CimInstance 按 CommandLine 精确匹配查 8777 studio 残留进程
         （主指纹 '%html_prototype%server.py%' 复刻 agnes_proxy 启动命令；
          补充指纹捕获"经 shell 包装启动、子进程 python server.py 但命令行无 html_prototype"
          的孤儿进程，避免杀了包装壳却漏掉真正占端口的 python）。
          !!! 绝不误杀：补充指纹显式排除 shared_board / agnes_proxy，绝不动 8788/8787。
          !!! 绝不用 Get-NetTCPConnection 查残留（它会把 8777 归 PID 0 假象）。
      2. 逐个 Stop-Process -Force 杀掉。
      3. 确认 8777 无 Listening（Test-NetConnection 返回 false，且 CimInstance 无残留）。
      4. 用与 agnes_proxy 完全相同的命令重拉：
         PY_BIN short_drama_workflow/html_prototype/server.py
         cwd=仓库根, env REAL=1, detached 后台（无控制台窗口、脱离父进程独立存活）。
      5. 轮询 /api/projects 直到 8777 回绿，从 CimInstance 查回新 PID 打印。
    -All 开关：顺带按同样方式重启 8788(board) 与 8787(proxy)。默认只重启 8777。
    幂等：重复跑安全；无残留时直接拉起（冷启动）。
.PARAMETER All
    顺带重启 8788 / 8787。
.PARAMETER NoStart
    只杀残留 + 确认端口空闲，不重拉（用于"清场"场景）。
.EXAMPLE
    .\clean_restart_studio.ps1            # 只干净重启 8777
    .\clean_restart_studio.ps1 -All       # 8777 + 8788 + 8787 全清重启
    .\clean_restart_studio.ps1 -NoStart   # 只清场，不拉起
#>

[CmdletBinding()]
param(
    [switch]$All,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ===== 写死事实（与 agnes_proxy.py:90-121 完全一致）=====
$PY_BIN = "C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe"
$REPO_ROOT = (Resolve-Path (Split-Path (Split-Path $PSScriptRoot))).Path   # .../workbuddy

# 各服务的「进程精确指纹」。Match 为主 WQL 片段；Exclude 为补充指纹的排除项。
$SERVICES = @(
    [PSCustomObject]@{
        Name      = "studio(8777)"
        Port      = 8777
        # 主指纹：复刻 agnes_proxy 启动命令（脚本全路径含 html_prototype）
        Match     = "CommandLine LIKE '%html_prototype%server.py%'"
        # 补充指纹：仅捕获"python.exe server.py"（脚本名前无路径，即 cwd=html_prototype 的孤儿子进程）。
        # 用裸 script 形态精确限定，避免误杀其他带全路径的 server.py（如 jianying-mcp 等）。
        # board/proxy 均带全路径且非此形态，天然不命中。
        MatchExtra = "(CommandLine LIKE '%python.exe server.py%' AND NOT (CommandLine LIKE '%shared_board%') AND NOT (CommandLine LIKE '%agnes_proxy%'))"
        Script    = "short_drama_workflow/html_prototype/server.py"
        EnvExtra  = @{ "REAL" = "1" }              # 复刻 _launch_studio 的 {"REAL":"1"}
        Include   = $true                          # 默认总包含
    },
    [PSCustomObject]@{
        Name      = "board(8788)"
        Port      = 8788
        Match     = "CommandLine LIKE '%shared_board%server.py%'"
        MatchExtra = $null
        Script    = "shared_board/server.py"
        EnvExtra  = @{}                            # 复刻 _launch_board 的 {}
        Include   = $false                         # 仅 -All
    },
    [PSCustomObject]@{
        Name      = "proxy(8787)"
        Port      = 8787
        Match     = "CommandLine LIKE '%agnes_proxy.py%'"
        MatchExtra = $null
        Script    = "agnes_proxy.py"
        EnvExtra  = @{}                            # 复刻 _launch_service 默认 env
        Include   = $false                         # 仅 -All
    }
)

function Write-Step($msg) { Write-Host ("==> " + $msg) -ForegroundColor Cyan }

function Find-Procs($svc) {
    # 主指纹 + （若有）补充指纹，分两次 Get-CimInstance 查询后 PowerShell 端去重并集。
    # 仍纯 Get-CimInstance，绝不用 netstat 查残留。
    $result = @()
    try {
        $result += Get-CimInstance Win32_Process -Filter $svc.Match -ErrorAction Stop
    } catch {
        Write-Warning ("Get-CimInstance(主指纹) 失败: " + $_.Exception.Message)
    }
    if ($svc.MatchExtra) {
        try {
            $result += Get-CimInstance Win32_Process -Filter $svc.MatchExtra -ErrorAction Stop
        } catch {
            Write-Warning ("Get-CimInstance(补充指纹) 失败: " + $_.Exception.Message)
        }
    }
    $seen = @{}
    $out = @()
    foreach ($p in $result) {
        if (-not $seen.ContainsKey($p.ProcessId)) { $seen[$p.ProcessId] = $true; $out += $p }
    }
    return $out
}

function Test-PortIdle($port) {
    try {
        $up = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
        return (-not $up)
    } catch {
        return $true
    }
}

function Start-DetachedService($svc) {
    # 复刻 agnes_proxy._launch_service：subprocess.Popen([PY_BIN, script], env=..., creationflags=DETACH)
    # 用 Start-Process -PassThru（Windows 等价 detached：子进程独立存活，脚本退出不影响它）。
    # 注入服务专属 env（如 studio 的 REAL=1），启动后即时还原，避免污染当前会话。
    $backup = @{}
    foreach ($k in $svc.EnvExtra.Keys) {
        $backup[$k] = [Environment]::GetEnvironmentVariable($k, "Process")
        [Environment]::SetEnvironmentVariable($k, [string]$svc.EnvExtra[$k], "Process")
    }
    try {
        $p = Start-Process -FilePath $PY_BIN -ArgumentList $svc.Script `
            -WorkingDirectory $REPO_ROOT -WindowStyle Hidden -PassThru -ErrorAction Stop
        return $p
    } catch {
        Write-Error ("启动子进程失败: " + $_.Exception.Message)
        return $null
    } finally {
        foreach ($k in $backup.Keys) {
            if ($null -eq $backup[$k]) { [Environment]::SetEnvironmentVariable($k, $null, "Process") }
            else { [Environment]::SetEnvironmentVariable($k, $backup[$k], "Process") }
        }
    }
}

function Wait-HealthGreen($port, $timeoutSec = 40) {
    $uri = "http://127.0.0.1:$port/api/projects"
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $uri -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-ServicePid($svc) {
    $procs = Find-Procs $svc
    if ($procs.Count -eq 0) { return $null }
    $foundPid = ($procs | Sort-Object ProcessId -Descending | Select-Object -First 1).ProcessId
    return $foundPid
}

# ===== 主流程 =====
$targets = $SERVICES | Where-Object { $_.Include -or $All }
Write-Step ("目标服务: " + ($targets.Name -join ", "))

foreach ($svc in $targets) {
    Write-Host ("`n##### " + $svc.Name + " #####") -ForegroundColor Yellow

    # 1) 查残留（精确 CommandLine，主指纹 + 补充指纹并集）
    $oldProcs = Find-Procs $svc
    if ($oldProcs.Count -gt 0) {
        Write-Step ("发现 " + $oldProcs.Count + " 个残留进程，精确杀除")
        $killed = @()
        foreach ($proc in $oldProcs) {
            Write-Host ("  - PID " + $proc.ProcessId + "  " + ($proc.CommandLine | Out-String).Trim())
            try { Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop; $killed += $proc.ProcessId }
            catch { Write-Warning ("  杀 PID " + $proc.ProcessId + " 失败: " + $_.Exception.Message) }
        }
        Write-Host ("  已杀 PID: " + ($killed -join ", ")) -ForegroundColor DarkGray
    } else {
        Write-Step ("无残留进程（冷启动或已停）")
    }

    # 2) 确认端口空闲（给操作系统一点时间释放）
    $idle = $false
    for ($i = 0; $i -lt 6; $i++) {
        if (Test-PortIdle $svc.Port) { $idle = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $idle) {
        Write-Warning ("端口 " + $svc.Port + " 仍被占用（可能有非本指纹进程占用，已避免误杀）。请人工排查。")
    } else {
        Write-Step ("端口 " + $svc.Port + " 已空闲")
    }

    if ($NoStart) {
        Write-Step ("-NoStart：跳过拉起")
        continue
    }

    # 3) 用与 agnes_proxy 完全相同的命令重拉（detached）
    Write-Step ("重拉: $PY_BIN $($svc.Script)  (cwd=$REPO_ROOT, env=REAL=$($svc.EnvExtra['REAL']))")
    $p = Start-DetachedService $svc
    if ($null -eq $p) {
        Write-Error ("✗ 子进程启动失败，详见上方错误")
        exit 1
    }
    Write-Host ("  已派生子进程 PID=" + $p.Id)

    # 4) 轮询 healthcheck 回绿
    Write-Step ("等待 " + $svc.Port + " 回绿...")
    $green = Wait-HealthGreen $svc.Port
    if (-not $green) {
        Write-Error ("✗ " + $svc.Name + " 重启后 " + $svc.Port + " 未在超时内回绿，请查看日志 output/launches/")
        exit 1
    }
    Write-Host ("  [OK] " + $svc.Port + " 已回绿") -ForegroundColor Green

    # 5) 从 CimInstance 查回新 PID（确认确实是新进程绑定）
    $newPid = Get-ServicePid $svc
    if ($newPid) {
        Write-Host ("  [OK] 新 PID = " + $newPid + "  (CommandLine 指纹匹配)") -ForegroundColor Green
    } else {
        Write-Warning ("  端口已回绿但未能从 CimInstance 查到进程（可能权限/瞬时），服务实际已在工作。")
    }
}

Write-Host ("`n[OK] clean_restart 完成。目标: " + ($targets.Name -join ", ")) -ForegroundColor Green
exit 0
