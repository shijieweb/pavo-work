
# 项目可行性与技术实施方案书

> 项目名称：本地多 Agent 群聊网页端（Agent Hub）  
> 版本：v1.0（MVP）  
> 日期：2025-01-01

---

## 一、项目背景与需求

### 1.1 目标
将多个运行在本地电脑上的 AI Agent 工具接入同一个网页端，通过群聊方式与它们交互。用户发送消息时通过下拉框指定某个 Agent 或 @所有人，被指定的 Agent 自动获取消息并回复，所有对话集中展示在同一个聊天时间线中，并具备已读回执状态。

### 1.2 核心用户
仅用户本人，单人使用。

### 1.3 MVP 范围
- 先接入 1 个本地 Agent，跑通“@ → 拉取消息 → 处理 → 推送回复 → 前端展示”完整链路。
- 数据先使用本地 JSON 文件保存，后续再扩展数据库与多聊天窗口。

### 1.4 后续演进
- 支持多个 Agent 同时接入
- 支持协作、对抗、辩论
- 多个聊天窗口
- 数据量增大后引入数据库

---

## 二、业务架构设计

### 2.1 核心价值交换链路

1. 用户打开网页端，进入群聊页面。
2. 用户输入消息，通过下拉框选择目标：某个 Agent 或 @所有人。
3. 前端将消息发送至后端，后端保存消息，并为目标 Agent(s) 创建未读回执记录。
4. 被 @ 的 Agent 通过**短轮询**调用后端接口，拉取 @ 自己且未读的消息，后端随即将其标记为已读。
5. Agent 在本地处理完消息后，调用后端“提交回复”接口，将回复推送回网页端。
6. 后端保存 Agent 回复，并在响应中捎带该 Agent 若有新的未读消息，减少下一次轮询次数。
7. 前端通过轮询历史消息接口，实时展示用户消息、Agent 回复以及已读状态。

### 2.2 消息路由规则

- 消息只对目标 Agent 可见：
  - 当 `target_type = single` 时，只有 `target_agent_name` 对应的 Agent 能拉取到。
  - 当 `target_type = all` 时，所有已注册 Agent 均可拉取。
- 每个 Agent 拉取后，仅将该 Agent 对应回执标记为已读，不影响其他 Agent。
- Agent 提交回复时，可在响应中捎带返回该 Agent 剩余未读消息，降低轮询频率。

### 2.3 最小可行产品（MVP）定义

- 一个聊天窗口（群聊时间线）
- 一个本地 Agent 接入
- 消息发送与回复
- 单 Agent 已读状态显示
- 本地 JSON 文件存储
- 移动端优先的响应式页面

---

## 三、交互设计与数据模型

### 3.1 用户操作流程图（文字版）

```
[打开网页端]
      ↓
[页面加载]：读取本地聊天记录 + 动态获取已注册的 Agent 列表
      ↓
[输入消息]
      ↓
[选择 @ 对象]：从下拉框选择某个 Agent / @所有人
      ↓
[点击发送]
      ↓
[前端处理]：
   - 在聊天流中立即显示用户消息
   - 若 @单个Agent：显示“未读”图标
   - 若 @所有人：列出所有目标 Agent 并显示未读状态
      ↓
[后端保存消息]：写入本地文件，并标记目标 Agent(s) 为“未读”
      ↓
[等待 Agent 获取]：
   - 被 @ 的 Agent 通过轮询或提交回复时捎带，拿到 @ 自己且未读的消息
   - 后端将该消息对该 Agent 标记为“已读”，并返回给前端更新已读状态
      ↓
[Agent 本地处理]
      ↓
[Agent 调用“提交回复”接口]
      ↓
[后端保存回复]：写入本地文件，并检查该 Agent 是否还有其他未读消息
      ↓
[后端响应]：将回复返回给前端展示，并附带“是否有新待处理消息”标志
      ↓
[前端展示]：在聊天流中显示 Agent 回复；更新已读图标
      ↓
[继续输入下一条消息，循环]
```

### 3.2 核心数据实体关系图

**实体：**

- **Agent**（本地 AI 代理）
  - `id`：唯一标识（自动注册时生成）
  - `name`：显示名称（初始化预设或首次发现时手动命名）
  - `registered_at`：注册时间

