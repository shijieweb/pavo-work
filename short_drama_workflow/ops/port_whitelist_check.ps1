<#
.SYNOPSIS
    port_whitelist_check.ps1 —— 比对 studio 实际路由 与 agnes_proxy 白名单 STUDIO_PREFIXES
.DESCRIPTION
    固化历史踩坑点：加了 studio 路由却忘在 agnes_proxy.STUDIO_PREFIXES 加白名单，
    导致经 8787 访问该路由 404/501。
    做法（只读分析，绝不改文件）：
      1. 解析 agnes_proxy.py 的 STUDIO_PREFIXES 元组（提取所有双引号字符串）。
      2. 解析 server.py 注册的全部路由（p.path == / startswith / in，源码均为双引号）。
      3. 用与 agnes_proxy._is_studio 完全一致的语义（path == w OR path.startswith(w)）
         判断每个 studio 路由是否被白名单覆盖。
      4. 输出"不在白名单的 studio 路由"缺漏清单；若全绿则明确提示。
    反向也检查：白名单中存在、但 studio 无任何路由命中的条目（疑似死配置，仅提示）。
.EXAMPLE
    .\port_whitelist_check.ps1
#>

[CmdletBinding()]
param(
    [string]$ProxyPath,
    [string]$StudioPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 仓库根 = ops 的上两级（PS5.1 的 Join-Path 只接受单 child，多级用 Split-Path 链）
$RepoRoot  = (Resolve-Path (Split-Path (Split-Path $PSScriptRoot))).Path
if (-not $ProxyPath)  { $ProxyPath  = Join-Path $RepoRoot "agnes_proxy.py" }
if (-not $StudioPath) { $StudioPath = Join-Path (Join-Path (Join-Path $RepoRoot "short_drama_workflow") "html_prototype") "server.py" }

# 提取字符串字面量（源码均用双引号，故只匹配 "..."）。
# 用 [char]34 构造双引号字符，避免源码里直接嵌 " 导致字符串字面量失配。
function Parse-StringLiterals($text) {
    $dq = [char]34
    $bs = [char]92
    $pat = ([string]$bs + [string]$dq) + "([^" + [string]$dq + "]*)" + ([string]$bs + [string]$dq)
    $out = @()
    $m = [regex]::Matches($text, $pat)
    foreach ($x in $m) { $out += $x.Groups[1].Value }
    return $out
}

# ===== 1) 解析 STUDIO_PREFIXES =====
if (-not (Test-Path $ProxyPath)) { Write-Error ("找不到代理文件: " + $ProxyPath); exit 1 }
$proxyTxt = Get-Content $ProxyPath -Raw -Encoding UTF8
$m = [regex]::Match($proxyTxt, 'STUDIO_PREFIXES\s*=\s*\(([^)]*)\)')
if (-not $m.Success) { Write-Error "未能在 agnes_proxy.py 解析到 STUDIO_PREFIXES 元组"; exit 1 }
$WHITELIST = Parse-StringLiterals $m.Groups[1].Value
Write-Host ("STUDIO_PREFIXES 共 " + $WHITELIST.Count + " 条白名单前缀：") -ForegroundColor Cyan
Write-Host ("  " + ($WHITELIST -join ", "))

# 复刻 agnes_proxy._is_studio 语义
function Test-Covered($route) {
    foreach ($w in $WHITELIST) {
        if ($route -eq $w -or $route.StartsWith($w)) { return $true }
    }
    return $false
}

# ===== 2) 解析 studio 路由 =====
if (-not (Test-Path $StudioPath)) { Write-Error ("找不到 studio 文件: " + $StudioPath); exit 1 }
$lines = Get-Content $StudioPath -Encoding UTF8

$ROUTES = @()
$currentMethod = "?"
foreach ($idx in 0..($lines.Count - 1)) {
    $ln = $lines[$idx]
    if     ($ln -match "def do_GET\(self\)")      { $currentMethod = "GET" }
    elseif ($ln -match "def do_POST\(self\)")     { $currentMethod = "POST" }
    elseif ($ln -match "def do_PUT\(self\)")      { $currentMethod = "PUT" }
    elseif ($ln -match "def do_DELETE\(self\)")   { $currentMethod = "DELETE" }

    # p.path == "..."  (也兼容 self.path == "..."，但 studio 源码统一用 p.path)
    $m1 = [regex]::Match($ln, 'p\.path\s*==\s*"([^"]*)"')
    if ($m1.Success) {
        $ROUTES += [PSCustomObject]@{ Method = $currentMethod; Path = $m1.Groups[1].Value; Kind = "exact"; Line = ($idx + 1) }
        continue
    }
    # p.path.startswith("...")
    $m2 = [regex]::Match($ln, 'p\.path\.startswith\(\s*"([^"]*)"\s*\)')
    if ($m2.Success) {
        $ROUTES += [PSCustomObject]@{ Method = $currentMethod; Path = $m2.Groups[1].Value; Kind = "prefix"; Line = ($idx + 1) }
        continue
    }
    # p.path in ("...", "...")
    $m3 = [regex]::Match($ln, 'p\.path\s+in\s*\(')
    if ($m3.Success) {
        foreach ($s in (Parse-StringLiterals $ln)) {
            $ROUTES += [PSCustomObject]@{ Method = $currentMethod; Path = $s; Kind = "exact"; Line = ($idx + 1) }
        }
    }
}

# 去重
$seen = @{}
$UNIQUE = @()
foreach ($r in $ROUTES) {
    $key = ($r.Method + "|" + $r.Kind + "|" + $r.Path)
    if (-not $seen.ContainsKey($key)) { $seen[$key] = $true; $UNIQUE += $r }
}

Write-Host ("`nstudio 解析到 " + $UNIQUE.Count + " 条路由（去重后）") -ForegroundColor Cyan

# ===== 3) 比对 =====
# 静态 HTML 入口（/ 与 /studio.html）由代理在 do_GET 里作为 hub/entry 直接服务，
# 不经 _is_studio 路径匹配转发给 studio（详见 agnes_proxy.py:223），故不应加入 STUDIO_PREFIXES。
# 这些静态入口不计入"缺漏"，仅单独提示，避免误报。
$STATIC_ENTRIES = @("/", "/studio.html")

$MISSING = @()
$STATIC_NOTE = @()
foreach ($r in $UNIQUE) {
    if ($STATIC_ENTRIES -contains $r.Path) {
        $STATIC_NOTE += $r
        continue
    }
    if (-not (Test-Covered $r.Path)) { $MISSING += $r }
}

Write-Host ("`n===== 白名单比对结果 =====") -ForegroundColor Yellow
if ($MISSING.Count -eq 0) {
    Write-Host ("✅ 全部 studio 路由（API/动态前缀）均被 STUDIO_PREFIXES 覆盖（经 8787 访问不会 404/501）") -ForegroundColor Green
} else {
    Write-Host ("⚠ 发现 " + $MISSING.Count + " 条 studio 路由 [不在] 白名单，经 8787 访问将 404/501：") -ForegroundColor Red
    foreach ($r in $MISSING) {
        $kind = if ($r.Kind -eq "prefix") { "前缀(任意子路径)" } else { "精确" }
        Write-Host ("  - [$($r.Method)] $($r.Path)  ($kind, server.py:$($r.Line))") -ForegroundColor Red
        Write-Host ("      修复：在 agnes_proxy.STUDIO_PREFIXES 增加对应项（提单走流程，本脚本不改文件）") -ForegroundColor DarkGray
    }
}
if ($STATIC_NOTE.Count -gt 0) {
    Write-Host ("ℹ 静态 HTML 入口（不计入缺漏，由代理 hub 直接服务，不应加入白名单）：") -ForegroundColor DarkGray
    foreach ($r in $STATIC_NOTE) {
        Write-Host ("  - [$($r.Method)] $($r.Path)  (server.py:$($r.Line))") -ForegroundColor DarkGray
    }
}

# ===== 4) 反向：白名单孤立项（仅提示）=====
Write-Host ("`n===== 反向检查（白名单孤立项，仅提示）=====") -ForegroundColor Yellow
$orphan = @()
foreach ($w in $WHITELIST) {
    $hit = $false
    foreach ($r in $UNIQUE) {
        if ($r.Path -eq $w -or $r.Path.StartsWith($w) -or $w.StartsWith($r.Path)) { $hit = $true; break }
    }
    if (-not $hit) { $orphan += $w }
}
if ($orphan.Count -eq 0) {
    Write-Host ("✅ 白名单无孤立项（每条前缀都至少有一处 studio 路由命中）") -ForegroundColor Green
} else {
    Write-Host ("ℹ 以下白名单前缀在 studio 中无对应路由（可能是 board/代理专用或历史遗留，未阻塞）：") -ForegroundColor DarkGray
    foreach ($o in $orphan) { Write-Host ("  - $o") -ForegroundColor DarkGray }
}

if ($MISSING.Count -gt 0) { exit 1 } else { exit 0 }

