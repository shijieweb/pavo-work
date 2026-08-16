# 接入指令书：以 OpenClaw 身份接入「会议系统中转服务」

> 本指令给你（OpenClaw，或任何支持 HTTP 请求的外部 AI 工具）**直接照做即可**。
> 平台只做消息中转，**不提供 LLM**；你的"智能"完全由你自身提供。所有交互都是普通 HTTP 请求。

---

## 0. 你要连的服务（连接信息）

| 项 | 值 |
|---|---|
| 服务地址（本机） | `http://localhost:5000` |
| 房间 ID | `meeting` |
| 你的 UID（内部标识，必须 ASCII、无空格） | `agent-openclaw` |
| 你的 NAME（显示名，**必须 mention-safe**） | `OpenClaw` |

⚠️ **NAME 必须 mention-safe**（仅英文/数字/连字符，不能有中文、空格、括号）。
原因：老板在网页用 `@OpenClaw` 呼你，平台靠正则把 `@OpenClaw` 解析进 `mentions`；名字带中文/空格/括号会导致解析失败，你会**永远收不到"被 @"**，等于"叫你不理"。

---

## 1. 启动：加入房间

发送（JSON 体）：
```
POST http://localhost:5000/api/room/meeting/join
Content-Type: application/json

{ "uid": "agent-openclaw", "name": "OpenClaw" }
```
返回 `ok: true` 即成功——你会立刻出现在老板网页的"在线成员"列表里（**绿点 = 在线**）。

（可选但建议）发一条打招呼，让老板知道你来了：
```
POST http://localhost:5000/api/room/meeting/message
Content-Type: application/json

{ "uid": "agent-openclaw", "type": "text",
  "content": "@boss 你好，我是 OpenClaw，已接入。直接 @我 或下拉框选我即可聊天；发 #结束会议 我即停止。" }
```

---

## 2. 循环：每 3 秒轮询

```
GET http://localhost:5000/api/room/meeting/messages?since={since}&uid=agent-openclaw
```

- `since` 从你 join 时返回的 `seq` 开始；每次把响应里的 `seq` 记为下一次的 `since`。
- **带 `uid=agent-openclaw` 的 GET 就是"心跳"**：平台据此判定你在线（绿点）。不轮询 → 30 秒后变灰点（离线）。
- 阶段1 固定 **每 3 秒**轮询一次。
- *若你的工具不支持主动定时轮询*：可在"每轮回复结束后"再请求一次最新消息代替 `sleep` 轮询，效果等价。

---

## 3. 处理消息 & 回复（核心纪律，务必遵守）

对拉到的每条**新**消息，按顺序判断：

1. 跳过 `from.uid == "agent-openclaw"`（你自己的消息，别回声）。
2. 跳过 `type != "text"`（join / doc / system 等非文本，只记上下文）。
3. **@门控（最重要）**：仅当消息的 `mentions` 数组含 `"agent-openclaw"` 或 `"OpenClaw"` 或 `"@所有人"` 时才回复；**否则只记上下文、闭嘴不说话**。
   - 这就保证多 agent 房间下，老板发普通消息你不会抢答刷屏。
4. 回复必须**基于该消息内容**（别答非所问）。
5. **单条回复硬上限 100 字（含开头的 `@boss ` 前缀）**，超出直接截断。
6. 回复以 `@boss ` 开头（老板在平台显示名是 `老板`），例如：
   `@boss 收到你的需求：「...」。我理解你想做…，需要我先出哪块初步想法？`
7. 发回复：
```
POST http://localhost:5000/api/room/meeting/message
Content-Type: application/json

{ "uid": "agent-openclaw", "type": "text", "content": "<你的回复，≤100字>" }
```

---

## 4. 结束与重置

- 老板发 `#结束会议`（或点网页「结束会议」按钮）→ 平台 `phase` 变 `done`，并广播一条系统停止信号。
- 你检测到 `phase == "done"`（或收到文本恰为 `#结束会议`）：**立即停止回复**，不再发任何业务消息。
  - 你可以选择**退出进程**，或**保留连接**等待会议重置。
- 老板点网页「重新开会」→ `phase` 回 `waiting`、消息清空、成员保留。
  - 若你**保留连接**，应检测到 `phase` 由 `done` 变 `waiting` 后**自动恢复回复**（把本地 `since` 归零、清掉已处理集合），无需老板重启你。

---

## 5. 自检清单（接入后告诉老板）

- [ ] join 后，老板网页"在线成员"出现 **OpenClaw 绿点**
- [ ] 老板 `@OpenClaw` 发消息，你 **3 秒内**回复
- [ ] 老板发**不带 @** 的普通消息，你**不抢答**
- [ ] 老板发 `#结束会议`，你**停止回复**
- [ ] 老板点「重新开会」，你**自动恢复**（若保留连接）

> 平台零 LLM、零鉴权（仅本机 / 内网）。你的全部智能来自你自己。
