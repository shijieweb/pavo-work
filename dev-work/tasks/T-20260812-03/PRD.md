# PRD · T-20260812-03 运维脚本工作流（不建角色·固化为脚本）

> 模板：`dev-work/templates/TEMPLATE_PRD.md`。阿编填写，闸1 主理人自签（老板 2026-08-12 授权：纯内部工具化任务，不影响需求基线，主理人可自签）。
> 背景：老板定「所有能脚本化的全部脚本化、形成工作流；运维/部署只有固化不成脚本工作流才加角色」。本任务把历史踩坑点（8777 干净重启 / 端口白名单同步 / 部署）固化为 `short_drama_workflow/ops/` 脚本包，**不建运维角色**——日常全脚本化、一次性手动（VPS 首装）可接受。

- **需求基线闸：主理人自签 ☑（老板 2026-08-12 授权：内部工具化、不改产品需求基线）**
- **目标**：交付 `short_drama_workflow/ops/` 脚本包（干净重启 / 健康检查 / 端口白名单自检 / 部署骨架），把运维从"主理人临场救火"变成一键脚本。全程零 AGNES 额度。
- **关联**：历史坑见 `agnes_proxy.py` + `dev-work/MEMORY.md`（8777 脏重启 / PUT 501 / STUDIO_PREFIXES 不同步）。

---

## 一、功能清单

- F1 `clean_restart_studio.ps1`：干净重启 8777 工作台（查残留→杀→确认无监听→按 agnes_proxy 原命令重拉→核实新 PID）。
- F2 `healthcheck.ps1`：探活 8777/8787/8788 三端口 HTTP 200。
- F3 `port_whitelist_check.ps1`：比对 `agnes_proxy.py` 的 `STUDIO_PREFIXES` 与 studio 实际路由，报告缺漏（防"加路由忘加白名单"）。
- F4 `deploy.ps1`：rsync 到 VPS（host 可配，未配安全跳过）+ 远程起服务 + healthcheck；O5 未 provisioned 时仅 `--check` 验证不误杀本地。
- F5 `README.md`：用法 runbook。

## 二、需求清单（AC 锚点）

- [ ] AC-1.1 `clean_restart_studio.ps1` 查 8777 全部 studio 进程用 `Get-CimInstance Win32_Process`（CommandLine like `%html_prototype%server.py%`，**不用 netstat 假象**）→ 逐一 `Stop-Process -Force` → 确认 8777 无 Listening → 用与 agnes_proxy 相同命令重拉（`PY_BIN short_drama_workflow/html_prototype/server.py`，cwd=仓库根，env `REAL=1`，detached）→ 核实新 PID 已绑定 8777。幂等可重复。
- [ ] AC-1.2 `healthcheck.ps1` 探活 8777/8787/8788（含 `/api/projects` 真实探活），输出每端口状态（up/down + 耗时）。
- [ ] AC-1.3 `port_whitelist_check.ps1` 解析 `agnes_proxy.py` 的 `STUDIO_PREFIXES` 与 studio 路由，报告缺漏（任何 studio 路由不在白名单 → 告警，防 PUT 501/404）。
- [ ] AC-1.4 `deploy.ps1`：host 从 env/参数读，未配置则安全跳过并提示；`deploy --check` 模式可安全验证脚本逻辑不误杀本地；远程起服务 + 跑 healthcheck。O5 未 provisioned 时仅验证脚本不报错退出。
- [ ] AC-1.5 全部脚本幂等、可重复执行；**零 AGNES 额度**；测试角色实跑验证（clean_restart 真重启 8777 并 healthcheck 回绿；healthcheck/whitelist 真实输出正确；deploy --check 安全通过）。
- [ ] AC-1.6 附 `ops/README.md` runbook，列各脚本用法与"何时跑哪个"。

## 三、产出路径

- 新增：`short_drama_workflow/ops/{clean_restart_studio,healthcheck,port_whitelist_check,deploy}.ps1` + `ops/README.md`
- 不动：`agnes_proxy.py` / `server.py` 业务逻辑（除非 AC-1.3 发现白名单缺漏需补——那属 P0 类 bug，提单走流程，不在本任务改）。

## 四、边界与禁止项

- 禁止：误杀非 studio 进程（必须用 CommandLine 精确匹配 `%html_prototype%server.py%`）；禁止烧 AGNES 额度（纯进程/端口管理）。
- 已知坑（主理人提示）：
  1. `Get-NetTCPConnection` 常把 8777 归 PID 0（假象），必须用 `Get-CimInstance Win32_Process` 按 CommandLine 查。
  2. 重启命令必须复刻 agnes_proxy 的 `_launch_studio`：`PY_BIN= C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe`，script=`short_drama_workflow/html_prototype/server.py`，cwd=仓库根，env `REAL=1`。
  3. 加 studio 路由后必须同步加 `STUDIO_PREFIXES`（agnes_proxy.py:45 起），否则经 8787 访问 404/501。

## 五、闸1 签核（主理人自签 · 老板 2026-08-12 授权）

- 主理人确认验收标准（逐条）：☑ 已自签（纯内部工具化，依授权自主推进）
- 备注：依老板"不影响需求你可自己做主"，本任务主理人自签闸1 并派开发实现、测试实跑验证，不建运维角色。