- **Message**（聊天消息）
  - `id`：唯一标识
  - `content`：消息内容
  - `sender_type`：`user` 或 `agent`
  - `sender_agent_name`：当 sender_type 为 agent 时的 Agent 名字
  - `target_type`：`single` 或 `all`
  - `target_agent_name`：当 target_type 为 single 时的目标 Agent 名字；当 target_type 为 all 时为空
  - `created_at`：消息创建时间

- **MessageRead**（消息已读回执）
  - `message_id`：关联的消息 id
  - `agent_name`：关联的 Agent 名字
  - `read_at`：该 Agent 读取该消息的时间（null 表示未读）

**关系：**
- 一个 Agent 可以关联多条 MessageRead。
- 一条 Message 可以有多条 MessageRead（当 @所有人时）。
- 一条 Message 如果是 Agent 的回复，则 sender_agent_name 指向某个 Agent。

---

## 四、技术选型与项目结构

### 4.1 技术选型

- **后端框架**：FastAPI + Uvicorn（原生异步，适合短轮询，自动生成文档）
- **前端**：原生 HTML + CSS + JavaScript（移动端优先，响应式设计）
- **数据存储**：本地 JSON 文件（`agents.json`、`messages.json`、`reads.json`）
- **进程管理**：直接使用 `uvicorn` 启动，不引入容器
- **开发环境**：Python 3.x

### 4.2 项目根目录结构树

```
agent-hub/
├── app/                         # 后端主应用
│   ├── main.py                  # FastAPI 入口，挂载路由和静态文件
│   ├── config.py                # 配置项（数据目录、服务地址等）
│   ├── models/
│   │   └── schemas.py           # Pydantic 数据模型
│   ├── routers/
│   │   ├── agents.py            # Agent 注册、列表、命名
│   │   ├── messages.py          # 消息拉取、提交回复、已读状态
│   │   └── pages.py             # 前端页面路由（可选）
│   ├── services/
│   │   ├── storage.py           # 通用 JSON 文件读写封装
│   │   ├── agent_store.py       # Agent 注册与查询逻辑
│   │   └── message_store.py     # 消息、已读回执、回复逻辑
│   └── static/                  # 挂载前端静态文件
│       ├── index.html           # 主页面（移动端优先）
│       ├── styles.css           # 响应式样式
│       └── app.js               # 前端交互逻辑
├── data/                        # 本地数据存储（运行时生成）
│   ├── agents.json              # Agent 注册信息
│   ├── messages.json            # 聊天消息
│   └── reads.json               # 已读回执
├── requirements.txt             # Python 依赖
├── run.sh                       # 本地一键启动脚本
└── README.md                    # 项目说明
```

---

## 五、后端设计方案

### 5.1 API 接口设计

所有接口前缀为 `/api`。

#### 1. Agent 注册
- **方法**：`POST /api/agents/register`
- **请求体**：
  ```json
  { "name": "agent1" }
  ```
- **响应**：
  ```json
  { "status": "ok", "message": "Agent registered successfully" }
  ```
- **说明**：Agent 首次启动时调用，若名字已存在则返回已存在信息。

#### 2. 获取 Agent 列表
- **方法**：`GET /api/agents`
- **响应**：
  ```json
  { "agents": ["agent1", "agent2"] }
  ```

#### 3. 拉取未读消息（短轮询）
- **方法**：`GET /api/messages/pull?agent_name=agent1`
- **响应（有未读消息）**：
  ```json
  {
    "messages": [
      {
        "id": "msg_123",
        "content": "帮我分析一下",
        "sender_type": "user",
        "target_type": "single",
        "target_agent_name": "agent1",
        "created_at": "2025-01-01T12:00:00"
      }
    ]
  }
  ```
- **响应（无未读消息）**：
  ```json
  { "messages": [] }
  ```
- **说明**：Agent 定时调用（如每 3 秒）。返回后立即将这些消息标记为已读。

#### 4. 提交回复
- **方法**：`POST /api/messages/reply`
- **请求体**：
  ```json
  {
    "agent_name": "agent1",
    "content": "这是 Agent 的回复内容",
    "reply_to_message_id": "msg_123"
  }
  ```
