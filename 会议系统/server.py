# -*- coding: utf-8 -*-
"""
会议系统中转服务 (minimal meeting relay server)
- Pure Flask HTTP API, port 5000 (no WebSocket)
- All data in memory (lost on restart)
- Rooms, members (with seq_num), messages (with seq), phase
- @mention support: @uid in content -> mentions field
- Phase switch: only via "/" prefix commands (/开始提问 /出方案 /互相评审 /结束会议)
"""
import os
import re
import time
import uuid
import threading

# gevent monkey patch 必须在其他 import 之前，用于 Flask + gevent 并发
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    pass

from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")

app = Flask(__name__)

# ---------------------------------------------------------------- state
# rooms[room_id] = {
#     "members": {uid: {"uid":..., "name":..., "seq_num": n, "joined_at": ts}},
#     "messages": [msg, ...],
#     "seq": int,          # last assigned message seq
#     "phase": str,
#     "next_seq_num": int, # next join order number
# }
rooms = {}
rooms_lock = threading.RLock()

# ---------------------------------------------------------------- phase commands (exact "/" prefix required)
# Only these exact strings trigger phase transitions; everything else is ignored.
PHASE_COMMANDS = {
    "asking":     "/开始提问",
    "planning":   "/出方案",
    "reviewing":  "/互相评审",
    "done":       "/结束会议",
}
COMMAND_TO_PHASE = {v: k for k, v in PHASE_COMMANDS.items()}

# 上线状态：超过该秒数无任何活动(发/收)即判离线（对应 AC-6）
ONLINE_TIMEOUT = 30
# 结束会议关键词（可配置，满足 A3）：无斜杠的纯文本也能结束（对应 AC-3 双触发）
END_KEYWORDS = {"结束会议"}

# ---------------------------------------------------------------- mention parsing
MENTION_RE = re.compile(r'@([\w-]+)')


def parse_mentions(content):
    """Extract mentioned uids from @uid patterns in content string."""
    return list(dict.fromkeys(MENTION_RE.findall(content)))


def build_msg(room, uid, member, msg_type, content, reply_to=None, doc_url=None, mentions=None):
    return {
        "id": f"msg_{uuid.uuid4().hex[:10]}",
        "seq": 0,
        "from": {"uid": uid, "name": member["name"]},
        "type": msg_type,
        "content": content,
        "reply_to": reply_to,
        "doc_url": doc_url,
        "mentions": mentions if mentions is not None else parse_mentions(content),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seq_num": member["seq_num"],
        "phase": room["phase"],
    }


def get_room(room_id):
    with rooms_lock:
        if room_id not in rooms:
            rooms[room_id] = {
                "members": {},
                "messages": [],
                "seq": 0,
                "phase": "waiting",
                "next_seq_num": 1,
            }
        return rooms[room_id]


def members_list(room):
    return sorted(room["members"].values(), key=lambda m: m["seq_num"])


def public_members(room):
    now = time.time()
    return [
        {
            "uid": m["uid"],
            "name": m["name"],
            "seq_num": m["seq_num"],
            "online": (now - m["last_seen"]) < ONLINE_TIMEOUT,
        }
        for m in members_list(room)
    ]


def room_snapshot(room_id, since=0):
    room = get_room(room_id)
    msgs = [m for m in room["messages"] if m["seq"] > since]
    return {
        "seq": room["seq"],
        "messages": msgs,
        "members": public_members(room),
        "phase": room["phase"],
    }


def add_message(room_id, msg):
    room = get_room(room_id)
    with rooms_lock:
        room["seq"] += 1
        msg["seq"] = room["seq"]
        room["messages"].append(msg)
    return msg


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    return CHAT_HTML


@app.route("/api/room/<room_id>/join", methods=["POST"])
def join_room(room_id):
    data = request.get_json(force=True) or {}
    uid = str(data.get("uid") or "").strip()
    name = str(data.get("name") or "").strip() or uid or f"user_{uuid.uuid4().hex[:6]}"
    if not uid:
        uid = f"user_{uuid.uuid4().hex[:6]}"

    room = get_room(room_id)
    with rooms_lock:
        if uid in room["members"]:
            member = room["members"][uid]
            member["name"] = name
        else:
            member = {
                "uid": uid,
                "name": name,
                "seq_num": room["next_seq_num"],
                "joined_at": time.time(),
                "last_seen": time.time(),
            }
            room["next_seq_num"] += 1
            room["members"][uid] = member
            add_message(
                room_id,
                build_msg(room, uid, member, "join", f"{name} 加入了会议"),
            )
        resp_member = room["members"][uid]

    return jsonify(
        {
            "ok": True,
            "seq": room["seq"],
            "seq_num": resp_member["seq_num"],
            "members": public_members(room),
            "phase": room["phase"],
        }
    )


