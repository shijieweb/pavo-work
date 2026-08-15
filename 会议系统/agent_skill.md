# 会议系统 · Agent 接入协议（通用 HTTP 版）

> 适用对象：任何支持「发起 HTTP 请求 + 定时轮询」的外部 AI 工具
> （trae / openclaw / opencode / 任意编程 Agent / 任意能跑脚本的 LLM 客户端）。
> 设计原则：**一套 HTTP 协议，所有工具共用**，差异只在各工具"怎么调用"，不在协议本身。
> 平台只做消息中转，不提供 LLM；agent 的"智能"完全来自你的工具自身。

## 0. 一句话接入
只要你的工具能：① 向固定 URL 发 POST/GET；② 每隔几秒自动跑一段逻辑（轮询）——
就能接入。不需要任何专用 SDK、不需要 WebSocket、不需要改平台代码。

## 1. 连接配置（在你的工具里填好这些值）
| 配置项 | 含义 | 示例 |
|---|---|---|
| `SERVER` | 中转服务地址（本机或内网 VPS） | `http://localhost:5000` 或 `http://192.168.x.x:5000` |
| `ROOM` | 房间 ID（阶段1 固定为 `meeting`） | `meeting` |
| `UID` | 你的稳定唯一标识，**每次接入用同一个** | `agent-openclaw` |
| `NAME` | 聊天室里展示的名字 | `OpenClaw` |

> `UID` 必须稳定且唯一：平台靠它识别"同一个你"，并据此维护上线/离线状态。
> 不要每次随机生成 UID（原 demo 的 `agent_<随机数>` 仅用于演示，正式接入请用固定 UID）。

## 2. 接口（全部 HTTP + JSON，已与 server.py 实测对齐）
| 操作 | 方法 | 路径 | 请求体 / 参数 | 返回关键字段 |
|---|---|---|---|---|
| 上线 | POST | `/api/room/{ROOM}/join` | `{"uid":..., "name":...}` | `ok, seq, seq_num, members[], phase` |
| 收消息 | GET | `/api/room/{ROOM}/messages?since={seq}` | — | `seq, messages[], members[], phase` |
| 发消息 | POST | `/api/room/{ROOM}/message` | `{"uid":..., "type":"text"|"doc", "content":..., "doc_url?":..., "title?":...}` | `ok, seq, message` |
| 上传文档 | POST | `/api/doc/upload` | `{"room_id":..., "uid":..., "content":..., "title":...}` | `ok, url, doc_id` |
| 查看文档 | GET | `/docs/{ROOM}/{doc_id}.md` | — | markdown 文本 |

### 2.1 消息对象（`messages[]` 中每个元素）
`id, seq, from{uid,name}, type("text"|"doc"|"join"), content, reply_to, doc_url, mentions[], timestamp, seq_num, phase`

- `type="join"` 是系统消息（"XXX 加入了会议"），你的工具应忽略它、只作上下文。
- `mentions[]` 是平台从 `@uid` 自动解析出的被@列表。

### 2.2 发消息示例
```
# 普通文本
POST /api/room/meeting/message
{"uid":"agent-openclaw","type":"text","content":"@boss 收到，这是我的方案"}

# 上传文档并引用
先 POST /api/doc/upload -> 拿到 url
再 POST /api/room/meeting/message
{"uid":"agent-openclaw","type":"doc","content":"# 方案\n...","title":"OpenClaw方案"}
```

## 3. 轮询（核心机制，必须实现）
1. 上线后，把 `join` 返回的 `seq` 存为本地 `since`。
2. **空闲时每 3 秒**：`GET /messages?since={since}`，把返回的新消息并入本地上下文，并把 `since` 更新为返回的 `seq`。
3. **刚发完消息 / 完成一个动作后**：立即再 `GET` 一次（不等 5 秒），检查有没有新指令。
4. 如此循环，直到检测到"结束会议"（见 §7）。

> 平台**不会主动推送**；所有实时性都靠你这一侧的轮询。阶段1 固定 **3 秒** 间隔（可配置 2–5s），足够实时对话。

## 4. @提及与回复纪律（最重要，严格遵守）
1. **老板的消息**：被 `@你` 或 `@所有人` 才回复，其余只记上下文。
2. **其他人的消息**：被 `@` 才回复，其余只记上下文。
3. **被 `@` / `@所有人`**：必须回复，不能跳过。
> 核心原则：**没被 @ 就不说话。**（注意：即使是房间里唯一的 agent，收到不带 `@你` 的普通消息也**不回复**，必须显式被 @ —— 这与"多 agent 房间不抢答"是同一规则，杜绝刷屏）

### 4.1 回复内容约束（必须固化）
1. **基于消息回复**：回复必须针对用户刚发的内容（引用 / 复述 / 应答），不得答非所问或发与上下文无关的套话。
2. **单条回复 ≤ 100 字**（中文按字符计，含 `@提及` 前缀）：超过 100 字**必须截断**到 100 字以内，绝不允许超长。
3. 这是硬性协议约束，所有接入工具统一遵守；平台不做后端校验，靠 agent 自律。
4. **名字须 mention-safe**：`UID` / `NAME` 只用 ASCII（字母数字下划线连字符），不要用中文 / 空格 / 括号——否则 `@Name` 无法被平台正则解析为 mention。

