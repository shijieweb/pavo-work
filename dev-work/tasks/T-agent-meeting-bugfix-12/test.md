# test.md · T-agent-meeting-bugfix-12 自测清单（第 1 轮 · 实现者自测）

> 实现轮自测：后端用隔离端口 **8011 + 独立 DATA_DIR** 跑 design §9 curl 套件；前端用 grep + `node --check` + 代码审查验证。
> 隔离命令（Windows / Git Bash）：
> ```
> cd /c/Users/67972/WorkBuddy/workbuddy/agent-meeting/server
> export DATA_DIR="D:/tmp/am-test-data"
> /c/Users/67972/.workbuddy/binaries/python/envs/default/Scripts/python -m uvicorn app.main:app --port 8011 --reload --reload-dir app
> ```
> 所有 curl 打 `http://localhost:8011`，数据落 `D:/tmp/am-test-data`，**未触碰生产 8000 的 `agent-meeting/server/data`**。

---

## F2 sender_type 锁 user（AC-2.1 / 2.2 / 2.3）— 后端 PASS

| AC | 命令 | 结果 | 判定 |
|---|---|---|---|
| AC-2.1 伪造 agent→422 | `curl -X POST :8011/api/messages/send -d '{"sender_type":"agent","content":"x","target_type":"all"}'` | HTTP **422** | PASS |
| AC-2.2 默认 user→200 且存 sender_type=="user" | `curl -X POST :8011/api/messages/send -d '{"content":"hello user","target_type":"all"}'` → 查 history | HTTP **200**；history 中该消息 `sender_type == "user"` | PASS |
| AC-2.3 非 user(admin)→422 | `curl -X POST :8011/api/messages/send -d '{"sender_type":"admin","content":"x","target_type":"all"}'` | HTTP **422** | PASS |

实测输出：
```
F2 forge agent -> 422
F2 default user -> 200   (history 校验 sender_type = user)
F2 non-user admin -> 422
```
实现：schemas.py `MessageSend.sender_type: Literal["user"] = "user"`，Pydantic 在解析阶段对非 user 返回 422，请求体不进入端点、不入库。

## F3 client_msg_id 幂等（AC-3.1 / 3.2 / 3.3）— 后端 PASS / 前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-3.1 前端携带非空 client_msg_id | grep `app.js` 有 `client_msg_id: genClientMsgId()`；`genClientMsgId()` 生成 `usr_<uuidv4>` | 存在 | PASS（前端代码） |
| AC-3.2 后端幂等去重 | 同 `client_msg_id` 连续 `POST /send` 两次 → `messages.json` 计数 | 两次均 200，`messages.json` 中该 `client_msg_id` 仅 **1** 条 | PASS |
| AC-3.3 重试不重复 | 依赖 AC-3.2 + 前端 `insertedIds` 去重 | `message-list` 仅 1 气泡（前端行为，QA 轮浏览器确认） | PASS（代码级） |

实测：
```
register WorkBuddy: 200   register Claude: 200
F3 first send  (client_msg_id=usr_<uuid>) -> 200
F3 duplicate   (same client_msg_id)       -> 200
  messages.json 中该 client_msg_id 计数: 1
```

## F4 失败无幽灵消息（AC-4.1 / 4.2）— 前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-4.1 失败不残留气泡 | `app.js` `sendMessage`：`if (!res.ok) { input.value=''; return; }` 且失败路径不 `appendMessage` | 代码确认：失败时仅清输入框并 return，不追加气泡 | PASS（代码级） |
| AC-4.2 输入框清空 | 同上 `input.value = ''` | PASS | PASS（代码级） |

> 浏览器级 DOM 计数验证移交 QA 第 2 轮（前端交互需真实 DOM）。

## F5 有界 read 轮询（AC-5.1 / 5.2）— 前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-5.1 请求 limit≤200 | grep `app.js`：`fetch('/api/messages/history?limit=200')`；无 `limit=10000` | PASS（无 `limit=10000`，改为 200） |
| AC-5.2 已读徽标仍刷新 | 逻辑保留（仅改 limit；原地刷新 read 徽标逻辑不变） | PASS（代码级，QA 轮浏览器确认） |

## F6 下拉框动态刷新（AC-6.1 / 6.2）— 后端+前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-6.1 新 Agent 入下拉 | 后端 `POST /api/agents/register NewAgent` 后 `GET /api/agents` | 返回 `['WorkBuddy','Claude','NewAgent']`；前端 `init()` 已 `setInterval(loadAgents, 30000)` | PASS |
| AC-6.2 既有 Agent 不丢失 | `loadAgents` 刷新前存 `select.value`，重建 options 后还原（若仍含） | 代码确认保留选中值 | PASS（代码级） |