- **响应**：
  ```json
  {
    "status": "ok",
    "new_messages": [
      {
        "id": "msg_456",
        "content": "第二条消息",
        "sender_type": "user",
        "target_type": "all",
        "created_at": "2025-01-01T12:05:00"
      }
    ]
  }
  ```
- **说明**：Agent 处理完消息后调用。保存回复，同时检查该 Agent 是否还有其他未读消息并随响应返回。

#### 5. 发送用户消息
- **方法**：`POST /api/messages/send`
- **请求体**：
  ```json
  {
    "sender_type": "user",
    "content": "帮我分析一下",
    "target_type": "single",
    "target_agent_name": "agent1"
  }
  ```
- **响应**：
  ```json
  { "status": "ok", "message_id": "msg_123" }
  ```
- **说明**：前端发送消息时调用，创建消息并生成未读回执。

#### 6. 获取聊天历史
- **方法**：`GET /api/messages/history`
- **响应**：
  ```json
  {
    "messages": [
      {
        "id": "msg_001",
        "content": "你好",
        "sender_type": "user",
        "sender_agent_name": null,
        "target_type": "all",
        "target_agent_name": null,
        "created_at": "2025-01-01T11:00:00",
        "read_by": ["agent1", "agent2"]
      },
      {
        "id": "msg_002",
        "content": "你好，我是 agent1",
        "sender_type": "agent",
        "sender_agent_name": "agent1",
        "target_type": "user",
        "target_agent_name": null,
        "created_at": "2025-01-01T11:01:00",
        "read_by": []
      }
    ]
  }
  ```

### 5.2 本地 JSON 数据结构

**`data/agents.json`**
```json
[
  { "name": "agent1", "registered_at": "2025-01-01T10:00:00" },
  { "name": "agent2", "registered_at": "2025-01-01T10:05:00" }
]
```

**`data/messages.json`**
```json
[
  {
    "id": "msg_001",
    "content": "帮我分析一下",
    "sender_type": "user",
    "sender_agent_name": null,
    "target_type": "single",
    "target_agent_name": "agent1",
    "created_at": "2025-01-01T12:00:00"
  },
  {
    "id": "msg_002",
    "content": "这是 agent1 的回复",
    "sender_type": "agent",
    "sender_agent_name": "agent1",
    "target_type": "user",
    "target_agent_name": null,
    "created_at": "2025-01-01T12:01:00"
  }
]
```

**`data/reads.json`**
```json
[
  { "message_id": "msg_001", "agent_name": "agent1", "read_at": "2025-01-01T12:00:05" },
  { "message_id": "msg_001", "agent_name": "agent2", "read_at": null }
]
```

### 5.3 核心业务逻辑伪代码

#### 注册 Agent
```python
def register_agent(name):
    agents = load_json("agents.json")
    if name not in [a["name"] for a in agents]:
        agents.append({"name": name, "registered_at": now()})
        save_json("agents.json", agents)
    return ok
```

#### 发送用户消息
```python
def send_user_message(content, target_type, target_agent_name=None):
    message = {
        "id": generate_id(),
        "content": content,
        "sender_type": "user",
        "sender_agent_name": None,
        "target_type": target_type,
        "target_agent_name": target_agent_name,
        "created_at": now()
    }
    append_message(message)
    
    reads = load_json("reads.json")
    if target_type == "single":
        reads.append({"message_id": message["id"], "agent_name": target_agent_name, "read_at": None})
    elif target_type == "all":
        agents = load_json("agents.json")
        for agent in agents:
            reads.append({"message_id": message["id"], "agent_name": agent["name"], "read_at": None})
    save_json("reads.json", reads)
    return message["id"]
```

#### Agent 拉取未读消息
```python
def pull_messages(agent_name):
    messages = load_json("messages.json")
    reads = load_json("reads.json")
    unread_messages = []
    for msg in messages:
        if msg["sender_type"] == "user":
            if (msg["target_type"] == "single" and msg["target_agent_name"] == agent_name) or \
               (msg["target_type"] == "all"):
                read_record = find_read_record(reads, msg["id"], agent_name)
                if read_record and read_record["read_at"] is None:
                    unread_messages.append(msg)
                    read_record["read_at"] = now()
    save_json("reads.json", reads)
    return unread_messages
```

