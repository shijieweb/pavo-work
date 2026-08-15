# 会议系统 · server.py 阶段1 兼容性评估

> 评估对象：`会议系统/server.py`（原 .qclaw 团队开发的中转服务）
> 评估基准：`会议系统/docs/阶段1_需求简报.md` 的 AC-1 ~ AC-7
> 评估方法：① 通读源码 ② 实弹 smoke test（系统 Python 3.14 + Flask 3.0，`app.test_client()` 实测路由）
> 日期：2026-08-16

---

## 一、结论（一句话）
**server.py 的架构（Flask 单体中转 / 纯 HTTP / 内存态 / 无鉴权 / 房间参数化）与阶段1 既定方向完全契合，无需重写。**
核心链路（接入 / 双向聊天 / 单房间 / 不调 LLM / 进入提示）已原生支持；
**仅需在现有文件上补 3 处小补丁**，即可 100% 覆盖 AC-1 ~ AC-7。

---

## 二、AC 逐项对照（✅ 已支持 / ⚠️ 部分支持 / ❌ 需改）

| # | 验收标准 | 状态 | 证据（源码 / 实测） |
|---|---|---|---|
| **AC-1 接入成功** | ✅ | `POST /join` 加成员并返回 `members[]`；实测 boss+agent 均入列 | server.py L126-162；smoke 实测 members 含"老板/OpenClaw" |
| **AC-2 双向聊天** | ✅ | `POST /message` + `GET /messages?since=` 收发；网页 `/` 可发可收 | server.py L165-200；smoke 实测 4 条消息往返 |
| **AC-3 结束即停** | ⚠️ | ① 网页**无结束按钮**（仅输入框）；② 仅精确 `/结束会议` 触发，`结束会议`(无斜杠) 不触发（A3 要求可配关键词）；③ 停止靠 agent 轮询发现 phase=done，无显式"停止信号"消息 | L43-49 / L188-193 精确匹配；smoke 实测：`结束会议`(无斜杠)→phase 仍 `waiting`，`/结束会议`→`done` |
| **AC-4 单房间群聊** | ✅ | `room_id` 入参，结构支持多房间；阶段1 单房间直接用 | 所有路由带 `<room_id>` |
| **AC-5 平台不调 LLM** | ✅ | 全文件零 LLM 调用，纯转发 | 通读确认 |
| **AC-6 上线状态** | ❌ | 成员对象仅 `{uid,name,seq_num}`，**无 online 字段 / 无 last_seen / 无心跳**；一旦 join 永不离线 | L93-97 `public_members`；smoke 实测 member keys=`name,seq_num,uid` |
| **AC-7 进入提示** | ✅ | join 时自动插入 `type="join"` 系统消息"X 加入了会议"，网页绿字渲染 | L148-151 + 网页 L279 |

**小结：5 ✅ / 1 ⚠️ / 1 ❌** → 架构可用，2 项需补代码。

---

## 三、必须修改的 3 处（阶段1 上线前置）

### 补丁 A — AC-6 上线 / 离线状态（server.py）
- 成员结构加 `last_seen = time.time()`；在 `join` / `send_message` / `get_messages`（任何活动）时刷新。
- `public_members` 增加 `online` 字段：`online = (now - last_seen) < 阈值(默认30s)`。
- 新增显式 `/api/room/{room_id}/leave`（可选）或 phase=done 时标记离线。
- 网页成员列表：按 `online` 渲染绿点 / 灰点。
- 工作量：server.py ~15 行 + 网页样式 ~5 行。

### 补丁 B — AC-3 结束触发（双触发 + 可配关键词）
- 网页加「结束会议」按钮 → 点击即 `POST /message` 内容为 `/结束会议`（或新增专用 `/api/room/{room_id}/end`）。
- `/message` 处理里，在精确 `/` 命令之外，增加对**可配置关键词**（默认 `"结束会议"`）的匹配：命中即 `phase="done"`（满足 A3 可配）。
- 可选增强：phase 置 done 时，额外插入一条 `type="system"` 停止消息，让 agent 明确收到停止信号（当前靠轮询发现 done 已可用，补一条更稳，对应 R3 兜底）。
- 工作量：server.py ~10 行 + 网页按钮/JS ~15 行。

### 补丁 C — R3 停止可靠性兜底（与补丁 A 合并）
- HTTP 无长连接，平台无法主动断 agent；停止完全依赖 agent 侧遵守 §7（见 agent_skill.md）。
- 平台侧只需靠补丁 A 的 `last_seen` 超时把成员标灰，作为"已停"的可见证据；超时阈值建议 30s（与 A 同源）。
- 无需额外代码，随补丁 A 落地。

---

## 四、建议增强（非必须，留待联调时按需）
- 网页：消息流区分"系统提示"样式（AC-7 已能用，样式可优化）。
- `agent_skill.md` 已重写（见同目录）为**通用 HTTP 协议**，覆盖 §3 轮询 / §4 @纪律 / §7 停止，与各工具实现解耦。
- 内存态重启即丢：阶段1 本机调试可接受；后续若需持久化再引 SQLite（不影响当前）。

---

## 五、架构结论
- **不用重写、不用换框架、不用加 WebSocket**：老板定的"通用 HTTP"方向与原 server.py 天然一致。
- 阶段1 实际开发量 = 在 `server.py` 打 2 处小补丁（上线状态、结束触发）+ 网页加按钮/状态点，约 40~50 行。
- 另有 `agent_client.py` / `boss_driver.py` / `agent_a.py` / `agent_b.py` / `*.ps1` / `msgs*.json` 为原团队**演示与诊断脚本**，阶段1 不必依赖；正式接入由外部工具照新 `agent_skill.md` 直连。

---

*由主理人（阿编）基于实弹路由测试产出 · 2026-08-16*
