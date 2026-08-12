# 测试 · T-20260812-03 运维脚本工作流（独立验收报告）

> 角色：测试（独立验收者）。**只验收、绝不改码**。
> 方法：实跑四个 PowerShell 脚本 + 主理人亲自复验实证（实跑 `clean_restart_studio.ps1` 前后比对 PID）。
> 零 AGNES 额度（纯进程/端口管理，无任何 AI 生成调用）。
> 说明：本文件由主理人据「测试实跑结论 + 主理人亲自复验实证」整理落地（原测试 Agent 写文件时工具反复报错，仅给出口头结论，主理人按"证据不信任"原则逐条亲自实测核实后补写）。

## 整体结论：❌ 退回开发修复（不通过）

实跑发现 **4 个 BUG**，其中 **2 个 P0/P1 阻断核心 AC（AC-1.1 / AC-1.4 / AC-1.5）**。脚本的"安全红线（绝不误杀无关进程）"实测通过，但"干净重启"这一核心功能在真实单残留场景下完全失效（留下脏双进程，正是本脚本要杜绝的）。

## 逐条 AC（实跑证据）

- **AC-1.1 ❌ FAIL**：`clean_restart_studio.ps1` 在"恰好 1 个 studio 残留"的日常稳态下**不杀进程**。实跑铁证：BASELINE studio=`21120` → 脚本报「无残留进程」跳过杀 → 端口仍被 21120 占 → 又派生 `17712` → POST studio=`21120,17712`（两个！）。`OLD studio all killed: False`。详见 BUG-1。
- **AC-1.2 ✅ PASS**：`healthcheck.ps1` 三端口探活正常（8777 UP / 8787 UP / 8788 UP，含 `/api/projects` 真实 200 + 耗时）。
- **AC-1.3 ✅ PASS**：`port_whitelist_check.ps1` 解析 `agnes_proxy.py` 的 `STUDIO_PREFIXES`（31 条前缀）与 studio 路由逐条比对，**0 缺漏**，且无孤立白名单项。
- **AC-1.4 ❌ FAIL**：`deploy.ps1 --check` 不进入检查模式（详见 BUG-2）。PRD AC-1.4 与 README 写的都是 `deploy --check`，据文档调用必失败。
- **AC-1.5 ❌ FAIL**：因 AC-1.1 失效，clean_restart 不幂等（单↔双进程交替），且派生重复进程污染端口。
- **AC-1.6 ✅ PASS**：`ops/README.md` runbook 存在，列各脚本用法与"何时跑哪个"。

## 🔴 安全红线专项验证（PASS）

实跑 `clean_restart_studio.ps1` 前后，对照无关进程 PID 存活情况：

| 进程 | 跑前 PID | 跑后 PID | 结果 |
| --- | --- | --- | --- |
| board(8788) | 21500 | 21500 | ✅ 存活 |
| proxy(8787) | 19572,25008,25964 | 19572,25008,25964 | ✅ 存活 |
| jianying-mcp | 28876,29048 | 28876,29048 | ✅ 存活 |
| node ×11 | 11 个 | 11 个 | ✅ 全部存活 |

**结论：0 误杀。** 主指纹 `%html_prototype%server.py%` + MatchExtra 排除 `shared_board`/`agnes_proxy` 的设计在"不误杀"上有效。但 BUG-4 指出该指纹未限定 `Name='python.exe'`，存在理论误中风险（见下）。

## 缺陷清单（仅报告，不改）

### BUG-1 [S1|P0] ✅ 已修复（主理人复验 PASS） `Find-Procs` 单命中被 PowerShell 管道拆包 → 跳过杀进程分支（AC-1.1/1.5）
- **严重度 S1（核心功能失效，留下脏双进程）**；**优先级 P0（阻断 AC-1.1/1.5）**。
- **根因（主理人实测确认）**：`Find-Procs` 末尾 `return $out`（数组）。PowerShell 函数返回数组会被**管道枚举拆包**；当只有 1 个匹配时，调用方 `$oldProcs = Find-Procs $svc` 拿到的是**裸 `CimInstance`** 而非数组，其 `.Count` 为 `$null` → `$oldProcs.Count -gt 0` 恒 `False` → 整段杀进程逻辑被跳过。
- **主理人复验证据**：独立 helper 实跑 `clean_restart_studio.ps1`（helper 自身命令行不含 `html_prototype`/`server.py` 令牌，避免被 `Find-Procs` 误中自身）。BASELINE studio=`21120`；脚本报「无残留」→ 跳过杀 → 又 `Start-Process` 派生 `17712`；POST `studio PIDs: 21120,17712`、`OLD studio all killed: False`、`EXACTLY ONE new studio: False`。**完全复现**。
- **隔离探针对照（解释为何初步推断误判）**：在本地变量上直接查 `@()` 包裹数组的 `.Count` 得 1，故一度误以为"单命中会进杀分支"；但经函数 `return` 拆包后调用方拿到的 `.Count` 为 `$null`——**实测 > 推断**，根因确为拆包。
- **修复建议**：`Find-Procs` 改 `return ,$out`（逗号包裹防拆包）；调用方加 `@(Find-Procs $svc)` 双重保险；`Get-ServicePid` 同理 `@(Find-Procs)`。

