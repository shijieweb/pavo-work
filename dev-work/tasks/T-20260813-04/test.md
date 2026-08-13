# T-20260813-04 测试（test）

> 全部由主理人主会话实测（子 agent 静默空返回，按 SOP §3.6 接管）。

## 一、鉴权取消（AC-1 ~ AC-3）

| 命令（localhost:8787） | 期望 | 实际 | 结果 |
|---|---|---|---|
| `GET /studio`（无 token） | 200 | `-> 200` | ✅ PASS |
| `GET /api/projects`（无 token） | 200 | `-> 200` | ✅ PASS |
| `PUT /api/spec`（无 token） | 非 401 | `-> 400 错误的请求`（业务层，非鉴权） | ✅ PASS |
| `GET /`（导航页） | 200 | `-> 200` | ✅ PASS |

## 二、系统自启（AC-4）

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 旧后台代理（PID 6336） | 终止 | 已终止，8787 释放 | ✅ |
| `schtasks /run AgnesPortal` | 任务启动 | 成功: 尝试运行 | ✅ |
| 8787 LISTEN 归属 | 新 PID（非 agent 会话） | `PID=26296 CMD=...python.exe agnes_proxy.py` | ✅ |
| 计划任务状态 | 就绪 | 就绪（onlogon） | ✅ |

## 三、内部自愈（AC-5）

| 命令 | 期望 | 实际 | 结果 |
|---|---|---|---|
| `GET 127.0.0.1:8777/api/projects` | 200 | `-> 200` | ✅ PASS |

## 结论
AC-1~5 全 PASS。鉴权取消生效、8787 由 schtasks 体系托管（登录自启、agent 掉线存活）、内部链路正常。

## 四、rev2 事故修复（2026-08-13 17:30 补测）

### 事故
- 初版 `start_portal.bat` 直接 `python agnes_proxy.py`（前台循环），`AgnesPortal` 是 onlogon **交互式任务**——手动 `/run` 触发的进程挂在触发会话（一次性 PowerShell）的进程树上；**触发会话结束 → 任务被 Ctrl+C 终止 → python 子进程连带被杀 → 8787 失联**（portal_service.log 尾部 `portal starting...` + `^C` 铁证）。
- 主理人上轮只验证了"LISTEN + 新 PID"，**未验证"父会话结束后仍存活"**——验证不充分，向老板如实认责。

### 修复（rev2，commit 5b5e1aa）
- bat 改为 `Start-Process` 启动 python（独立进程）+ bat 自身秒退 → 任务立即"完成"，不再持有 python 进程树；python 独立存活。

### rev2 实测（触发会话已结束后复验）
| 检查项 | 结果 |
|---|---|
| 触发后 T+4s | ✅ 8787 LISTEN PID=21120 |
| **T+19s（父会话已结束）** | ✅ 仍存活，`GET /studio → 200` |
| 归属 | schtasks → Start-Process 独立 python（CMD=`...python.exe agnes_proxy.py`） |

### 回归基线（rev2 独立进程·注册表收敛前）
GET `/` `/studio` `/board` `/console` `/api/projects` `/logs` `/hub` 全 **200**；`PUT /api/spec → 400`（业务层）；`PUT /board/api/projects → 404`（board 无该项目）。
