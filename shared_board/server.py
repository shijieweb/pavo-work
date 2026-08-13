#!/usr/bin/env python3
# 共享任务看板 · 后端（纯标准库，零 pip 依赖）
# 启动: python server.py  ->  http://0.0.0.0:8788 (手机/电脑同WiFi可用电脑局域网IP访问)
import json, sqlite3, os, datetime, traceback, urllib.parse, secrets
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "board.db")
PORT = 8788

# ── 服务端令牌门禁（上 VPS 前加固）──
# BOARD_TOKEN 缺失时自动生成并持久化到 shared_board/.env；配置后所有写接口强制校验。
# 读接口(GET)不校验，老板浏览器照常查看；写接口(POST/PUT/DELETE)须带 X-Board-Token 或 ?token=。
TOKEN_FILE = os.path.join(HERE, ".env")
BOARD_TOKEN = os.environ.get("BOARD_TOKEN")
if BOARD_TOKEN is None and os.path.isfile(TOKEN_FILE):
    for _l in open(TOKEN_FILE, encoding="utf-8"):
        _l = _l.strip()
        if _l.startswith("BOARD_TOKEN="):
            BOARD_TOKEN = _l.split("=", 1)[1].strip().strip('"').strip("'")
            break
if not BOARD_TOKEN:
    BOARD_TOKEN = secrets.token_hex(16)
    try:
        with open(TOKEN_FILE, "a", encoding="utf-8") as _f:
            _f.write(f"\n# 看板服务端令牌（上 VPS 前已生成；写接口须带 X-Board-Token 或 ?token=）\nBOARD_TOKEN={BOARD_TOKEN}\n")
    except Exception:
        pass
    print(f"[board] BOARD_TOKEN 未配置，已自动生成并写入 {TOKEN_FILE}")
print(f"[board] BOARD_TOKEN={BOARD_TOKEN}  (请妥善保管；老板浏览器访问 /?token={BOARD_TOKEN} 后自动记忆)")

# 本地自用（老板 0807 指令）：托管 index.html 时把令牌直接注入页面，
# 浏览器/手机零配置即可读写，不必再手贴 ?token=。上 VPS 前设 BOARD_INJECT_TOKEN=0 关闭。
INJECT_TOKEN = os.environ.get("BOARD_INJECT_TOKEN", "1") != "0"
print(f"[board] 页面令牌注入 = {'开（本地自用免登录）' if INJECT_TOKEN else '关（须手动带 token）'}")

def now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def touch(c, agent):
    if agent:
        c.execute("INSERT OR REPLACE INTO presence(agent,last_seen) VALUES(?,?)",(agent, now())); c.commit()
def audit(c, agent, action, target, project_id=None):
    c.execute("INSERT INTO audit(ts,agent,action,target,project_id) VALUES(?,?,?,?,?)",(now(), agent or "老板", action, target, project_id)); c.commit()
def proj_owner(c, pid):
    r=c.execute("SELECT owner FROM projects WHERE id=?",(pid,)).fetchone(); return r[0] if r else None
def task_proj_owner(c, tid):
    r=c.execute("SELECT p.owner FROM tasks t JOIN projects p ON t.project_id=p.id WHERE t.id=?",(tid,)).fetchone(); return r[0] if r else None
def task_pid(c, tid):
    r=c.execute("SELECT project_id FROM tasks WHERE id=?",(tid,)).fetchone(); return r[0] if r else None
def allowed(agent, owner):
    return agent=="老板" or agent==owner
def agent_of(self):
    # HTTP 头按 RFC 以 latin-1 解码，中文会变乱码 -> 转回 UTF-8
    raw=self.headers.get("X-Agent")
    if raw:
        try: raw=raw.encode("latin-1").decode("utf-8")
        except Exception: pass
    return raw

def board_token_ok(self):
    """写接口鉴权：未配置令牌时本地信任；配置后须 X-Board-Token 头 或 ?token= 匹配。"""
    if not BOARD_TOKEN:
        return True
    h = self.headers.get("X-Board-Token")
    if h and h == BOARD_TOKEN:
        return True
    if "?" in self.path:
        q = urllib.parse.parse_qs(self.path.split("?", 1)[1])
        if q.get("token", [""])[0] == BOARD_TOKEN:
            return True
    return False

