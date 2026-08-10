#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGNES 轻量代理（同源本地服务器 + 资产库视频拼接）
================================================
把 API 密钥留在服务端，同时托管 agnes_console.html，使页面与 API 同端口（同源），
从而彻底绕开预览面板的跨域 / CSP 拦截——这是修复「Failed to fetch」的关键。

- 读 ~/.workbuddy/.env 的 AGNES_API_KEY / AGNES_API_KEYS（不打印）
  （找不到时兜底读取同目录 HTML 内嵌 key，仅测试模式）
- GET / 或 /console.html → 返回 agnes_console.html（同源托管）
- GET /files/<name> → 返回 output/ 下的合并视频等文件
- GET /api/state → 返回服务端持久化的 {assets, settings}（localhost 与 127.0.0.1 共享）
- POST /api/state → 写入 {assets, settings} 到服务端（原子落盘 agnes_state.json）
- POST /merge → 下载多个视频 URL，ffmpeg 重编码拼接，返回本地 URL
- 转发 /v1/* 到 https://apihub.agnes-ai.cn/v1/*
- 转发 /agnesapi* 到 https://apihub.agnes-ai.cn/agnesapi*
- 自动加 CORS 头
- 零第三方依赖（仅标准库 + 系统 ffmpeg）

运行：python agnes_proxy.py  （默认 8787 端口）
使用：浏览器打开 http://localhost:8787/ 即可（页面内所有请求同源转发）
"""
import os, sys, json, re, time, shutil, subprocess, tempfile, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer

API_ROOT = "https://apihub.agnes-ai.cn"
PORT = int(os.environ.get("AGNES_PROXY_PORT", "8787"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(SCRIPT_DIR, "agnes_console.html")
HUB_FILE = os.path.join(SCRIPT_DIR, "hub.html")
LOGS_FILE = os.path.join(SCRIPT_DIR, "logs.html")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

# ===== 统一门户：8787 作为唯一入口，工作台(8777)整段反向代理过来 =====
# 两个台的路由集经逐条核对【零冲突】，故无需改动任何前端请求路径即可共存：
#   调试台独占  /console /api/state /merge /files/* /agnesapi* /v1*
#   工作台独占  /studio /api/projects /api/spec /api/generate/* /api/project/*
#               /api/export /api/shot/* /api/assemble /api/finalize /api/quality
#               /api/diagnose /assets/* /projects/*
#   注意：老板只能访问 8787，凡工作台用到的 /api/* 路由都必须在此白名单，
#   否则经代理访问会 404（曾漏 /api/export、/api/shot/ → 导出/返工在 8787 上 404）。
STUDIO_PORT = int(os.environ.get("STUDIO_PORT", "8777"))
STUDIO_BASE = "http://127.0.0.1:%d" % STUDIO_PORT
STUDIO_PREFIXES = ("/studio", "/api/projects", "/api/spec", "/api/generate",
                   "/api/project/", "/api/pipeline", "/api/agent",
                   "/api/export", "/api/shot/",
                   "/api/assemble", "/api/finalize", "/api/quality",
                   "/api/diagnose", "/api/queue/", "/api/key-pool", "/api/meta",
                   "/api/series/", "/api/prompt/", "/api/novel/", "/api/style/",
                   "/api/outline/", "/api/asset/", "/assets/", "/projects/", "/vendor/",
                   "/api/faceqc", "/api/facefix",
                   "/api/log", "/api/logs")
BOARD_PORT = int(os.environ.get("BOARD_PORT", "8788"))
BOARD_BASE = "http://127.0.0.1:%d" % BOARD_PORT

# ===== 看板令牌自动注入（老板 0807 指令：本地自用，网页端零配置，不做门禁）=====
# 看板写接口(POST/PUT/DELETE)要求 X-Board-Token，手机经 8787 访问时前端没有令牌 -> 401。
# 这里由代理从 shared_board/.env 读出 BOARD_TOKEN，转发时自动补上，网页端无需 ?token=。
# 上 VPS 前把环境变量 BOARD_AUTO_TOKEN=0 即可关闭注入、恢复门禁。
BOARD_ENV_FILE = os.path.join(SCRIPT_DIR, "shared_board", ".env")
BOARD_AUTO_TOKEN = os.environ.get("BOARD_AUTO_TOKEN", "1") != "0"
_BOARD_TOKEN_CACHE = {"val": None, "mtime": None}

def _board_token():
    """惰性读取看板令牌：.env 由看板首次启动时才生成，故按 mtime 复查，避免缓存住空值。"""
    if not BOARD_AUTO_TOKEN:
        return None
    try:
        mt = os.path.getmtime(BOARD_ENV_FILE)
    except OSError:
        return _BOARD_TOKEN_CACHE["val"]
    if _BOARD_TOKEN_CACHE["val"] and _BOARD_TOKEN_CACHE["mtime"] == mt:
        return _BOARD_TOKEN_CACHE["val"]
    val = None
    try:
        with open(BOARD_ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOARD_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    _BOARD_TOKEN_CACHE["val"] = val
    _BOARD_TOKEN_CACHE["mtime"] = mt
    return val

# ===== 一键拉起（C）：门户代理可派生后台子服务，免手敲命令 =====
# 子进程 detached 启动，脱离父进程独立存活（关掉 8787 也不影响已拉起的服务）。
PY_BIN = "C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe"
STUDIO_SCRIPT = os.path.join(SCRIPT_DIR, "short_drama_workflow", "html_prototype", "server.py")
BOARD_SCRIPT = os.path.join(SCRIPT_DIR, "shared_board", "server.py")
LAUNCH_LOG_DIR = os.path.join(SCRIPT_DIR, "output", "launches")
DETACH = 0x00000008  # DETACHED_PROCESS：无控制台窗口、脱离父进程

def _launch_service(script, env_extra, label):
    """派生一个后台子服务，已在线则跳过；否则 detached 启动并记录日志。"""
    os.makedirs(LAUNCH_LOG_DIR, exist_ok=True)
    log = os.path.join(LAUNCH_LOG_DIR, label + ".log")
    try:
        proc = subprocess.Popen(
            [PY_BIN, script],
            env=dict(os.environ, **env_extra),
            stdout=open(log, "ab"), stderr=subprocess.STDOUT,
            creationflags=DETACH,
        )
        return {"ok": True, "pid": proc.pid, "log": log}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _launch_studio():
    try:
        urllib.request.urlopen(STUDIO_BASE + "/api/projects", timeout=2)
        return {"ok": True, "already_running": True}
    except Exception:
        pass
    return _launch_service(STUDIO_SCRIPT, {"REAL": "1"}, "studio")

def _launch_board():
    try:
        urllib.request.urlopen("http://127.0.0.1:8788/api/projects", timeout=2)
        return {"ok": True, "already_running": True}
    except Exception:
        pass
    return _launch_service(BOARD_SCRIPT, {}, "board")

def _is_studio(path):
    return any(path == p or path.startswith(p) for p in STUDIO_PREFIXES)

def _is_board(path):
    return path in ("/board", "/board/", "/board.html") or path.startswith("/board/")
# 服务端持久化文件：资产库 + 设置。使 localhost 与 127.0.0.1 访问同一份数据（同源共享）
STATE_FILE = os.path.join(SCRIPT_DIR, "agnes_state.json")
# 已知 ffmpeg 路径（WinGet 安装），找不到时回退到 PATH
FFMPEG_PATH = r"C:\Users\67972\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

def _load_env():
    for p in [os.path.join(os.path.expanduser("~"), ".workbuddy", ".env"),
              r"C:\Users\67972\WorkBuddy\workbuddy\short_drama_workflow\.env"]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

_load_env()
KEYS = os.environ.get("AGNES_API_KEYS") or os.environ.get("AGNES_API_KEY", "")
KEY = KEYS.split(",")[0].strip() if KEYS else ""

# 服务端持久化（资产库 + 设置），使 localhost 与 127.0.0.1 同源共享同一份数据
_STATE = {"assets": [], "settings": {}}
def _load_state():
    global _STATE
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                _STATE = {"assets": d.get("assets", []) or [], "settings": d.get("settings", {}) or {}}
    except Exception:
        pass
def _save_state():
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_STATE, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)  # 原子写，避免半截文件
    except Exception:
        pass
_load_state()

# 兜底：环境里没配 key 时，从同目录 HTML 读取内嵌 key（测试模式）
if not KEY:
    try:
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            m = re.search(r'const API_KEY\s*=\s*"([^"]+)"', f.read())
        if m:
            KEY = m.group(1)
    except Exception:
        pass

def _ffmpeg_bin():
    ff = shutil.which("ffmpeg") or (FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None)
    return ff

def _ffprobe_bin(ff):
    if ff and ff.endswith("ffmpeg.exe"):
        fp = ff[:-len("ffmpeg.exe")] + "ffprobe.exe"
        if os.path.exists(fp):
            return fp
    return shutil.which("ffprobe")


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if isinstance(body, (bytes, bytearray)):
            self.wfile.write(body)
        else:
            self.wfile.write(body.encode("utf-8"))

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html", "/hub", "/hub.html"):
            self._serve_html(HUB_FILE)          # 导航首页：选调试台 or 工作台
            return
        if path in ("/console", "/console.html"):
            self._serve_html(HTML_FILE)         # 原 AGNES 调试台
            return
        if path in ("/logs", "/logs.html"):
            self._serve_html(LOGS_FILE)         # 运行日志查看页
            return
        if path == "/api/hub/status":
            self._hub_status()
            return
        if _is_board(path):
            self._proxy_board("GET", None)
            return
        if _is_studio(path):
            self._proxy_studio("GET", None)
            return
        if path.startswith("/files/"):
            self._serve_file(path[len("/files/"):])
            return
        if path == "/api/state":
            self._send(200, json.dumps(_STATE))
            return
        self._proxy("GET", None)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else None
        path = self.path.split("?")[0]
        if _is_board(path):
            self._proxy_board("POST", data)
            return
        if _is_studio(path):
            self._proxy_studio("POST", data)
            return
        if path == "/api/hub/start-studio":
            self._send(200, json.dumps(_launch_studio(), ensure_ascii=False))
            return
        if path == "/api/hub/start-board":
            self._send(200, json.dumps(_launch_board(), ensure_ascii=False))
            return
        if path == "/api/state":
            self._state_post(data)
            return
        if path == "/merge":
            self._merge(data)
            return
        self._proxy("POST", data)

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else None
        path = self.path.split("?")[0]
        if _is_board(path):
            self._proxy_board("PUT", data)
            return
        if _is_studio(path):
            self._proxy_studio("PUT", data)
            return
        self._send(501, json.dumps({"error": "unsupported method PUT for " + path}))

    def do_DELETE(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else None
        path = self.path.split("?")[0]
        if _is_board(path):
            self._proxy_board("DELETE", data)
            return
        if _is_studio(path):
            self._proxy_studio("DELETE", data)
            return
        self._send(501, json.dumps({"error": "unsupported method DELETE for " + path}))

    def _hub_status(self):
        """门户健康探测：报告工作台/共享看板后端是否在线（首页卡片据此显示在线/未启动）。"""
        st = {"console": True, "studio": False, "studio_port": STUDIO_PORT,
              "board": False, "board_port": 8788}
        try:
            with urllib.request.urlopen(STUDIO_BASE + "/api/projects", timeout=2) as r:
                j = json.loads(r.read().decode("utf-8"))
            st["studio"] = True
            st["studio_active"] = j.get("active")
            st["studio_projects"] = len(j.get("projects") or [])
        except Exception as e:
            st["error"] = str(e)[:120]
        try:
            urllib.request.urlopen("http://127.0.0.1:8788/api/projects", timeout=2)
            st["board"] = True
        except Exception:
            pass
        self._send(200, json.dumps(st, ensure_ascii=False))

    def _proxy_studio(self, method, data):
        """把工作台路由整段转发到 8777，实现单入口双台。响应原样回传（含 mp4/图片）。"""
        raw = self.path
        p0 = raw.split("?")[0]
        if p0 in ("/studio", "/studio/", "/studio.html"):
            raw = "/studio.html"
        target = STUDIO_BASE + raw
        req = urllib.request.Request(target, data=data, method=method)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)
        try:
            # 视频生成单镜可达 250s+，超时给足
            with urllib.request.urlopen(req, timeout=900) as resp:
                body = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type",
                                 resp.headers.get("Content-Type", "application/octet-stream"))
                # 透传缓存策略：否则 studio.html 的 no-store 在代理层被吞掉，
                # 手机经 8787 仍会缓存旧页面，前端修复看不到。
                cc = resp.headers.get("Cache-Control")
                if cc:
                    self.send_header("Cache-Control", cc)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            # 自愈：工作台掉线时自动按 REAL=1 拉起并重试一次，避免手机端直接吃 503
            if not getattr(self, "_studio_retried", False):
                self._studio_retried = True
                try:
                    _launch_studio()
                    for _ in range(15):
                        time.sleep(1)
                        try:
                            urllib.request.urlopen(STUDIO_BASE + "/api/projects", timeout=2)
                            break
                        except Exception:
                            continue
                    self._proxy_studio(method, data)
                    return
                except Exception:
                    pass
            self._send(503, json.dumps({
                "error": "工作台后端(%d)未启动或不可达：%s" % (STUDIO_PORT, e),
                "hint": "cd short_drama_workflow/html_prototype && REAL=1 python server.py",
            }, ensure_ascii=False))

    def _proxy_board(self, method, data):
        """把看板路由整段转发到 8788，使其也只经 8787 单入口可达（手机同 WiFi 无需直连 8788）。
        看板前端 API 基址为 location.origin + 绝对 /api/...，故转发 HTML 时把 /api/ 改写为
        /board/api/，使后续请求仍走 8787 反代，不与工作台 /api/ 冲突。"""
        raw = self.path
        p0 = raw.split("?")[0]
        if p0 in ("/board", "/board/", "/board.html"):
            target = BOARD_BASE + "/"
        else:
            target = BOARD_BASE + raw[len("/board"):]   # 保留 /api/... 等子路径
        req = urllib.request.Request(target, data=data, method=method)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)
        # 客户端自带令牌优先；网页端没有则由代理自动补服务端令牌（本地自用免门禁）
        tok = self.headers.get("X-Board-Token") or _board_token()
        if tok:
            req.add_header("X-Board-Token", tok)
        # 透传 agent 身份：带 X-Agent 时看板按 owner 校验并记审计；不带则视为「老板」全权
        ag = self.headers.get("X-Agent")
        if ag:
            req.add_header("X-Agent", ag)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
                if method == "GET" and p0 in ("/board", "/board/", "/board.html") \
                        and "text/html" in ctype:
                    body = body.replace(b"/api/", b"/board/api/")
                self.send_response(resp.status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._send(503, json.dumps({
                "error": "看板后端(%d)未启动或不可达：%s" % (BOARD_PORT, e),
                "hint": "cd shared_board && python server.py",
            }, ensure_ascii=False))

    def _state_post(self, data):
        try:
            body = json.loads(data.decode("utf-8")) if data else {}
        except Exception as e:
            self._send(400, json.dumps({"error": "bad json: " + str(e)}))
            return
        if not isinstance(body, dict):
            self._send(400, json.dumps({"error": "state 必须是对象"}))
            return
        global _STATE
        _STATE = {
            "assets": body["assets"] if isinstance(body.get("assets"), list) else _STATE["assets"],
            "settings": body["settings"] if isinstance(body.get("settings"), dict) else _STATE["settings"],
        }
        _save_state()
        self._send(200, json.dumps({"ok": True}))

    def _serve_html(self, html_file=None):
        try:
            with open(html_file or HTML_FILE, "r", encoding="utf-8") as f:
                body = f.read().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}), "application/json")

    def _serve_file(self, name):
        name = os.path.basename(name)
        fp = os.path.join(OUTPUT_DIR, name)
        if not os.path.exists(fp):
            self._send(404, json.dumps({"error": "not found"}))
            return
        ctype = "video/mp4" if name.lower().endswith(".mp4") else "application/octet-stream"
        try:
            with open(fp, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def _proxy(self, method, data):
        if not KEY:
            self._send(500, json.dumps({"error": "AGNES_API_KEY 未配置"}))
            return
        path = self.path.split("?")[0]
        if path.startswith("/agnesapi"):
            target = API_ROOT + path + (("?" + self.path.split("?", 1)[1]) if "?" in self.path else "")
        elif path.startswith("/v1"):
            target = API_ROOT + path
        else:
            self._send(404, json.dumps({"error": "unknown path"}))
            return
        # 自愈：连接重置(10054)/超时/5xx 自动退避重试，扛过 AGNES 网关瞬时抖动，
        # 避免旧进程在抖动窗口里持续 502 而需手动重启。4xx(参数/鉴权)不重试。
        last_err = None
        for attempt in range(4):  # 首次 + 最多 3 次重试
            req = urllib.request.Request(target, data=data, method=method)
            req.add_header("Authorization", "Bearer " + KEY)
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    self._send(resp.status, resp.read())
                    return
            except urllib.error.HTTPError as e:
                if 400 <= e.code < 500:
                    self._send(e.code, e.read())  # 客户端错误，立即透传，不重试
                    return
                last_err = "HTTP %d %s" % (e.code, e.read().decode("utf-8", "ignore")[:200])
            except Exception as e:
                last_err = str(e)  # 连接重置(10054)/超时/解析失败等网络层错误
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))  # 退避 2s / 4s / 8s
        self._send(502, json.dumps({"error": "AGNES 网关持续不可用（已重试3次）: " + str(last_err)}))

    def _merge(self, data):
        if not data:
            self._send(400, json.dumps({"error": "no body"}))
            return
        try:
            body = json.loads(data.decode("utf-8"))
            urls = body.get("urls") or []
        except Exception as e:
            self._send(400, json.dumps({"error": "bad json: " + str(e)}))
            return
        if len(urls) < 2:
            self._send(400, json.dumps({"error": "需要至少 2 个视频 URL"}))
            return
        ff = _ffmpeg_bin()
        if not ff or not os.path.exists(ff):
            self._send(500, json.dumps({"error": "未找到 ffmpeg，无法拼接（请安装 ffmpeg 或检查路径）"}))
            return
        fp = _ffprobe_bin(ff)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        tmp = tempfile.mkdtemp()
        try:
            norm = []
            for i, u in enumerate(urls):
                try:
                    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                    raw = urllib.request.urlopen(req, timeout=120).read()
                    src = os.path.join(tmp, "s%d.mp4" % i)
                    with open(src, "wb") as f:
                        f.write(raw)
                except Exception as e:
                    self._send(502, json.dumps({"error": "下载失败: " + str(e)}))
                    return
                has_a = False
                if fp:
                    try:
                        o = subprocess.run([fp, "-v", "error", "-show_entries",
                                            "stream=codec_type", "-of", "csv=p=0", src],
                                           capture_output=True, text=True, timeout=30).stdout
                        has_a = "audio" in o
                    except Exception:
                        pass
                dst = os.path.join(tmp, "n%d.mp4" % i)
                if has_a:
                    cmd = [ff, "-y", "-i", src, "-c:v", "libx264", "-preset", "fast",
                           "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac",
                           "-map", "0:v:0", "-map", "0:a:0", "-shortest", dst]
                else:
                    cmd = [ff, "-y", "-f", "lavfi", "-i", "anullsrc=cl=stereo:r=44100",
                           "-i", src, "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-map", "1:v:0",
                           "-map", "0:a:0", "-shortest", dst]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=300)
                except Exception as e:
                    self._send(500, json.dumps({"error": "转码失败: " + str(e)}))
                    return
                if not os.path.exists(dst) or os.path.getsize(dst) == 0:
                    self._send(500, json.dumps({"error": "转码输出为空"}))
                    return
                norm.append(dst)
            # 拼接
            fc = "".join("[%d:v][%d:a]" % (i, i) for i in range(len(norm)))
            fc += "concat=n=%d:v=1:a=1[v][a]" % len(norm)
            inputs = []
            for p in norm:
                inputs += ["-i", p]
            ts = int(time.time())
            outname = "merged_%d.mp4" % ts
            outpath = os.path.join(OUTPUT_DIR, outname)
            cmd = [ff, "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                   "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac",
                   "-pix_fmt", "yuv420p", outpath]
            try:
                subprocess.run(cmd, capture_output=True, timeout=400)
            except Exception as e:
                self._send(500, json.dumps({"error": "拼接失败: " + str(e)}))
                return
            if not os.path.exists(outpath) or os.path.getsize(outpath) == 0:
                self._send(500, json.dumps({"error": "拼接输出为空"}))
                return
            host = self.headers.get("Host", "127.0.0.1:%d" % PORT)
            self._send(200, json.dumps({"url": "http://%s/files/%s" % (host, outname)}))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if not KEY:
        print("⚠️ 未找到 AGNES_API_KEY，请检查 ~/.workbuddy/.env")
        sys.exit(1)
    ff = _ffmpeg_bin()
    print("=" * 58)
    print(" AGNES 短剧工作站 · 统一门户  http://localhost:%d" % PORT)
    print("   ├─ 导航首页   /            (选择进入哪个台)")
    print("   ├─ 调试台     /console     (直连 AGNES 原始接口)")
    print("   └─ 工作台     /studio      (反向代理 -> :%d)" % STUDIO_PORT)
    print("=" * 58)
    print("密钥留在服务端 | ffmpeg: %s" % (ff if ff else "未找到（视频拼接不可用）"))
    # 默认拉起共享看板（8788）：手机经 8787 入口可一键直达，跨设备看进度预览
    try:
        lb = _launch_board()
        if lb.get("already_running"):
            print("   共享看板   :8788        -> 已在线（复用既有进程）")
        elif lb.get("ok"):
            print("   共享看板   :8788        -> 已拉起（PID %s）" % lb.get("pid"))
        else:
            print("   共享看板   :8788        -> 拉起失败：%s" % lb.get("error"))
    except Exception as e:
        print("   共享看板   :8788        -> 拉起异常：%s" % e)
    # 默认拉起工作台（8777, REAL=1）：此前只有看板自启，studio 需手动点按钮，
    # 一旦旧进程退出，手机从门户进 /studio 就 503。现与看板对齐自启。
    try:
        ls = _launch_studio()
        if ls.get("already_running"):
            print("   工作台     :8777        -> 已在线（复用既有进程）")
        elif ls.get("ok"):
            print("   工作台     :8777        -> 已拉起 REAL=1（PID %s）" % ls.get("pid"))
        else:
            print("   工作台     :8777        -> 拉起失败：%s" % ls.get("error"))
    except Exception as e:
        print("   工作台     :8777        -> 拉起异常：%s" % e)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
