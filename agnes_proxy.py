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
import os, sys, json, re, time, shutil, subprocess, tempfile, csv, urllib.request, urllib.error, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer

API_ROOT = "https://apihub.agnes-ai.cn"
PORT = int(os.environ.get("AGNES_PROXY_PORT", "8787"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(SCRIPT_DIR, "agnes_console.html")
HUB_FILE = os.path.join(SCRIPT_DIR, "hub.html")
LOGS_FILE = os.path.join(SCRIPT_DIR, "logs.html")
# 音效台静态页（T-12）：SoundsFree 离线程序化音效生成器，与 /logs、/training 同构走 _serve_html
SOUNDSFREE_FILE = os.path.join(SCRIPT_DIR, "soundsfree_home.html")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
# batch 训练采纳面板（T-0815）：training_panel.html 整目录静态托管在 /batch（外网经 8787 可达）
BATCH_PANEL_DIR = r"C:\Users\67972\projects\short-drama-training"
# 项目生命周期看板原型（T-0822）：整目录静态托管在 /board-prototype
BOARD_PROTOTYPE_DIR = os.path.join(SCRIPT_DIR, "dev-work", "board-prototype")

# T-19: 资产路由批次白名单 — <batch> 段 -> 对应 out 目录 (防任意目录穿越 + 支持多批次)
BATCH_DIRS = {
    "batch-001": os.path.join(BATCH_PANEL_DIR, "01_配方训练", "实验批次", "batch-001", "out"),
    "batch-002": os.path.join(BATCH_PANEL_DIR, "01_配方训练", "实验批次", "batch-002", "out"),
}
# 角色参考图目录 (各批次共用, 经 /batch/__asset__/<batch>/ref/<file> 定位)
BATCH_REF_DIR = os.path.join(BATCH_PANEL_DIR, "01_配方训练", "角色参考图")

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
                   "/api/diagnose", "/api/precheck", "/api/queue/", "/api/key-pool", "/api/meta",
                   "/api/series/", "/api/prompt/", "/api/novel/", "/api/style/",
                   "/api/outline/", "/api/asset/", "/assets/", "/projects/", "/vendor/",
                   "/api/faceqc", "/api/facefix", "/api/agnes/", "/api/vision/",
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
# 【训练看板·老板 0811】提示词训练营：数据 experiments_data/*.json + 实验视频
TRAIN_FILE = os.path.join(SCRIPT_DIR, "training.html")
TRAIN_DATA = os.path.join(SCRIPT_DIR, "experiments_data")
TRAIN_VIDEO = os.path.join(SCRIPT_DIR, "short_drama_workflow", "scripts", "diag", "experiments")
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

# ===== 路由注册表（route_registry.json）单一事实源（T-20260813-02）=====
# 加服务 = 注册表加一行（prefix + target + kind + 可选 flags），对外永远只有 8787。
# 无注册表 / 解析失败 / 空 routes → 回退上面的硬编码（STUDIO_PREFIXES + _is_board），保证兼容不崩。
# 前缀唯一校验：任一 prefix 与另一条存在「相等或互为路径前缀」（如 /api 与 /api/spec）
# 会抢同一路径 → 启动即报错（raise SystemExit）。
ROUTE_REGISTRY_FILE = os.path.join(SCRIPT_DIR, "route_registry.json")

class RouteRegistryError(Exception):
    """路由注册表配置错误（如前缀冲突），启动时中止。"""

def _find_prefix_conflict(prefixes):
    """返回互相冲突的一对 (a, b)，无冲突返回 None。
    路径段感知：/api 与 /api/spec 冲突（/api/spec 是 /api/ 下子路径，会抢同一路径）；
    /api/log 与 /api/logs 不冲突（同为独立端点，且同挂 8777，不影响匹配）。"""
    for i in range(len(prefixes)):
        for j in range(i + 1, len(prefixes)):
            a, b = prefixes[i], prefixes[j]
            if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                return (a, b)
    return None

def _load_route_registry(path=None):
    """加载路由注册表。
    缺失/解析失败/空 routes → 返回 None（回退硬编码白名单）；
    前缀冲突 → 抛 RouteRegistryError（启动即报错，防两服务抢同一路径）。"""
    p = path if path is not None else ROUTE_REGISTRY_FILE
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("routes")
    if not isinstance(raw, list) or not raw:
        return None
    routes = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        prefix = item.get("prefix")
        target = item.get("target")
        if not isinstance(prefix, str) or not prefix.startswith("/"):
            return None
        if not isinstance(target, str) or not (target.startswith("http://") or target.startswith("https://")):
            return None
        flags = item.get("flags")
        if flags is not None and not isinstance(flags, dict):
            return None
        routes.append({
            "prefix": prefix,
            "target": target.rstrip("/"),
            "kind": item.get("kind") if isinstance(item.get("kind"), str) else "generic",
            "flags": flags if isinstance(flags, dict) else {},
            "demo": bool(item.get("demo", False)),
            "note": item.get("note", ""),
        })
    conflict = _find_prefix_conflict([r["prefix"] for r in routes])
    if conflict:
        raise RouteRegistryError(
            "route_registry.json 前缀冲突：%r 与 %r 相等或互为路径前缀，会抢同一路径，请修正注册表" % conflict)
    return routes

# ===== 路由注册表 mtime 惰性热加载（T-20260813-07 · 照抄 _BOARD_TOKEN_CACHE 模式 L63-86）=====
# 每次路由匹配 stat route_registry.json 的 mtime，变化才重载（缓存秒级）；
# 冲突/解析失败/空 → 拒绝加载、沿用旧路由（原子性：要么全新要么全旧，不能半套）；
# 代码逻辑变更仍走干净重启（工程铁律）。
_ROUTE_REGISTRY_CACHE = {"val": None, "mtime": None, "error": None}

def _get_route_registry():
    """mtime 惰性重载 route_registry.json（照抄 _board_token L63-86）：
    - 每次调用 stat mtime，与缓存一致直接返回（stat 一次，开销可忽略，秒级生效）；
    - 不一致才重新 _load_route_registry()；
    - 冲突(RouteRegistryError) → 拒绝加载、沿用旧路由；
    - 解析失败/空 routes → 返回 None（回退硬编码白名单，兼容不崩）。"""
    try:
        mt = os.path.getmtime(ROUTE_REGISTRY_FILE)
    except OSError:
        return _ROUTE_REGISTRY_CACHE["val"]
    if _ROUTE_REGISTRY_CACHE["mtime"] == mt:
        return _ROUTE_REGISTRY_CACHE["val"]
    try:
        routes = _load_route_registry()
    except RouteRegistryError as e:
        if _ROUTE_REGISTRY_CACHE["error"] != str(e):
            print("[route_registry] 热加载冲突，沿用旧路由：%s" % e)
        _ROUTE_REGISTRY_CACHE["error"] = str(e)
        _ROUTE_REGISTRY_CACHE["mtime"] = mt
        return _ROUTE_REGISTRY_CACHE["val"]
    _ROUTE_REGISTRY_CACHE["val"] = routes
    _ROUTE_REGISTRY_CACHE["mtime"] = mt
    _ROUTE_REGISTRY_CACHE["error"] = None
    if routes is not None:
        print("[route_registry] 热重载成功：%d 条路由" % len(routes))
    return routes

try:
    _ROUTE_REGISTRY = _load_route_registry()
except RouteRegistryError as e:
    raise SystemExit("[route_registry] " + str(e))
# 启动播种：缓存 mtime，使首请求零重读；运行时变更由 _get_route_registry() 惰性接管
try:
    _ROUTE_REGISTRY_CACHE["val"] = _ROUTE_REGISTRY
    _ROUTE_REGISTRY_CACHE["mtime"] = os.path.getmtime(ROUTE_REGISTRY_FILE)
except OSError:
    pass

def _route_matches(path, route):
    """单条路由匹配：board 需边界（/board、/board/、/board.html、/board/*），其余 == 或 startswith。"""
    p = route["prefix"]
    if route["kind"] == "board":
        return path in (p, p + "/", p + ".html") or path.startswith(p + "/")
    return path == p or path.startswith(p)

def _route_for(path):
    """注册表驱动：返回命中的第一条路由；无注册表时返回 None（走硬编码回退）。"""
    reg = _get_route_registry()
    if reg is None:
        return None
    for route in reg:
        if _route_matches(path, route):
            return route
    return None
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
        if path in ("/training", "/training.html"):
            self._serve_html(TRAIN_FILE)        # 提示词训练营看板（实验过程/结果/方案审查）
            return
        if path in ("/soundsfree", "/soundsfree.html"):
            self._serve_html(SOUNDSFREE_FILE)   # 音效台（T-12：SoundsFree 本地静态页，_route_dispatch 之前，避免被反代吞掉）
            return
        if path in ("/board-prototype", "/board-prototype/"):
            self._serve_board_prototype()       # 项目生命周期看板原型（T-0822）
            return
        if path.startswith("/board-prototype/"):
            self._serve_board_prototype_asset(path[len("/board-prototype/"):])
            return
        if path.startswith("/batch"):
            if path.startswith("/batch/__asset__/"):
                self._serve_batch_asset(path)   # T-18: 纯 ASCII 资产路由 (绕过中文目录 URL 被外网拒载)
            else:
                self._serve_batch(path)         # batch 训练采纳面板（T-0815）：整目录静态托管，外网经 8787 可达
            return
        if path == "/training/api/experiments":
            self._train_experiments()
            return
        if path.startswith("/training/api/experiments/") and path.endswith("/status"):
            self._train_status_update(path)
            return
        if path.startswith("/training/video/"):
            self._serve_train_video(path[len("/training/video/"):])
            return
        if path == "/api/hub/status":
            self._hub_status()
            return
        if self._route_dispatch(path, "GET", None):
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
        if self._route_dispatch(path, "POST", data):
            return
        if path == "/batch/api/correction":
            self._serve_correction(data)
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
        if self._route_dispatch(path, "PUT", data):
            return
        self._send(501, json.dumps({"error": "unsupported method PUT for " + path}))

    def do_DELETE(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length) if length else None
        path = self.path.split("?")[0]
        if self._route_dispatch(path, "DELETE", data):
            return
        self._send(501, json.dumps({"error": "unsupported method DELETE for " + path}))

    def _route_dispatch(self, path, method, data):
        """注册表驱动路由判定：命中返回 True 并转发；未命中/无注册表回退硬编码，均返回 False。"""
        reg = _get_route_registry()
        if reg is not None:
            route = _route_for(path)
            if route is not None:
                if route["kind"] == "studio":
                    self._proxy_studio(method, data)
                elif route["kind"] == "board":
                    self._proxy_board(method, data)
                else:
                    self._proxy_route(method, data, route)
                return True
        else:
            # 无注册表（缺失/解析失败/空 routes）→ 回退现有硬编码行为，保证兼容不崩
            if _is_board(path):
                self._proxy_board(method, data)
                return True
            if _is_studio(path):
                self._proxy_studio(method, data)
                return True
        return False

    def _proxy_route(self, method, data, route):
        """通用注册表路由转发：去掉挂载前缀后的子路径拼到 target；可选 token 注入 / HTML 改写。
        供 kind=generic 的新服务使用（board 仍走 _proxy_board、studio 仍走 _proxy_studio，逻辑不动）。"""
        raw = self.path
        p0 = raw.split("?")[0]
        prefix = route["prefix"]
        target = route["target"]
        flags = route.get("flags") or {}
        if p0 == prefix:
            sub = "/"
        else:
            sub = p0[len(prefix):]
            if not sub.startswith("/"):
                sub = "/" + sub
        query = ("?" + raw.split("?", 1)[1]) if "?" in raw else ""
        req = urllib.request.Request(target + sub + query, data=data, method=method)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)

        # ── R1 令牌闸（T-am-hardening-r1）：令牌透传 + 真实客户端 IP 注入 ──
        # ① 透传浏览器从 8787 取得的 Authorization，使其能到达 8000 校验（AC-1.7）。
        # ② 覆盖式注入 X-Forwarded-For = 网关直连客户端 IP（覆盖而非追加，防伪造）。
        # ③ 客户端自带 X-Gateway-* 头本就不会被转发（本方法仅显式转发
        #    Content-Type / X-Board-Token / X-Agent），无需额外剥离代码。
        auth = self.headers.get("Authorization")
        if auth:
            req.add_header("Authorization", auth)
        req.add_header("X-Forwarded-For", self.client_address[0])
        # 可选：仿看板的令牌自动注入（本地自用免门禁）
        if flags.get("board_token_inject"):
            tok = self.headers.get("X-Board-Token") or _board_token()
            if tok:
                req.add_header("X-Board-Token", tok)
        ag = self.headers.get("X-Agent")
        if ag:
            req.add_header("X-Agent", ag)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
                # 可选：仿看板的 HTML/JS 改写，使子服务前端仍走 8787 单入口。
                # 注意：Agent Hub 前端硬编码绝对路径 /api/ 与 /static/，且 app.js 以
                # application/javascript 返回，故对 JS 也做 /api/ 改写；/static/ 改写同理。
                if (flags.get("rewrite_html_api") or flags.get("rewrite_html_static")) and method == "GET":
                    if "text/html" in ctype:
                        if flags.get("rewrite_html_api"):
                            body = body.replace(b"/api/", (prefix + "/api/").encode("utf-8"))
                        if flags.get("rewrite_html_static"):
                            body = body.replace(b"/static/", (prefix + "/static/").encode("utf-8"))
                    if "javascript" in ctype:
                        body = body.replace(b"/api/", (prefix + "/api/").encode("utf-8"))
                        if flags.get("rewrite_html_static"):
                            body = body.replace(b"/static/", (prefix + "/static/").encode("utf-8"))
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
                "error": "路由目标不可达（%s -> %s）：%s" % (prefix, target, e),
                "hint": "检查 route_registry.json 对应服务是否已启动",
            }, ensure_ascii=False))

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

    def _serve_batch(self, path):
        """静态托管 batch 训练采纳面板（training_panel.html 及其相对资源）。
        挂载前缀 /batch，根目录 = BATCH_PANEL_DIR；防目录穿越。
        8787 已绑 0.0.0.0，外部经此入口即可访问面板，无需本机 file://。"""
        rel = path[len("/batch"):].lstrip("/")
        rel = urllib.parse.unquote(rel)    # HTTP 路径是百分号编码(中文目录→%XX)，必须解码才能匹配磁盘路径
        norm_base = os.path.normpath(BATCH_PANEL_DIR)
        if rel == "" or rel.endswith("/"):
            rel = "training_panel.html"
        full = os.path.normpath(os.path.join(norm_base, rel))
        if full != norm_base and not full.startswith(norm_base + os.sep):
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        if not os.path.isfile(full):
            self._send(404, json.dumps({"error": "not found: " + rel}))
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".htm": "text/html; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".json": "application/json",
            ".css": "text/css",
            ".js": "application/javascript",
            ".csv": "text/csv; charset=utf-8",
        }.get(ext, "application/octet-stream")
        try:
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def _serve_batch_asset(self, path):
        """T-18/T-19: 纯 ASCII 静态资产路由, 绕过中文目录 URL 被外网隧道/代理层拒载的问题.

        路径格式: /batch/__asset__/<batch>/<kind>/<name>
          - batch 段 -> BATCH_DIRS 白名单映射到对应 out 目录 (cand) 或共用 ref 目录 (ref)
          - kind=cand -> BATCH_DIRS[batch]/<name>  (候选图)
          - kind=ref  -> BATCH_REF_DIR/<name>        (角色参考图, 各批次共用)
        返回对应磁盘 PNG (HTTP 200 image/png); 段数不对 / batch 非白名单 / 路径含 ..
        或 / 等穿越字符 / kind 非白名单 / 文件不存在 / 非 .png -> 拒绝。
        """
        rel = path[len("/batch/__asset__/"):]
        parts = rel.split("/")
        if len(parts) != 3:
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        batch_id, kind, rest = parts
        if batch_id not in BATCH_DIRS:
            self._send(403, json.dumps({"error": "forbidden batch: " + batch_id}))
            return
        name = os.path.basename(rest)  # 拒绝含 / 或 .. 的穿越字符
        if name != rest or ".." in rest or "/" in rest:
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        if kind not in ("cand", "ref"):
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        if kind == "cand":
            full = os.path.normpath(os.path.join(BATCH_DIRS[batch_id], name))
        else:
            full = os.path.normpath(os.path.join(BATCH_REF_DIR, name))
        if not os.path.isfile(full):
            self._send(404, json.dumps({"error": "not found: " + rel}))
            return
        if os.path.splitext(full)[1].lower() != ".png":
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        try:
            with open(full, "rb") as f:
                data = f.read()
            self._send(200, data, "image/png")
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def _update_writing_purpose(self, csv_path, writing, note, next_prompt):
        """更新 writing_purpose.csv 中指定写法号行的「提示词修正意见 / 修正后prompt」。

        保留 UTF-8 BOM、全部列、行顺序与其它行内容; 原子写盘 (先写 .tmp 再 os.replace)。
        写法号不在表中时追加一行 (补齐列)。返回 True 成功 / False 失败。
        """
        if not os.path.isfile(csv_path):
            return False
        try:
            rows = []
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                if not fieldnames:
                    return False
                # 确保两列存在 (AC-1.1): 缺失则追加到列尾
                fn = list(fieldnames)
                for col in ("提示词修正意见", "修正后prompt"):
                    if col not in fn:
                        fn.append(col)
                fieldnames = fn
                for r in reader:
                    rows.append(r)
            wkey = str(int(writing))
            found = False
            for r in rows:
                raw = (r.get("写法号") or "").strip()
                norm = raw
                try:
                    norm = str(int(raw))
                except (ValueError, TypeError):
                    norm = raw
                if norm == wkey:
                    r["提示词修正意见"] = note
                    r["修正后prompt"] = next_prompt
                    found = True
                    break
            if not found:
                new_row = {c: "" for c in fieldnames}
                new_row["写法号"] = wkey
                new_row["提示词修正意见"] = note
                new_row["修正后prompt"] = next_prompt
                rows.append(new_row)
            tmp = csv_path + ".tmp"
            with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in rows:
                    writer.writerow({c: (r.get(c) or "") for c in fieldnames})
            os.replace(tmp, csv_path)
            return True
        except Exception as e:
            print("[correction] 写回 CSV 失败:", e)
            return False

    def _serve_correction(self, data):
        """T-19: POST /batch/api/correction 接收 {writing, note, next_prompt[, batch]}。

        data 为 do_POST 已读取的请求体字节 (避免重复读取 rfile 导致挂起)。
        校验 writing∈1..27、note/next_prompt 为字符串且不含路径穿越/超长,
        然后写回对应批次 writing_purpose.csv。成功 200 JSON, 非法 400, 写入失败 403。
        """
        try:
            body = json.loads(data.decode("utf-8")) if data else {}
        except Exception as e:
            self._send(400, json.dumps({"ok": False, "error": "bad json: " + str(e)}))
            return
        if not isinstance(body, dict):
            self._send(400, json.dumps({"ok": False, "error": "body 必须是对象"}))
            return
        writing = body.get("writing")
        note = body.get("note", "")
        next_prompt = body.get("next_prompt", "")
        batch = body.get("batch", "batch-001")
        # writing 必须为 1..27 整数
        try:
            writing = int(writing)
        except (TypeError, ValueError):
            self._send(400, json.dumps({"ok": False, "error": "writing 必须为 1..27 整数"}))
            return
        if writing < 1 or writing > 27:
            self._send(400, json.dumps({"ok": False, "error": "writing 超出范围 1..27"}))
            return
        if not isinstance(note, str) or not isinstance(next_prompt, str):
            self._send(400, json.dumps({"ok": False, "error": "note/next_prompt 必须为字符串"}))
            return
        # next_prompt 仅作文本落盘, 绝不拼路径: 禁路径穿越字符 / 超长
        if (len(next_prompt) > 20000 or "\x00" in next_prompt
                or "../" in next_prompt or "..\\" in next_prompt
                or next_prompt.startswith("..")):
            self._send(400, json.dumps({"ok": False, "error": "next_prompt 含非法字符或超长"}))
            return
        if len(note) > 20000 or "\x00" in note:
            self._send(400, json.dumps({"ok": False, "error": "note 含非法字符或超长"}))
            return
        # batch 白名单
        if batch not in BATCH_DIRS:
            self._send(400, json.dumps({"ok": False, "error": "未知批次: " + str(batch)}))
            return
        csv_path = os.path.join(BATCH_DIRS[batch], "writing_purpose.csv")
        ok = self._update_writing_purpose(csv_path, writing, note, next_prompt)
        if ok:
            self._send(200, json.dumps({"ok": True, "writing": writing, "batch": batch}))
        else:
            self._send(403, json.dumps({"ok": False, "error": "写入 writing_purpose.csv 失败"}))

    def _serve_board_prototype(self, path="/board-prototype/"):
        """项目生命周期看板原型（T-0822）：整目录静态托管在 /board-prototype。"""
        rel = path[len("/board-prototype"):].lstrip("/")
        rel = urllib.parse.unquote(rel)
        norm_base = os.path.normpath(BOARD_PROTOTYPE_DIR)
        if rel == "" or rel.endswith("/"):
            rel = "index.html"
        full = os.path.normpath(os.path.join(norm_base, rel))
        if full != norm_base and not full.startswith(norm_base + os.sep):
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        if not os.path.isfile(full):
            self._send(404, json.dumps({"error": "not found: " + rel}))
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".htm": "text/html; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".json": "application/json",
            ".css": "text/css",
            ".js": "application/javascript",
        }.get(ext, "application/octet-stream")
        try:
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}))

    def _serve_board_prototype_asset(self, path):
        """T-0822: 项目生命周期看板原型资产路由。"""
        self._serve_board_prototype("/board-prototype/" + path)

    def _serve_train_video(self, rel):
        """训练实验视频（experiments 目录内 .mp4，防止目录穿越）。"""
        rel = rel.replace("\\", "/")
        if ".." in rel or not rel.endswith(".mp4"):
            self._send(403, json.dumps({"error": "forbidden"}))
            return
        fp = os.path.join(TRAIN_VIDEO, rel)
        if not os.path.isfile(fp):
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            with open(fp, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            pass

    def _train_experiments(self):
        """返回 experiments_data/ 下所有实验（倒序），含状态/候选/变体摘要。"""
        out = []
        if os.path.isdir(TRAIN_DATA):
            for fn in sorted(os.listdir(TRAIN_DATA), reverse=True):
                if fn.endswith(".json"):
                    try:
                        with open(os.path.join(TRAIN_DATA, fn), encoding="utf-8") as f:
                            out.append(json.load(f))
                    except Exception:
                        pass
        self._send(200, json.dumps({"ok": True, "experiments": out}, ensure_ascii=False))

    def _train_status_update(self, path):
        """老板看板操作：POST /training/api/experiments/<id>/status {status: adopted|rejected}"""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            status = data.get("status")
            if status not in ("adopted", "rejected", "candidate", "done"):
                self._send(400, json.dumps({"ok": False, "error": "无效状态"})); return
            eid = path.split("/")[4]
            fp = os.path.join(TRAIN_DATA, eid + ".json")
            if not os.path.isfile(fp):
                self._send(404, json.dumps({"ok": False, "error": "实验不存在"})); return
            with open(fp, encoding="utf-8") as f:
                exp = json.load(f)
            exp["status"] = status
            exp["reviewed_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(exp, f, ensure_ascii=False, indent=2)
            self._send(200, json.dumps({"ok": True, "status": status}))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)}))

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
    _rr = _get_route_registry()
    if _rr is not None:
        print("   路由注册表   route_registry.json  (%d 条路由·单一事实源)" % len(_rr))
    else:
        print("   路由注册表   缺失/解析失败 → 回退硬编码白名单（兼容模式）")
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