def db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, created TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER,
        parent_id INTEGER, title TEXT, detail TEXT,
        status TEXT DEFAULT 'todo', author TEXT, updated TEXT,
        priority TEXT DEFAULT '中')""")
    try:
        c.execute("ALTER TABLE projects ADD COLUMN owner TEXT DEFAULT '老板'")
    except Exception:
        pass  # 旧库已存在该列时忽略
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT '中'")
    except Exception:
        pass  # 旧库已存在该列时忽略
    c.execute("""CREATE TABLE IF NOT EXISTS presence(
        agent TEXT PRIMARY KEY, last_seen TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent TEXT, action TEXT, target TEXT, project_id INTEGER)""")
    try:
        c.execute("ALTER TABLE audit ADD COLUMN project_id INTEGER")
    except Exception:
        pass  # 旧库已存在该列时忽略
    # 外部指导留言（T-20260813-05）：远程指导角色经 8787 /ext/notes 写入，前端「指导留言」栏/审计流展示
    c.execute("""CREATE TABLE IF NOT EXISTS notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        text TEXT,
        agent TEXT,
        ts TEXT)""")
    c.commit(); return c

def send(h, code, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent, X-Board-Token")
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data); h.wfile.flush()

def body(h):
    n = int(h.headers.get("Content-Length") or 0)
    return json.loads(h.rfile.read(n) or b"{}") if n else {}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent, X-Board-Token")
        self.end_headers()
    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    html = f.read()
                if INJECT_TOKEN and BOARD_TOKEN:
                    tag = ("<script>window.__BOARD_TOKEN__=%s;</script>"
                           % json.dumps(BOARD_TOKEN)).encode("utf-8")
                    html = html.replace(b"</head>", tag + b"</head>", 1) \
                        if b"</head>" in html else tag + html
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers(); self.wfile.write(html); return
            c = db(); raw=agent_of(self)
            if raw: touch(c, raw)
            if self.path.startswith("/api/projects"):
                owner = None
                if "?" in self.path:
                    qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                    owner = qs.get("owner", [None])[0]
                if owner:
                    rows = c.execute("SELECT id,name,owner,created FROM projects WHERE owner=? ORDER BY id", (owner,)).fetchall()
                else:
                    rows = c.execute("SELECT id,name,owner,created FROM projects ORDER BY id").fetchall()
                send(self, 200, [{"id": r[0], "name": r[1], "owner": r[2], "created": r[3]} for r in rows]); c.close(); return
            if self.path.startswith("/api/tasks?"):
                pid = int(self.path.split("project_id=")[1])
                rows = c.execute("SELECT id,parent_id,title,detail,status,author,updated,priority FROM tasks WHERE project_id=? ORDER BY CASE priority WHEN '紧急' THEN 0 WHEN '高' THEN 1 WHEN '中' THEN 2 WHEN '低' THEN 3 ELSE 2 END, id", (pid,)).fetchall()
                send(self, 200, [{"id": r[0], "parent_id": r[1], "title": r[2], "detail": r[3], "status": r[4], "author": r[5], "updated": r[6], "priority": r[7] or "中"} for r in rows]); c.close(); return
            if self.path.startswith("/api/presence"):
                rows = c.execute("SELECT agent,last_seen FROM presence ORDER BY last_seen DESC").fetchall()
                send(self, 200, [{"agent": r[0], "last_seen": r[1]} for r in rows]); c.close(); return
            if self.path.startswith("/api/audit"):
                q = {}
                if "?" in self.path:
                    q = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                pid = q.get("project_id", [None])[0]
                if pid:
                    rows = c.execute("SELECT ts,agent,action,target FROM audit WHERE project_id=? ORDER BY id DESC LIMIT 20", (pid,)).fetchall()
                else:
                    rows = c.execute("SELECT ts,agent,action,target FROM audit ORDER BY id DESC LIMIT 20").fetchall()
                send(self, 200, [{"ts": r[0], "agent": r[1], "action": r[2], "target": r[3]} for r in rows]); c.close(); return
            # ---- 外部指导 API（T-20260813-05）：只读 + 留言，经 8787 /ext/* 访问，无鉴权直达 ----
            if self.path.startswith("/api/ext/status"):
                projs = c.execute("SELECT id,name,owner,created FROM projects ORDER BY id").fetchall()
                inflight = c.execute("""SELECT id,parent_id,title,detail,status,author,updated,priority
                    FROM tasks WHERE status<>'done'
                    ORDER BY CASE priority WHEN '紧急' THEN 0 WHEN '高' THEN 1 WHEN '中' THEN 2 WHEN '低' THEN 3 ELSE 2 END, id""").fetchall()
                recent = c.execute("SELECT ts,agent,action,target FROM audit ORDER BY id DESC LIMIT 8").fetchall()
                send(self, 200, {
                    "projects": [{"id": r[0], "name": r[1], "owner": r[2], "created": r[3]} for r in projs],
                    "in_flight_tasks": [{"id": r[0], "parent_id": r[1], "title": r[2], "detail": r[3], "status": r[4], "author": r[5], "updated": r[6], "priority": r[7] or "中"} for r in inflight],
                    "recent_audit": [{"ts": r[0], "agent": r[1], "action": r[2], "target": r[3]} for r in recent],
                    "generated_at": now(),
                }); c.close(); return
            if self.path.startswith("/api/ext/projects"):
                owner = None
                if "?" in self.path:
                    qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                    owner = qs.get("owner", [None])[0]
                if owner:
                    rows = c.execute("SELECT id,name,owner,created FROM projects WHERE owner=? ORDER BY id", (owner,)).fetchall()
                else:
                    rows = c.execute("SELECT id,name,owner,created FROM projects ORDER BY id").fetchall()
                send(self, 200, [{"id": r[0], "name": r[1], "owner": r[2], "created": r[3]} for r in rows]); c.close(); return
            if self.path.startswith("/api/ext/tasks"):
                q = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
                pid = q.get("project_id", [None])[0]
                if pid is None or not pid.isdigit():
                    send(self, 400, {"error": "project_id 必填且为整数"}); c.close(); return
                rows = c.execute("SELECT id,parent_id,title,detail,status,author,updated,priority FROM tasks WHERE project_id=? ORDER BY CASE priority WHEN '紧急' THEN 0 WHEN '高' THEN 1 WHEN '中' THEN 2 WHEN '低' THEN 3 ELSE 2 END, id", (int(pid),)).fetchall()
                send(self, 200, [{"id": r[0], "parent_id": r[1], "title": r[2], "detail": r[3], "status": r[4], "author": r[5], "updated": r[6], "priority": r[7] or "中"} for r in rows]); c.close(); return
            if self.path.startswith("/api/ext/audit"):
                q = {}
                if "?" in self.path:
                    q = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                pid = q.get("project_id", [None])[0]
                if pid:
                    rows = c.execute("SELECT ts,agent,action,target FROM audit WHERE project_id=? ORDER BY id DESC LIMIT 20", (pid,)).fetchall()
                else:
                    rows = c.execute("SELECT ts,agent,action,target FROM audit ORDER BY id DESC LIMIT 20").fetchall()
                send(self, 200, [{"ts": r[0], "agent": r[1], "action": r[2], "target": r[3]} for r in rows]); c.close(); return
            if self.path.startswith("/api/ext/presence"):
                rows = c.execute("SELECT agent,last_seen FROM presence ORDER BY last_seen DESC").fetchall()
                send(self, 200, [{"agent": r[0], "last_seen": r[1]} for r in rows]); c.close(); return
            if self.path.startswith("/api/ext/notes"):
                q = {}
                if "?" in self.path:
                    q = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                pid = q.get("project_id", [None])[0]
                if pid:
                    rows = c.execute("SELECT id,project_id,text,agent,ts FROM notes WHERE project_id=? ORDER BY id DESC LIMIT 100", (pid,)).fetchall()
                else:
                    rows = c.execute("SELECT id,project_id,text,agent,ts FROM notes ORDER BY id DESC LIMIT 100").fetchall()
                send(self, 200, [{"id": r[0], "project_id": r[1], "text": r[2], "agent": r[3], "ts": r[4]} for r in rows]); c.close(); return
            send(self, 404, {"error": "not found"})
        except Exception:
            traceback.print_exc(); send(self, 500, {"error": "server error"})
    def do_POST(self):
        try:
            if not board_token_ok(self):
                send(self, 401, {"error": "未授权：写接口须带 X-Board-Token 或 ?token="}); return
            c = db(); d = body(self); raw=agent_of(self); agent=raw or "老板"
            if self.path == "/api/projects":
                owner = agent if raw else d.get("owner", "老板")  # agent 只能建自己名下的项目；boss 用表单归属
                cur = c.execute("INSERT INTO projects(name,owner,created) VALUES(?,?,?)", (d.get("name", ""), owner, now()))
                c.commit(); 
                if raw: audit(c, agent, "创建项目", f"{owner}/{d.get('name','')}", cur.lastrowid)
                if raw: touch(c, raw)
                send(self, 200, {"id": cur.lastrowid, "owner": owner}); c.close(); return
            if self.path == "/api/tasks":
                pid = d.get("project_id"); ow = proj_owner(c, pid)
                if not allowed(agent, ow):
                    send(self, 403, {"error": f"无权限修改此项目(owner={ow})"}); c.close(); return
                pri = d.get("priority") or "中"
                cur = c.execute("INSERT INTO tasks(project_id,parent_id,title,detail,status,author,updated,priority) VALUES(?,?,?,?,?,?,?,?)",
                          (d.get("project_id"), d.get("parent_id"), d.get("title", ""), d.get("detail", ""), d.get("status", "todo"), d.get("author", ""), now(), pri))
                c.commit(); 
                if raw: audit(c, agent, "创建任务", f"项目{pid}/{d.get('title','')}", pid)
                if raw: touch(c, raw)
                send(self, 200, {"id": cur.lastrowid}); c.close(); return
            if self.path == "/api/ext/notes":
                # 外部指导留言（T-20260813-05）：写 notes 表 + 审计 agent=远程指导 + 刷新在线；无鉴权（代理注入 token 过写闸）
                pid = d.get("project_id")
                if pid is None or not isinstance(pid, int):
                    send(self, 400, {"error": "project_id 必填且为整数"}); c.close(); return
                if proj_owner(c, pid) is None:
                    send(self, 404, {"error": f"项目不存在: {pid}"}); c.close(); return
                text = d.get("text")
                if not isinstance(text, str) or not text.strip():
                    send(self, 400, {"error": "text 不能为空"}); c.close(); return
                note_agent = raw or "远程指导"
                cur = c.execute("INSERT INTO notes(project_id,text,agent,ts) VALUES(?,?,?,?)", (pid, text.strip(), note_agent, now()))
                c.commit()
                audit(c, note_agent, "指导留言", f"项目{pid}/留言：{text.strip()[:30]}", pid)
                touch(c, note_agent)
                send(self, 200, {"ok": True, "id": cur.lastrowid}); c.close(); return
            send(self, 404, {"error": "not found"})
        except Exception:
            traceback.print_exc(); send(self, 500, {"error": "server error"})
    def do_PUT(self):
        try:
            if not board_token_ok(self):
                send(self, 401, {"error": "未授权：写接口须带 X-Board-Token 或 ?token="}); return
            c = db(); d = body(self); raw=agent_of(self); agent=raw or "老板"
            if self.path.startswith("/api/projects/"):
                pid = int(self.path.split("/")[-1]); ow = proj_owner(c, pid)
                if not allowed(agent, ow):
                    send(self, 403, {"error": f"无权限修改此项目(owner={ow})"}); c.close(); return
                sets = []; vals = []
                for k in ("name", "owner"):
                    if k in d: sets.append(f"{k}=?"); vals.append(d[k])
                if sets:
                    vals.append(pid)
                    c.execute(f"UPDATE projects SET {','.join(sets)} WHERE id=?", vals)
                    c.commit()
                if raw: audit(c, agent, "更新项目", f"项目{pid}", pid)
                if raw: touch(c, raw)
                send(self, 200, {"ok": True}); c.close(); return
            if self.path.startswith("/api/tasks/"):
                tid = int(self.path.split("/")[-1]); ow = task_proj_owner(c, tid)
                if not allowed(agent, ow):
                    send(self, 403, {"error": f"无权限修改此任务(owner={ow})"}); c.close(); return
                sets = []; vals = []
                for k in ("title", "detail", "status", "author", "priority"):
                    if k in d: sets.append(f"{k}=?"); vals.append(d[k])
                sets.append("updated=?"); vals.append(now()); vals.append(tid)
                c.execute(f"UPDATE tasks SET {','.join(sets)} WHERE id=?", vals)
                c.commit(); 
                if raw: audit(c, agent, "更新任务", f"#{tid}/{d.get('title','')}", task_pid(c, tid))
                if raw: touch(c, raw)
                send(self, 200, {"ok": True}); c.close(); return
            send(self, 404, {"error": "not found"})
        except Exception:
            traceback.print_exc(); send(self, 500, {"error": "server error"})
    def do_DELETE(self):
        try:
            if not board_token_ok(self):
                send(self, 401, {"error": "未授权：写接口须带 X-Board-Token 或 ?token="}); return
            c = db(); raw=agent_of(self); agent=raw or "老板"
            if self.path.startswith("/api/tasks/"):
                tid = int(self.path.split("/")[-1]); ow = task_proj_owner(c, tid)
                if not allowed(agent, ow):
                    send(self, 403, {"error": f"无权限删除此任务(owner={ow})"}); c.close(); return
                c.execute("DELETE FROM tasks WHERE id=?", (tid,))
                c.execute("DELETE FROM tasks WHERE parent_id=?", (tid,))
                c.commit()
                if raw: audit(c, agent, "删除任务", f"#{tid}", task_pid(c, tid))
                if raw: touch(c, raw)
                send(self, 200, {"ok": True}); c.close(); return
            send(self, 404, {"error": "not found"})
        except Exception:
            traceback.print_exc(); send(self, 500, {"error": "server error"})

if __name__ == "__main__":
    db().close()
    print(f"board running at http://0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