#### Agent 提交回复
```python
def submit_reply(agent_name, content, reply_to_message_id=None):
    reply_message = {
        "id": generate_id(),
        "content": content,
        "sender_type": "agent",
        "sender_agent_name": agent_name,
        "target_type": "user",
        "target_agent_name": None,
        "created_at": now()
    }
    append_message(reply_message)
    new_messages = pull_messages(agent_name)  # 捎带返回新未读消息
    return {"status": "ok", "new_messages": new_messages}
```

#### 并发与幂等处理
- **并发拉取**：使用全局文件锁（或线程锁）串行化对 `reads.json` 的读写，防止同一消息被重复领取。
- **提交回复幂等**：后续可增加 `client_msg_id` 字段，由 Agent 生成，后端根据该字段去重，防止网络重试导致重复保存。MVP 可不强制。

---

## 六、前端设计方案

### 6.1 页面结构（`index.html`）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Agent Hub</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="chat-container">
    <header class="chat-header">
      <h1>Agent 群聊</h1>
      <span id="agent-status" class="status-dot"></span>
    </header>
    <main id="message-list" class="message-list"></main>
    <footer class="input-area">
      <select id="agent-select" class="agent-select">
        <option value="all">@所有人</option>
      </select>
      <input type="text" id="message-input" class="message-input" placeholder="输入消息..." autocomplete="off">
      <button id="send-btn" class="send-btn">发送</button>
    </footer>
  </div>
  <script src="app.js"></script>
</body>
</html>
```

### 6.2 移动端优先样式（`styles.css`）

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; height: 100vh; display: flex; justify-content: center; }
.chat-container { width: 100%; max-width: 600px; height: 100%; display: flex; flex-direction: column; background: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.05); }
.chat-header { padding: 12px 16px; background: #4a90d9; color: white; display: flex; justify-content: space-between; font-size: 1.2rem; }
.message-list { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.input-area { display: flex; padding: 8px; background: #fafafa; border-top: 1px solid #ddd; gap: 8px; align-items: center; }
.agent-select { flex: 0 0 auto; max-width: 120px; height: 36px; border-radius: 8px; border: 1px solid #ccc; padding: 0 8px; }
.message-input { flex: 1; height: 36px; border: 1px solid #ccc; border-radius: 18px; padding: 0 16px; }
.send-btn { height: 36px; padding: 0 16px; border: none; border-radius: 18px; background: #4a90d9; color: white; cursor: pointer; }
.message-bubble { max-width: 80%; padding: 10px 14px; border-radius: 16px; word-wrap: break-word; }
.message-bubble.user { align-self: flex-end; background: #4a90d9; color: white; border-bottom-right-radius: 4px; }
.message-bubble.agent { align-self: flex-start; background: #e5e5ea; color: #000; border-bottom-left-radius: 4px; }
.read-status { font-size: 0.75rem; color: #888; margin-top: 4px; display: flex; align-items: center; gap: 4px; }
@media (min-width: 768px) {
  .chat-container { margin: 20px auto; height: calc(100vh - 40px); border-radius: 12px; }
}
```

### 6.3 核心交互逻辑（`app.js`）

