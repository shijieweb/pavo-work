# 本地看板归档说明（可随时重启）

> 状态：**已归档 / 冻结开发 / 服务可随时重开**。A 方案（飞书多维表格）为后续主线，
> 本地看板作为可回退的备份与富文档后台保留，**不删除、不禁用**。

## 架构与端口
- `8777` = studio 工作台（`short_drama_workflow/server.py`）
- `8787` = agnes_proxy 统一门户（hub 控制台 + 反代 8777/8788）
- `8788` = 任务看板（`shared_board/index.html` 由 8787 `/board` 反代）

## 自启任务（已就绪）
- Windows 计划任务：`AgnesPortal`（登录时触发，Start-Process 独立进程，rev2）
- 查询：`schtasks /query /tn AgnesPortal`
- 手动（重）启动：`schtasks /run /tn AgnesPortal`
- 停止：`schtasks /end /tn AgnesPortal`

## 当前健康（归档时）
- 端口 8777/8787/8788 均处于 LISTEN（PID 29144/29296/13040）
- 最近归档提交：`e218874 archive: 本地看板归档快照 + 飞书推送/迁移准备`

## 重启标准动作
1. 确认端口是否还在：
   `powershell -Command "Get-NetTCPConnection -LocalPort 8777,8787,8788 | Where State -eq Listen"`
2. 若不在，启动：`schtasks /run /tn AgnesPortal`
3. 浏览器访问 `http://localhost:8787`（门户）/ `http://localhost:8788`（看板）

## 注意
- 不要删 `schtasks AgnesPortal`，否则失去开机自启。
- 代码改动务必先 `git commit`（参考团队纪律 `before:` 提交）。
- 外网暴露（VPS / 公网）暂不启用，仅本机 + 局域网使用。