实测：
```
/api/agents/status -> ['WorkBuddy','Claude']
/api/agents        -> ['WorkBuddy','Claude']
register NewAgent  -> 200
/api/agents 再查   -> ['WorkBuddy','Claude','NewAgent']
```

## F7 set_session 注册校验（AC-7.1 / 7.2）— 后端 PASS

| AC | 命令 | 结果 | 判定 |
|---|---|---|---|
| AC-7.1 未注册→400 无幽灵 | `curl -X POST :8011/api/agents/NotRegistered/session?active=false` | HTTP **400** `{"detail":"agent not registered: NotRegistered"}`；`agents.json` 未新增该名 | PASS |
| AC-7.2 已注册→200 | `curl -X POST :8011/api/agents/WorkBuddy/session?active=true` | HTTP **200**；`/api/agents/status` 该 agent `session==true`/`status==working` | PASS |

实测：
```
F7 unregistered -> {"detail":"agent not registered: NotRegistered"} [400]
F7 registered WorkBuddy active=true -> {"status":"ok","session":true,"has_unread":true} [200]
  status: {'name':'WorkBuddy','last_seen':'...','status':'working','session':True}
```

## F8 I-10 软保护（AC-8.1 / 8.2 / 8.3）— 后端 PASS

| AC | 命令 | 结果 | 判定 |
|---|---|---|---|
| AC-8.1 响应含 has_unread | `POST /api/agents/WorkBuddy/session?active=false` 返回体 | 含 `"has_unread": <bool>` | PASS |
| AC-8.2 不阻断收工 | `has_unread=true` 时仍 HTTP **200**，`session==false`/`status==offline` | PASS |
| AC-8.3 未读判定真实 | 发 @WorkBuddy → set_session → `has_unread=true`；pull 一次 → set_session → `has_unread=false` | PASS |

实测：
```
F8 send @WorkBuddy single -> 200
F8 set_session end (before pull) -> {"status":"ok","session":false,"has_unread":true} [200]
F8 pull WorkBuddy (mark read)    -> 200
F8 set_session end (after pull)  -> {"status":"ok","session":false,"has_unread":false} [200]
  WorkBuddy after end: {'name':'WorkBuddy','status':'offline','session':False}
```
实现：`agents.py` 调新增只读函数 `message_store.agent_has_unread(name)`（逻辑同 pull_messages 未读判定，含 reads.json 种子，只读不写）。

## F9 动态文案（AC-9.1 / 9.2）— 前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-9.1 状态文案用真实名 | grep `app.js` 无 `'阿编'` 硬编码；`loadAgentStatus` 用 `${name}·处理中` | PASS（无 '阿编'） |
| AC-9.2 全部状态态用动态名 | 待命/已收工/离线/掉线 四类均 `${name}·...` | PASS（代码级） |

## F10 空页面跳过轮询（AC-10.1 / 10.2）— 前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-10.1 空聊天不发请求 | `app.js` `refreshReadReceipts` 开头 `if (readStatusNodes.size === 0) return;` | PASS（代码级，QA 轮浏览器确认） |
| AC-10.2 有消息则恢复 | 出现 user 消息后 `readStatusNodes` 非空，轮询恢复 | PASS（代码级） |

## F11 回复长度（AC-11.1 / 11.2 / 11.3）— 后端 PASS（硬红线）

> 方案①：`config.REPLY_MAX_LEN = 4000`；`reply` 对 `>4000` 返回 400，否则全接受。

| AC | 命令 | 结果 | 判定 |
|---|---|---|---|
| AC-11.1 ~500 字长回复必过（硬红线） | `curl -X POST :8011/api/messages/reply -d '{"agent_name":"WorkBuddy","content":"<500×a>"}'` | HTTP **200**；history 中消息 `content` 长度 **500**、`sender_type=="agent"` | PASS |
| AC-11.2 方案① | `REPLY_MAX_LEN=4000`；500→200；5000→400 | PASS |
| AC-11.3 严禁 `len>100` 简单拒 | grep 全后端 `len(content) > 100` | **无匹配**（PASS） |

实测：
```
F11 reply 500 chars -> 200  (history 校验: sender_type=agent, len=500)
F11 reply 5000 chars -> 400  {"detail":"reply too long: 5000 > REPLY_MAX_LEN (4000)"}
grep 全库 "len(content) > 100": NO (PASS)
```

## F12 新增 /cleanup 端点（AC-12.1 / 12.2 / 12.3 / 12.4）— 后端 PASS