```javascript
let currentAgentList = [];

async function init() {
  await loadAgents();
  await loadHistory();
  setInterval(loadHistory, 2000); // 每2秒轮询历史消息
}

async function loadAgents() {
  const res = await fetch('/api/agents');
  const data = await res.json();
  currentAgentList = data.agents;
  const select = document.getElementById('agent-select');
  select.innerHTML = '<option value="all">@所有人</option>';
  currentAgentList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
}

async function loadHistory() {
  const res = await fetch('/api/messages/history');
  const data = await res.json();
  renderMessages(data.messages);
}

function renderMessages(messages) {
  const list = document.getElementById('message-list');
  list.innerHTML = '';
  messages.forEach(msg => {
    const bubble = document.createElement('div');
    bubble.classList.add('message-bubble');
    if (msg.sender_type === 'user') {
      bubble.classList.add('user');
      bubble.textContent = msg.content;
    } else {
      bubble.classList.add('agent');
      bubble.textContent = `${msg.sender_agent_name}: ${msg.content}`;
    }
    list.appendChild(bubble);

    if (msg.sender_type === 'user') {
      const status = document.createElement('div');
      status.classList.add('read-status');
      if (msg.target_type === 'single') {
        const isRead = msg.read_by && msg.read_by.includes(msg.target_agent_name);
        status.innerHTML = isRead ? '<span>✓</span> 已读' : '<span>○</span> 未读';
      } else if (msg.target_type === 'all') {
        const total = currentAgentList.length;
        const readCount = msg.read_by ? msg.read_by.length : 0;
        status.innerHTML = (readCount === total && total > 0) ? '✓✓ 全部已读' : `${readCount}/${total} 已读`;
      }
      list.appendChild(status);
    }
  });
  list.scrollTop = list.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById('message-input');
  const content = input.value.trim();
  if (!content) return;
  const target = document.getElementById('agent-select').value;
  const payload = {
    sender_type: 'user',
    content: content,
    target_type: target === 'all' ? 'all' : 'single',
    target_agent_name: target === 'all' ? null : target
  };
  await fetch('/api/messages/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  input.value = '';
  await loadHistory();
}

document.getElementById('send-btn').addEventListener('click', sendMessage);
document.getElementById('message-input').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendMessage();
});

init();
```

---

## 七、测试与运维方案

### 7.1 边界测试用例清单

#### 1. Agent 注册

| 编号 | 场景 | 输入 | 预期结果 |
|------|------|------|---------|
| T-REG-01 | 正常注册 | 新名字 `agent1` | 注册成功，列表包含 `agent1` |
| T-REG-02 | 重复注册 | 同名再次注册 | 不重复添加，返回已存在 |
| T-REG-03 | 空名字 | `name=""` | 返回错误 |
| T-REG-04 | 特殊字符名字 | 含空格、中文 | 注册成功 |
| T-REG-05 | 超长名字 | 200字符以上 | 成功或明确长度限制错误 |

#### 2. 发送用户消息

| 编号 | 场景 | 输入 | 预期结果 |
|------|------|------|---------|
| T-SEND-01 | 发送给单个 Agent | `single`, `agent1` | 保存消息，为 `agent1` 创建未读回执 |
| T-SEND-02 | 发送给所有人 | `all` | 为所有 Agent 创建未读回执 |
| T-SEND-03 | 目标 Agent 不存在 | `ghost` | 返回错误，不保存 |
| T-SEND-04 | 空内容 | `content=""` | 返回错误 |
| T-SEND-05 | 超长内容 | 10万字符 | 保存成功或明确限制 |
| T-SEND-06 | 缺少字段 | 缺 `target_type` | 返回 422 |

#### 3. Agent 拉取未读消息

| 编号 | 场景 | 输入 | 预期结果 |
|------|------|------|---------|
| T-PULL-01 | 正常拉取 | 存在未读 | 返回未读列表并标记已读 |
| T-PULL-02 | 再次拉取 | 刚拉取过 | 返回空，不重复 |
| T-PULL-03 | 无未读 | 无新消息 | 返回空 |
| T-PULL-04 | Agent 不存在 | `ghost` | 返回空或错误 |
| T-PULL-05 | 并发拉取 | 5个请求同时 | 仅一个拿到消息，其余空 |
| T-PULL-06 | @所有人 场景 | `agent1` 拉取 | 返回消息，只标记 `agent1` 已读 |

#### 4. Agent 提交回复

| 编号 | 场景 | 输入 | 预期结果 |
|------|------|------|---------|
| T-REPLY-01 | 正常回复 | 内容有效 | 保存为 Agent 消息 |
| T-REPLY-02 | 捎带新消息 | 同时有未读 | 响应包含未读消息并标记已读 |
| T-REPLY-03 | 空回复 | `content=""` | 返回错误 |
| T-REPLY-04 | Agent 未注册 | `ghost` | 返回错误 |
| T-REPLY-05 | 回复不存在的消息ID | `reply_to_message_id=not_exist` | 忽略该字段，正常保存 |
| T-REPLY-06 | 幂等性 | 相同 `client_msg_id` 提交两次 | 只保存一条 |

#### 5. 已读状态展示