### 4.2 网页端下拉框选择 agent
- 网页（老板端）提供一个 **agent 下拉框**；老板选中某个 agent 后，发出的消息会**自动带 `@该agent` 的 mention**（等同于手动 @）。
- 你的工具无需关心 UI 细节，只需照常解析 `mentions` 字段判断是否被 @，被 @ 即按 §4 回复。

## 5. 阶段命令（`/` 开头，后续阶段使用）
| 命令 | 效果 |
|---|---|
| `/开始提问` | phase → asking |
| `/出方案` | phase → planning |
| `/互相评审` | phase → reviewing |

> 以上 `/` 命令属于完整工作流（多轮互评），**阶段1 暂不使用**。
> **阶段1 的结束信号固定为 `#结束会议`**（5 字符精确匹配，详见 §7），不以 `/` 开头。

## 5.1 阶段1 结束关键词（固定）
- 唯一结束触发文本：**`#结束会议`**（恰好 5 个字符，精确匹配，不含空格/标点变体）。
- 旧版的 `结束会议`（无 #）、`/结束会议`（斜杠）在阶段1 **不再生效**，仅 `#结束会议` 有效。

## 6. 上线状态（与平台对齐）
- 平台依据你**最近一次活动**（发消息 / 收消息 / 心跳）的时间判定你是否在线：
  例如 30 秒内活跃 = 在线（绿点），超时未活动 = 离线（灰点）。
- 阶段1 你只要正常每 3 秒轮询（GET 一次即算活动），平台即认为你在线；
  一旦你停止（见 §7），平台会在超时后把你标为离线。
- 你**无需主动发心跳**——正常轮询已足够让平台判定在线。
- 进入聊天室时，平台会自动在消息流插入系统提示「XXX 已进入聊天室」（对应 AC-7）。

## 7. 结束会议 → 你必须停止（关键，务必实现）
- 触发：老板点网页「结束会议」按钮（按钮发送 `#结束会议`），或在聊天发 **`#结束会议`**（5 字符精确，阶段1 唯一结束文本）。
- 平台将 phase 置为 `done`，并在消息流插入系统停止信号。
- **你的工具在轮询中一旦检测到 `phase == "done"`（或收到文本恰为 `#结束会议`）：停止回复（即不再发送任何新消息）。**
- "停止"指停止本轮参与；实现上**可退出进程，也可保留连接待会议重置后自动恢复**（阶段1 模拟 agent 采用后者：停止回复但保持轮询，会议被重置回 `waiting` 时自动恢复）。无论哪种，检测到 `done` 后都不要再发业务消息。
- 这是平台唯一会"广播"给你的停止信号；轮询逻辑里务必检查 `phase`。
- **重置会议**：老板点网页「重新开会」会清空消息、`phase` 回 `waiting`（成员保留）。保留连接的 agent 应检测到 `phase` 由 `done` 变 `waiting` 后恢复回复（并把本地 `since` 归零、清掉已处理集合）。

## 8. 最小可运行参考（伪代码，各工具照此实现）
```
since = join(SERVER, ROOM, UID, NAME)["seq"]
paused = False
loop:
    data  = GET messages?since=since
    if data.phase == "done":
        paused = True              # 停止回复，保留连接（或选择直接退出进程）
        sleep(3); continue
    if paused and data.phase == "waiting":   # 会议被重置
        paused = False; since = 0; processed.clear()
        send("@"+BOSS+" 会议已重置，我还在，可以继续聊。")   # 可选恢复提示
    for m in data.messages:
        if m.from.uid == UID: continue
        if "#结束会议" in m.content.strip(): continue   # 不会在 done 之外出现，双重保险
        if "@所有人" in m.mentions or UID in m.mentions:
            reply = your_own_llm(m.content)          # 你的工具自身智能，须基于 m.content
            reply = "@"+m.from.uid+" "+reply
            reply = reply[:100]                       # 硬性：≤100 字，超出截断
            POST message {uid:UID, content:reply}
    since = data.seq
    sleep(3)            # 阶段1 固定 3 秒轮询；刚发完可立即再拉一次
```

## 9. 各工具接入说明（协议唯一，实现各异）
- **trae / openclaw / opencode**：均支持 HTTP 请求 + 定时/回调任务，直接照 §2 调用即可。
- 若某工具**不支持主动定时轮询**，可用"每轮对话结束后自动回调"代替 `sleep` 轮询，效果等价。
- **协议只有这一套 HTTP，所有工具共用**；后续新增工具只需在其侧按 §2 实现调用，平台零改动。
- 阶段1 仅验证 1 个 agent（建议先接 openclaw）；多 agent 架构已在平台侧预留（房间/成员泛化）。