### BUG-2 [S2|P1] ✅ 已修复（主理人复验 PASS） `deploy.ps1 --check` 不生效（AC-1.4）
- **严重度 S2（安全验证路径失效）**；**优先级 P1（阻断 AC-1.4 文档化调用）**。
- **根因（代码确认）**：param 块仅 `[switch]$Check`，PowerShell **不认 GNU 风格 `--check`（双横线）**。`--check` 被当位置参数塞进 `[string]$DeployHost`，于是 `$DeployHost="--check"` 非空 → 跳过「未配置安全跳过」分支 → 直冲真实部署逻辑（本机无 rsync 才 `exit 1`）。若装了 rsync 的机器会真跑 `rsync -avz --delete`。
- **修复建议**：脚本识别 `--check`——param 块后加 `if ($DeployHost -eq '--check') { $Check = $true; $DeployHost = '' }`（或规范文档为 `-Check` 并同步 PRD）。确保 `deploy --check` 进入检查模式打印命令、不执行、不误杀。

### BUG-3 [S3|P2] ✅ 已修复（主理人复验 PASS） deploy 远端 `nohup` 写死 Windows PY_BIN 绝对路径（Linux VPS 必失败）
- **严重度 S3（真实部署路径 latent 失败）**；**优先级 P2（O5 未 provisioned，暂不触发，但上线必爆）**。
- **根因（代码确认）**：`deploy.ps1` 的 `$remoteLaunch` 把 `$PY_BIN = "C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe"` 直接替换进远端 `nohup __PYBIN__ ...` 命令。Linux VPS 上该 Windows 路径不存在 → 远程起服务失败。
- **修复建议**：新增 `[string]$RemotePyBin = "python3"` 参数，远端 `nohup` 用 `$RemotePyBin`（默认 `python3`），本地 PY_BIN 仅用于本地运维（deploy 实际不依赖本地 PY_BIN）。

### BUG-4 [S2|P2] ✅ 已修复（主理人复验 PASS） 主指纹未限定 `Name='python.exe'`（理论误中无关进程）
- **严重度 S2（违反 PRD 边界禁止项"绝不误杀"）**；**优先级 P2（日常稳态不触发，但风险真实）**。
- **实证佐证**：主理人隔离探针时，自身 powershell 进程的命令行因含 `html_prototype`+`server.py` 字面量，被 `%html_prototype%server.py%` **误中**（命中 PID 26888）。日常只有真 studio 含该相邻子串，但任一命令行提及该路径的终端/工具进程会被误杀。
- **修复建议**：主指纹改为 `CommandLine LIKE '%html_prototype%server.py%' AND Name='python.exe'`；MatchExtra 已限定 `python.exe server.py` 形态，天然安全。

## 环境已恢复

主理人实测后已将 8777 恢复为**单一健康进程**（精确按 PID 杀 21120/17712 + 干净重拉 → 新 PID 10664，HEALTH_OK=True，COUNT=1）。当前 `git status --short` 工作树干净（除本文件与 current_state.md 外无脚本被改动）。

## 主理人独立复验（修复后重测 · 2026-08-12）

> 因测试 Agent 写文件时工具反复报错（仅给出口头结论），主理人按"证据不信任"原则，**亲自实跑**对 4 BUG 逐一复验（零 AGNES 额度）。enh 开发自测全绿、声称"0 缺漏"时，正是主理人/测试独立实跑才抓出 S1 P0 脏双进程——双角色闭环的价值在此体现。

### BUG-1 复验 ✅ PASS（关键）
重跑独立 helper `C:/tmp/verify_clean_restart.ps1`：
- BASELINE studio=`29716` → 脚本**「发现 1 个残留进程，精确杀除 - PID 29716 ... 已杀」** → 端口空闲 → 重拉 `3188` → 回绿。
- POST `studio PIDs: 3188`（**单一**）；`OLD studio all killed: True`、`EXACTLY ONE new studio: True`。
- 修复前必失败、修复后通过 → 分支有效，确为真修。

### 安全红线复验 ✅ PASS
跑前/跑后对照：board(21500) 1/1、proxy(19572/25008/25964) 3/3、jianying(28876/29048) 2/2、node×11 全部存活 → **0 误杀**。

### BUG-2 复验 ✅ PASS
`deploy.ps1 --check` → 进入 `[CHECK mode]`，打印 rsync/ssh/`python3` 命令、`[OK] --check passed`、`exit 0`，**未执行** rsync/ssh（本机无 rsync 也未误跑）。`-Check` 同样进检查模式；无 host 时安全跳过 `exit 0`。

### BUG-3 复验 ✅ PASS
CHECK 输出远端命令为 `nohup python3 short_drama_workflow/html_prototype/server.py ...`（非 Windows 路径）；Grep 确认 `$RemotePyBin="python3"`（deploy.ps1:18）且 `.Replace("__PYBIN__", $RemotePyBin)`（:62），Windows `$PY_BIN` 不再进入远端。

### BUG-4 复验 ✅ PASS
clean_restart 实跑**只命中 1 个**真实 studio（python.exe），未误中主理人自身的 powershell 探针（修复前该探针会被误中）→ 指纹 `AND Name='python.exe'` 生效。

### 回归
healthcheck 三端口 UP、port_whitelist_check 0 缺漏，均无回退。

## 闭环结论

- **放行决定：✅ 完成（主理人把关）**。AC-1.1~1.6 全部 PASS（原 FAIL 的 1.1/1.4/1.5 经修复复验通过）；4 BUG 经主理人独立实跑确认全真修。
- 核心价值：本任务的双角色闭环**独立抓出开发自测"全绿"掩盖的 S1 P0 脏双进程 + S2 P1 `--check` 失效 + S3 P2 远端路径错误 + S2 P2 误杀风险**，正是"绝不盲信自测、实跑取证"框架存在的意义。
- git：锚点 `ed3b562`、修复 `a500bbc`（仅改 `ops/`）。最终 8777 单一健康 PID 3188。
