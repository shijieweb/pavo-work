# 设计说明 / 提测文档 · T-20260812-03 运维脚本工作流

> 关联 PRD：`dev-work/tasks/T-20260812-03/PRD.md`（主理人自签闸1，纯内部工具化，不影响需求基线）
> 产出目录：`short_drama_workflow/ops/`
> 测试角色：开发自检（零 AGNES 额度，纯进程/端口管理）

## 一、接口契约（4 脚本 + README）

### 1. `clean_restart_studio.ps1`（AC-1.1）
- **入参**：`-All`（顺带重启 8788/8787）、`-NoStart`（只清场不拉起）。
- **行为**：
  1. `Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%html_prototype%server.py%'"` 查 studio 残留（**绝不用 Get-NetTCPConnection**，避免 8777 归 PID 0 假象）。
  2. 补充指纹 `%python.exe server.py%`（仅裸 `server.py` 形态，精确捕获经 shell 包装的孤儿子进程），排除 `shared_board`/`agnes_proxy`，**绝误杀 8788/8787/其他 server.py（如 jianying-mcp）**。
  3. 逐 `Stop-Process -Force`；确认 8777 无 Listening。
  4. `Start-Process -FilePath $PY_BIN -ArgumentList "short_drama_workflow/html_prototype/server.py" -WorkingDirectory <仓库根> -WindowStyle Hidden -PassThru`（detached 等价；env 经会话注入 REAL=1 后即时还原，复刻 `agnes_proxy._launch_studio`）。
  5. 轮询 `/api/projects` 至回绿，从 CimInstance 查回新 PID。
- **退出**：成功 0；回绿超时/启动失败 1。
- **幂等**：无残留则冷启动；重复跑安全；能清理重复实例。

### 2. `healthcheck.ps1`（AC-1.2）
- **入参**：`-Ports`（默认 8777,8787,8788）、`-HostName`（默认 127.0.0.1）。
- **行为**：每端口 `Invoke-WebRequest -Uri http://<host>:<port>/api/projects -TimeoutSec 5`，输出 `8777 studio: UP (xx ms)` / `DOWN`。
- **退出**：全 UP 0；有 DOWN 1。

### 3. `port_whitelist_check.ps1`（AC-1.3）
- **入参**：`-ProxyPath`、`-StudioPath`（默认自动定位仓库根下的 `agnes_proxy.py` 与 `server.py`）。
- **行为**：解析 `STUDIO_PREFIXES` 元组（31 条）+ 解析 `server.py` 全部 `p.path == / startswith / in` 路由（64 条去重），用与 `agnes_proxy._is_studio` 完全一致的语义（精确/前缀匹配）比对，输出"不在白名单的 studio 路由"。静态 HTML 入口 `/`、`/studio.html` 由代理 hub 直接服务（不应加入白名单），单独提示不计入缺漏。
- **退出**：有缺漏 1；无缺漏 0。**只读，不改任何文件**。

### 4. `deploy.ps1`（AC-1.4）
- **入参**：`-Check`（仅打印计划不执行）、`-DeployHost`（或 env `DEPLOY_HOST`）、`-RemotePath`（默认 `/opt/workbuddy`）、`-IdentityFile`（或 env `DEPLOY_KEY`）。
- **行为**：
  - `DEPLOY_HOST` 未配置 → 打印"DEPLOY_HOST 未配置，跳过"并 `exit 0`（安全，不误杀本地）。
  - `-Check` → 打印 rsync/ssh/health 计划命令，不执行。
  - 真实模式 → rsync 同步 → ssh 远程拉起 8777/8788/8787 → 远程 healthcheck。
  - O5 未 provisioned 时：仅 `-Check` 验证脚本逻辑不报错即通过。
- **退出**：skip/check/成功 0；真实模式 rsync 缺失或失败 1。

### 5. `README.md`（AC-1.6）
- 各脚本用法 + "何时跑哪个" runbook。

## 二、提测说明（交测试角色）
1. 改完 `server.py` → `.\clean_restart_studio.ps1`（默认只 8777；`-All` 顺带 8788/8787）。
2. 改完/新增 studio 路由 → `.\port_whitelist_check.ps1`，有缺漏须先在 `agnes_proxy.STUDIO_PREFIXES` 补白名单（**本包不改 proxy/server 业务逻辑**，白名单缺漏提单走流程）。
3. 上线 → `.\deploy.ps1 -Check` 验证逻辑 → 配 `DEPLOY_HOST` 后 `.\deploy.ps1`。
4. 全脚本零 AGNES 额度，纯进程/端口管理。

## 三、自测证据（开发自检，全部纯进程/端口，零额度）

### 3.1 healthcheck.ps1（三端口）
```
 8777 studio: UP (81 ms)
 8787 proxy : UP (34 ms)
 8788 board : UP (18 ms)
✅ 全部探测端口 UP
```

