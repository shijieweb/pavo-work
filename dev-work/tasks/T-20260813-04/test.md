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
