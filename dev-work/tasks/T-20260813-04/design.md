# T-20260813-04 设计（design）

## 1 取消鉴权（commit dec5ce9）
- 删除 5 处闸门代码：注释块 / `PORTAL_TOKEN` 模块级读取 / `_is_protected` / `_authorized`+`_guard` / 4 处 `do_*` 守卫调用。
- 验证：`py_compile` 通过；grep 残留为空；`git diff` = 34 行纯删除。
- 效果：恢复 T-20260813-03 之前的行为（全开放）。

## 2 系统自启（schtasks onlogon）
- 脚本：`short_drama_workflow/ops/start_portal.bat`
  - 托管 python 绝对路径（`~/.workbuddy/binaries/python/versions/3.13.12/python.exe`）
  - `cd` 到仓库根 → 运行 `agnes_proxy.py` → 崩溃后 3s 自动重启循环
  - 日志追加 `logs/portal_service.log`
- 任务：`AgnesPortal`（`schtasks /create /tn AgnesPortal /tr "<bat>" /sc onlogon /f`）
  - 登录自启，独立于 agent 会话 → agent 掉线 8787 仍存活
- 切换流程：杀旧后台代理（PID 6336）→ 确认端口释放 → `schtasks /run` 触发 → 验证新 PID（26296）持有 8787

## 3 残余风险（老板已接受）
- 公网隧道 `agnes.owen1.de5.net` 无鉴权可达（本地单人使用，接受）。
- 如需恢复鉴权：重新加 `PORTAL_TOKEN` 读取 + 守卫（commit 2c2e0f6 可作参考）。
