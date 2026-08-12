# short_drama_workflow/ops — 运维脚本工作流

> 任务 `T-20260812-03` 产出：**纯 PowerShell（Windows）**运维脚本包，把历史踩坑点固化为一键工作流。
> 零 AGNES 额度：所有脚本仅做**进程 / 端口管理**，不调任何生成 API。
> 不改动 `agnes_proxy.py` / `server.py` 业务逻辑（除非发现白名单缺漏 → 提单，不改）。

## 目录

| 脚本 | 对应 AC | 作用 |
| --- | --- | --- |
| `clean_restart_studio.ps1` | AC-1.1 | 干净重启 8777（精确查杀残留 → 确认空闲 → 复刻 agnes_proxy 原命令重拉 → 轮询回绿 + 打印新 PID） |
| `healthcheck.ps1` | AC-1.2 | 探活 8777/8787/8788 三端口 `/api/projects`，输出 UP(xx ms)/DOWN |
| `port_whitelist_check.ps1` | AC-1.3 | 比对 studio 实际路由 与 `agnes_proxy.STUDIO_PREFIXES` 白名单，报"不在白名单的路由"（防加路由忘加白名单→404/501） |
| `deploy.ps1` | AC-1.4 | rsync 到 VPS（host 可配，未配安全跳过）+ 远程起服务 + healthcheck；`--check` 仅验证逻辑不误杀本地 |

## 何时跑哪个（runbook）

| 场景 | 跑哪个 |
| --- | --- |
| 改完 `server.py` / 卡端口假占用 / 8777 行为异常 | `.\clean_restart_studio.ps1`（默认只重启 8777；加 `-All` 顺带 8788/8787） |
| 想确认三服务是否都在线 | `.\healthcheck.ps1` |
| 给 studio **新增 / 修改路由**后（防经 8787 访问 404/501） | `.\port_whitelist_check.ps1`，有缺漏就提单在 `agnes_proxy.STUDIO_PREFIXES` 补白名单 |
| 上线到 VPS（host 未配则跳过） | `.\deploy.ps1 --check` 先验证逻辑 → 配好 `DEPLOY_HOST` 后 `.\deploy.ps1` 真部署 |
| 只清场、不拉起 | `.\clean_restart_studio.ps1 -NoStart` |

## 用法

### 1) clean_restart_studio.ps1（AC-1.1）
```powershell
.\clean_restart_studio.ps1            # 干净重启 8777（studio）
.\clean_restart_studio.ps1 -All       # 8777 + 8788(board) + 8787(proxy) 全清重启
.\clean_restart_studio.ps1 -NoStart   # 只杀残留 + 确认端口空闲，不拉起
```
要点（复刻 `agnes_proxy._launch_studio`）：
- 查残留用 `Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%html_prototype%server.py%'"`（**绝不用 `Get-NetTCPConnection`** —— 它会把 8777 归 PID 0 假象）。
- 重拉命令与代理完全一致：`PY_BIN short_drama_workflow/html_prototype/server.py`，`cwd=仓库根`，`env REAL=1`，detached 后台。
- 幂等：无残留时直接拉起；重复跑安全。

### 2) healthcheck.ps1（AC-1.2）
```powershell
.\healthcheck.ps1                 # 探活 8777/8787/8788
.\healthcheck.ps1 -Ports 8777     # 只探 8777
```
输出示例：
```
 8777 studio: UP (12 ms)
 8787 proxy : UP (9 ms)
 8788 board : UP (11 ms)
✅ 全部探测端口 UP
```
全 UP 退出码 0；有 DOWN 退出码 1（可接 CI）。

### 3) port_whitelist_check.ps1（AC-1.3）
```powershell
.\port_whitelist_check.ps1
```
- 解析 `agnes_proxy.py` 的 `STUDIO_PREFIXES` 元组 + `server.py` 的全部 `p.path == / startswith / in` 路由。
- 用与 `agnes_proxy._is_studio` 完全相同的语义（精确或前缀匹配）判定覆盖。
- 有缺漏：列出"不在白名单的 studio 路由"并提示去 `agnes_proxy.STUDIO_PREFIXES` 补（**只读，不改文件**）。
- 全绿：明确提示"全部 studio 路由均在白名单内"。
- 退出码：有缺漏 1，无缺漏 0。

### 4) deploy.ps1（AC-1.4）
```powershell
$env:DEPLOY_HOST = "user@vps.example.com"   # 或 -DeployHost
.\deploy.ps1 --check                         # 只打印将执行的命令，不真连 VPS、不动本地
.\deploy.ps1 -Check                           # 同上（PowerShell 原生只认 -Check，脚本已兼容 --check）
.\deploy.ps1                                 # 真实 rsync + 远程起服务 + healthcheck
```
- `DEPLOY_HOST` 未配置 → 打印"DEPLOY_HOST 未配置，跳过"并 `exit 0`（安全）。
- `--check` 模式：打印 rsync/ssh 计划命令，不执行。`.\deploy.ps1 --check` 与 `.\deploy.ps1 -Check` 均可进入检查模式（PowerShell 原生只认 `-Check`，脚本已兼容 `--check`）。
- O5 未 provisioned 时：仅 `--check` 验证脚本不报错即视为通过。
- 配置项：`DEPLOY_HOST`（必填）/ `DEPLOY_PATH`（默认 `/opt/workbuddy`）/ `DEPLOY_KEY`（私钥路径）。

## 已知坑（已在脚本内规避）

1. `Get-NetTCPConnection` 常把 8777 归 PID 0（假象）→ 一律改用 `Get-CimInstance Win32_Process` 按 CommandLine 精确查。
2. 重启命令必须复刻 `agnes_proxy._launch_studio`：`PY_BIN` + 相对脚本路径 + `cwd=仓库根` + `env REAL=1` + detached。
3. 加 studio 路由后必须同步加 `agnes_proxy.STUDIO_PREFIXES`，否则经 8787 访问 404/501 → 用 `port_whitelist_check.ps1` 防漏。

## 验证记录

见 `dev-work/tasks/T-20260812-03/design.md` 的"自测证据"小节（healthcheck 输出、whitelist 输出、clean_restart 前后 PID 对比、deploy --check 输出）。