| AC | 命令 | 结果 | 判定 |
|---|---|---|---|
| AC-12.1 端点+统计 | `curl -X POST :8011/api/messages/cleanup -d '{"keep_last":10}'` | HTTP **200** `{"status":"ok","archived":N,"remaining":M}` | PASS |
| AC-12.2 按条数 | 17 条 → `keep_last=5` → `archived:12, remaining:5`；history 计数=5 | PASS |
| AC-12.3 按时间 | `older_than=2099-01-01` → `archived:4, remaining:0`（早于阈值全移除） | PASS |
| AC-12.4 不影响主流程 | cleanup 后 `send`→200、`history`→200 | PASS |

实测：
```
messages before: 17
F12 keep_last=10          -> {"status":"ok","archived":0,"remaining":4} [200]   (仅4条，无移除)
F12 both-missing {}       -> {"detail":"provide keep_last or older_than"} [400]
F12 older_than future     -> {"status":"ok","archived":4,"remaining":0} [200]
--- strong case ---
count before: 17
F12 keep_last=5           -> {"status":"ok","archived":12,"remaining":5} [200]
count after : 5   history after: 5
F12 AC-12.4 send   -> 200
F12 AC-12.4 history -> 200
```
实现：`message_store.cleanup_messages(keep_last, older_than)` 用 `update_json_atomic` 在锁内按 `(created_at, 原数组下标)` 升序排序计算保留集，并清理 `reads.json` 孤儿回执；`archived`=移除条数。

## F1 状态显示不硬编码（AC-1.1 / 1.2 / 1.3 / 1.4）— 后端+前端代码 PASS

| AC | 验证 | 结果 | 判定 |
|---|---|---|---|
| AC-1.1 多 Agent 状态接口可用 | `GET /api/agents/status` | 返回含多元素数组，各带 name/last_seen/status/session | PASS |
| AC-1.2 不再写死名字过滤 | grep `app.js` 无 `a.name === 'WorkBuddy'`、无 `'WorkBuddy'` 名匹配 | PASS |
| AC-1.3 非 WorkBuddy 状态可见 | `loadAgentStatus` 遍历全 agent 在 `#agent-status` 动态渲染 | PASS（代码级，QA 轮浏览器确认） |
| AC-1.4 多 Agent 各自独立 | 同一接口多 agent，前端逐个渲染 | PASS（代码级） |

---

## 全局 grep 红线校验（对应设计 §10.2 / PRD 第四节）

| 检查项 | 命令 | 结果 |
|---|---|---|
| app.js 无 `'阿编'` 硬编码文案 | `grep -q "阿编" app.js` | 无 → PASS |
| app.js 无 `'WorkBuddy'` 名字匹配 | `grep -q "a.name === 'WorkBuddy'" app.js` | 无 → PASS |
| app.js 无 `limit=10000` | `grep -q "limit=10000" app.js` | 无 → PASS |
| 后端无 `len(content) > 100` | `grep -rq "len(content) > 100" app/` | 无 → PASS |
| app.js 语法 | `node --check app/static/app.js` | SYNTAX OK → PASS |

## 生产 8000 污染检查（红线③）

| 检查项 | 结果 |
|---|---|
| 隔离实例数据落点 | `D:/tmp/am-test-data`（5 条残留：m11–m15；agents: WorkBuddy/Claude/NewAgent） |
| 生产 `agent-meeting/server/data/messages.json` 是否含测试标记 | grep `F8 unread probe`/`post-cleanup send`/`dup test`/`hello user`/`m1`/`m15`/`NewAgent` 全部 **0 命中** → 未污染 |
| 生产无 `agent_read_NewAgent.json` | 确认不存在（NewAgent 仅注册在隔离 8011） |
| 8011 实例已停止 | `curl :8011` → 000 不可达 |

---

## 结论

- 后端 12 项 AC（F2/F3.2/F7/F8/F11/F12 全部，F1.1/F6 后端部分）均通过**真实 curl + 真实输出**验证。
- 前端 F1/F3/F4/F5/F6/F9/F10 通过 **grep 红线校验 + `node --check` 语法 + 代码审查** 验证；浏览器级 DOM 交互（AC-1.3/3.3/4.1/5.2/6.1/9.1/10.1 等）按 3 轮协议移交 **QA 第 2 轮**确认。
- 所有自测均在隔离端口 8011 + 独立 DATA_DIR 完成，**生产 8000 数据零污染**（已用测试标记 grep 证伪）。
- 与设计的偏差：无功能性偏差；仅将 `messages.py` 的 `MessageCleanup` 模型内联定义（设计即要求"内联"），并补充 `from app.models.schemas import ... BaseModel`（运行必需，设计未显式列出但属实现细节）。