| 编号 | 场景 | 前置条件 | 预期前端展示 |
|------|------|---------|------------|
| T-READ-01 | 单 Agent 已读 | `agent1` 拉取后 | “✓ 已读” |
| T-READ-02 | @所有人 部分已读 | 仅 `agent1` 拉取 | “1/3 已读” |
| T-READ-03 | @所有人 全部已读 | 所有 Agent 拉取 | “✓✓ 全部已读” |
| T-READ-04 | 未读 | 刚发送 | “未读”或“0/3 已读” |

#### 6. 数据持久化与容错

| 编号 | 场景 | 操作 | 预期结果 |
|------|------|------|---------|
| T-DATA-01 | 重启服务 | 重启后端 | 历史消息和 Agent 列表存在 |
| T-DATA-02 | JSON 文件为空 | 清空 `messages.json` | 启动不报错 |
| T-DATA-03 | JSON 格式错误 | 手动写入非法 JSON | 启动捕获异常并创建新文件 |
| T-DATA-04 | 并发写文件 | 多个请求同时写 | 文件不损坏，数据一致 |

#### 7. 权限与越权

| 编号 | 场景 | 操作 | 预期结果 |
|------|------|------|---------|
| T-PERM-01 | 同名 Agent 冲突 | 两个程序用相同名字注册 | 第二个返回已存在，提示唯一性 |
| T-PERM-02 | 未注册 Agent 拉取 | 未注册名字调用 | 返回空或错误，不泄露消息 |
| T-PERM-03 | Agent 伪造名字 | Agent A 使用 B 的名字 | MVP 可接受，后续版本加强鉴权 |

#### 8. 前端兼容性

| 编号 | 场景 | 操作 | 预期结果 |
|------|------|------|---------|
| T-FE-01 | 手机端显示 | 375px 宽度 | 布局正常，输入框固定底部 |
| T-FE-02 | 桌面端显示 | 宽度 > 768px | 居中，最大宽度限制 |
| T-FE-03 | 动态刷新列表 | 注册新 Agent 不刷新页面 | 下拉框在下一次轮询或手动刷新后更新 |
| T-FE-04 | 快速连续发送 | 连续发送 10 条 | 顺序正确，不丢失 |

#### 9. 性能边界

| 编号 | 场景 | 操作 | 预期结果 |
|------|------|------|---------|
| T-PERF-01 | 历史消息量大 | 1000 条消息打开页面 | 加载 <2秒，滚动流畅 |
| T-PERF-02 | 多 Agent 高频轮询 | 10 个 Agent 每 1 秒轮询 | 后端不崩溃 |
| T-PERF-03 | 大回复内容 | Agent 回复 10 万字符 | 保存和展示正常 |

### 7.2 本地一键启动部署脚本

#### `run.sh`

```bash
#!/bin/bash
echo "==> 检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误：未找到 Python3，请先安装 Python 3.8 或更高版本。"
    exit 1
fi

echo "==> 创建数据目录..."
mkdir -p data

echo "==> 创建虚拟环境（可选）..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "==> 安装依赖..."
pip install -r requirements.txt

echo "==> 启动服务..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
deactivate
```

#### `run.bat`（Windows）

```bat
@echo off
echo ==> 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python，请先安装 Python 3.8+
    exit /b 1
)

echo ==> 创建数据目录...
if not exist data mkdir data

echo ==> 安装依赖...
pip install -r requirements.txt

echo ==> 启动服务...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### `requirements.txt`

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pydantic>=2.0.0
```

**启动后访问：**
- 本机：`http://localhost:8000`
- 手机（同一局域网）：`http://<本机局域网IP>:8000`

---

## 八、后续迭代方向

1. **多 Agent 协作/对抗/辩论**：引入消息路由策略，支持 Agent 之间互相调用或发起会话。
2. **多聊天窗口**：每个窗口独立时间线和参与 Agent 集合，同时只激活一个窗口。
3. **数据库升级**：由 JSON 文件迁移至 SQLite/PostgreSQL，支持大规模数据和查询。
4. **身份认证**：为 Agent 分配 token，防止名字伪造和消息越权。
5. **长轮询/WebSocket**：提升实时性，减少轮询开销。
6. **前端框架化**：如需求复杂，可引入 Vue/React 重构界面。
7. **部署优化**：Docker 化，支持后台运行和日志管理。

---

**方案书完。**