### 3.2 port_whitelist_check.ps1（白名单比对）
```
STUDIO_PREFIXES 共 31 条白名单前缀：
  /studio, /api/projects, /api/spec, /api/generate, /api/project/, /api/pipeline,
  /api/agent, /api/export, /api/shot/, /api/assemble, /api/finalize, /api/quality,
  /api/diagnose, /api/queue/, /api/key-pool, /api/meta, /api/series/, /api/prompt/,
  /api/novel/, /api/style/, /api/outline/, /api/asset/, /assets/, /projects/,
  /vendor/, /api/faceqc, /api/facefix, /api/agnes/, /api/vision/, /api/log, /api/logs

studio 解析到 64 条路由（去重后）
===== 白名单比对结果 =====
✅ 全部 studio 路由（API/动态前缀）均被 STUDIO_PREFIXES 覆盖（经 8787 访问不会 404/501）
ℹ 静态 HTML 入口（不计入缺漏，由代理 hub 直接服务，不应加入白名单）：
  - [GET] /  (server.py:3847)
  - [GET] /studio.html  (server.py:3847)
===== 反向检查（白名单孤立项，仅提示）=====
✅ 白名单无孤立项（每条前缀都至少有一处 studio 路由命中）
```
**结论：当前 0 个 API 路由缺漏（无需提单）。** 静态入口 `/`、`/studio.html` 由代理 hub（`agnes_proxy.py:223`）直接服务，按设计不进 `STUDIO_PREFIXES`。
> 观察项（非阻塞，不计入 BUG）：白名单含 `/studio`，但代理 `do_GET` 未把 `/studio` 路由到 studio HTML（转发为 8777 `/studio` 会 404）。studio HTML 目前经 8787 实际不可达，属既有产品/代理路由问题，不在本任务范围，交主理人酌情处理。

### 3.3 clean_restart_studio.ps1（真重启 8777）
- 重启前：存在重复/陈旧 studio 实例（PID 23868、31408 同时 LISTEN 8777，系前序测试残留）。
- 执行：精确查杀（CommandLine 指纹，未误杀 jianying-mcp）→ 端口空闲 → 复刻 agnes_proxy 命令重拉 → 轮询回绿。
```
==> 发现 2 个残留进程，精确杀除
  - PID 23868  "...python.exe" short_drama_workflow/html_prototype/server.py
  - PID 31408  "...python.exe" short_drama_workflow/html_prototype/server.py
  已杀 PID: 23868, 31408
==> 端口 8777 已空闲
==> 重拉: C:/.../python.exe short_drama_workflow/html_prototype/server.py  (cwd=..., env=REAL=1)
  已派生子进程 PID=22768
==> 等待 8777 回绿...
  [OK] 8777 已回绿
  [OK] 新 PID = 22768  (CommandLine 指纹匹配)
[OK] clean_restart 完成。目标: studio(8777)
```
- 重启后复核：`Get-CimInstance ... '%html_prototype%server.py%'` 仅匹配 **PID 22768 单实例**；三端口 healthcheck 全 UP；**jianying-mcp 2 个进程（PID 28876/29048）存活**（证明补充指纹未误杀）。

### 3.4 deploy.ps1 --check（安全验证，假 host）
```
Target VPS : test@vps.example.com
Remote path: /opt/workbuddy
[CHECK mode] commands that would run on real deploy (not executed, no local change):
  RSYNC : rsync -avz --delete --exclude=.git ... 'C:\...\workbuddy/' 'test@vps.example.com:/opt/workbuddy/'
  SSH   : ssh  'test@vps.example.com' <start 3 services>
           cd /opt/workbuddy
           nohup C:/.../python.exe short_drama_workflow/html_prototype/server.py > output/launches/studio.log 2>&1 &
           nohup C:/.../python.exe shared_board/server.py > output/launches/board.log 2>&1 &
           nohup C:/.../python.exe agnes_proxy.py > output/launches/proxy.log 2>&1 &
  HEALTH: ssh  'test@vps.example.com' 'curl ... 8777/8787/8788 ...'
[OK] --check passed: script logic validated, no change to local/VPS.
```
- 未配置 `DEPLOY_HOST` 时：`deploy.ps1` 与 `deploy.ps1 -Check` 均打印"DEPLOY_HOST 未配置，跳过"并 `exit 0`（安全）。

## 四、已知坑规避回顾（已固化进脚本）
1. 查残留只用 `Get-CimInstance`（CommandLine 精确匹配），绝不用 `Get-NetTCPConnection`（8777 归 PID 0 假象）。
2. 重拉命令复刻 `agnes_proxy._launch_studio`：`PY_BIN` + 相对脚本 + `cwd=仓库根` + `env REAL=1` + detached。
3. 加 studio 路由须同步 `STUDIO_PREFIXES` → `port_whitelist_check.ps1` 防漏（当前 0 缺漏）。
4. 补充指纹 `%python.exe server.py%` 精确限定裸脚本形态，避免误杀其他全路径 `server.py`（如 jianying-mcp）。

## 五、状态
- 开发自检完成，状态机推进至「待验证(开发自检完)」，待测试角色独立验收。开发无 done 权。