@app.route("/api/room/<room_id>/messages", methods=["GET"])
def get_messages(room_id):
    since = request.args.get("since", 0, type=int)
    uid = request.args.get("uid", type=str)
    if uid:
        room = get_room(room_id)
        with rooms_lock:
            if uid in room["members"]:
                room["members"][uid]["last_seen"] = time.time()  # 轮询即心跳
    return jsonify(room_snapshot(room_id, since))


@app.route("/api/room/<room_id>/message", methods=["POST"])
def send_message(room_id):
    data = request.get_json(force=True) or {}
    uid = str(data.get("uid") or "").strip()
    content = str(data.get("content") or "").strip()
    if not uid or not content:
        return jsonify({"ok": False, "error": "uid and content are required"}), 400

    room = get_room(room_id)
    with rooms_lock:
        member = room["members"].get(uid)
        if member is None:
            return jsonify({"ok": False, "error": "uid not joined"}), 400
        member["last_seen"] = time.time()  # 刷新在线心跳

        msg_type = str(data.get("type") or "text").strip() or "text"
        reply_to = data.get("reply_to")

        # Phase switch: exact "/" prefix commands, or configurable end keywords (AC-3 双触发).
        next_phase = COMMAND_TO_PHASE.get(content)
        if next_phase is None and content.strip() in END_KEYWORDS:
            next_phase = "done"
        if next_phase is not None:
            room["phase"] = next_phase

        msg = build_msg(
            room, uid, member, msg_type, content,
            reply_to=reply_to, doc_url=data.get("doc_url"),
        )
        add_message(room_id, msg)

        # 会议结束时插入停止信号消息，明确通知所有接入 agent 停止轮询(R3 兜底)
        if next_phase == "done":
            add_message(
                room_id,
                build_msg(room, "system", {"name": "系统", "seq_num": 0}, "system",
                          "会议已结束，所有接入的 agent 请停止轮询并退出。"),
            )

    return jsonify({"ok": True, "seq": room["seq"], "message": msg})


@app.route("/api/doc/upload", methods=["POST"])
def upload_doc():
    data = request.get_json(force=True) or {}
    room_id = str(data.get("room_id") or "").strip()
    uid = str(data.get("uid") or "").strip()
    content = str(data.get("content") or "")
    title = str(data.get("title") or "未命名文档").strip()

    if not room_id or not uid:
        return jsonify({"ok": False, "error": "room_id and uid are required"}), 400
    room = get_room(room_id)
    with rooms_lock:
        member = room["members"].get(uid)
        if member is None:
            return jsonify({"ok": False, "error": "uid not joined"}), 400

        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        doc_dir = os.path.join(DOCS_DIR, room_id)
        os.makedirs(doc_dir, exist_ok=True)
        path = os.path.join(doc_dir, f"{doc_id}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        url = f"/docs/{room_id}/{doc_id}.md"
        doc_content = f"上传了文档：{title}"
        doc_mentions = parse_mentions(content) + parse_mentions(title)
        doc_mentions = list(dict.fromkeys(doc_mentions))
        add_message(
            room_id,
            build_msg(
                room, uid, member, "doc", doc_content,
                doc_url=url, mentions=doc_mentions,
            ),
        )

    return jsonify({"ok": True, "url": url, "doc_id": doc_id})


@app.route("/docs/<room_id>/<doc_id>")
def get_doc(room_id, doc_id):
    if not doc_id.endswith(".md"):
        doc_id += ".md"
    doc_dir = os.path.join(DOCS_DIR, room_id)
    path = os.path.join(doc_dir, doc_id)
    if not os.path.isfile(path):
        return "Not Found", 404
    return send_from_directory(doc_dir, doc_id, mimetype="text/markdown; charset=utf-8")


# ---------------------------------------------------------------- chat html
CHAT_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>会议系统</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Microsoft YaHei", sans-serif; display: flex; height: 100vh; background: #f5f6fa; }
  #sidebar { width: 240px; background: #2f3542; color: #fff; padding: 16px; overflow-y: auto; flex-shrink: 0; }
  #sidebar h3 { font-size: 14px; opacity: .8; margin-bottom: 10px; }
  #phase-badge { display: inline-block; background: #3742fa; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-bottom: 14px; }
  #member-list li { list-style: none; padding: 6px 10px; border-radius: 6px; margin-bottom: 4px; font-size: 13px; background: rgba(255,255,255,.06); }
  #member-list li.me { background: #3742fa; }
  #main { flex: 1; display: flex; flex-direction: column; }
  #messages { flex: 1; overflow-y: auto; padding: 16px 20px; }
  .msg { background: #fff; border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.08); max-width: 78%; }
  .msg.me { margin-left: auto; background: #dff0ff; }
  .msg.mentioned { border: 2px solid #ff6b6b; background: #fff5f5; }
  .msg.mentioned.me { background: #ffd4d4; }
  .msg .head { font-size: 12px; color: #888; margin-bottom: 4px; }
  .msg .head b { color: #3742fa; }
  .msg .head .mention-tag { color: #ff6b6b; font-size: 11px; margin-left: 6px; }
  .msg .body { font-size: 14px; white-space: pre-wrap; word-break: break-word; }
  .msg .doc-link { color: #3742fa; text-decoration: none; font-size: 13px; }
  .msg .doc-link:hover { text-decoration: underline; }
  .msg.join .body { color: #27ae60; }
  #inputbar { display: flex; gap: 8px; padding: 12px 20px; background: #fff; border-top: 1px solid #eee; }
  #input { flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; }
  #input:focus { border-color: #3742fa; }
  #agent-select { padding: 10px 8px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; background: #fff; outline: none; max-width: 170px; }
  #agent-select:focus { border-color: #3742fa; }
  #send { padding: 10px 22px; background: #3742fa; color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }
  #send:hover { background: #2f35c4; }
  #endbtn { padding: 10px 18px; background: #ff6b6b; color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }
  #endbtn:hover { background: #e74c3c; }
  #member-list li .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  #member-list li .dot.online { background: #2ecc71; }
  #member-list li .dot.offline { background: #95a5a6; }
#hint { padding: 8px 20px; background: #fffbe6; border-bottom: 1px solid #ffe58f; font-size: 13px; color: #ad6800; min-height: 18px; }
</style>
</head>
<body>
  <div id="sidebar">
    <h3>📋 阶段</h3>
    <div id="phase-badge">waiting</div>
    <h3>👥 在线成员</h3>
    <ul id="member-list"></ul>
  </div>
  <div id="main">
    <div id="hint"></div>
    <div id="messages"></div>
    <div id="inputbar">
      <select id="agent-select"><option value="">@ 选择 agent…</option></select>
      <input id="input" placeholder="输入消息，回车发送..." autocomplete="off">
      <button id="send">发送</button>
      <button id="endbtn">结束会议</button>
    </div>
  </div>

<script>
var roomId = "meeting";
var myUid = "user_" + Math.random().toString(36).slice(2, 8);
var myName = "";
var seq = 0;
var lastPhase = "waiting";
var selectedAgent = "";  // 下拉框选中的 agent（选中即相当于 @它）

function init() {
  myName = (prompt("请输入你的名字：", "用户" + Math.floor(Math.random() * 1000)) || "匿名").trim();
  if (myName === "老板") myUid = "boss";  // 老板输入"老板"即获得 boss 身份与提示
  fetch("/api/room/" + roomId + "/join", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({uid: myUid, name: myName})
  }).then(function(r) { return r.json(); }).then(function(data) {
    seq = data.seq;
    renderSidebar(data.members, data.phase);
    renderMessages(data.messages);
  });
}

function isMentioned(msg) {
  if (!msg.mentions) return false;
  for (var i = 0; i < msg.mentions.length; i++) {
    if (msg.mentions[i] === myUid || msg.mentions[i] === myName) return true;
  }
  return false;
}

function renderSidebar(members, phase) {
  document.getElementById("phase-badge").textContent = phase || "waiting";
  var ul = document.getElementById("member-list");
  ul.innerHTML = "";
  for (var i = 0; i < members.length; i++) {
    var m = members[i];
    var li = document.createElement("li");
    var dot = document.createElement("span");
    dot.className = "dot " + (m.online ? "online" : "offline");
    li.appendChild(dot);
    li.appendChild(document.createTextNode(m.seq_num + ". " + m.name));
    if (m.uid === myUid) li.classList.add("me");
    ul.appendChild(li);
  }
  renderAgentSelect(members);  // 同步下拉框里的 agent 列表
}

function renderAgentSelect(members) {
  var sel = document.getElementById("agent-select");
  if (!sel) return;
  var prev = selectedAgent;
  sel.innerHTML = '<option value="">@ 选择 agent…</option>';
  for (var i = 0; i < members.length; i++) {
    var m = members[i];
    if (m.uid === myUid) continue;  // 不列自己
    var opt = document.createElement("option");
    opt.value = m.name;
    opt.textContent = "@ " + m.name;
    sel.appendChild(opt);
  }
  // 保留此前选中的 agent（若它仍在房间）
  var keep = "";
  for (var j = 0; j < sel.options.length; j++) {
    if (sel.options[j].value === prev) { keep = prev; break; }
  }
  sel.value = keep;
  selectedAgent = keep;
}

function renderMessages(msgs) {
  var box = document.getElementById("messages");
  for (var i = 0; i < msgs.length; i++) {
    var m = msgs[i];
    var mentioned = isMentioned(m);
    var div = document.createElement("div");
    var cls = "msg";
    if (m.from.uid === myUid) cls += " me";
    if (mentioned) cls += " mentioned";
    if (m.type === "join") cls += " join";
    div.className = cls;

    var head = document.createElement("div");
    head.className = "head";
    var timeStr = (m.timestamp || "").slice(11, 16);
    head.innerHTML = "<b>" + esc(m.from.name) + "</b> · " + esc(timeStr) + " · " + esc(m.phase || "");
    if (mentioned) {
      var tag = document.createElement("span");
      tag.className = "mention-tag";
      tag.textContent = "@你";
      head.appendChild(tag);
    }

    var body = document.createElement("div");
    body.className = "body";
    body.textContent = m.content;

    div.appendChild(head);
    div.appendChild(body);
    if (m.doc_url) {
      div.appendChild(document.createElement("br"));
      var a = document.createElement("a");
      a.className = "doc-link";
      a.href = m.doc_url;
      a.target = "_blank";
      a.textContent = "📄 " + m.doc_url;
      div.appendChild(a);
    }
    box.appendChild(div);
  }
  box.scrollTop = box.scrollHeight;
}

function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

var allMsgs = [];
function updateHint() {
  var hint = document.getElementById("hint");
  if (!hint) return;
  if (myUid !== "boss") { hint.textContent = ""; return; }  // 仅老板可见提示
  var phase = lastPhase;
  var last = allMsgs.length ? allMsgs[allMsgs.length - 1] : null;
  if (phase === "asking") {
    if (last && last.from.uid !== "boss" && /@boss|@老板/.test(last.content || "")) {
      hint.textContent = "👉 老板，请回答 " + last.from.name;
    } else if (last && last.from.uid === "boss") {
      hint.textContent = "⏳ 等待 Agent 按顺序提问…";
    } else {
      hint.textContent = "提问阶段：等待 Agent 提问";
    }
  } else if (phase === "planning") {
    hint.textContent = "📝 方案阶段：Agent 正在独立出方案";
  } else if (phase === "reviewing") {
    hint.textContent = "🔍 评审阶段：Agent 正在互相质疑";
  } else if (phase === "done") {
    hint.textContent = "✅ 会议已结束";
  } else {
    hint.textContent = "等待老板输入 /开始提问 启动会议";
  }
}

function poll() {
  fetch("/api/room/" + roomId + "/messages?since=" + seq + "&uid=" + encodeURIComponent(myUid))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.messages && data.messages.length) {
        for (var i = 0; i < data.messages.length; i++) allMsgs.push(data.messages[i]);
        renderMessages(data.messages);
      }
      seq = data.seq;
      lastPhase = data.phase;
      renderSidebar(data.members, data.phase);  // 每次轮询刷新在线状态点
      updateHint();
    }).catch(function() {});
}

function sendMsg() {
  var input = document.getElementById("input");
  var content = input.value.trim();
  if (!content) return;
  // 选中了 agent 且消息开头还不是 @它，则自动补上 @（下拉框选择 = 相当于 @该 agent）
  if (selectedAgent) {
    var pre = "@" + selectedAgent;
    if (content.indexOf(pre) !== 0 && content.indexOf(pre + " ") !== 0) {
      content = pre + " " + content;
    }
  }
  input.value = "";
  fetch("/api/room/" + roomId + "/message", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({uid: myUid, type: "text", content: content})
  }).catch(function() {});
}

document.getElementById("send").addEventListener("click", sendMsg);
document.getElementById("input").addEventListener("keydown", function(e) { if (e.key === "Enter") sendMsg(); });
document.getElementById("agent-select").addEventListener("change", function() {
  selectedAgent = this.value;
  if (selectedAgent) {
    var inp = document.getElementById("input");
    var pre = "@" + selectedAgent;
    if (inp.value.indexOf(pre) !== 0) inp.value = pre + " " + inp.value;  // 选中即把 @它 带进输入框
    inp.focus();
  }
});
document.getElementById("endbtn").addEventListener("click", function() {
  fetch("/api/room/" + roomId + "/message", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({uid: myUid, type: "text", content: "/结束会议"})
  }).catch(function() {});
});

init();
setInterval(poll, 3000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    os.makedirs(DOCS_DIR, exist_ok=True)
    print("* Meeting relay server running on http://localhost:5000")
    print("  Phase commands: " + ", ".join(COMMAND_TO_PHASE.keys()))
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
