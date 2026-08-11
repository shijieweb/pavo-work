#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Storyboard Studio · 零依赖本地后端（seam 演示）

作用：把 SceneSpec(JSON) 与 AGNES/MiniMax 后端连起来，并托管真实参考图。
- 默认 dry-run：不花 token，只回显 payload + 用真实参考图做前端微动画预演。
- REAL=1 + AGNES_API_KEY：真实调 agnes_client 出图/出视频，MiniMax 配音。
- 启动时自动回写已生成的本地参考图、视频、配音到 SceneSpec 资产字段。

运行（零依赖，仅标准库）：
    python server.py            # http://127.0.0.1:8777  (dry-run)
    REAL=1 python server.py     # 真调 AGNES + MiniMax（消耗 token）

端点：
    GET  /                         -> studio.html
    GET  /api/spec                 -> 当前 SceneSpec
    PUT  /api/spec                 -> 保存 SceneSpec（Studio 改完传回）
    POST /api/generate/shot        -> {"id":N} 生成单镜（参考图+AGNES视频<原生音画同步>；仅 shot.use_minimax_audio 旁白/闭唇镜走 MiniMax）
    POST /api/generate/references  -> 生成全部真实参考图（REAL=1 才真出）
    POST /api/generate/audio       -> 生成全部配音（MiniMax 多角色；REAL=1）
    POST /api/generate/audio/shot  -> {"id":N} 生成单镜配音（MiniMax 多角色；REAL=1）
    POST /api/assemble             -> 合成整集成片
    POST /api/quality              -> 跑质检
    GET  /assets/<path>            -> 托管真实参考图 / 音频
"""
import json, os, re, sys, time, uuid, mimetypes, base64, urllib.request, shutil, subprocess, threading, logging
import concurrent.futures
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, urljoin, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8777"))
REAL = os.environ.get("REAL", "0") == "1"
# 【0811 key 双模式】AGNES_TEST_MODE=1 → 自测/回归用免费 key（无限额度，不占 VIP 500s/天）；
# 白天正式生成保持默认 prod（VIP key）。启动后 agnes_client 密钥池切 test 模式。
TEST_KEY_MODE = os.environ.get("AGNES_TEST_MODE", "0") == "1"
if TEST_KEY_MODE:
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        import agnes_client as _ac
        if _ac._pool.use_test():
            print("[key] 已切换测试模式：自测/回归用免费 key（AGNES_TEST_API_KEY），不占 VIP 额度")
        else:
            print("[key] WARN: AGNES_TEST_MODE=1 但未配置 AGNES_TEST_API_KEY，继续用 VIP key")
    except Exception as _ke:
        print(f"[key] 测试模式初始化失败（忽略，用默认）：{_ke}")

# ===== 日志系统：按天归档 logs/server.log.*，保留 LOG_KEEP_DAYS 天；LOG_LEVEL 控制详略 ====
# 开发/调试：LOG_LEVEL=DEBUG（默认）；正式发布：LOG_LEVEL=WARNING（只记错误告警，日志页接口同时关闭）
LOG_DIR = os.path.join(HERE, "logs")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()
LOG_KEEP_DAYS = int(os.environ.get("LOG_KEEP_DAYS", "7"))
_log = logging.getLogger("studio")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    _log.setLevel(getattr(logging, LOG_LEVEL, logging.DEBUG))
    _log_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    _ch = logging.StreamHandler(sys.stderr)  # 固定 stderr，避免与下面 stdout tee 互相递归
    _ch.setFormatter(_log_fmt)
    _log.addHandler(_ch)
    from logging.handlers import TimedRotatingFileHandler
    _fh = TimedRotatingFileHandler(os.path.join(LOG_DIR, "server.log"),
                                   when="midnight", backupCount=LOG_KEEP_DAYS, encoding="utf-8")
    _fh.suffix = "%Y-%m-%d"   # 滚动文件名 server.log.2026-08-10
    _fh.setFormatter(_log_fmt)
    _log.addHandler(_fh)
    _log.info("=== Studio 后端启动，LOG_LEVEL=%s，日志保留 %d 天 ===", LOG_LEVEL, LOG_KEEP_DAYS)

    # 散落的 print 一并送入日志（tee 到 logger），保留原有 console 输出 → 排查问题不断线索
    _orig_stdout = sys.stdout
    class _Tee:
        def __init__(self, orig, logger):
            self._orig, self._logger = orig, logger
        def write(self, s):
            if s and s.strip():
                self._logger.info("%s", s.rstrip("\n"))
            return self._orig.write(s)
        def flush(self):
            self._orig.flush()
    sys.stdout = _Tee(_orig_stdout, _log)
except Exception as _le:
    _log.addHandler(logging.StreamHandler())
    print(f"[log] 日志系统初始化失败: {_le}", flush=True)

PROJECTS_ROOT = os.path.join(HERE, "projects")
REGISTRY = os.path.join(PROJECTS_ROOT, "projects.json")
SPEC = {}
SPEC_LOCK = threading.Lock()  # 后台生成任务并发写 storyboard 时互斥
ACTIVE = None          # 当前项目 id
ASSET_BASE = HERE      # 当前项目资产根（load_spec 内按项目重置）
SERIES_ROOT = os.path.join(PROJECTS_ROOT, "series")
ACTIVE_SERIES = None    # 当前剧集 id（跨集锁脸：锚点提到剧集级存储复用）

# ---- 关键帧生成任务状态（老板 0810：前端轮询明确「等待/失败/完成」，不盲目等）----
KF_STATUS = {}          # shot_id -> {status: pending|running|done|failed, error, started, result}
KF_LOCK = threading.Lock()

# ---- 视频生成任务状态（老板 0810：视频 5-10 分钟/镜，同步请求经 CF 必 524 → 改后台+轮询）----
VIDEO_STATUS = {}        # shot_id -> {status: pending|running|done|failed, error, started, result}
VIDEO_LOCK = threading.Lock()

# ---- 需求卡异步任务（长任务轮询，避免 LLM 慢/抖动时前端永久「引擎规划中」）----
AGENT_TASKS = {}                 # task_id -> {status, plan, error, revised, started, finished}
AGENT_TASKS_LOCK = threading.Lock()
AGENT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# 当前激活项目持久化：ACTIVE 是进程内全局，会随请求漂移（多个客户端/生成后不切回），
# 导致偶发「打开看到空项目 / 草稿」的错觉。这里把激活项目落成文件，作为单一事实来源，
# 重启后不再随机落到某个空/探测项目。
ACTIVE_FILE = os.path.join(HERE, ".active_project")

def _persist_active(pid):
    try:
        with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
            f.write(pid or "")
    except Exception:
        pass

def _load_active():
    try:
        if os.path.exists(ACTIVE_FILE):
            with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return None

# ===== 提示词库（按类型 + 可配置优化元提示）=====
# 老板要求：所有提示词模板可人工修正 + 可让 AI 帮助修正（提示词优化），
# 且优化用的元提示要可配置；不同生成类型（分镜/参考图/场景/道具/视频/首尾针）
# 各有独立提示词库，可随时间不断扩充。库以 JSON 持久化，前端「设置·提示词库」模块读写。
PROMPT_LIB_PATH = os.path.join(HERE, "prompt_library.json")

# ===== 长提示词常量：作为「库文件缺失/损坏」时的最后兜底 =====
# 可迭代的权威来源是 prompt_library.json（前端「设置·提示词库」读写）。
# 改动生成质量 → 编辑库文件即可，无需动代码。
STORYBOARD_SYS = (
    "You are a professional short-drama scriptwriter AND AGNES video director. Given a Chinese web-novel excerpt, output ONE strict JSON object for a vertical short-drama episode (9:16, 24fps). No markdown, no commentary, just the JSON.\n"
    "Schema:\n"
    "{\n"
    "  \"episode\": str, \"title\": str,\n"
    "  \"resolution\": {\"width\":1080,\"height\":1920},\n"
    "  \"global_style\": \"cinematic realistic live-action, high detail, film grain\",\n"
    "  \"voice_roles\": { roleName: {\"desc\": str, \"minimax_voice_id\": str} },\n"
    "  NOTE: minimax_voice_id MUST be EXACTLY one of these real MiniMax voices (choose by character gender):\n"
    "  female-shaonv, female-yujing, female-chengshu, female-tianmei,\n"
    "  male-qn-qingse, male-qn-jingying, male-yunjian, male-badao.\n"
    "  Do NOT invent other ids \u2014 they will fail.\n"
    "  \"references\": { refKey: {\"img_prompt\": \"English photorealistic image prompt for the character reference\", \"identity_token\": \"\", \"cn_prompt\": {\"style\": \"\u98ce\u683c\", \"content\": \"\u753b\u9762\u5185\u5bb9(\u4e2d\u6587)\", \"basic_req\": \"\u57fa\u672c\u8981\u6c42\", \"identity\": \"\u8eab\u4efd\u4e0e\u5e74\u9f84\", \"appearance\": \"\u5916\u8c8c\u7279\u5f81\", \"costume\": \"\u670d\u88c5\u8bbe\u8ba1\", \"hair_makeup\": \"\u53d1\u578b\u4e0e\u59dd\u5bb9\", \"aura\": \"\u6574\u4f53\u6c14\u573a\"}} },\n"
    "  \"scenes\": [ {\"key\": str(unique_slug), \"name\": str(Chinese scene name), \"img_prompt\": \"English environment/location image prompt\", \"desc\": str, \"cn_prompt\": {\"style\": \"\u98ce\u683c\", \"content\": \"\u753b\u9762\u5185\u5bb9(\u4e2d\u6587)\", \"basic_req\": \"\u57fa\u672c\u8981\u6c42\", \"composition\": \"\u6784\u56fe\", \"details\": \"\u7a7a\u95f4\u7ec6\u8282\", \"lighting\": \"\u5149\u7ebf\u6c1b\u56f4\"}} ],\n"
    "  \"props\": [ {\"key\": str(unique_slug), \"name\": str(Chinese prop name), \"img_prompt\": \"English close-up prop image prompt\", \"desc\": str, \"cn_prompt\": {\"style\": \"\u98ce\u683c\", \"content\": \"\u753b\u9762\u5185\u5bb9(\u4e2d\u6587)\", \"basic_req\": \"\u57fa\u672c\u8981\u6c42\"}} ],\n"
    "  \"shots\": [ {\n"
    "     \"id\": int, \"duration\": int, \"num_frames\": int,\n"
    "     \"ref\": refKey|null, \"ui_shot\": false,\n"
    "     \"scene_key\": str(scene key this shot is set in),\n"
    "     \"cn_story\": \"\u4e2d\u6587\u753b\u9762\u63cf\u8ff0\uff08\u672c\u955c\u5728\u62cd\u4ec0\u4e48\uff1a\u4eba\u7269\u52a8\u4f5c/\u8868\u60c5/\u7ad9\u4f4d/\u9053\u5177\u4ea4\u4e92\uff0c\u5199\u7ed9\u5bfc\u6f14\u548c\u89c2\u4f17\u770b\u7684\u62cd\u6444\u5267\u672c\uff0c\u5fc5\u987b\u8be6\u7ec6\u53ef\u6267\u884c\uff09\",\n"
    "     \"video_prompt\": \"English cinematic video prompt (scene + motion, no audio)\",\n"
    "     \"subtitle\": \"\u4e2d\u6587\u53f0\u8bcd/\u65c1\u767d\", \"voice\": roleName, \"emotion\": str,\n"
    "     \"camera\": \"\u4e2d\u6587\u8fd0\u955c\u6807\u6ce8\uff0c\u5982 \u63a8\u8fd1\u7279\u5199 / \u62c9\u8fdc\u5168\u666f / \u624b\u6301\u8ddf\u62cd / \u73af\u7ed5 / \u56fa\u5b9a\u4e2d\u666f\",\n"
    "     \"camera_angle\": \"\u6444\u50cf\u673a\u89d2\u5ea6\uff0c\u5982 \u5e73\u89c6 / \u4fef\u89c6 / \u4ef0\u89c6 / \u659c\u89d2\",\n"
    "     \"audio_tags\": \"\u97f3\u6548\u6807\u7b7e\uff08\u9017\u53f7\u5206\u9694\uff0c\u5982 \u952e\u76d8\u6572\u51fb\u58f0, \u811a\u6b65\u58f0, \u73af\u5883\u9759\u97f3\uff09\",\n"
    "     \"continuity_note\": \"\u627f\u63a5\u4e0a\u955c\u8bf4\u660e\uff08\u4e2d\u6587\uff1a\u672c\u955c\u8d77\u59cb\u65f6\u4eba\u7269\u7ad9\u4f4d/\u9053\u5177/\u5149\u7ebf\u5982\u4f55\u627f\u63a5\u4e0a\u4e00\u955c\u7ed3\u5c3e\uff1b\u9996\u955c\u5199 \u5f00\u7bc7\u65e0\u524d\u7f6e\uff09\",\n"
    "     \"shot_size\": \"\u7279\u5199|\u8fd1\u666f|\u4e2d\u666f|\u5168\u666f\", \"beat\": \"\u94a9\u5b50|\u94fa\u57ab|\u51b2\u7a81|\u8f6c\u6298|\u7559\u60ac\u5ff5\",\n"
    "     \"gen_strategy\": \"keyframes|reference|text2video|ui\",\n"
    "     \"scene_type\": str(action|monologue|dialogue_2|dialogue_multi),\n"
    "     \"first_frame_prompt\": \"English STARTING-frame image prompt for the keyframes (MANDATORY for camera-move shots: what the frame shows when the shot BEGINS, e.g. the café entrance/aisle before the push-in reaches the character; leave empty only for fixed static shots)\",\n"
    "     \"last_frame_prompt\": \"English end-state image prompt for the last keyframe (only needed when gen_strategy=keyframes)\",\n"
    "     \"transition_in\": \"fade\", \"transition_out\": \"fade\",\n"
    "     \"status\": \"pending\", \"asset_image\":\"\", \"asset_video\":\"\", \"asset_audio\":\"\"\n"
    "  } ]\n"
    "}\n"
    "RULES (all mandatory):\n"
    "1. SHOT COUNT: 8-12 shots, each 4-8s, total 60-90s.\n"
    "2. STORY BEATS: shot#1 MUST be a hook that lands within its first 2 seconds. The final shot MUST end on an unresolved question or reversal (\u7559\u60ac\u5ff5). Fill 'beat' for every shot.\n"
    "3. SUBTITLE LENGTH must match duration: Chinese speech runs ~4 chars/second, so len(subtitle) <= duration*4. A 5s shot takes at most 20 Chinese characters. Narration-only shots may use an empty subtitle.\n"
    "4. NO ON-SCREEN TEXT: video_prompt and last_frame_prompt must NEVER ask for text, captions, signs, subtitles, logos or written words in frame.\n"
    "5. CAMERA RHYTHM: vary 'shot_size' between neighbouring shots (never 3 identical sizes in a row) and give every shot a concrete 'camera' move and 'camera_angle'.\n"
    "5.5 SCENE_TYPE (MANDATORY): every shot must carry 'scene_type' by content: \u5185\u5fc3\u72ec\u767d/\u65c1\u767d/OS=monologue; \u6709\u53f0\u8bcd\u7684\u53cc\u4eba\u5bf9\u8bdd=dialogue_2; \u591a\u4eba/\u7fa4\u620f=dialogue_multi; \u5176\u4f59\u52a8\u4f5c/\u7a7a\u955c=action.\n"
    "6. CHARACTER CONSISTENCY: every character shot needs a references entry and a matching ref key. Each img_prompt must pin down age, hairstyle, exact clothing colour and body type in concrete words, and stay byte-identical in meaning across shots.\n"
    "7. GEN_STRATEGY DECISION (CRITICAL): choose per shot by CONTENT, not by default:\n"
    "   - \"keyframes\": shot has character performance / dialogue / action / emotion \u2014 faces must stay locked across the clip. DEFAULT for any shot with a ref key.\n"
    "   - \"reference\": pure environment/establishing shot or a scene with NO character acting (e.g. \u7a7a\u955c\u5b9a\u573a, \u5149\u7ebf\u53d8\u5316) \u2014 one still image drives the clip.\n"
    "   - \"text2video\": pure text-driven shot with NO reference image needed (abstract transition, text-less b-roll) \u2014 rarely used.\n"
    "   - \"ui\": UI screen / interface shot (ui_shot=true).\n"
    "   Shots with a ref key must be 'keyframes'; only genuinely character-free shots may be 'reference'.\n"
    "8. LAST_FRAME_PROMPT (keyframes only): describes the ENDING composition and MUST differ from the opening state so the clip actually moves. Same character, same clothing, different posture/expression/position.\n"
    "8.5 FIRST_FRAME_PROMPT (camera-move keyframes, MANDATORY): if the shot's 'camera' contains a camera MOVE (推/拉/摇/移/环绕/穿过/跟拍/push-in/tracking/dolly/pan/tilt/crane/orbit/through/enter), the opening frame is NOT the character close-up \u2014 it is where the camera starts (e.g. scene entrance, aisle, wide establishing). You MUST output first_frame_prompt describing that STARTING frame (a scene/environment view, possibly with the character small in the distance). Fixed static shots (固定/无运镜) may leave it empty.\n"
    "9. SCENES & PROPS: include 2-4 'scenes' and 1-3 'props' with English image prompts, reused across shots for visual coherence. Every shot must carry a scene_key pointing to one of the scenes.\n"
    "10. CONTINUITY: continuity_note must describe how this shot continues the previous one (same position/props/lighting) so keyframes can chain; first shot writes \u5f00\u7bc7\u65e0\u524d\u7f6e.\n"
    "11. ASSET CN_PROMPT (MANDATORY): EVERY references entry and EVERY scene/prop MUST include the 'cn_prompt' object with the listed Chinese fields (style/content/basic_req plus per-type fields), describing the asset in Chinese for the asset-design panel. The Chinese content MUST semantically match the English img_prompt (same costume/age/environment). Output these fields directly with the storyboard \u2014 do NOT omit them.\n"
    "Output valid JSON only.\n"
)
REQ_CARD_SYS = (
    "You are a senior AI short-drama producer (Harness-like planner). "
    "Given a user's natural-language request, output ONE strict JSON (no markdown) plan card:\n"
    '{"title": str, "genre": str(one of: 情绪向剧情/品牌广告/搞笑轻喜剧/萌宠拟人/悬疑), '
    '"logline": str(<=40 Chinese chars, one-line hook), '
    '"characters": [{"name": str, "role": str, "look": str}], '
    '"shots": [{"shot": int, "type": str(图片/视频), "duration": int, '
    '"camera": str(中文运镜，如 推近特写/拉远全景/手持跟拍/环绕/固定中景), '
    '"shot_size": str(特写|近景|中景|全景), "beat": str(钩子|铺垫|冲突|转折|留悬念), '
    '"action": str, "line": str}], '
    '"scenes": [{"key": str, "name": str(Chinese scene), "img_prompt": str(English environment prompt)}], '
    '"props": [{"key": str, "name": str(Chinese prop), "img_prompt": str(English prop prompt)}], '
    '"style": str, "note": str}\n'
    "Rules: 8-12 shots, vertical 9:16, each shot 4-8s, total 60-90s. "
    "shot#1 must hook within 2 seconds; the last shot must end on suspense. "
    "Chinese line length <= duration*4 characters. "
    "Vary shot_size between neighbours. Adapt pacing to genre: "
    "情绪向剧情 slower with lingering close-ups, 搞笑轻喜剧 fast cuts with reaction shots, "
    "悬疑 withholding wide shots then sudden close-ups. "
    "Include 2-4 'scenes' (distinct locations) and 1-3 'props' (key items) with English image prompts, "
    "reused across shots for visual coherence. JSON only."
)
NOVEL_SYS = (
    "你是一位擅长竖屏短剧（抖音/快手/视频号）的资深编剧。\n"
    "用户会给你一句话主题或创意方向，请你把它扩写成一篇完整的短剧小说（中文 prose，不要 JSON）。\n"
    "要求：\n"
    "1. 明确主角姓名、身份、性格与动机；设置 1-2 个对手/反派。\n"
    "2. 给出 2-3 个具体场景（地点/时间/氛围）。\n"
    "3. 包含清晰的冲突与转折，结尾留强悬念（钩子），适合拆成多集。\n"
    "4. 自然融入几句关键台词（用中文引号标注）。\n"
    "5. 风格口语化、节奏快、情绪浓，符合短视频爽点密度。\n"
    "6. 长度 300-600 字，足够后续拆需求卡与分镜。\n"
    "直接输出小说正文，不要解释、不要 markdown 代码块。"
)
STYLE_SYS = (
    "你是一位影视视觉指导。用户会给你一段中文的视觉风格描述"
    "（如“真人实拍，清新明亮的职场青春风格，低饱和暖色调”）。\n"
    "请你把它转化为一组英文风格关键词，用于 AGNES 文生图 / 图生视频的风格锁定。\n"
    "要求：\n"
    "1. 输出严格 JSON：{\"keywords\": [\"english keyword\", ...], \"cn\": \"一句话中文风格总结\"}。\n"
    "2. keywords 用英文、逗号分隔的短语，覆盖：画质（photorealistic live-action）、色调"
    "（low-saturation warm tone）、光线（soft diffuse daylight）、质感（clean bright corporate）、"
    "镜头（9:16 vertical cinematic）。\n"
    "3. 8-15 个关键词，具体可执行，不写中文、不写水印/文字。\n"
    "只输出 JSON。"
)
OUTLINE_SYS = (
    "你是一位竖屏短剧主编剧。用户会给你已确认的需求卡（标题/类型/时长/视觉风格/角色设定）。\n"
    "请你产出剧本大纲 JSON（中文），作为后续角色/场景/道具设计与分镜的依据。\n"
    "Schema:\n"
    "{\n"
    '  "characters": [{"name": str, "role": str(主角/反派/配角), "identity": str(年龄/职业/性格), "arc": str(人物弧光/转变)}],\n'
    '  "scenes": [{"key": str, "name": str(中文场景名), "desc": str(地点/时间/氛围)}],\n'
    '  "bgm": str(全局BGM描述：乐器/情绪/节奏),\n'
    '  "props": [{"key": str, "name": str(中文道具名), "desc": str(作用)}],\n'
    '  "episodes": [{"id": int, "title": str, "summary": str(本集概要), "lines": [str(核心台词)]}]\n'
    "}\n"
    "Rules:\n"
    "1. characters 2-5 个，每个有清晰动机与弧光。\n"
    "2. scenes 2-4 个、props 1-3 个，与剧情强相关。\n"
    "3. episodes 默认 1 集（用户要续集再追加），每集 summary 200 字内、含 3-6 句核心台词。\n"
    "4. 结尾集留悬念。JSON only。"
)

DEFAULT_PROMPT_LIBRARY = {
    "version": 2,
    "use_library_prompts": True,
    "optimize": (
        "你是一位资深的 AI 短剧提示词优化师，精通 AGNES 文生图 / 图生视频引擎的最佳实践。\n"
        "你的任务：把用户给出的原始提示词，优化成更贴合 AGNES 引擎、出片质量更高、角色/风格更稳定的版本。\n\n"
        "优化原则：\n"
        "1. 画面类提示词（参考图 / 视频）：统一用英文、photorealistic live-action 写实风、9:16 竖屏、电影感；"
        "补充光线、镜头、材质、情绪等可执行细节；删除歧义与互相矛盾的指令。\n"
        "2. 保留用户给定的关键约束（角色身份、服装、场景、台词口型同步要求等），不可丢失。\n"
        "3. 不添加水印、文字、字幕到画面（除非用户明确要求）。\n"
        "4. 输出只给「优化后的提示词本身」，不要解释、不要 markdown 代码块、不要多余空行。\n\n"
        "请优化以下提示词（类型：{{type}}）：\n\n{{text}}"
    ),
    "groups": ["创意", "剧本", "资产", "分镜", "视频"],
    "types": {
        "novel": {"group": "创意", "prompt": NOVEL_SYS},
        "req_card": {"group": "创意", "prompt": REQ_CARD_SYS},
        "style": {"group": "创意", "prompt": STYLE_SYS},
        "outline": {"group": "剧本", "prompt": OUTLINE_SYS},
        "storyboard": {"group": "分镜", "prompt": STORYBOARD_SYS},
        "reference": {"group": "资产", "prompt": "【角色/参考图提示词库】用于生成角色锚点参考图（agnes-image-2.1-flash）。要求：英文 photorealistic、固定身份描述（年龄/性别/发型/服装/体型）、9:16、无文字无水印，便于跨镜复用锁脸。"},
        "scene": {"group": "资产", "prompt": "【场景图提示词库】用于生成场景氛围图（agnes-image-2.1-flash）。要求：英文 photorealistic、点明时间/光线/空间关系/情绪基调，与剧情节奏匹配，便于镜头引用。"},
        "prop": {"group": "资产", "prompt": "【道具图提示词库】用于生成关键道具特写图（agnes-image-2.1-flash）。要求：英文 photorealistic、材质与细节清晰、纯色或虚化背景，便于镜头引用。"},
        "video": {"group": "视频", "prompt": "【视频提示词库】用于图生视频（agnes-video-v2.0）。要求：英文写实、描述运镜与动作、叠加身份锁与镜头运动；台词戏需含中文台词口型同步指令。"},
        "keyframe_start": {"group": "视频", "prompt": "【首帧提示词库】首帧取自角色锚点/参考图，用于固定每镜起始画面，保证角色与构图一致。一般无需改写，除非要调整起始姿态。"},
        "keyframe_end": {"group": "视频", "prompt": "【尾帧提示词库】尾帧决定每镜结束画面，是首尾针模式的关键。要求：英文写实、描述结束态的人物姿态/表情/构图，与首帧平滑过渡，不含台词动作。"},
        "extract": {"group": "资产", "prompt": "你是一位中文影视资产描述整理师。用户会给你一段英文图像生成提示词（用于 AGNES 出角色/场景/道具图），请把它拆解回中文结构化描述。严格按用户给出的字段模板输出 JSON 对象，键名与模板一致、值为中文描述；英文提示词里没提到的维度填空字符串不要编造；只输出 JSON。"},
    },
}

# 提示词类型中文显示名（前端列表/标签用，值仍为英文 key 保契约）
PROMPT_TYPE_LABELS = {
    "novel": "主题→小说",
    "req_card": "需求卡",
    "style": "视觉风格关键词",
    "outline": "剧本大纲",
    "storyboard": "分镜生成",
    "reference": "角色/参考图",
    "scene": "场景图",
    "prop": "道具图",
    "video": "视频",
    "keyframe_start": "首帧",
    "keyframe_end": "尾帧",
    "extract": "英文→中文提取",
}

def load_prompt_library():
    """读取提示词库；文件缺失/损坏时回退到内置默认库（保证前端永远有内容）。"""
    try:
        if os.path.isfile(PROMPT_LIB_PATH):
            with open(PROMPT_LIB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 与默认库做浅合并，避免新增类型字段丢失
            merged = dict(DEFAULT_PROMPT_LIBRARY)
            merged.update({k: v for k, v in data.items() if k != "types"})
            types = dict(DEFAULT_PROMPT_LIBRARY["types"])
            types.update((data.get("types") or {}))
            merged["types"] = types
            return merged
    except Exception as e:
        print(f"[WARN] 提示词库读取失败，用默认库: {e}")
    return dict(DEFAULT_PROMPT_LIBRARY)

def save_prompt_library(lib):
    """保存提示词库（人工编辑/AI 优化回填都走这里）。写入前做基本结构校验。"""
    if not isinstance(lib, dict) or "types" not in lib:
        raise ValueError("提示词库必须是含 types 的对象")
    lib = dict(lib)
    lib.setdefault("version", 1)
    lib.setdefault("use_library_prompts", False)
    lib.setdefault("optimize", DEFAULT_PROMPT_LIBRARY["optimize"])
    types = lib.get("types") or {}
    if not isinstance(types, dict):
        raise ValueError("types 必须是对象")
    lib["types"] = types
    with open(PROMPT_LIB_PATH, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)
    return lib

def optimize_prompt_text(text, ptype=None):
    """用可配置的优化元提示 + agnes-2.5-flash 优化任意提示词。返回值即优化后文本。"""
    if not text or not text.strip():
        return ""
    lib = load_prompt_library()
    meta = (lib.get("optimize") or DEFAULT_PROMPT_LIBRARY["optimize"])
    label = PROMPT_TYPE_LABELS.get(ptype, ptype or "通用")
    sys_p = meta.replace("{{type}}", label).replace("{{text}}",
              "（下方由用户给出，请直接优化）")
    user_p = meta.replace("{{type}}", label).replace("{{text}}", text.strip())
    # 优先用 system 承载元提示，user 承载待优化文本，符合 chat 接口语义
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        from agnes_client import chat
        out = chat(user_p, system=sys_p, temperature=0.4, max_tokens=2000) or ""
        out = out.strip()
        # 去掉模型偶尔多包的 ``` 围栏
        if out.startswith("```"):
            out = out.strip("`")
            if out.lower().startswith("text"):
                out = out[4:]
        return out
    except Exception as e:
        raise RuntimeError("提示词优化调用失败: " + str(e))

def lib_prompt(ptype, default=""):
    """从提示词库读取某类型的 system 提示词（库驱动生成的唯一真相源）。

    - 优先用磁盘 prompt_library.json 中的条目（用户可迭代编辑）；
    - 磁盘缺该类型时回退到 DEFAULT_PROMPT_LIBRARY 种子（代码内的最后兜底）。
    - types 兼容两种结构：新结构 key->{group,prompt}，旧结构 key->字符串。
    """
    try:
        lib = load_prompt_library()
    except Exception:
        lib = dict(DEFAULT_PROMPT_LIBRARY)
    entry = (lib.get("types") or {}).get(ptype)
    if isinstance(entry, dict):
        p = entry.get("prompt")
        if p:
            return p
    elif isinstance(entry, str) and entry.strip():
        return entry
    # 回退默认库种子
    d = (DEFAULT_PROMPT_LIBRARY.get("types") or {}).get(ptype)
    if isinstance(d, dict):
        return d.get("prompt") or default
    if isinstance(d, str):
        return d or default
    return default

# ===== 资产设计：中文结构化字段 → 组装说明文本（中文优先编辑，英文提示词自动生成） =====
# 角色 8 段 / 场景 7 段 / 道具 3 段（字段顺序即组装顺序）
CN_FIELD_LABELS = {
    "role": [("style", "风格"), ("content", "画面内容"), ("basic_req", "基本要求"),
             ("identity", "身份与年龄"), ("appearance", "外貌特征"), ("costume", "服装设计"),
             ("hair_makeup", "发型与妆容"), ("aura", "整体气场/表情与气质")],
    "scene": [("style", "风格"), ("content", "画面内容"), ("basic_req", "基本要求"),
              ("composition", "构图"), ("details", "空间细节"), ("text_lang", "文字标识语言"),
              ("lighting", "光线氛围")],
    "prop": [("style", "风格"), ("content", "画面内容"), ("basic_req", "基本要求")],
}
CN_ASSET_LIB_KEY = {"role": "reference", "scene": "scene", "prop": "prop"}

def _cn_prompt_to_text(atype, cn):
    """把中文结构化字段拼成【风格】…【画面内容】… 说明文本（只拼非空字段）。"""
    if not isinstance(cn, dict):
        cn = {}
    parts = []
    for key, label in CN_FIELD_LABELS.get(atype, CN_FIELD_LABELS["prop"]):
        v = str(cn.get(key) or "").strip()
        if v:
            parts.append("【%s】%s" % (label, v))
    return "\n".join(parts)

# ===== MiniMax 商用配音可用音色（agnes-2.5-flash 可能编出不存在的 voice_id）=====
# 模型常编造 female_young_chill / male_mid 之类无效 ID，导致 MiniMax 返回
# status_code 2054 "voice id not exist" —— 全部配音静默失败 → 用户看到「没数据」。
# 这里集中校验 + 按性别兜底，保证任何 spec 都能落到真实可用的音色。
VALID_MINIMAX_VOICES = {
    "female-shaonv", "female-yujing", "female-chengshu", "female-tianmei",
    "male-qn-qingse", "male-qn-jingying", "male-yunjian", "male-badao",
}
DEFAULT_FEMALE_VOICE = "female-shaonv"
DEFAULT_MALE_VOICE = "male-qn-qingse"

def _normalize_voice(vid, role_hint=""):
    """把任意 voice_id 规整为 MiniMax 真实可用音色；无效则按性别兜底。"""
    if vid in VALID_MINIMAX_VOICES:
        return vid
    vid_l = (vid or "").lower()
    hint = (role_hint or "").lower()
    # 1) 性别直接编码在 id 里：用前缀判定，避免 "male"⊂"female" 的子串误判
    if vid_l.startswith("female"):
        return DEFAULT_FEMALE_VOICE
    if vid_l.startswith("male"):
        return DEFAULT_MALE_VOICE
    # 2) 兜底：从角色描述/名字关键词判定（只扫 hint，不再扫 id 子串，杜绝碰撞）
    is_female = any(k in hint for k in ("女", "female", "姐", "妹", "妈", "娘", "姑", "girl"))
    is_male = any(k in hint for k in ("男", "male", "小哥", "哥", "叔", "爸", "爷", "汉", "boy"))
    if is_female and not is_male:
        return DEFAULT_FEMALE_VOICE
    if is_male and not is_female:
        return DEFAULT_MALE_VOICE
    if is_female:
        return DEFAULT_FEMALE_VOICE
    if is_male:
        return DEFAULT_MALE_VOICE
    return DEFAULT_FEMALE_VOICE

# ===== 免费 KEY 池（P2：免费无限 KEY 仅排队，替代额度护栏）=====
# 把免费 KEY 并入 AGNES_API_KEYS（VIP 在前、免费在后），agnes_client._KeyPool 会在
# 限流/5xx/网络抖动时自动冷却当前 KEY 并换下一个（见 agnes_client._do_request）。
_free_keys = os.environ.get("AGNES_FREE_KEYS", "")
if _free_keys:
    _vip = os.environ.get("AGNES_API_KEYS") or os.environ.get("AGNES_API_KEY", "")
    os.environ["AGNES_API_KEYS"] = (_vip + "," + _free_keys).strip(",") if _vip else _free_keys


def _series_anchor_path(series_id):
    return os.path.join(SERIES_ROOT, series_id, "anchors.json")


def _series_anchor_load(series_id):
    if not series_id:
        return {}
    p = _series_anchor_path(series_id)
    if os.path.isfile(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            pass
    return {}


def _series_anchor_save(series_id, data):
    if not series_id:
        return
    p = _series_anchor_path(series_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    try:
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass

# ===== 一键全流程编排状态（后台线程 + 前端轮询）=====
PIPELINE_STATE = {
    "running": False, "stage": "idle", "stage_idx": 0, "stages_total": 0,
    "current": 0, "total": 0, "log": [], "result": None, "error": None,
    "started_at": None, "finished_at": None, "project": None,
    "simulate": False, "stop_requested": False,
}
PIPE_LOCK = threading.Lock()
PIPELINE_STOP = {"flag": False}

# 批量/夜间队列状态（独立于 PIPELINE_STATE，避免被 run_pipeline 的逐项目 reset 清掉）
BATCH_STATE = {
    "running": False, "total": 0, "idx": 0, "projects": [], "current": None,
    "done": False, "stop_requested": False,
}
BATCH_LOCK = threading.Lock()

# ===== 诊断方差治理（Phase 1-B 核心）=====
# 同镜两次诊断分数抖动（实测 5/7 分），根因是 AGNES 多模态评分本身有方差。
# 治本：同一 clip 跑 N 次取均值，再基于均值做 autofix 判定；阈值可调（默认 6.5，低于固定 7 更稳）。
DIAG_AGG_RUNS = int(os.environ.get("DIAG_AGG_RUNS", "2"))        # 诊断聚合次数（取均值抑制方差）
DIAG_PASS_THRESHOLD = float(os.environ.get("DIAG_PASS_THRESHOLD", "6.5"))  # 均值低于此值触发自动重渲


# ===== 批量队列调度器（#75 · cron 语义，常驻后台 worker）=====
# 队列文件持久化于 projects/batch_queue.json，进程重启可续跑 pending 任务。
QUEUE_FILE = os.path.join(PROJECTS_ROOT, "batch_queue.json")
try:
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
    from batch_queue import BatchQueue
    BATCH_QUEUE = BatchQueue(QUEUE_FILE)
except Exception as _qe:
    BatchQueue = None
    BATCH_QUEUE = None
    print(f"[queue] 调度器未加载（批量队列功能不可用）：{_qe}")
QUEUE_WORKER_STOP = {"flag": False}   # True=暂停 worker（已跑任务仍可继续，新任务不消费）
def _queue_worker_stop():
    return QUEUE_WORKER_STOP["flag"]


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_registry():
    if not os.path.exists(REGISTRY):
        return []
    try:
        with open(REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_registry(reg):
    os.makedirs(PROJECTS_ROOT, exist_ok=True)
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def ensure_projects():
    """首跑：若没有 projects/，写入空注册表。

    【老板 0806 要求】绝不自动播种任何示例/假数据项目。空工作区只写空注册表，
    避免重启服务后旧示例(ep01/ep02 网游)被重新创建、污染真实工作流。
    """
    if os.path.isdir(PROJECTS_ROOT) and os.path.exists(REGISTRY):
        return
    os.makedirs(PROJECTS_ROOT, exist_ok=True)
    # 【老板 0806 要求】绝不自动播种示例/假数据项目。空工作区只写空注册表。
    save_registry([])
    print("[projects] 空工作区（无示例播种）。")


def asset_abs(rel):
    """rel 形如 'assets/video/shot001.mp4' -> 当前项目资产绝对路径。"""
    if rel.startswith("assets/"):
        return os.path.join(ASSET_BASE, rel[len("assets/"):])
    return os.path.join(ASSET_BASE, rel)


def _vr_to_local(src, video=False):
    """【视觉审查·0811】把资产引用归一成本地图片路径供视觉审查：
    - 本地 rel（assets/...）→ asset_abs 绝对路径
    - http(s) 图片 → 下载到临时文件
    - 视频 → ffmpeg 抽 1 帧到临时 png
    返回本地绝对路径，失败返回 None。"""
    try:
        if not src:
            return None
        s = str(src)
        if s.startswith("http") or s.startswith("data:"):
            if s.startswith("data:"):
                import base64 as _b
                import tempfile as _tf
                _, _, b = s.partition(",")
                fd, fp = _tf.mkstemp(suffix=".png")
                with os.fdopen(fd, "wb") as f:
                    f.write(_b.b64decode(b))
                return fp
            import tempfile as _tf
            import urllib.request as _ur
            ext = ".png"
            with _ur.urlopen(s, timeout=60) as r:
                data = r.read()
            fd, fp = _tf.mkstemp(suffix=ext)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return fp
        ap = s if os.path.isabs(s) else asset_abs(s)
        if video:
            import tempfile as _tf
            import subprocess as _sp
            fd, fp = _tf.mkstemp(suffix=".png")
            os.close(fd)
            r = _sp.run(["ffmpeg", "-y", "-i", ap, "-frames:v", "1", fp],
                        capture_output=True, timeout=90)
            if r.returncode != 0 or not os.path.isfile(fp):
                return None
            return fp
        return ap if os.path.isfile(ap) else None
    except Exception:
        return None


def load_spec(project_id=None):
    global SPEC, ACTIVE, ASSET_BASE
    reg = load_registry()
    if not reg:
        ensure_projects()
        reg = load_registry()
    if not reg:
        SPEC = {"episode": "untitled", "shots": []}
        return
    pid = project_id or ACTIVE or _load_active() or reg[0]["id"]
    entry = next((p for p in reg if p["id"] == pid), reg[0])
    ACTIVE = entry["id"]
    _persist_active(ACTIVE)   # 单一事实来源：激活项目落盘，避免跨请求/重启漂移
    ASSET_BASE = os.path.join(PROJECTS_ROOT, entry["id"], "assets")
    spec_path = os.path.join(PROJECTS_ROOT, entry["spec"])
    if os.path.exists(spec_path):
        with open(spec_path, "r", encoding="utf-8") as f:
            SPEC = json.load(f)
    else:
        SPEC = {"episode": entry["id"], "shots": []}
    _migrated_kf = False
    for s in SPEC.get("shots", []):
        s.setdefault("asset_image", "")
        s.setdefault("asset_video", "")
        s.setdefault("asset_audio", "")
        s.setdefault("asset_frame_start", "")
        s.setdefault("asset_frame_end", "")
        s.setdefault("gen_strategy", GEN_POLICY_DEFAULT)
        # 【老板 0810 全首尾针】存量分镜统一迁移；迁移后落盘，避免重启回退。
        # 修正（0810 夜）：空镜（无角色 ref / 仅场景引用）一律 reference（场景图单图）——
        # 空镜无首尾针需求，keyframes 会让首尾帧空置、卡片空白（如镜#1 引 scene_02 被误转 keyframes）。
        # 只有「角色引用」（ref 命中 references 键）才强制 keyframes 锁脸。
        _rref = s.get("ref") or ""
        _is_role_ref = _rref in (SPEC.get("references") or {})
        _gs = s.get("gen_strategy")
        if s.get("ui_shot") or _gs == "ui":
            if _gs != "ui":
                s["gen_strategy"] = "ui"
                _migrated_kf = True
        elif _is_role_ref:
            if _gs != "keyframes":
                s["gen_strategy"] = "keyframes"
                _migrated_kf = True
        else:
            if _gs != "reference":
                s["gen_strategy"] = "reference"
                _migrated_kf = True
        s.setdefault("first_frame_prompt", "")
        s.setdefault("last_frame_prompt", "")
        s.setdefault("camera_move", "auto")  # 运镜手动标注：auto/yes/no（0811 运镜首帧）
        # 中文拍摄剧本字段契约（分镜模块）：旧项目载入时兜底
        s.setdefault("cn_story", "")
        s.setdefault("camera_angle", "")
        s.setdefault("audio_tags", "")
        s.setdefault("continuity_note", "")
        s.setdefault("scene_key", "")
        s.setdefault("status", "pending")
        # 【T2 兜底·老板 0811】scene_type：源头模型输出有波动（覆盖 70-100%），
        # load_spec 时对缺失/非法的统一规则兜底写回，保证数据层 100%、前端徽章恒显示。
        if s.get("scene_type") not in ("action", "monologue", "dialogue_2", "dialogue_multi"):
            _classify_scene_type(s)
            _migrated_kf = True
        # 前端精控面板会编辑这几个字段；不在这里声明，存量项目就是「绑了个不存在的 key」，
        # Vue 里表现为输入框始终空白 + 改了不落盘。统一兜底成契约字段。
        s.setdefault("subtitle", "")
        s.setdefault("video_prompt", "")
        s.setdefault("emotion", "")
        s.setdefault("camera", "")
        s.setdefault("duration", 5)
    # 【0811 修复·模型偶发 dict】scenes/props 规范为数组（前端按数组渲染/遍历）。
    # 模型偶发输出 {"SC01": {...}} 而非 [{key,name,...}] → dict 会让 ③ 资产场景列表空、
    # 场景图生成崩溃（sc[0] KeyError）。load_spec 统一规范化，dict→list 并补 key/name。
    _chg = False
    for _k in ("scenes", "props"):
        _v = SPEC.get(_k)
        if isinstance(_v, dict):
            _items = []
            for _kk in sorted(_v.keys()):
                _vv = _v[_kk]
                if isinstance(_vv, dict):
                    _it = dict(_vv)
                    _it.setdefault("key", _it.get("key") or _kk)
                    _it.setdefault("name", _it.get("name") or _kk)
                    _items.append(_it)
                else:
                    _items.append({"key": _kk, "name": _kk, "img_prompt": str(_vv)})
            SPEC[_k] = _items
            _chg = True
    if _chg:
        _migrated_kf = True
    if _migrated_kf:
        try:
            _save_spec()
            _log.info("[spec] 存量分镜策略已迁移为全首尾针(keyframes)")
        except Exception as _me:
            _log.error("[spec] 迁移落盘失败: %s", _me)
    # 回写已生成的本地真实资产
    manifest_path = asset_abs("assets/references/manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            n = 0
            for s in SPEC.get("shots", []):
                ref = s.get("ref")
                if ref and not s.get("asset_image") and manifest.get(ref):
                    s["asset_image"] = manifest[ref]
                    n += 1
            if n:
                print(f"[spec] 已回写 {n} 张本地真实参考图")
        except Exception as e:
            print(f"[spec] 读取参考图清单失败: {e}")
    # 配音/视频回写：刻意解耦出参考图 manifest 门禁——只要磁盘有对应文件就回写，
    # 否则缺少 references/manifest.json 的项目（如 simulate/纯视频重渲）会漏回写，
    # 导致 assemble 按 spec 找不到视频、闭环断裂。
    _recovered = False
    audio_dir = asset_abs("assets/audio")
    if os.path.isdir(audio_dir):
        for s in SPEC.get("shots", []):
            ap = f"assets/audio/shot{s['id']:03d}.mp3"
            if os.path.isfile(asset_abs(ap)) and not s.get("asset_audio"):
                s["asset_audio"] = ap
                _recovered = True
    video_dir = asset_abs("assets/video")
    if os.path.isdir(video_dir):
        for s in SPEC.get("shots", []):
            vp = f"assets/video/shot{s['id']:03d}.mp4"
            if os.path.isfile(asset_abs(vp)) and not s.get("asset_video"):
                s["asset_video"] = vp
                s["status"] = "done"
                _recovered = True
    if _recovered:
        try:
            _save_spec()
            print(f"[spec] 已回写本地配音/视频并落盘")
        except Exception as e:
            print(f"[spec] 回写资产后保存失败: {e}")
    # 更新 last_opened
    entry["last_opened"] = now_iso()
    save_registry(reg)
    print(f"[spec] loaded {len(SPEC.get('shots', []))} shots | project={ACTIVE} | assets={ASSET_BASE}")
    _load_meta()  # 加载项目元数据（source_mode/novel/visual_style/outline）

# ===== 项目元数据（meta.json）—— 需求卡/小说/视觉风格/大纲 =====
META = {}

def _load_meta():
    """从 active 项目的 meta.json 加载非 storyboard 字段。"""
    global META
    if not ACTIVE:
        META = {}
        return
    mp = os.path.join(PROJECTS_ROOT, ACTIVE, "meta.json")
    if os.path.isfile(mp):
        try:
            with open(mp, "r", encoding="utf-8") as f:
                META = json.load(f)
        except Exception:
            META = {}
    else:
        # 【0811 修复】新项目无 meta.json → 必须清空全局 META，否则残留上一项目
        # 的 req_card/outline/novel 等（曾致新建项目需求卡显示旧项目"深夜一碗面"）。
        META = {}
    # 补缺以保证前端读取不报 undefined
    META.setdefault("source_mode", "")
    META.setdefault("source_text", "")
    META.setdefault("novel", "")
    META.setdefault("visual_style", {"locked": False, "cn_text": "", "en_keywords": [], "confirmed": False})
    META.setdefault("outline", None)


def _save_meta(partial=None):
    """写回 meta.json。partial 为 dict 时做增量更新（META.update(partial)）。"""
    global META
    if not ACTIVE:
        return
    if isinstance(partial, dict):
        META.update(partial)
    mp = os.path.join(PROJECTS_ROOT, ACTIVE, "meta.json")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(META, f, ensure_ascii=False, indent=2)


def find_shot(sid):
    for s in SPEC.get("shots", []):
        if s.get("id") == sid:
            return s
    return None


def _save_spec():
    """把内存中的 SPEC 写回当前活跃项目的 storyboard.json（生成函数改完 shot 后必须调用）。
    加 SPEC_LOCK：后台并行生成任务（关键帧/视频）同时落盘时互斥，防写坏文件。"""
    if not SPEC or not ACTIVE:
        return
    with SPEC_LOCK:
        reg = load_registry()
        entry = next((p for p in reg if p["id"] == ACTIVE), None)
        if entry:
            path = os.path.join(PROJECTS_ROOT, entry["spec"])
            # 同 PUT /api/spec 的保护：内存 SPEC 若被意外清空（切项目竞态、加载失败），
            # 绝不能把这个空壳刷到盘上覆盖掉真实分镜。宁可不保存，也不能毁数据。
            disk_shots = 0
            if os.path.isfile(path):
                try:
                    disk_shots = len(json.load(open(path, encoding="utf-8")).get("shots") or [])
                except Exception:
                    disk_shots = 0
            if not (SPEC.get("shots") or []) and disk_shots > 0:
                print(f"[WARN] _save_spec 已拦截清零写入：内存 0 镜 / 磁盘 {disk_shots} 镜，保留磁盘版本")
                return
            try:
                if os.path.isfile(path) and disk_shots > 0:
                    import shutil as _sh
                    _sh.copyfile(path, path.replace(".json", ".bak.json"))
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(SPEC, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[WARN] _save_spec 失败: {e}")


def _ref_prompt(ref_key):
    ref = SPEC.get("references", {}).get(ref_key, {})
    if isinstance(ref, dict):
        return ref.get("img_prompt", "")
    return str(ref or "")


def _ref_anchor(ref_key, series_id=None):
    """取角色的【云端锁脸锚点图 URL】——全片每个角色只生成一次，之后所有镜头复用同一张。

    这是跨镜「不换脸」的根本：文生图是随机采样，同一段 prompt 调两次会得到两个不同的人。
    只要每镜各自生成参考图，角色一致性就必然崩。锚点图一旦生成即写回 SPEC 持久化。

    O1 跨集锁脸：若当前属于某剧集(ACTIVE_SERIES / 显式 series_id)，优先查【剧集级锚点库】
    （series/<id>/anchors.json）——同一角色在跨集间只生成一次脸，后续集直接复用，
    既保证跨集同脸，又省下重复出图额度。
    """
    if not ref_key:
        return None
    series_id = series_id or globals().get("ACTIVE_SERIES")
    ref = SPEC.get("references", {}).get(ref_key)
    url = ref.get("remote_url") if isinstance(ref, dict) else None
    sref = None
    # 跨集复用：先看剧集锚点库
    if (not url) and series_id:
        sstore = _series_anchor_load(series_id)
        sref = sstore.get(ref_key)
        if isinstance(sref, dict) and sref.get("remote_url"):
            url = sref["remote_url"]
            if isinstance(ref, dict):
                ref["remote_url"] = url
                if not ref.get("img_prompt") and sref.get("img_prompt"):
                    ref["img_prompt"] = sref["img_prompt"]
                if not ref.get("identity_token") and sref.get("identity_token"):
                    ref["identity_token"] = sref["identity_token"]
                _save_spec()
    if url and str(url).startswith("http"):
        return url  # 命中缓存（本集或跨集）：复用同一张脸
    prompt = (ref.get("img_prompt") if isinstance(ref, dict) else None) \
        or (sref.get("img_prompt") if isinstance(sref, dict) else None)
    if not prompt:
        return None
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import generate_image
    for size in ("768x1344", "1024x1024"):
        try:
            url = generate_image(prompt, size=size)
            break
        except Exception:
            url = None
    if not url:
        return None
    if isinstance(ref, dict):
        ref["remote_url"] = url
        _save_spec()
    # 写回剧集锚点库（跨集复用）：同一角色在剧集内只出一次脸
    if series_id:
        sstore = _series_anchor_load(series_id)
        sstore[ref_key] = {
            "img_prompt": prompt,
            "remote_url": url,
            "identity_token": (ref.get("identity_token", "") if isinstance(ref, dict) else ""),
        }
        _series_anchor_save(series_id, sstore)
    return url


# 身份锁：同一段英文在每镜 prompt 里逐字复用，是无 LoRA 场景下最便宜的一致性杠杆
_IDENTITY_LOCK = ("stable face, consistent facial features, locked character identity, "
                  "same person in every shot, no face distortion, no identity drift, "
                  "same actor, same ethnicity, same hairstyle")
_NEG_IDENTITY = ("different person, face swap, changing face, inconsistent identity, "
                 "different ethnicity, morphing features, deformed face, "
                 "text, subtitles, captions, written words, letters, on-screen text, watermark")


def _identity_lock(ref_key):
    """角色身份锁片段 = 该角色的 identity_token（若有）+ 通用锁脸约束。"""
    ref = SPEC.get("references", {}).get(ref_key) or {}
    tok = ref.get("identity_token", "") if isinstance(ref, dict) else ""
    return f"{tok}, {_IDENTITY_LOCK}" if tok else _IDENTITY_LOCK


def _build_identity_token(desc, timeout=30):
    """把角色外貌冻结成一句英文「人脸身份令牌」（<=22 词）。
    无 LoRA 场景下性价比最高的一致性杠杆：同一句话每镜原样复用，模型不会自由发挥换脸。
    硬性超时：令牌只是「次要」一致性杠杆（主杠杆是 _ref_anchor 锚点复用），绝不允许它阻塞
    主流程——AGNES 免费档慢/排队时，chat 可能单次 180s×重试卡 20+ 分钟。故用线程包一层，
    超时(默认30s)直接返回空令牌继续往前走。"""
    if not desc:
        return ""
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    try:
        from agnes_client import chat
    except Exception:
        return ""
    sys_p = ("You are a character designer. From the description output ONE English "
             "sentence (<=22 words) that freezes the character's face identity: "
             "face shape, skin tone, hair color/style, eye shape, one distinguishing "
             "feature. Output ONLY the sentence, no quotes, no markdown.")

    def _call():
        return (chat(desc, system=sys_p, temperature=0.15, max_tokens=80) or "").strip().strip('"').strip()

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(_call).result(timeout=timeout)
    except Exception as e:
        print(f"[WARN] identity_token 生成失败/超时({timeout}s): {e}")
        return ""
    finally:
        ex.shutdown(wait=False)  # 不等待可能挂死的子线程，避免 jion 阻塞主流程


def _gen_video_with_timeout(shot_id, timeout=1200):
    """单镜视频生成硬超时兜底。

    教训：AGNES 免费档偶发「半开连接」——wait_for_video 的 900s 墙钟上限在 urllib
    未正常触发时完全失效，单镜能无声卡死整条流水线数小时。故用线程包一层，超时
    (默认 1200s，给足免费档排队余量) 直接记为失败并继续，绝不让单镜拖垮全流程。"""
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(generate_video_real, shot_id).result(timeout=timeout)
    except Exception as e:
        return {"ok": False, "shot_id": shot_id,
                "error": f"单镜生成超时/异常（{timeout}s 兜底）：{e}"}
    finally:
        ex.shutdown(wait=False)


def _diag_with_timeout(vabs, timeout=120, face_check=False, storyboard=None, deep=False):
    """单镜 AI 诊断硬超时兜底（与 _gen_video_with_timeout 同源修复）。

    diagnose_clip 也是 AGNES 多模态网络调用，免费档偶发半开连接会让它无限阻塞，
    拖垮整条流水线。线程包一层，超时(默认 120s)返回哨兵值继续，绝不卡主流程。"""
    from diagnosis import diagnose_clip
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        # 必须用关键字参数：diagnose_clip(video, rubric=None, n_frames=4, ...)
        # 曾误写成 diagnose_clip(vabs, 4) → 4 被当成 rubric(prompt) → AGNES 400，
        # 且失败被 .get("overall", 10) 默认成满分，诊断阶段长期静默失效。
        return ex.submit(diagnose_clip, vabs, None, 4, face_check=face_check,
                          storyboard=storyboard, deep=deep).result(timeout=timeout)
    except Exception as e:
        return {"ok": False, "overall": None, "verdict": "timeout",
                "error": f"诊断超时/异常（{timeout}s 兜底）：{e}"}
    finally:
        ex.shutdown(wait=False)


def _diag_average(vabs, runs=DIAG_AGG_RUNS, timeout=120, face_check=False, storyboard=None, deep=False):
    """同一 clip 跑 N 次 AGNES 诊断取均值，抑制评分方差（同镜实测 5/7 分抖动）。

    返回合并诊断：scores=各维均值, overall=均值, runs=成功次数, spread=各维最大离散度(最大-最小),
    verdict 按 DIAG_PASS_THRESHOLD 判定。失败 run 不计入均值，但如实反映在 runs/ok 上，
    绝不以"部分成功"掩盖"全失败"。供流水线 autofix 与手动 diagnose(runs>1) 复用。"""
    runs = max(1, int(runs))
    results = []
    for _ in range(runs):
        d = _diag_with_timeout(vabs, timeout=timeout, face_check=face_check, storyboard=storyboard, deep=deep)
        # 仅采纳 ok 非 False 的结果；超时/异常哨兵(ok=False)丢弃
        if d.get("ok") is not False:
            results.append(d)
    if not results:
        return {"ok": False, "overall": None, "verdict": "fail", "scores": {},
                "runs": 0, "spread": None,
                "error": "所有诊断 run 均失败/超时"}
    dim_sums, dim_n, overall_sum = {}, {}, 0.0
    for d in results:
        sc = d.get("scores") or {}
        for k, v in sc.items():
            if isinstance(v, (int, float)):
                dim_sums[k] = dim_sums.get(k, 0.0) + v
                dim_n[k] = dim_n.get(k, 0) + 1
        ov = d.get("overall")
        if isinstance(ov, (int, float)):
            overall_sum += ov
    n = len(results)
    avg_scores = {k: round(dim_sums[k] / dim_n[k], 2) for k in dim_sums}
    avg_overall = round(overall_sum / n, 2)
    # 各维离散度（最大-最小）用于日志提示方差，帮助识别"抖动镜"
    spread = None
    try:
        per_dim = {}
        for d in results:
            sc = d.get("scores") or {}
            for k, v in sc.items():
                if isinstance(v, (int, float)):
                    per_dim.setdefault(k, []).append(v)
        spreads = {k: (max(v) - min(v)) for k, v in per_dim.items() if len(v) > 1}
        if spreads:
            spread = round(max(spreads.values()), 2)
    except Exception:
        spread = None
    verdict = "pass" if avg_overall >= DIAG_PASS_THRESHOLD else "fail"
    return {
        "ok": True, "overall": avg_overall, "scores": avg_scores,
        "verdict": verdict, "runs": n, "spread": spread,
        "raw_runs": results,  # 逐次原始结果，写回 spec 前由调用方剥除
        "summary": f"平均 {n} 次诊断，overall={avg_overall}，离散度={spread}",
    }


# 诊断维度 → prompt 修正规则表（正面补强 / 负面压制）
# 依据：AGNES 四维评分给的是"哪里坏"，原样重抽卡只是再赌一次运气（实测 3 分→5 分仍不合格）；
# 把失败维度翻译成生成约束再重渲，才是真正的自动修复。
_FIX_RULES = {
    "continuity": (
        "steady continuous camera movement, consistent subject count and positions across frames, "
        "smooth temporal transition",
        "abrupt camera jump, cut, changing number of people, objects appearing or disappearing, flicker",
    ),
    "physical": (
        "anatomically correct hands and body, physically plausible motion and gravity, "
        "consistent light direction and shadows",
        "extra fingers, deformed limbs, broken anatomy, floating objects, impossible physics, warped geometry",
    ),
    "character": (
        "same single character throughout, locked facial identity, consistent hairstyle and outfit",
        "cloned characters, duplicated identical people, face morphing, identity change, "
        "inconsistent facial features",
    ),
    "first_last": (
        "gradual coherent progression from first frame to last frame, moderate camera distance change",
        "extreme perspective change, sudden zoom, disjointed first and last frame",
    ),
}


def _prompt_fix_from_diagnosis(shot, diag, threshold=7):
    """按诊断低分维度改写本镜 prompt/negative_prompt，供重渲使用。

    返回被修正的维度列表；无低分维度返回 []。修正词幂等追加（已含则不重复叠加），
    并把 fix_history 写回 shot 便于复盘"改了什么、改完涨了几分"。
    """
    scores = (diag or {}).get("scores") or {}
    weak = [k for k, v in scores.items()
            if isinstance(v, (int, float)) and v < threshold and k in _FIX_RULES]
    if not weak:
        return []
    pos = shot.get("video_prompt") or ""
    neg = shot.get("negative_prompt") or _NEG_IDENTITY
    for k in weak:
        add_p, add_n = _FIX_RULES[k]
        if add_p not in pos:
            pos = f"{pos}, {add_p}" if pos else add_p
        if add_n not in neg:
            neg = f"{neg}, {add_n}" if neg else add_n
    shot["video_prompt"] = pos
    shot["negative_prompt"] = neg
    hist = shot.setdefault("fix_history", [])
    hist.append({"at": now_iso(), "weak_dims": weak,
                 "before_overall": (diag or {}).get("overall"),
                 "scores": scores})
    return weak


# 运镜词典：把分镜表里的中文运镜标注翻译成 AGNES 能理解的英文摄影指令。
# 对标 PAVO⑧「结构化 NL 指令」——分镜可标「运镜:从花推向人物」并真正作用于生成，
# 而不是像旧版那样：前端有个「运镜」输入框，后端却从来不读，填了等于没填。
_CAMERA_MAP = [
    ("环绕", "orbital camera arc slowly around the subject"),
    ("推近", "slow dolly-in pushing toward the subject"),
    ("推", "slow dolly-in pushing toward the subject"),
    ("拉远", "slow dolly-out pulling back to reveal the environment"),
    ("拉", "slow dolly-out pulling back to reveal the environment"),
    ("摇", "smooth horizontal pan across the scene"),
    ("跟拍", "tracking shot following the subject"),
    ("跟", "tracking shot following the subject"),
    ("移", "lateral tracking movement"),
    ("升", "crane up rising above the scene"),
    ("降", "crane down descending toward the subject"),
    ("手持", "handheld camera with subtle natural shake"),
    ("固定", "locked-off static camera, no movement"),
    ("变焦", "smooth optical zoom"),
    ("特写", "tight close-up framing"),
    ("近景", "medium close-up framing"),
    ("中景", "medium shot framing"),
    ("远景", "wide establishing framing"),
    ("全景", "wide establishing framing"),
    ("俯", "high angle looking down at the subject"),
    ("仰", "low angle looking up at the subject"),
]


def _ceil_div(a, b):
    return -(-a // b)


# ===== 官方电影语法注入（agnes 知识库 prompt_engine 预设，老板 0810 拍板增强）=====
# 来源：~/.workbuddy/skills/agnes-ai/scripts/prompt_engine.py（官方技巧固化）
# 原则：保留已验证的中文台词/身份锁/运镜逻辑，只「追加」官方缺失段——
#   场景类型景别+情绪语法、光线、背景锁定、竖屏构图、静态帧语法。
_OFF_LIGHTING = {
    "黄金时刻": "warm golden hour sunlight",
    "逆光": "backlit silhouette with rim light",
    "霓虹夜": "neon cyberpunk night lighting, wet reflections",
    "柔光": "soft diffuse studio light",
    "阴雨": "overcast rainy daylight, muted tones",
    "戏剧光": "dramatic chiaroscuro lighting, deep shadows",
    "月夜": "cold moonlight, blue palette",
    "顶光": "harsh top light, tense mood",
}
_OFF_LOCATION_LOCK = ("consistent set and location throughout every shot, identical room and "
                      "furnishings, stable background environment, same indoor setting, "
                      "do not change location or background between shots, no background morphing, "
                      "no location change")
_OFF_VERTICAL_FRAME = "vertical 9:16 mobile short-drama framing, subject chest-up, shallow depth of field"
_OFF_HORIZONTAL_FRAME = "horizontal 16:9 landscape framing, subject centered, shallow depth of field, cinematic composition"

# 【0811 修复·中英混杂】中文情绪词 → 英文（_speech_clause 语音指令段用；情绪字段常被模型/用户
# 填中文，直接拼进英文 prompt 会中英混杂。英文原样透传，中文查表/关键词匹配。）
_EMOTION_MAP = {
    "平静": "calm", "疲惫": "tired", "孤寂": "lonely", "疲惫孤寂": "tired and lonely",
    "激动": "excited", "愤怒": "angry", "生气": "angry", "悲伤": "sad", "难过": "sad",
    "开心": "happy", "高兴": "happy", "喜悦": "joyful", "温柔": "gentle", "坚定": "determined",
    "紧张": "nervous", "失落": "lost", "期待": "expectant", "冷漠": "cold", "淡然": "indifferent",
    "尴尬": "awkward", "感动": "moved", "恐惧": "frightened", "害怕": "frightened",
    "惊讶": "surprised", "震惊": "shocked", "害羞": "shy", "无奈": "helpless",
    "委屈": "aggrieved", "忧虑": "worried", "担心": "worried", "绝望": "desperate",
    "深情": "affectionate", "心疼": "heartbroken", "欣慰": "relieved", "坚定": "determined",
    "冷静": "composed", "讽刺": "sarcastic", "嘲讽": "sarcastic", "委屈": "aggrieved",
    "焦急": "anxious", "不耐烦": "impatient", "犹豫": "hesitant", "崩溃": "devastated",
}

def _emotion_en(e):
    """情绪中文→英文；英文原样返回；空→neutral；无匹配→原样（宁可保留原文也不瞎翻）。"""
    e = (e or "").strip()
    if not e:
        return "neutral"
    if e in _EMOTION_MAP:
        return _EMOTION_MAP[e]
    for cn, en in _EMOTION_MAP.items():
        if cn in e:
            return en
    if re.search(r"[\u4e00-\u9fff]", e):
        return "expressive"  # 中文未匹配情绪词 → 通用表情词，避免中英混杂
    return e
_OFF_STYLE = {
    "写实电影": "realistic cinematic, film grain, shallow depth of field",
    "动漫": "semi-realistic anime, vibrant colors",
    "国风": "Chinese period drama style, rich costumes",
    "赛博": "cyberpunk, high contrast neon",
    "温馨": "warm soft focus, cozy atmosphere",
    "暗黑": "dark moody cinematic, desaturated",
}
_OFF_MOUTH_STILL = ("lips firmly sealed, mouth closed, completely motionless mouth, no lip movement, "
                    "no speaking, silent, only subtle eye and breath movement, "
                    "an inner voiceover plays without any mouth motion")
_OFF_STATIC_STOP = "static pose, frozen moment, no motion blur, sharp focus, film-still"
# 场景类型四套电影语法（action / monologue / dialogue_2 / dialogue_multi）
_OFF_SCENE_PRESETS = {
    "action": {
        "framing": "",
        "extra": "",
        "default_lighting": "戏剧光",
    },
    "monologue": {
        "framing": "medium close-up, the character is alone in frame",
        "extra": ("gazing off-camera into the distance, lost in thought, contemplative "
                  "introspective mood, soft wistful atmosphere, slight background defocus, "
                  "as if an inner voiceover is playing"),
        "default_lighting": "柔光",
    },
    "dialogue_2": {
        "framing": "two-person shot, both characters visible chest-up",
        "extra": ("the two facing each other, making eye contact, engaged in conversation, "
                  "a natural overlapping-dialogue beat"),
        "default_lighting": "戏剧光",
    },
    "dialogue_multi": {
        "framing": "group shot, multiple characters arranged semi-circularly",
        "extra": "multiple eye-lines among the group, ensemble interaction",
        "default_lighting": "戏剧光",
    },
}


def _classify_scene_type(shot):
    """镜头类型（官方电影语法）：独白/对话/动作。
    【T2 源头优先·老板 0811】分镜生成时模型已带 scene_type（STORYBOARD_SYS schema 字段）→ 直接复用；
    旧数据/缺失时才规则兜底。优先级：独白词 > 多人词 > 有台词 > 动作。"""
    exist = (shot.get("scene_type") or "").strip()
    if exist in ("action", "monologue", "dialogue_2", "dialogue_multi"):
        return exist
    t = (shot.get("cn_story") or "") + " " + (shot.get("subtitle") or "")
    has_sub = bool((shot.get("subtitle") or "").strip())
    if re.search(r"独白|内心|旁白|心想|默念|自语|OS|VO|vo", t):
        st = "monologue"
    elif re.search(r"众人|大家|会议|群戏|全场|各自|几位|一群", t):
        st = "dialogue_multi"
    elif has_sub:
        st = "dialogue_2"   # 有台词即对话镜（口型/视线按对话处理）
    else:
        st = "action"
    shot["scene_type"] = st
    return st


def _cinema_clause(shot):
    """官方电影语法注入段：场景类型景别+情绪 + 光线 + 背景锁定 + 竖屏构图（全部英文）。
    光线/风格优先取镜头手填参数（shot.lighting/shot.style，⑤模块 UI 可选，映射官方词库），
    否则用场景类型默认。独白+MiniMax 旁白（闭唇镜）额外加 MOUTH_STILL（嘴不动 VO）。"""
    st = _classify_scene_type(shot)
    preset = _OFF_SCENE_PRESETS.get(st, _OFF_SCENE_PRESETS["action"])
    parts = []
    if preset.get("framing"):
        parts.append(preset["framing"])
    if preset.get("extra"):
        parts.append(preset["extra"])
    # 光线：镜头手填 > 场景类型默认 > 戏剧光
    light = (shot.get("lighting") or "").strip() or preset.get("default_lighting") or "戏剧光"
    parts.append(_OFF_LIGHTING.get(light, light))
    # 风格：镜头手填（前端 select 官方 6 风格），无则跳过（video_prompt/global_style 已带风格）
    sty = (shot.get("style") or "").strip()
    if sty:
        parts.append(_OFF_STYLE.get(sty, sty))
    if st == "monologue" and shot.get("use_minimax_audio"):
        parts.append(_OFF_MOUTH_STILL)
    parts.append(_OFF_LOCATION_LOCK)
    # 画幅构图词：横屏 16:9 / 竖屏 9:16（随项目 aspect_mode 走，避免模型按竖屏构图生成横屏视频）
    parts.append(_OFF_HORIZONTAL_FRAME if (META.get("aspect_mode") or "portrait") == "landscape" else _OFF_VERTICAL_FRAME)
    return ", ".join(parts)


def _camera_clause(shot):
    """把 shot['camera'] 转成英文摄影指令片段；英文原样透传，中文查表翻译。"""
    cam = (shot.get("camera") or "").strip()
    if not cam:
        return ""
    if not re.search(r"[\u4e00-\u9fff]", cam):
        return cam                      # 已是英文，直接用
    hits = [en for zh, en in _CAMERA_MAP if zh in cam]
    seen, out = set(), []
    for h in hits:                      # 去重且保序（"推近特写" → 两条都要，但不重复）
        if h not in seen:
            seen.add(h); out.append(h)
    return ", ".join(out)


def _speech_clause(shot):
    """把中文台词嵌入视频 prompt，驱动 AGNES 原生中文音画同步（office_drama ASR 已验证 LANG=zh 念对）。

    关键：agnes-video-v2.0 的 _submit_video 不接收 text/voice 字段，原生语音只能从 prompt 读取。
    若 prompt 是英文 → 飘英文；把中文台词 + 'speaks in Mandarin Chinese, lips moving...' 写进 prompt → 原生念中文且口型同步。
    仅当：有 subtitle 且本镜未标 use_minimax_audio（旁白/闭唇镜走 MiniMax 时不在此嵌入，避免双音轨）。"""
    if shot.get("use_minimax_audio"):
        return ""
    text = (shot.get("subtitle") or "").strip()
    if not text:
        return ""
    role = shot.get("voice") or "narrator"
    role_label = {"male_lead": "the young man", "narrator": "the narrator",
                  "bullet": "a crowd"}.get(role, role)
    emotion = _emotion_en(shot.get("emotion") or "")   # 【0811 修复】中文情绪词翻译成英文，防中英混杂
    return (f'The {role_label} speaks in Mandarin Chinese, {emotion}: "{text}". '
            "speaking Mandarin Chinese, lips moving with natural Chinese speech rhythm, "
            "closed-lip Chinese pronunciation, mouth forming Chinese syllables, subtle jaw movement, "
            "no exaggerated Western mouth opening. "
            "CRITICAL: the spoken words are AUDIO-ONLY — they must NOT appear as on-screen text, "
            "subtitles, captions, or any visible written characters in the video.")


# ===== 关键帧管线（首尾针 / 参考图，统一决策）=====
# gen_strategy 每镜可覆盖，缺省走全局默认：
#   "keyframes" : 默认。首帧=锁脸锚点(免费复用) + 尾帧(img2img首帧→结束态)，
#                 create_video(keyframes=[首,末])，prompt 改成过渡描述。
#                 两端都控住：脸不漂(首帧锚点) + 结尾可控(尾帧)。
#   "reference" : 单图生视频(image=锚点=首帧)，省一张尾帧图成本；结尾交引擎自由发挥。
#   "ui"        : UI 动效镜(ui_animate 处理)，跳过 AGNES。
GEN_POLICY_DEFAULT = "keyframes"


def _img_to_datauri(path):
    """本地图片 → base64 data URI（供 AGNES 云 img2img 读取，避免依赖本地 http 可达性）。"""
    try:
        with open(path, "rb") as f:
            b = f.read()
        import base64 as _b64
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "webp": "image/webp"}.get(ext, "image/png")
        return f"data:{mime};base64," + _b64.b64encode(b).decode("ascii")
    except Exception:
        return None


def _prev_shot(shot):
    """返回分镜序列中本镜的上一镜（按 id 顺序），无则 None。用于链式首帧。"""
    shots = sorted(SPEC.get("shots", []), key=lambda x: int(x.get("id", 0)))
    cur = int(shot.get("id", 0))
    prev = None
    for s in shots:
        if int(s.get("id", 0)) < cur:
            prev = s
        else:
            break
    return prev


def _scene_family(key):
    """场景族：scene_key 前缀（cafe_window/cafe_interior → cafe）。同族视为同场景（链式依据）。"""
    k = str(key or "")
    if not k:
        return ""
    return k.split("_")[0] if "_" in k else k


# =====================================================================
# 【运镜镜头首帧·老板 0811】有运镜的镜头，首帧 = 运镜起点画面（场景入口/过道/全景），
# 不再贴角色锚点特写（否则关键帧动画与提示词"从门口推入"矛盾，运镜感全丢）。
# 生成方式：资产图（场景图优先，否则角色锚点）+ first_frame_prompt → img2img 生成起点画面。
# =====================================================================
_CAMERA_MOVE_KW = [
    # 中文运镜
    "推", "拉远", "拉全", "摇", "移", "环绕", "跟拍", "跟移", "横移", "穿越", "穿过",
    "推进", "后拉", "上摇", "下摇", "扫视", "巡览", "升降", "甩镜", "从", "进入", "推向",
    # 英文运镜
    "push-in", "push in", "pushin", "tracking", "dolly", "pan", "tilt", "crane", "zoom",
    "orbit", "pull-back", "pull back", "pullback", "through", "enter", "into", "sweep",
    "follow", "glide", "drift", "camera moves", "camera moves toward",
]


def _is_camera_move(shot):
    """判定该镜是否为「运镜镜头」：shot.camera_move 手动三态（auto/yes/no）优先，
    否则关键词匹配 camera / video_prompt / cn_story。返回 bool。"""
    cm = (shot.get("camera_move") or "auto").strip().lower()
    if cm == "yes":
        return True
    if cm == "no":
        return False
    texts = " ".join([
        str(shot.get("camera") or ""),
        str(shot.get("video_prompt") or ""),
        str(shot.get("cn_story") or ""),
    ]).lower()
    return any(k in texts for k in _CAMERA_MOVE_KW)


def _gen_camera_start(shot):
    """【运镜镜头·老板 0811】生成「运镜起点」首帧图：资产图(场景图优先→角色锚点) +
    first_frame_prompt → img2img 生成起点画面（如咖啡店门口/过道），落盘 kf_start。
    返回本地 rel，失败返回 None（调用方回退锚点/文生兜底）。"""
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        prompt = (shot.get("first_frame_prompt") or "").strip()
        if not prompt:
            return None
        # 底图：场景图优先（运镜起点多为场景环境）；无则角色锚点
        base = None
        sk = shot.get("scene_key") or ""
        for sc in SPEC.get("scenes", []) or []:
            if (sc.get("key") or sc.get("name") or "") == sk and sc.get("asset_image"):
                base = sc["asset_image"]
                break
        if not base:
            ref_key = shot.get("ref")
            ref = SPEC.get("references", {}).get(ref_key) if ref_key else None
            if isinstance(ref, dict):
                base = ref.get("remote_url") or ref.get("asset_image") or ""
        # 底图归一：http 直接用；本地 rel/data → data URI（AGNES 只收 URL 或 data URI）
        img_input = None
        if base:
            bs = str(base)
            if bs.startswith("http"):
                img_input = bs
            else:
                du = _to_agnes_image(bs) if (bs.startswith("assets/") or os.path.exists(asset_abs(bs))) else None
                if du:
                    img_input = du
        gs = _clean_global_style()
        if gs and gs not in prompt:
            prompt = prompt + ", " + gs
        cine = _cinema_clause(shot)
        if cine:
            prompt = prompt + ", " + cine
        prompt = prompt + ", " + _OFF_STATIC_STOP
        from agnes_client import generate_image, image_to_image
        _log.info("[keyframes] shot#%s 运镜镜头 → 起点首帧（底图=%s）",
                  shot.get("id"), ("有" if img_input else "无·纯文生"))
        url = None
        _fb_ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            if img_input:
                fut = _fb_ex.submit(image_to_image, prompt, img_input)
            else:
                fut = _fb_ex.submit(generate_image, prompt)  # 无底图：纯文生起点画面（老板：必须符合标准）
            url = fut.result(timeout=180)
        except Exception as _fe:
            _log.error("[keyframes] 运镜起点生成失败 shot#%s: %s", shot.get("id"), _fe)
        finally:
            _fb_ex.shutdown(wait=False)
        if not url:
            return None
        sid = int(shot.get("id", 0))
        sp = os.path.join(asset_abs("assets/references"), f"kf_start_{sid:03d}.png")
        try:
            import urllib.request as _ur
            with _ur.urlopen(url, timeout=60) as r:
                data = r.read()
            with open(sp, "wb") as f:
                f.write(data)
            shot["asset_frame_start"] = f"assets/references/kf_start_{sid:03d}.png"
        except Exception:
            shot["asset_frame_start"] = url
        shot["frame_start_source"] = "camera-start"
        return shot["asset_frame_start"]
    except Exception as e:
        _log.error("[keyframes] 运镜起点首帧生成异常 shot#%s: %s", shot.get("id"), e)
        return None


def _first_frame_source(shot, allow_chain=True):
    """返回该镜「首帧图」可用来源：(url_or_datauri, is_public_url)。

    优先级（链式首尾针，老板定）：
      0. 同场景链式：上一镜尾帧(asset_frame_end) — 同场景族 + 同角色 才链
      1. remote_image_ref(http)
      2. asset_image(本地base64)
      3. ref.remote_url(http)
      4. None
    """
    # ---- 链式：同场景取上镜尾帧（场景切换/首镜/角色不一致 不链）----
    if allow_chain:
        prev = _prev_shot(shot)
        if prev is not None:
            same_family = (_scene_family(prev.get("scene_key")) == _scene_family(shot.get("scene_key"))
                           and _scene_family(shot.get("scene_key")))
            same_char = (prev.get("ref") or "") == (shot.get("ref") or "") or not shot.get("ref")
            if same_family and same_char:
                pend = prev.get("asset_frame_end") or ""
                if str(pend).startswith("http") or str(pend).startswith("data:") or str(pend).startswith("assets/"):
                    return pend, str(pend).startswith("http")
    ref_key = shot.get("ref")
    rir = shot.get("remote_image_ref") or ""
    if str(rir).startswith("http"):
        return rir, True
    ai = shot.get("asset_image") or ""
    if ai and not str(ai).startswith("http"):
        du = _img_to_datauri(asset_abs(ai) if str(ai).startswith("assets/") else ai)
        if du:
            return du, False
    if str(ai).startswith("http"):
        return ai, True
    # 【空镜兜底·老板 0810】ref 为空时优先用场景图作首帧（空镜不要套人物锚点）
    if not ref_key:
        sk = shot.get("scene_key") or ""
        for sc in SPEC.get("scenes", []) or []:
            sk_s = sc.get("key") or sc.get("name") or ""
            if sk_s == sk and sc.get("asset_image"):
                sa = sc["asset_image"]
                if str(sa).startswith("http"):
                    return sa, True
                du = _img_to_datauri(asset_abs(sa)) if str(sa).startswith("assets/") else None
                if du:
                    return du, False
                break
    ref = SPEC.get("references", {}).get(ref_key) if ref_key else None
    if isinstance(ref, dict) and str(ref.get("remote_url", "")).startswith("http"):
        return ref["remote_url"], True
    return None, False


def _clean_video_prompt(prompt):
    """清洗 video_prompt（老板 0810：最终提示词要干净、无重复、纯英文）：
    - 尺寸词（9:16/16:9/vertical/landscape/portrait）：宽高由 width/height 参数控制（官方 720x1280），
      prompt 里写尺寸冗余且冲突（模型偶发写 '16:9 landscape' 会误导出横屏）；
    - 水印/文字类（no watermark/no text/subtitles...）：是 negative_prompt 的职责，prompt 里重复无意义；
    - 保留风格/质量词（film grain/8K/volumetric 等，无害）。"""
    if not prompt:
        return ""
    p = re.sub(r"\b9:16\b|\b16:9\b|\blandscape\b|\bportrait\b|\bvertical\b", "", prompt, flags=re.I)
    p = re.sub(r"\bno watermark\b|\bwatermark\b|\bno on-screen text\b|\bno text\b|\bno subtitles\b", "", p, flags=re.I)
    p = re.sub(r",\s*,+", ",", p).strip(" ,.")
    return p


def _clean_global_style():
    """全局风格清洗（同 _clean_video_prompt）：模型生成的 global_style 常带 '16:9 landscape'
    等脏尺寸词（schema 默认就写死过），拼接进 prompt 前必须清洗，防横竖屏冲突/重复。"""
    return _clean_video_prompt(SPEC.get("global_style") or "")


def _cam_mentioned(prompt):
    """检测画面描述是否已含运镜词（避免 video_prompt 自带运镜 + 运镜参数翻译重复追加）。"""
    pl = (prompt or "").lower()
    return any(w in pl for w in ("push", "dolly", "tracking", "orbit", "pan ", "tilt", "crane",
                                 "zoom", "handheld", "dutch", "over-the-shoulder", "pov", "whip",
                                 "static camera", "locked-off"))


def _last_frame_prompt(shot):
    """尾帧(结束态)图像 prompt。优先用分镜手填的 last_frame_prompt，否则按 video_prompt 启发式派生。
    0810 增强（官方静态帧语法）：末帧 = 场景基底 + then settling into a final pose + 光线/景别/竖屏 +
    凝固帧（锐焦、无运动模糊、film-still）——保证尾帧是一张可作 keyframes 收尾的稳定构图。"""
    if shot.get("last_frame_prompt"):
        return shot["last_frame_prompt"]
    base = _clean_video_prompt(shot.get("video_prompt", ""))
    if not base:
        base = (shot.get("cn_story") or "").strip().rstrip(". ")
    cine = _cinema_clause(shot)
    return (f"{base}, then settling into a stable final pose, final frame, end of shot, "
            f"same character and camera angle, {_OFF_STATIC_STOP}"
            + (f", {cine}" if cine else ""))


def _transition_prompt(shot):
    """首尾针模式下的视频过渡 prompt（官方最佳实践：描述首→末平滑过渡，而非详细场景）。
    注：尺寸/竖屏词不在此写（_cinema_clause 统一注入一次），避免与 video_prompt 残留尺寸词重复。"""
    style = _clean_global_style()
    return (f"Smooth cinematic transition from the first keyframe to the second keyframe, "
            f"maintaining character identity and consistent camera angle, natural motion"
            + (f", {style}" if style else ""))


def _to_agnes_image(src):
    """把本地 rel 路径 / http URL / data URI 统一成 AGNES 可读取的 URL 或 data URI。"""
    if not src:
        return None
    if str(src).startswith("http") or str(src).startswith("data:"):
        return src
    return _img_to_datauri(asset_abs(src) if str(src).startswith("assets/") else src)


def _gen_first_frame_fallback(shot):
    """【老板 0810 自动兜底】首帧参考图全缺失（跳场景空镜/锚点未生成）时，
    AI 文生图直接生成该镜首帧——流程永不卡死。返回本地 rel 或 http url，失败返回 None。"""
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        from agnes_client import generate_image
        prompt = (shot.get("first_frame_prompt") or "").strip()
        if not prompt:
            prompt = (shot.get("cn_story") or "").strip()
        if not prompt:
            prompt = "cinematic still, " + (shot.get("scene") or shot.get("scene_key") or "scene")
        gs = _clean_global_style()
        if gs and gs not in prompt:
            prompt = prompt + ", " + gs
        # 【空镜描述关键词检测】含"无行人/无人/空镜/空无一人"等 → 强化 NEG 抑制人物幻觉（老板 0810 修复）
        if re.search(r"无行人|无人|空镜|空无一人|没有人|无车|空旷", prompt):
            prompt = prompt + ". NO people, NO characters, NO pedestrians, empty scene"
        # 【官方静态帧语法注入·0810】首帧兜底也带景别/光线/竖屏 + 凝固帧（锐焦、无运动模糊）
        cine = _cinema_clause(shot)
        if cine:
            prompt = prompt + ", " + cine
        prompt = prompt + ", " + _OFF_STATIC_STOP
        _log.info("[keyframes] shot#%s 参考图缺失 → 文生图兜底生成首帧", shot.get("id"))
        url = None
        # 【防挂起】线程池硬超时 180s，AGNES 挂起不阻塞批量（老板 0810 修复）
        _fb_ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            for size in ("768x1344", "1024x1024"):
                try:
                    fut = _fb_ex.submit(generate_image, prompt, size=size)
                    url = fut.result(timeout=180)
                    if url:
                        break
                except Exception as _fe:
                    _log.error("[keyframes] 兜底文生图超时/失败(%s): %s", size, _fe)
                    url = None
        finally:
            _fb_ex.shutdown(wait=False)
        if not url:
            return None
        sid = int(shot.get("id", 0))
        sp = os.path.join(asset_abs("assets/references"), f"kf_start_{sid:03d}.png")
        try:
            import urllib.request as _ur
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            with open(sp, "wb") as f:
                f.write(data)
            shot["asset_frame_start"] = f"assets/references/kf_start_{sid:03d}.png"
        except Exception:
            shot["asset_frame_start"] = url  # 下载失败直接用远程 URL
        shot["frame_start_source"] = "text2img-fallback"
        return shot["asset_frame_start"]
    except Exception as e:
        _log.error("[keyframes] 文生图兜底失败 shot#%s: %s", shot.get("id"), e)
        return None


def generate_keyframes_real(shot_id, force=False):
    _log.info("[keyframes] shot#%s 开始生成首尾针%s", shot_id, "（强制重生成）" if force else "")
    """REAL=1：生成该镜首帧 + 尾帧，写回 asset_frame_start/end。

    策略（老板定）：
    - keyframes：链式首帧（同场景取上一镜尾帧→保证剧情连贯；否则锚点/参考图）+
      尾帧(img2img首帧→结束态锁脸)。
    - reference / text2video：无需尾帧，首帧=锚点/场景图（text2video 连首帧都不要，纯文生视频）。
    - 幂等（老板 0810）：首尾帧已生成且非 force 时直接跳过，不重复烧 token；单镜「重生成」走 force=True。
    """
    shot = find_shot(shot_id)
    if not shot:
        return {"ok": False, "error": f"shot {shot_id} not found"}
    strategy = shot.get("gen_strategy", GEN_POLICY_DEFAULT)
    if strategy == "ui":
        return {"ok": True, "skipped": True, "reason": "ui_shot：由 ui_animate 处理，跳过 AGNES 关键帧"}
    if strategy == "text2video":
        # 纯文生视频：不需要任何关键帧（无首帧/尾帧），视频管线直接文生
        return {"ok": True, "skipped": True, "reason": "text2video：纯文生视频，无关键帧",
                "strategy": strategy, "shot_id": shot_id}
    # 【幂等跳过·老板 0810】首尾帧都已生成 → 批量时直接跳过（不重复消耗 AGNES 额度）
    if not force and shot.get("asset_frame_start") and shot.get("asset_frame_end"):
        _log.info("[keyframes] shot#%s 已生成过首尾针，跳过", shot_id)
        return {"ok": True, "skipped": True, "reason": "已生成过首尾针",
                "strategy": strategy, "shot_id": shot_id,
                "first": shot["asset_frame_start"], "last": shot["asset_frame_end"]}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import generate_image
    # ---- 链式首帧判定（同场景取上镜尾帧）----
    # 场景族：scene_key 前缀相同视为同场景（cafe_window/cafe_interior → cafe），
    # 避免粒度过细（窗边/店内）把同场景误判成切换。
    # 角色匹配：上镜尾帧的角色须与本镜一致，否则链了别人的脸（镜5周然不能链镜4林夏尾帧）。
    prev = _prev_shot(shot) if strategy == "keyframes" else None
    chained = False
    if prev is not None and strategy == "keyframes":
        same_family = (_scene_family(prev.get("scene_key")) == _scene_family(shot.get("scene_key"))
                       and _scene_family(shot.get("scene_key")))
        same_char = (prev.get("ref") or "") == (shot.get("ref") or "") or not shot.get("ref")
        if same_family and same_char and prev.get("asset_frame_end"):
            pend = prev["asset_frame_end"]
            if str(pend).startswith("http") or str(pend).startswith("assets/"):
                shot["asset_frame_start"] = pend
                shot["frame_start_source"] = f"chain:shot{prev.get('id')}"
                chained = True
    if not chained:
        # 【运镜镜头首帧·老板 0811】有运镜且首帧描述非空 → 先按「运镜起点画面」生成
        # （资产图+first_frame_prompt → img2img），不再直接贴角色锚点特写；失败回退旧来源链。
        if _is_camera_move(shot) and (shot.get("first_frame_prompt") or "").strip():
            cam_start = _gen_camera_start(shot)
            if cam_start:
                first_src, is_url = cam_start, str(cam_start).startswith("http")
            else:
                first_src, is_url = _first_frame_source(shot, allow_chain=False)
        else:
            first_src, is_url = _first_frame_source(shot, allow_chain=False)
        if not first_src:
            generate_references_real()
            first_src, is_url = _first_frame_source(shot, allow_chain=False)
        if not first_src:
            # 【老板 0810】参考图/锚点/场景图全缺失 → AI 文生图直接出首帧，流程不中断
            _log.info("[keyframes] shot#%s 参考图未就绪，自动文生图兜底", shot_id)
            first_src = _gen_first_frame_fallback(shot)
            if first_src:
                is_url = str(first_src).startswith("http")
        if not first_src:
            # 兜底也失败才报错（极少数：AGNES 不可用）
            reason = f"首帧生成失败（参考图缺失且文生图兜底失败）：镜#{shot_id}"
            _log.error("[keyframes] %s", reason)
            return {"ok": False, "error": reason, "shot_id": shot_id, "strategy": strategy}
        if strategy == "keyframes":
            # 首帧落盘为本地 rel（避免 JSON 塞 base64）；AGNES 调用时再转 data URI。
            if is_url:
                shot["asset_frame_start"] = first_src
            else:
                out_dir = asset_abs("assets/references")
                os.makedirs(out_dir, exist_ok=True)
                sp = os.path.join(out_dir, f"kf_start_{shot_id:03d}.png")
                du = first_src if str(first_src).startswith("data:") else _to_agnes_image(first_src)
                if du and str(du).startswith("data:"):
                    import base64 as _b64
                    _, _, b = du.partition(",")
                    with open(sp, "wb") as f:
                        f.write(_b64.b64decode(b))
                shot["asset_frame_start"] = f"assets/references/kf_start_{shot_id:03d}.png"
            if shot.get("frame_start_source") != "camera-start":
                shot["frame_start_source"] = "anchor"  # 锚点/参考图（camera-start 保留运镜起点标签）
        else:
            # reference：首帧直接用场景图/锚点（不额外落盘，视频管线会读 asset_image/ref）
            shot["asset_frame_start"] = first_src if str(first_src).startswith("http") else (
                shot.get("asset_image") or "")
            shot["frame_start_source"] = "scene_or_anchor"
    last_url = None
    if strategy == "keyframes":
        first_api = _to_agnes_image(shot["asset_frame_start"])
        # 尾帧：img2img 首帧 → 结束态（保持同一张脸/同一场景构图）
        last_prompt = _last_frame_prompt(shot)
        # 【0811 改造·老板洞察：关键帧关系地基】尾帧必须双参考合成：
        #   首帧(锁场景/构图) + 角色锚点(锁脸/服装)——否则首帧是空景时尾帧的脸自由发挥(角色漂移根源)。
        #   AGNES image 支持 extra_body.image 多图合成（官方文档 6.4）。
        _ref_key = shot.get("ref")
        _ref = SPEC.get("references", {}).get(_ref_key) if _ref_key else None
        _anchor_img = ""
        if isinstance(_ref, dict):
            _anchor_img = _ref.get("remote_url") or _ref.get("asset_image") or ""
        _kf_imgs = [first_api]
        if _anchor_img:
            _anchor_api = _to_agnes_image(str(_anchor_img))
            if _anchor_api:
                _kf_imgs.append(_anchor_api)
                last_prompt += (" Same character as the reference image: identical face, hairstyle and clothing. "
                                "Stay in the scene of the first reference image, natural transition.")
                _log.info("[keyframes] shot#%s 尾帧双参考合成（首帧锁场景 + 锚点锁角色）", shot_id)
        # 【防挂起】AGNES 偶发半开连接会无声挂死 → 线程池硬超时 180s，绝不无限阻塞（老板 0810 批量卡死修复）
        _kf_ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            for size in ("768x1344", "1024x1024"):
                try:
                    fut = _kf_ex.submit(generate_image, last_prompt, image_input=_kf_imgs, size=size)
                    last_url = fut.result(timeout=180)
                    if last_url:
                        break
                except Exception as _ke:
                    _log.error("[keyframes] shot#%s 尾帧生成超时/失败(%s): %s", shot_id, size, _ke)
                    last_url = None
        finally:
            _kf_ex.shutdown(wait=False)
        shot["asset_frame_end"] = last_url or ""
        shot["status"] = shot.get("status") or "ready"
    _save_spec()
    _log.info("[keyframes] shot#%s 首尾针完成 strategy=%s chained=%s", shot_id, strategy, chained)
    return {"ok": bool(last_url) if strategy == "keyframes" else True,
            "strategy": strategy, "shot_id": shot_id,
            "chained": chained, "prev_id": prev.get("id") if chained and prev else None,
            "first": shot["asset_frame_start"], "last": last_url}


def generate_keyframes_all():
    # 【老板 0810 全首尾针】先并行补齐缺失的角色锚点（幂等，只补缺失），再按顺序链式生成首尾针。
    # 链式有顺序依赖（后镜首帧=前镜尾帧），故逐镜串行；锚点补生成可并行。
    try:
        generate_references_real()
    except Exception as e:
        _log.error("[keyframes] 批量前锚点预生成异常: %s", e)
    out = []
    fails = []
    for s in SPEC.get("shots", []):
        r = generate_keyframes_real(s["id"])
        out.append({"id": s["id"], "ok": r.get("ok"), "strategy": r.get("strategy"),
                    "chained": r.get("chained"), "frame_source": s.get("frame_start_source", "")})
        if not r.get("ok") and not r.get("skipped"):
            fails.append({"id": s["id"], "strategy": r.get("strategy"), "error": r.get("error", "")})
    return {"ok": True, "results": out, "fail_count": len(fails), "fails": fails}


def kf_submit(shot_id, force=False):
    """【老板 0810 状态可见】关键帧生成改为后台任务：立即返回 accepted，
    前端轮询 /api/generate/keyframes/status 明确看到 pending/running/done/failed，
    不再盲目挂等（区分「真在生成」与「后端挂了」）。"""
    with KF_LOCK:
        KF_STATUS[shot_id] = {"status": "pending", "error": "", "started": now_iso(), "result": None}

    def _run():
        try:
            with KF_LOCK:
                KF_STATUS[shot_id]["status"] = "running"
            _log.info("[keyframes] 后台任务 shot#%s 执行中", shot_id)
            res = generate_keyframes_real(shot_id, force=force)
            with KF_LOCK:
                KF_STATUS[shot_id]["status"] = "done"
                KF_STATUS[shot_id]["result"] = res
        except Exception as e:
            _log.error("[keyframes] 后台任务 shot#%s 异常: %s", shot_id, e)
            with KF_LOCK:
                KF_STATUS[shot_id]["status"] = "failed"
                KF_STATUS[shot_id]["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()


def kf_status(shot_id):
    """返回某镜关键帧生成状态；进程重启后 KF_STATUS 丢失时，
    根据首尾帧是否已生成推断 done（幂等兜底）。"""
    with KF_LOCK:
        st = dict(KF_STATUS.get(shot_id) or {})
    if st:
        return st
    shot = find_shot(shot_id)
    if shot and shot.get("asset_frame_start") and shot.get("asset_frame_end"):
        return {"status": "done", "result": {"ok": True, "skipped": True, "shot_id": shot_id}}
    return {"status": "unknown"}


def video_submit(shot_id, force=False, payload=None):
    """【老板 0810】视频生成改后台任务：立即返回 accepted（同步长请求经 CF 会 524）。
    前端轮询 /api/generate/status 明确看到 running/done/failed。"""
    # 【0810 夜修】前端「保存并重渲」回传的字段（ref/subtitle/video_prompt/emotion/camera/duration
    # 等）必须先合并到 shot 再生成——否则改了引用素材/台词重渲不生效（原同步端点有此逻辑，后台化后丢失）。
    if payload:
        try:
            _p_sh = find_shot(shot_id)
            if _p_sh is not None:
                for _k, _v in payload.items():
                    if _k not in ("asset_video", "asset_image", "asset_audio",
                                  "asset_frame_start", "asset_frame_end", "status", "engine",
                                  "remote_image_ref", "id"):
                        _p_sh[_k] = _v
                _save_spec()  # 【0810 夜修】立即落盘：即使随后幂等跳过，前端改的 ref/台词也已保存
                _log.info("[video] 合并前端回传 shot 字段: %s", list(payload.keys()))
        except Exception as _pe:
            _log.error("[video] 合并 payload 异常 shot#%s: %s", shot_id, _pe)
    with VIDEO_LOCK:
        VIDEO_STATUS[shot_id] = {"status": "pending", "error": "", "started": now_iso(), "result": None}

    def _run():
        try:
            with VIDEO_LOCK:
                VIDEO_STATUS[shot_id]["status"] = "running"
            _log.info("[video] 后台任务 shot#%s 执行中", shot_id)
            # 与原同步端点等价：先补全参考图（幂等）→ 旁白/闭唇镜走 MiniMax 配音 → 生成视频
            _sh = find_shot(shot_id)
            if _sh is not None:
                if not _sh.get("asset_image"):
                    try:
                        _manifest = generate_references_real()
                        for _s in SPEC.get("shots", []):
                            if _manifest.get(_s.get("ref")):
                                _s["asset_image"] = _manifest[_s["ref"]]
                    except Exception as _re:
                        _log.error("[video] 后台补参考图异常 shot#%s: %s", shot_id, _re)
                if _sh.get("use_minimax_audio") and not _sh.get("asset_audio"):
                    try:
                        generate_single_audio(shot_id)
                    except Exception as _ae:
                        _log.error("[video] 后台配音异常 shot#%s: %s", shot_id, _ae)
            res = generate_video_real(shot_id, force=force)
            _sh2 = find_shot(shot_id)
            if _sh2 is not None:
                _sh2["status"] = "done" if res.get("ok") else "failed"
                _sh2["engine"] = {
                    "image": "agnes-image-2.1-flash",
                    "video": "agnes-video-v2.0",
                    "audio": "MiniMax-Speech" if _sh2.get("use_minimax_audio") else "AGNES 原生音画同步",
                }
            with VIDEO_LOCK:
                VIDEO_STATUS[shot_id]["status"] = "done"
                VIDEO_STATUS[shot_id]["result"] = res
        except Exception as e:
            # 【429 限流自动重试·老板 0811 走查】视频 RPM=5 是量产硬约束，批量提交会在
            # 创建请求时撞 429。限流失败延迟退避重试（15s/30s/45s，共 3 次），非限流错误不重试。
            _retried = False
            if "429" in str(e) or "限流" in str(e):
                _retried = True
                for _att in (15, 30, 45):
                    _log.warning("[video] shot#%s 429 限流，%ds 后自动重试", shot_id, _att)
                    time.sleep(_att)
                    try:
                        _res2 = generate_video_real(shot_id, force=force)
                        _sh3 = find_shot(shot_id)
                        if _sh3 is not None:
                            _sh3["status"] = "done" if _res2.get("ok") else "failed"
                        with VIDEO_LOCK:
                            VIDEO_STATUS[shot_id]["status"] = "done"
                            VIDEO_STATUS[shot_id]["result"] = _res2
                        break
                    except Exception as _e2:
                        e = _e2
                        _log.error("[video] shot#%s 重试仍失败: %s", shot_id, _e2)
                else:
                    _log.error("[video] 后台任务 shot#%s 429 重试 3 次仍失败: %s", shot_id, e)
                    with VIDEO_LOCK:
                        VIDEO_STATUS[shot_id]["status"] = "failed"
                        VIDEO_STATUS[shot_id]["error"] = str(e)
            if not _retried:
                _log.error("[video] 后台任务 shot#%s 异常: %s", shot_id, e)
                with VIDEO_LOCK:
                    VIDEO_STATUS[shot_id]["status"] = "failed"
                    VIDEO_STATUS[shot_id]["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()


def video_status(shot_id):
    """返回某镜视频生成状态；进程重启后 VIDEO_STATUS 丢失时按 asset_video 推断 done。"""
    with VIDEO_LOCK:
        st = dict(VIDEO_STATUS.get(shot_id) or {})
    if st:
        return st
    shot = find_shot(shot_id)
    if shot and shot.get("asset_video"):
        return {"status": "done", "result": {"ok": True, "skipped": True, "shot_id": shot_id}}
    return {"status": "unknown"}


def build_agnes_payload(shot):
    ref_key = shot.get("ref")
    ref_prompt = _ref_prompt(ref_key)
    strategy = shot.get("gen_strategy", GEN_POLICY_DEFAULT)
    if strategy == "ui":
        mode = "ui_skip"
    elif strategy == "keyframes":
        mode = "keyframes"
    elif strategy == "text2video":
        mode = "t2v"
    elif ref_key:
        mode = "i2v"
    else:
        mode = "t2v"
    kf = None
    if strategy == "keyframes":
        kf = [shot.get("asset_frame_start") or ref_prompt or "<首帧锚点>",
              shot.get("asset_frame_end") or "<待生成尾帧>"]
    # 【0811 认证固化】keyframes 过渡关系模板（v8 实测：过渡 prompt vs 场景 prompt → 角色 2→9 分、
    # 尾帧脸型 pass/内部一致 pass）。官方推荐：prompt 描述"过渡关系+保持身份"，禁止描述动作步骤。
    # 官方原句："在第一个关键帧与第二个关键帧之间生成流畅过渡，保持角色形象不变、摄像机视角统一，
    #            同时实现场景间自然的运动效果。"
    video_prompt = shot.get("video_prompt", "")
    if strategy == "keyframes":
        _KF_TRANSITION = (" Create a smooth transition between the first and last keyframes: "
                          "keep the character's appearance unchanged (no face morphing, no identity change), "
                          "keep the camera angle consistent (no shaking), "
                          "achieve natural motion between scenes (no jumps). "
                          "Keep face, hairstyle and clothing identical throughout the whole clip.")
        video_prompt = (video_prompt + _KF_TRANSITION).strip()
    return {
        "shot_id": shot.get("id"),
        "gen_strategy": strategy,
        "image": {"model": "agnes-image-2.1-flash", "prompt": ref_prompt, "seed": 42},
        "video": {"model": "agnes-video-v2.0", "prompt": video_prompt,
                   "mode": mode,
                   "keyframes": kf,
                   "num_frames": shot.get("num_frames", 145),
                   "width": SPEC.get("resolution", {}).get("width", 1080),
                   "height": SPEC.get("resolution", {}).get("height", 1920)},
        "voice": {"role": shot.get("voice"), "text": shot.get("subtitle", ""), "duration_sec": shot.get("duration", 5)},
    }


def fetch_image(url, fn):
    try:
        if url.startswith("http"):
            urllib.request.urlretrieve(url, fn)
        else:
            with open(fn, "wb") as f:
                f.write(base64.b64decode(url))
        return True
    except Exception:
        return False


def fetch_binary(url, fn):
    """下载 AGNES 返回的远程视频，失败时保留远程 URL 给前端直连播放。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WorkBuddy-Storyboard-Studio/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(fn, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"[video] 下载失败，改用远程 URL: {e}")
        return False


def _ffprobe_meta(vabs):
    """【T4 官方尺寸回读】ffprobe 读成片真实 WxH/秒数（官方：以实际输出为准，
    提交尺寸会被归一化到 480p/720p/1080p 档）。失败静默返回 (None, None)，不阻断生成。"""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=width,height:format=duration",
                              "-of", "json", vabs], capture_output=True, text=True, timeout=30)
        j = json.loads(out.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        w, h = st.get("width"), st.get("height")
        dur = None
        fmt = j.get("format") or {}
        if fmt.get("duration"):
            try:
                dur = round(float(fmt["duration"]), 1)
            except Exception:
                pass
        if w and h:
            return f"{w}x{h}", dur
    except Exception as e:
        _log.debug("[video] ffprobe 读取失败(忽略): %s", e)
    return None, None


def public_asset_url(rel_path):
    """AGNES 图生视频需要可访问图片 URL；本地服务运行时用 127.0.0.1 资产地址。"""
    if not rel_path:
        return ""
    if rel_path.startswith("http://") or rel_path.startswith("https://"):
        return rel_path
    return urljoin(f"http://127.0.0.1:{PORT}/", rel_path.replace("\\", "/"))


def _video_size():
    """【测试/正式分辨率开关·老板 0811】生成分辨率统一入口：
    - 环境变量 VIDEO_WIDTH/VIDEO_HEIGHT 优先（可覆盖，运维级）；
    - 否则按项目 meta.resolution_mode（'prod' → 720p / 默认 'test' → 480p）；
    - 画幅按 meta.aspect_mode：默认 portrait 竖屏 9:16（短剧标准）；'landscape' 横屏 16:9
      （横版平台/电脑端，宽高交换）。
    官方会把提交尺寸归一化到 480p/720p/1080p 档，测试档只验证流程不追求画质。"""
    ew, eh = os.environ.get("VIDEO_WIDTH"), os.environ.get("VIDEO_HEIGHT")
    if ew and eh:
        try:
            return int(ew), int(eh)
        except Exception:
            pass
    if (META.get("resolution_mode") or "test") == "prod":
        w, h = 720, 1280
    else:
        w, h = 480, 854
    if (META.get("aspect_mode") or "portrait") == "landscape":
        w, h = h, w
    return w, h


def _snap_nf(n, fr=24):
    """把任意帧数吸附到 AGNES 合法值 8*k+1（k>=1），并夹在 [9, 441]。
    AGNES 硬性要求 num_frames = 8*n+1，否则 400 拒绝。"""
    try:
        n = int(n)
    except Exception:
        n = 121
    k = round((n - 1) / 8)
    if k < 1:
        k = 1
    return max(9, min(8 * k + 1, 441))


def _shot_nf(shot):
    """单镜 num_frames：优先用分镜时长×帧率换算（保音画同步），否则吸附存储值。"""
    fr = SPEC.get("frame_rate", 24)
    d = shot.get("duration")
    if d:
        return _snap_nf(int(d) * fr)
    return _snap_nf(shot.get("num_frames", 121))


def generate_video_real(shot_id, force=False):
    _log.info("[video] shot#%s 开始生成视频%s", shot_id, "（强制重渲）" if force else "")
    """REAL=1：按 gen_strategy 生成单镜真实动画，并写回 asset_video。
    - keyframes：create_video(keyframes=[首帧,尾帧])，prompt 用过渡描述+身份锁+原生音轨。
    - reference：create_video(image=锚点首帧)，单图生视频。
    - ui：UI/界面镜走 AGNES 图生视频真动态（见下方 ui 分支，不再由 ui_animate 静帧占位）。
    - 幂等（老板 0810）：asset_video 已存在且非 force → 直接跳过，不重复烧视频额度。"""
    shot = find_shot(shot_id)
    if not shot:
        return {"ok": False, "error": f"shot {shot_id} not found"}
    # 【幂等跳过·老板 0810】视频已生成 → 批量时跳过（单镜重渲走 force=True）
    if not force and shot.get("asset_video") and not str(shot.get("asset_video") or "").startswith("sim://"):
        _log.info("[video] shot#%s 视频已生成，跳过", shot_id)
        return {"ok": True, "skipped": True, "reason": "视频已生成", "shot_id": shot_id,
                "output": shot["asset_video"]}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import create_video, wait_for_video

    strategy = shot.get("gen_strategy", GEN_POLICY_DEFAULT)
    if strategy == "ui":
        # 【ui_shot 真视频·老板要求】UI/界面镜用 AGNES 图生视频出真动态，
        # 不再走本地 ui_animate 静帧占位。用其 ui ref 锚点图(如 screen_base)作 image，
        # 纯界面视觉动效；不加原生 speech（旁白由 MiniMax 在配音阶段补齐），
        # 不加角色身份锁（UI 非人物，加锁反而让 AGNES 找"人"出错）。
        ref_key = shot.get("ref")
        image_ref = _ref_anchor(ref_key)
        if not image_ref:
            asset_image = shot.get("asset_image", "")
            if str(asset_image).startswith("http"):
                image_ref = asset_image
            elif asset_image:
                # 【本地资产→data URI·老板 0811】AGNES 不支持 localhost/私网 URL（400 实测），
                # 本地图必须转 base64（同 keyframes 首尾帧做法）。
                image_ref = _img_to_datauri(asset_abs(asset_image) if str(asset_image).startswith("assets/") else asset_image)
        if image_ref:
            shot["remote_image_ref"] = image_ref
        out_dir = asset_abs("assets/video")
        os.makedirs(out_dir, exist_ok=True)
        local_rel = f"assets/video/shot{shot_id:03d}.mp4"
        local_abs = asset_abs(local_rel)
        prompt = shot.get("video_prompt", "")
        _cgs = _clean_global_style()
        if _cgs and _cgs not in prompt:
            prompt = f"{prompt}, {_cgs}"
        prompt = prompt + ". subtle cinematic camera move, gentle interface motion, no people speaking"
        task = create_video(
            prompt=prompt,
            image=image_ref or None,
            width=_video_size()[0],
            height=_video_size()[1],
            num_frames=_shot_nf(shot),
            frame_rate=SPEC.get("frame_rate", 24),
            negative_prompt="static, frozen frame, no motion, watermark, blurry, deformed face, "
                             "text, subtitles, captions, written words, on-screen text",
            seed=shot.get("seed") or 1000 + int(shot.get("id") or 0),
        )
        video_id = task.get("video_id") or task.get("task_id") or task.get("id")
        if not video_id:
            return {"ok": False, "shot_id": shot_id, "task": task, "error": "AGNES 未返回 video_id"}
        remote_url = wait_for_video(video_id, timeout=900, interval=10)
        if remote_url and fetch_binary(remote_url, local_abs):
            shot["asset_video"] = local_rel
            _vsz, _vsec = _ffprobe_meta(local_abs)
            if _vsz:
                shot["video_size"] = _vsz
            if _vsec:
                shot["video_seconds"] = _vsec
        else:
            shot["asset_video"] = remote_url
        shot["status"] = "done"
        _save_spec()
        return {"ok": True, "shot_id": shot_id, "strategy": "ui-real", "video_id": video_id,
                "remote_url": remote_url, "output": shot["asset_video"]}

    # 【角色一致性】锚点图统一走 _ref_anchor：同角色全片复用同一张云端图，绝不每镜重抽。
    ref_key = shot.get("ref")
    image_ref = _ref_anchor(ref_key)
    if not image_ref:
        asset_image = shot.get("asset_image", "")
        if str(asset_image).startswith("http"):
            image_ref = asset_image           # 分镜里本就写了云端图
        else:
            # 【本地资产→data URI·老板 0811】AGNES 不支持 localhost/私网 URL，须 base64
            image_ref = (_img_to_datauri(asset_abs(asset_image) if str(asset_image).startswith("assets/") else asset_image)
                         if asset_image else None)
    # reference 空镜（无 ref）：从 scene_key 取场景图作为单针输入——空镜单针必须有场景图，
    # 否则 image=None 变成文生视频，画面与已生成的场景资产脱节。
    if not image_ref and (shot.get("gen_strategy") in ("reference",) or not ref_key):
        _sk = shot.get("scene_key") or ""
        for _sc in SPEC.get("scenes", []):
            if (_sc.get("key") or "") == _sk:
                _sa = _sc.get("asset_image") or ""
                if str(_sa).startswith("http"):
                    image_ref = _sa
                elif _sa:
                    # 【本地资产→data URI·老板 0811】同上
                    image_ref = _img_to_datauri(asset_abs(_sa) if str(_sa).startswith("assets/") else _sa)
                break
    if image_ref:
        shot["remote_image_ref"] = image_ref

    out_dir = asset_abs("assets/video")
    os.makedirs(out_dir, exist_ok=True)
    local_rel = f"assets/video/shot{shot_id:03d}.mp4"
    local_abs = asset_abs(local_rel)

    if strategy == "keyframes":
        # 防御：脏数据（如 sim:// 占位）会让 AGNES 报 "keyframes mode requires 2 to 3 images"
        for _f in ("asset_frame_start", "asset_frame_end"):
            if str(shot.get(_f) or "").startswith("sim://"):
                shot.pop(_f, None)
        # 确保首/尾帧已生成（首帧复用锚点，尾帧 img2img 首帧→结束态）
        if not shot.get("asset_frame_end"):
            kf = generate_keyframes_real(shot_id)
            shot = find_shot(shot_id)
            if not shot or not shot.get("asset_frame_end"):
                return {"ok": False, "shot_id": shot_id,
                        "error": "首尾针模式失败：尾帧未生成（" + str(kf.get("error", "")) + "）"}
        first = _to_agnes_image(shot.get("asset_frame_start"))
        last = _to_agnes_image(shot.get("asset_frame_end"))
        if not (first and last):
            # 关键帧不足 2 张 → 降级为单图参考模式，避免 AGNES 400 直接废掉整镜
            strategy = "reference"
            shot["gen_strategy_runtime"] = "reference(fallback:keyframes缺帧)"
            print(f"[warn] shot#{shot_id} 关键帧不足(first={bool(first)},last={bool(last)})，降级 reference 模式")

    if strategy == "keyframes":
        # 首尾针模式 prompt = 过渡描述（官方最佳实践），叠加身份锁 + 原生中文音轨 + 电影语法
        prompt = _transition_prompt(shot)
        if ref_key and "locked character identity" not in prompt:
            prompt = f"{prompt}, {_identity_lock(ref_key)}"
        cam = _camera_clause(shot)
        if cam and cam not in prompt and not _cam_mentioned(prompt):
            prompt = f"{prompt}, {cam}"
        cine = _cinema_clause(shot)
        if cine:
            prompt = f"{prompt}, {cine}"
        speech = _speech_clause(shot)
        if speech:
            prompt = f"{prompt}. {speech}"
        _log.info("[video] shot#%s keyframes prompt: %s", shot_id, prompt[:1200])
        task = create_video(
            prompt=prompt,
            keyframes=[first, last],
            width=_video_size()[0],
            height=_video_size()[1],
            num_frames=_shot_nf(shot),
            frame_rate=SPEC.get("frame_rate", 24),
            negative_prompt=(shot.get("negative_prompt") or _NEG_IDENTITY),
            seed=shot.get("seed") or 1000 + int(shot.get("id") or 0),
        )
    elif strategy == "reference":  # 单图生视频（image=锚点/场景图），省一张尾帧图成本
        prompt = _clean_video_prompt(shot.get("video_prompt", ""))
        _cgs = _clean_global_style()
        if _cgs and _cgs not in prompt:
            prompt = f"{prompt}, {_cgs}"
        if ref_key and "locked character identity" not in prompt:
            prompt = f"{prompt}, {_identity_lock(ref_key)}"
            # 【T1 官方图生视频结构·老板 0811】稳定句：描述"什么该动+哪些保持稳定"
            # 官方例子 "Animate the character ..., while keeping the face and outfit consistent"
            prompt = f"{prompt}, while keeping the face and outfit consistent, stable character identity throughout"
        cam = _camera_clause(shot)
        if cam and cam not in prompt and not _cam_mentioned(prompt):
            prompt = f"{prompt}, {cam}"
        cine = _cinema_clause(shot)
        if cine:
            prompt = f"{prompt}, {cine}"
        speech = _speech_clause(shot)
        if speech:
            prompt = f"{prompt}. {speech}"
        _log.info("[video] shot#%s reference prompt: %s", shot_id, prompt[:1200])
        task = create_video(
            prompt=prompt,
            image=image_ref or None,
            width=_video_size()[0],
            height=_video_size()[1],
            num_frames=_shot_nf(shot),
            frame_rate=SPEC.get("frame_rate", 24),
            negative_prompt=(shot.get("negative_prompt") or _NEG_IDENTITY),
            seed=shot.get("seed") or 1000 + int(shot.get("id") or 0),
        )
    else:  # text2video：纯文生视频（无图输入），用于无角色纯场景/空镜
        prompt = shot.get("video_prompt", "")
        _cgs = _clean_global_style()
        if _cgs and _cgs not in prompt:
            prompt = f"{prompt}, {_cgs}"
        cam = _camera_clause(shot)
        if cam and cam not in prompt and not _cam_mentioned(prompt):
            prompt = f"{prompt}, {cam}"
        task = create_video(
            prompt=prompt,
            image=None,  # 纯文生
            width=_video_size()[0],
            height=_video_size()[1],
            num_frames=_shot_nf(shot),
            frame_rate=SPEC.get("frame_rate", 24),
            negative_prompt=(shot.get("negative_prompt") or _NEG_IDENTITY),
            seed=shot.get("seed") or 1000 + int(shot.get("id") or 0),
        )

    video_id = task.get("video_id") or task.get("task_id") or task.get("id")
    if not video_id:
        return {"ok": False, "shot_id": shot_id, "task": task, "error": "AGNES 未返回 video_id"}
    remote_url = wait_for_video(video_id, timeout=900, interval=10)
    if remote_url and fetch_binary(remote_url, local_abs):
        shot["asset_video"] = local_rel
        _vsz, _vsec = _ffprobe_meta(local_abs)
        if _vsz:
            shot["video_size"] = _vsz
        if _vsec:
            shot["video_seconds"] = _vsec
    else:
        shot["asset_video"] = remote_url
    shot["status"] = "done"
    _save_spec()
    _log.info("[video] shot#%s 视频完成 strategy=%s video_id=%s size=%s", shot_id, strategy, video_id,
              shot.get("video_size") or "-")
    return {"ok": True, "shot_id": shot_id, "strategy": strategy, "video_id": video_id,
            "remote_url": remote_url, "output": shot["asset_video"]}


def generate_references_real():
    _log.info("[refs] 开始批量生成参考图")
    """REAL=1：用 AGNES 文生图出全部被引用的参考图，存本地。

    图片生成硬超时兜底（与 _gen_video_with_timeout 同源）：AGNES 免费档偶发「半开连接」，
    单张 generate_image 最坏 360s×重试会无声挂死整批；用线程包一层，单张超 300s 直接
    判失败并继续，绝不让一张图拖垮全部角色参考图（前端 loading 才能及时回落）。"""
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import generate_image
    refs = SPEC.get("references", {})
    used = list(dict.fromkeys([s.get("ref") for s in SPEC.get("shots", []) if s.get("ref")]))
    out_dir = asset_abs("assets/references")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {}
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(3, len(used))))  # 并行补锚点（老板 0810：异步批量）
    try:
        for key in used:
            prompt = _ref_prompt(key)
            if not prompt:
                continue
            # 先冻结身份令牌，再出图 —— 令牌同时用于每镜 video prompt，保证图与视频描述同源
            ref0 = refs.get(key)
            if isinstance(ref0, dict) and not ref0.get("identity_token"):
                ref0["identity_token"] = _build_identity_token(ref0.get("cn") or prompt)
            url = None
            for size in ("768x1344", "1024x1024"):
                try:
                    url = ex.submit(generate_image, prompt, size=size).result(timeout=300)
                    break
                except Exception as e:
                    url = None
                    print(f"[WARN] 参考图生成超时/异常(300s): {key}/{size}: {e}")
            if not url:
                manifest[key] = None
                continue
            fn = os.path.join(out_dir, f"{key}.png")
            manifest[key] = f"assets/references/{key}.png" if fetch_image(url, fn) else url
            # 【角色一致性关键】云端 URL 必须缓存，供所有引用该角色的镜头复用同一张锁脸锚点。
            # 若丢弃 URL，generate_video_real 会因"本地图云端读不到"而重新文生图抽卡 → 跨镜换脸。
            ref = refs.get(key)
            if isinstance(ref, dict):
                ref["remote_url"] = url
    finally:
        ex.shutdown(wait=False)  # 不等待可能挂死的子线程，避免 join 阻塞主流程
    _save_spec()
    return manifest


def _gen_image_assets_real(items, subdir, timeout=300):
    """REAL=1：批量用 AGNES 文生图出场景/道具资产，存本地 assets/{subdir}/，写回 asset_image。

    与 generate_references_real 同套「generate_image + fetch_image」模式，但不冻结身份令牌
    （场景/道具无需锁脸，只需风格一致）。items 为 spec.scenes / spec.props 的列表元素。

    图片生成硬超时兜底（与 _gen_video_with_timeout 同源）：单张超 timeout 秒直接判失败跳过，
    绝不让一张图挂死整批（前端 loading 才能及时回落，③关键帧按钮才点得动）。"""
    if not items:
        return {}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import generate_image
    out_dir = asset_abs(f"assets/{subdir}")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {}
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        for it in items:
            key = it.get("key") or it.get("name") or ""
            prompt = it.get("img_prompt")
            if not key or not prompt:
                continue
            # 文件名消毒：去掉 Windows 非法路径字符，其余（含中文）原样保留
            safe = "".join(c if (c.isalnum() or c in " _-") or ord(c) > 127 else "_" for c in str(key))
            url = None
            for size in ("768x1344", "1024x1024"):
                try:
                    url = ex.submit(generate_image, prompt, size=size).result(timeout=timeout)
                    break
                except Exception as e:
                    url = None
                    print(f"[WARN] 资产图生成超时/异常({timeout}s): {key}/{size}: {e}")
            if not url:
                manifest[key] = None
                continue
            fn = os.path.join(out_dir, f"{safe}.png")
            rel = f"assets/{subdir}/{safe}.png" if fetch_image(url, fn) else url
            it["asset_image"] = rel
            manifest[key] = rel
    finally:
        ex.shutdown(wait=False)  # 不等待可能挂死的子线程，避免 join 阻塞主流程
    _save_spec()
    return manifest


# ===== MiniMax 多角色配音 =====

FFMPEG_BIN = r"C:\Users\67972\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

def _reconcile_audio(in_path, target_dur, out_path, tol=0.12):
    """时长对账：把 MiniMax 生成的音频 pad/trim/提速到 shot.duration。
    core_rule: storyboard_shot_duration_unchangeable —— 只动音频，不动分镜时长。
    返回 True 表示已产出可用音频。"""
    if not os.path.isfile(in_path) or os.path.getsize(in_path) < 50:
        return False
    try:
        probe = FFMPEG_BIN.replace("ffmpeg.exe", "ffprobe.exe")
        r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", in_path],
                           capture_output=True, text=True)
        adur = float(r.stdout.strip() or 0)
    except Exception:
        adur = 0.0
    diff = adur - target_dur
    try:
        if diff > tol:
            if diff <= 0.3:                       # grade1: 小幅提速 1.0~1.2
                factor = min(1.2, target_dur / adur)
                subprocess.run([FFMPEG_BIN, "-y", "-i", in_path, "-af", f"atempo={factor:.3f}",
                                "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", out_path], capture_output=True)
            else:                                 # grade2/3: 极限提速 + 截断尾音
                tmp = out_path + ".sp.mp3"
                subprocess.run([FFMPEG_BIN, "-y", "-i", in_path, "-af", "atempo=1.2",
                                "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", tmp], capture_output=True)
                subprocess.run([FFMPEG_BIN, "-y", "-i", tmp, "-t", str(target_dur), "-c", "copy", out_path], capture_output=True)
        elif diff < -tol:                         # 欠时：补静音到目标时长
            subprocess.run([FFMPEG_BIN, "-y", "-i", in_path, "-af", "apad", "-t", str(target_dur),
                            "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", out_path], capture_output=True)
        else:                                     # 容差内：直接采用
            if in_path != out_path:
                shutil.copy(in_path, out_path)
        return os.path.isfile(out_path) and os.path.getsize(out_path) > 100
    except Exception as e:
        print(f"[audio] 时长对账失败: {e}")
        if in_path != out_path and os.path.isfile(in_path):
            shutil.copy(in_path, out_path)
        return os.path.isfile(out_path or in_path)


def _voice_for_shot(shot):
    """根据 shot.voice 字段 + voice_roles 映射，返回 MiniMax voice_id（已规整到真实音色）。"""
    voice_key = shot.get("voice", "narrator")
    roles = SPEC.get("voice_roles", {})
    vid = None
    hint = ""
    if voice_key in roles and isinstance(roles[voice_key], dict):
        vid = roles[voice_key].get("minimax_voice_id") or roles[voice_key].get("voice_id")
        hint = roles[voice_key].get("desc", "") or voice_key
    if not vid:
        vid = voice_key
        hint = voice_key
    # 规整：无效 voice_id（如模型编造的 female_young_chill）→ 按性别兜底到真实音色
    return _normalize_voice(vid, hint + " " + (shot.get("voice") or ""))


def _load_minimax_tts():
    """加载 MiniMax TTS 客户端。返回模块或 None。"""
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "voice")))
    try:
        import minimax_tts
        minimax_tts._load_env()
        return minimax_tts
    except Exception as e:
        print(f"[audio] 加载 minimax_tts 失败: {e}")
        return None


def generate_audio_real():
    """用 MiniMax 多角色 TTS 生成配音，仅对 shot.use_minimax_audio=True 的镜（旁白/闭唇镜）。
    对白镜默认走 AGNES 原生音画同步（见 /api/generate/shot 路由），避免双音轨覆盖。
    需 REAL=1 + MINIMAX_API_KEY。生成后做时长对账 pad/trim 到 shot.duration。"""
    tts_mod = _load_minimax_tts()
    if tts_mod is None:
        return {"ok": False, "note": "MiniMax TTS 客户端加载失败（scripts/voice/minimax_tts.py）"}
    if not os.environ.get("MINIMAX_API_KEY"):
        return {"ok": False, "note": "未配置 MINIMAX_API_KEY（~/.workbuddy/.env）"}
    if not os.environ.get("MINIMAX_GROUP_ID"):
        return {"ok": False, "note": "未配置 MINIMAX_GROUP_ID（~/.workbuddy/.env）"}

    out_dir = asset_abs("assets/audio")
    os.makedirs(out_dir, exist_ok=True)
    ok_list, skip_list, fail_list = [], [], []
    for s in SPEC.get("shots", []):
        sid = s.get("id")
        # 仅 use_minimax_audio 镜走 MiniMax（老板 0804 指令：对白镜用 AGNES 原生音画同步）
        if not s.get("use_minimax_audio"):
            continue
        text = s.get("subtitle", "")
        if not text:
            skip_list.append(sid)
            continue
        voice_id = _voice_for_shot(s)
        fn_raw = os.path.join(out_dir, f"shot{sid:03d}.raw.mp3")
        fn = os.path.join(out_dir, f"shot{sid:03d}.mp3")
        try:
            tts_mod.tts(text, voice_id=voice_id, out_path=fn_raw)
            target = float(s.get("duration", 5))
            _reconcile_audio(fn_raw, target, fn)
            s["asset_audio"] = f"assets/audio/shot{sid:03d}.mp3"
            ok_list.append(sid)
        except Exception as e:
            fail_list.append({"id": sid, "err": str(e)})
    return {"ok": True,
            "output": ("assets/audio/shot%03d.mp3" % ok_list[0]) if ok_list else "(无 MiniMax 镜)",
            "voices": ok_list, "skipped": skip_list, "failed": fail_list}


def generate_single_audio(shot_id):
    """生成单镜配音。"""
    _log.info("[audio] shot#%s 开始生成配音", shot_id)
    shot = find_shot(shot_id)
    if not shot:
        return {"ok": False, "error": f"shot {shot_id} not found"}
    tts_mod = _load_minimax_tts()
    if tts_mod is None:
        return {"ok": False, "note": "MiniMax TTS 客户端加载失败"}
    if not os.environ.get("MINIMAX_API_KEY"):
        return {"ok": False, "note": "未配置 MINIMAX_API_KEY"}
    if not os.environ.get("MINIMAX_GROUP_ID"):
        return {"ok": False, "note": "未配置 MINIMAX_GROUP_ID"}
    text = shot.get("subtitle", "")
    if not text:
        return {"ok": False, "error": "该镜无台词"}
    voice_id = _voice_for_shot(shot)
    out_dir = asset_abs("assets/audio")
    os.makedirs(out_dir, exist_ok=True)
    fn = os.path.join(out_dir, f"shot{shot_id:03d}.mp3")
    try:
        fn_raw = fn + ".raw.mp3"
        tts_mod.tts(text, voice_id=voice_id, out_path=fn_raw)
        target = float(shot.get("duration", 5))
        _reconcile_audio(fn_raw, target, fn)
        shot["asset_audio"] = f"assets/audio/shot{shot_id:03d}.mp3"
        return {"ok": True, "shot_id": shot_id, "voice": voice_id, "output": shot["asset_audio"]}
    except Exception as e:
        return {"ok": False, "shot_id": shot_id, "error": str(e)}


def build_manifest():
    """按 SceneSpec 生成 assemble.py 需要的 manifest.json（写入项目目录）。

    片源优先级：shot.asset_video -> assets/video/shot_NNN.mp4 -> assets/video/clip_NN.mp4
    返回 (manifest_path, records, missing)
    """
    pdir = os.path.join(PROJECTS_ROOT, ACTIVE)
    vdir = os.path.join(pdir, "assets", "video")
    recs, missing = [], []
    for shot in SPEC.get("shots", []):
        sid = int(shot.get("id"))
        cands = []
        av = (shot.get("asset_video") or "").strip()
        if av:
            cands.append(av if os.path.isabs(av) else asset_abs(av))
        # 兼容两种历史命名：生成器现写 shotNNN.mp4（无下划线），旧版写 shot_NNN.mp4
        cands.append(os.path.join(vdir, f"shot{sid:03d}.mp4"))
        cands.append(os.path.join(vdir, f"shot_{sid:03d}.mp4"))
        cands.append(os.path.join(vdir, f"clip_{sid:02d}.mp4"))
        src = next((c for c in cands if os.path.isfile(c)), None)
        if not src:
            missing.append(sid)
            continue
        recs.append({
            "id": sid,
            "path": os.path.normpath(src),
            "duration": shot.get("duration", 5),
            "subtitle": shot.get("subtitle", ""),
            "ui_shot": bool(shot.get("ui_shot", False)),
        })
    mpath = os.path.join(pdir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=2)
    return mpath, recs, missing


def _auto_global_bgm(pdir, dur=None):
    """生成整片全局 BGM（程序化占位，商用前须替换为授权音乐）。返回 wav 绝对路径。"""
    import subprocess
    sb_path = os.path.join(pdir, "storyboard.json")
    if dur is None:
        try:
            sb = json.load(open(sb_path, encoding="utf-8"))
            dur = sum(float(s.get("duration", 5)) for s in sb.get("shots", [])) or 60.0
        except Exception:
            dur = 60.0
    gbm_script = os.path.normpath(os.path.join(HERE, "..", "scripts", "voice", "gen_bgm.py"))
    audio_dir = os.path.join(pdir, "assets", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    subprocess.run([sys.executable, gbm_script, "--storyboard", "x", "--out", audio_dir,
                    "--global-mode", "--duration", f"{dur:.1f}", "--emotion", "neutral"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    path = os.path.join(audio_dir, "bgm_global.wav")
    return path if os.path.isfile(path) else None


def do_assemble(params=None):
    """去 stub：真调 scripts/edit/assemble.py 合成成片（本地 ffmpeg，不花 token）。
    params 可选：{transition, subtitle(bool), ai_watermark(bool), bgm(bool/str路径)} 透传精修。"""
    import subprocess
    try:
        pdir = os.path.join(PROJECTS_ROOT, ACTIVE)
        sb_path = os.path.join(pdir, "storyboard.json")
        if not os.path.isfile(sb_path):
            return {"ok": False, "error": f"分镜不存在: {sb_path}"}
        mpath, recs, missing = build_manifest()
        if not recs:
            return {"ok": False, "error": "无可用视频片段，先生成各镜视频", "missing_shots": missing}

        script = os.path.normpath(os.path.join(HERE, "..", "scripts", "edit", "assemble.py"))
        cmd = [sys.executable, script, "--storyboard", sb_path, "--out", pdir]
        # 【0811 修复·测试档合成】成片分辨率跟随项目生成档位（_video_size）：
        # 之前固定用 storyboard.resolution(1080x1920)，测试档 448x832 源片被拉成 1080p——
        # 又慢又糊。测试模式合成低分辨率成片，正式档合成 720p。横屏随 aspect 走。
        _vw, _vh = _video_size()
        cmd += ["--resolution", "%dx%d" % (_vw, _vh)]
        params = params or {}
        tr = params.get("transition")
        # 归一化：前端/用户可能传 fade/wipe/slide，但 assemble.py 底层只认 none/dissolve。
        # 这里统一映射到 dissolve（视觉最接近淡变），避免 rc=2 报错让「合成成片」按钮直接炸。
        if tr in ("fade", "wipe", "slide"):
            tr = "dissolve"
        if tr and tr != "none":
            cmd += ["--transition", tr]
        if params.get("subtitle") is False:
            cmd += ["--no-subtitle"]
        if params.get("ai_watermark") is False:
            cmd += ["--no-ai-watermark"]
        # 单一真源：成片默认带全局 BGM（无死角）；仅显式 bgm=False 才关闭
        bgm = params.get("bgm", True)
        if bgm:
            gbm = bgm if isinstance(bgm, str) else _auto_global_bgm(pdir)
            if gbm and os.path.isfile(gbm):
                cmd += ["--global-bgm", gbm]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        final = os.path.join(pdir, "final.mp4")
        ok = r.returncode == 0 and os.path.isfile(final)
        tail = (r.stdout or "")[-1500:] + (("\n[stderr]\n" + r.stderr[-800:]) if r.stderr else "")
        out = {
            "ok": ok,
            "dry_run": False,
            "project": ACTIVE,
            "clips": len(recs),
            "missing_shots": missing,
            "manifest": os.path.relpath(mpath, HERE).replace("\\", "/"),
            "returncode": r.returncode,
            "log_tail": tail,
        }
        if os.path.isfile(final):
            out["final"] = final
            out["final_size"] = os.path.getsize(final)
            out["final_url"] = f"/projects/{ACTIVE}/final.mp4"
        if not ok:
            out["error"] = f"assemble 失败(rc={r.returncode})"
        return out
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "assemble 超时(>30min)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ===== B：小说 → 分镜（贴小说自动出结构化 storyboard JSON）=====
def _repair_json_blob(blob):
    """AGNES 偶尔吐出非法 JSON（缺逗号 / 未转义引号 / 中文引号 / 超长截断）。"""
    # 0) 截断容错：结尾残缺时尝试补括号（超长截断常见于 max_tokens 打满）
    for suffix in ("]", "]}", "}]}", "\"}", "\"]}"):
        try:
            return json.loads(blob + suffix)
        except Exception:
            continue
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        from agnes_client import chat
        fix_p = ("Below is a JSON object with a syntax error. Return ONLY the corrected, "
                 "valid JSON object (no markdown, no commentary, keep all fields/values intact):\n\n"
                 + blob)
        out = chat(fix_p, temperature=0.0, max_tokens=6000) or ""
        s = (out or "").strip()
        a = s.find("{"); b = s.rfind("}")
        if a == -1 or b == -1:
            return None
        return json.loads(s[a:b + 1])
    except Exception:
        return None


def generate_storyboard_from_novel(novel, title="", episode="", script_json=None, series_id=None, req=None, project_id=None):
    """B：贴小说文本(或剧本JSON) → agnes-2.5-flash 产出结构化 storyboard JSON → 落为新项目并注册。"""
    if not novel or not novel.strip():
        if script_json:
            novel = ("以下为已生成的剧本 JSON，请严格按现有角色/场景拆成 AGNES 分镜 schema"
                     "（保持角色一致、台词不变）：\n" + json.dumps(script_json, ensure_ascii=False))
        else:
            return {"ok": False, "error": "请粘贴小说文本或提供剧本 JSON"}
    elif script_json:
        # Agent 采纳路径：前端只传一句 logline 作 novel，若丢掉完整需求卡会让分镜质量骤降。
        # 两者都在时合并进 prompt，保证角色/场景/台词不丢。
        novel = (novel.strip() + "\n\n以下为配套的结构化需求卡/剧本 JSON，"
                 "请严格遵循其中的标题、角色设定、场景与台词：\n"
                 + json.dumps(script_json, ensure_ascii=False))
    if req:
        # 需求卡片是用户已校对过的全局参数（标题/类型/时长/风格/拆镜数/角色），
        # 严格遵循它，避免「需求卡看到 6 镜、采纳后变 10 镜」的失控感。
        try:
            req_txt = json.dumps(req, ensure_ascii=False)
        except Exception:
            req_txt = str(req)
        novel = (novel.strip() + "\n\n以下为已确认的需求卡片（用户已校对，请严格遵循其中的"
                 "标题、类型、时长、视觉风格、拆镜数与角色设定来生成分镜）：\n" + req_txt)
    # R1：画幅透传——需求卡选 16:9 横屏时，强制提示模型输出横屏分辨率（提示词默认 9:16 竖屏）
    _aspect = str((req or {}).get("aspect") or "9:16")
    if _aspect == "16:9":
        novel = (novel.strip() +
                 "\n\nASPECT RATIO (MANDATORY): The output resolution MUST be "
                 '{"width":1920,"height":1080} (16:9 LANDSCAPE). '
                 "Ignore the 9:16 vertical defaults in the schema above. "
                 "global_style must read 'cinematic realistic live-action, high detail, film grain'. "
                 "Keep all other schema fields identical.")
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    # 库驱动：system 提示词来自 prompt_library.json 的 storyboard 类型（可迭代），
    # 缺库时回退 STORYBOARD_SYS 常量。改质量只改库文件，不动代码。
    sys_p = lib_prompt("storyboard", default=STORYBOARD_SYS)
    # 新 schema 含 cn_story/camera_angle/audio_tags/continuity_note + 资产 cn_prompt 等字段，
    # 输出更长，4000 token 会截断成非法 JSON → 提到 8000。
    # 【T5 Thinking·老板 0811】分镜生成开官方思考模式提升质量（max_tokens 10000 防 thinking
    # 预算挤占正文；需求卡等强实时调用保持 thinking=False 快响应）。
    # 【0811 修复】AGNES 偶发空响应/超时（59s 空串）或 thinking 截断致 shots 空 →
    # 重试最多 2 次，校验「解析成功且 shots 非空」才通过（曾静默生成 0 镜项目）。
    raw = ""
    sb = None
    for _try in range(3):
        if _try:
            _log.warning("[storyboard] 第 %d 次重试（上次空响应/shots 空/解析失败）", _try + 1)
        raw = chat(novel, system=sys_p, temperature=0.6, max_tokens=10000, thinking=True)
        text = (raw or "").strip()
        _s, _e = text.find("{"), text.rfind("}")
        sb = None
        if _s != -1 and _e != -1:
            try:
                sb = json.loads(text[_s:_e + 1])
            except Exception:
                sb = _repair_json_blob(text[_s:_e + 1])
        if sb and (sb.get("shots") or []):
            break
        _log.warning("[storyboard] 第 %d 次 shots 为空或解析失败（len=%d），重试", _try + 1, len(text))
    if not sb or not sb.get("shots"):
        return {"ok": False, "error": "模型未返回有效分镜（重试 3 次 shots 仍空）", "raw": (raw or "")[:500]}
    # 规范化缺失字段（R1：画幅决定分辨率/风格默认值）
    if _aspect == "16:9":
        sb.setdefault("resolution", {"width": 1920, "height": 1080})
        sb.setdefault("global_style", "cinematic realistic live-action, high detail, film grain")
    else:
        sb.setdefault("resolution", {"width": 1080, "height": 1920})
        sb.setdefault("global_style", "cinematic realistic live-action, high detail, film grain")
    sb.setdefault("voice_roles", {})
    sb.setdefault("references", {})
    sb.setdefault("scenes", [])
    sb.setdefault("props", [])
    for i, s in enumerate(sb.get("shots", []), 1):
        s.setdefault("id", i)
        s.setdefault("gen_strategy", "keyframes")
        # 【ui_shot 真视频·老板要求】UI/界面镜强制走 ui 真视频分支（AGNES 图生视频，纯界面动效），
        # 不再由 ui_animate 本地静帧占位；若分镜未给界面参考图则兜底 screen_base。
        if s.get("ui_shot"):
            s["gen_strategy"] = "ui"
            if not s.get("ref"):
                s["ref"] = "screen_base"
        s.setdefault("status", "pending")
        s.setdefault("asset_image", "")
        s.setdefault("asset_video", "")
        s.setdefault("asset_audio", "")
        s.setdefault("asset_frame_start", "")
        s.setdefault("asset_frame_end", "")
        s.setdefault("transition_in", "fade")
        s.setdefault("transition_out", "fade")
        s.setdefault("camera", "")          # 精控面板可编辑，_camera_clause 会译成摄影指令
        s.setdefault("emotion", "")
        s.setdefault("shot_size", "")
        s.setdefault("beat", "")
        # 中文拍摄剧本字段（分镜模块新契约）：cn_story/摄像机角度/音效/承接上镜/scene_key
        s.setdefault("cn_story", "")
        s.setdefault("camera_angle", "")
        s.setdefault("audio_tags", "")
        s.setdefault("continuity_note", "")
        s.setdefault("scene_key", "")
        # 【老板 0810 全首尾针】普通镜一律 keyframes（不再按场景自动分 reference/text2video），
        # UI 动效镜保持 ui。场景/空镜的自动识别后续版本再加。
        if s.get("ui_shot"):
            _gs = "ui"
        else:
            _gs = "keyframes"
        s["gen_strategy"] = _gs
        s.setdefault("first_frame_prompt", "")   # 首针提示词（文生图兜底/锚点生成描述用）
        s.setdefault("last_frame_prompt", "")
        # num_frames 必须 8*n+1（AGNES 硬性约束）：优先用时长换算，吸附到合法值。
        _dur = int(s.get("duration") or 5)
        s["num_frames"] = _snap_nf(_dur * SPEC.get("frame_rate", 24))
        # 台词时长兜底：中文约 4 字/秒，超了配音念不完会被硬切在半句。
        # 提示词里已经写了规则，但模型经常超——这里按「宁可加时长也不砍台词」处理。
        sub = (s.get("subtitle") or "").strip()
        if sub:
            need = _ceil_div(len(sub), 4)
            if need > _dur:
                capped = min(need, 12)      # 单镜上限 12s，再长就该拆镜了
                s["duration"] = capped
                s["num_frames"] = _snap_nf(capped * SPEC.get("frame_rate", 24))
                s["autofix_duration"] = f"{_dur}s→{capped}s（{len(sub)}字台词念不完）"
    sb["shots"] = sb.get("shots", [])
    # 跨集锁脸（O1）：若属于某剧集，复用剧集锚点库里已生成角色的 remote_url/identity_token/img_prompt，
    # 保证同一角色跨集同脸、且不重复消耗额度重新出图。
    if series_id:
        sstore = _series_anchor_load(series_id)
        if sstore:
            for rk, robj in sb.get("references", {}).items():
                if rk in sstore and isinstance(robj, dict):
                    sref = sstore[rk]
                    robj["remote_url"] = sref.get("remote_url", robj.get("remote_url", ""))
                    if sref.get("identity_token"):
                        robj["identity_token"] = sref["identity_token"]
                    if sref.get("img_prompt"):
                        robj["img_prompt"] = sref["img_prompt"]
        sb["series_id"] = series_id
    # 落到项目：若调用方指定了已存在的 project_id（新建项目后在其内生成分镜），则写入该项目；
    # 否则新建一个项目。这样「新建项目 → ①生成分镜」会在同一项目内填充，不再每次凭空新建导致孤儿项目。
    if project_id and os.path.isdir(os.path.join(PROJECTS_ROOT, project_id)):
        pid = project_id
    else:
        pid = "ep_" + datetime.now().strftime("%m%d_%H%M%S")
    pdir = os.path.join(PROJECTS_ROOT, pid)
    for sub in ("references", "audio", "video"):
        os.makedirs(os.path.join(pdir, "assets", sub), exist_ok=True)
    with open(os.path.join(pdir, "storyboard.json"), "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=2)
    reg = load_registry()
    existing = next((r for r in reg if r["id"] == pid), None)
    if existing:
        existing["name"] = sb.get("title") or sb.get("episode") or pid
        existing["last_opened"] = now_iso()
    else:
        reg.append({"id": pid, "name": sb.get("title") or sb.get("episode") or pid,
                    "spec": f"{pid}/storyboard.json", "created": now_iso(), "last_opened": now_iso()})
    save_registry(reg)
    return {"ok": True, "project_id": pid, "shots": len(sb.get("shots", [])),
            "title": sb.get("title"), "references": len(sb.get("references", {}))}


# ===== 一键全流程编排（P0 核心）=====

def _pip_log(msg, level="info"):
    ts = now_iso()
    with PIPE_LOCK:
        PIPELINE_STATE["log"].append({"t": ts, "msg": msg, "level": level})
    print(f"[pipeline] {msg}", flush=True)


def _pip_set(stage=None, current=None, total=None, **kw):
    with PIPE_LOCK:
        if stage is not None:
            PIPELINE_STATE["stage"] = stage
        if current is not None:
            PIPELINE_STATE["current"] = current
        if total is not None:
            PIPELINE_STATE["total"] = total
        for k, v in kw.items():
            PIPELINE_STATE[k] = v


def _pipeline_snapshot():
    """构建富进度的流水线快照（供 /api/pipeline/progress 与 SSE 复用）。

    在 PIPELINE_STATE 基础上补：stage_names(阶段名)、stage_list(各阶段 done/active/pending)、
    eta_sec(预计剩余秒)、current_sub(当前镜台词)。所有字段对前端事件流友好。"""
    with PIPE_LOCK:
        st = dict(PIPELINE_STATE)
    st["batch"] = dict(BATCH_STATE)
    stages_total = st.get("stages_total") or 0
    stage_idx = st.get("stage_idx") or 0
    names = st.get("stages_cache") or []
    if not names and stages_total:
        names = [f"阶段{i + 1}" for i in range(stages_total)]
    st["stage_names"] = names[:stages_total] if len(names) >= stages_total else names
    stage_status = []
    for i in range(stages_total):
        if i + 1 < stage_idx:
            stage_status.append("done")
        elif i + 1 == stage_idx:
            stage_status.append("active")
        else:
            stage_status.append("pending")
    st["stage_list"] = stage_status
    # ETA：elapsed / 进度比例 * 剩余比例
    eta = None
    started = st.get("started_at")
    if started and stage_idx > 0 and stages_total:
        try:
            el = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
            frac = (stage_idx - 1 + min(1.0, (st.get("current", 0) / st.get("total", 0) or 0))) / max(stages_total, 1)
            frac = max(frac, 0.01)
            eta = max(0, int(el / frac * (1 - frac)))
        except Exception:
            eta = None
    st["eta_sec"] = eta
    return st


def analyze_topic_real(seed):
    """选题分析：种子 → AGNES 结构化选题简报（接工作台，打通前半段）。"""
    if not seed or not seed.strip():
        return {"ok": False, "error": "请填写选题种子"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    sys_p = (
        "You are a veteran Chinese short-drama producer. Given a one-line seed idea, "
        "output ONE strict JSON (no markdown) for a monetizable vertical short-drama topic brief:\n"
        '{"topic": str, "hook": str, "target_platform": [str], "episode_count": int, '
        '"character_brief": [str], "risk": str, "why_hot": str, "monetization": str}\n'
        "Rules: vertical 9:16, platform-fit for 抖音/快手/视频号, IAA+IAP friendly, "
        "compliant with AI-content labeling rules. JSON only."
    )
    try:
        raw = chat(seed, system=sys_p, temperature=0.7, max_tokens=1500)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    text = (raw or "").strip()
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"ok": False, "error": "模型未返回 JSON", "raw": text[:400]}
    try:
        brief = json.loads(text[s:e + 1])
    except Exception as ex:
        return {"ok": False, "error": "JSON 解析失败: " + str(ex), "raw": text[s:e + 1][:400]}
    return {"ok": True, "brief": brief}


def generate_script_real(brief_or_seed, episode=1):
    """剧本生成：选题简报/种子 → AGNES 结构化剧本 JSON（接工作台前半段）。"""
    if not brief_or_seed or not str(brief_or_seed).strip():
        return {"ok": False, "error": "请先生成选题简报或填写种子"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    sys_p = (
        "You are a professional Chinese vertical short-drama screenwriter. "
        "Given a topic brief OR a one-line seed, output ONE strict JSON (no markdown) "
        "for a short-drama script episode:\n"
        '{"episode": str, "title": str, "duration_target": str,\n'
        ' "characters": [{"name": str, "age": int, "personality": str, "background": str}],'
        ' "scenes": [{"scene_id": str, "location": str, "time": str, "characters": [str],'
        ' "action": str, "dialogue": [str], "narration": str, "duration": int, "emotion": str}],'
        ' "plot_summary": str}\n'
        "Rules: 6-8 scenes, vertical 9:16, each scene 6-12s, monetizable, IAA+IAP friendly. JSON only."
    )
    try:
        raw = chat(str(brief_or_seed), system=sys_p, temperature=0.7, max_tokens=3000)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    text = (raw or "").strip()
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"ok": False, "error": "模型未返回 JSON", "raw": text[:400]}
    try:
        sc = json.loads(text[s:e + 1])
    except Exception as ex:
        return {"ok": False, "error": "JSON 解析失败: " + str(ex), "raw": text[s:e + 1][:400]}
    return {"ok": True, "script": sc, "episode": sc.get("episode"),
            "title": sc.get("title"), "scenes": len(sc.get("scenes", []))}


def agent_plan(prompt, prev_plan=None, history=None):
    """Agent 模式：自然语言需求 -> 结构化需求卡（标题/类型/角色/分镜草案）。

    支持「上下文记忆迭代」（对标 PAVO 护城河②）：带上 prev_plan 时进入**修订模式**，
    老板补一句「加个反转 / 女主换短发」只改被点名的部分，其余原样保留，
    不会把整张卡重新抽一遍（否则每次微调都换人换故事，等于不可用）。
    """
    if not prompt or not str(prompt).strip():
        return {"ok": False, "error": "请输入一句话需求"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    # 库驱动：base system 提示词来自 prompt_library.json 的 req_card 类型（可迭代），
    # 缺库时回退 REQ_CARD_SYS 常量。下面的 REVISION MODE 追加属逻辑，仍在代码里。
    sys_p = lib_prompt("req_card", default=REQ_CARD_SYS)
    # ---- 上下文记忆迭代：有旧卡就走「增量修订」，避免整卡重抽 ----
    user_msg = str(prompt)
    if isinstance(prev_plan, dict) and prev_plan.get("shots"):
        sys_p += (
            "\n\nREVISION MODE: The user already has a plan card (given below as CURRENT_PLAN). "
            "Apply ONLY the changes the user explicitly asks for. Keep every other field "
            "byte-identical to CURRENT_PLAN — same title, same character names/looks, same shot "
            "count and same untouched shots. Do NOT re-invent the story. "
            "Return the FULL updated JSON card (same schema), plus a top-level "
            '"changelog": [str] listing in Chinese what you changed.'
        )
        try:
            cur = json.dumps(prev_plan, ensure_ascii=False)
        except Exception:
            cur = "{}"
        hist = ""
        if isinstance(history, list) and history:
            # 只带最近 6 轮，够用且不撑爆上下文
            hist = "\n".join("- " + str(h)[:200] for h in history[-6:])
            hist = "\nEARLIER_REQUESTS:\n" + hist
        user_msg = f"CURRENT_PLAN:\n{cur}{hist}\n\nUSER_CHANGE_REQUEST: {prompt}"
    try:
        # 收紧重试：默认 chat() 会 max_attempts=max(8, keys*2) 次、每次 180s，
        # 网络抖动时单次可能卡 20+ 分钟 → 前端永久「引擎规划中」最终被代理掐断。
        # 需求卡是交互强实时场景，限 2 次、120s/次（~4min 封顶），超了明确报错让用户重试。
        raw = chat(user_msg, system=sys_p, temperature=0.6, max_tokens=2600,
                   timeout=120, backoff=2.0, max_attempts=2)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    text = (raw or "").strip()
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"ok": False, "error": "模型未返回 JSON", "raw": text[:400]}
    try:
        plan = json.loads(text[s:e + 1])
    except Exception as ex:
        return {"ok": False, "error": "JSON 解析失败", "raw": text[s:e + 1][:400]}
    revised = bool(isinstance(prev_plan, dict) and prev_plan.get("shots"))
    if revised:
        # 防退化：模型偶尔在修订模式下「偷懒」只回片段，缺什么就从旧卡补回来，
        # 绝不能让一次微调把老板的卡改残。
        for k in ("title", "genre", "logline", "characters", "style", "note"):
            if not plan.get(k) and prev_plan.get(k):
                plan[k] = prev_plan[k]
        if not plan.get("shots"):
            plan["shots"] = prev_plan.get("shots") or []
        if not plan.get("scenes"):
            plan["scenes"] = prev_plan.get("scenes") or []
        if not plan.get("props"):
            plan["props"] = prev_plan.get("props") or []
        plan.setdefault("changelog", ["已按要求更新（模型未回报改动明细）"])
    return {"ok": True, "plan": plan, "revised": revised}


# ===== 库驱动生成函数（提示词来自 prompt_library.json，可迭代） =====

def generate_novel_from_theme(theme):
    """主题→小说：一句话主题 → agnes-2.5-flash 扩写为完整短剧小说（库驱动）。"""
    if not theme or not str(theme).strip():
        return {"ok": False, "error": "请输入一句话主题"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    try:
        raw = chat(str(theme), system=lib_prompt("novel", default=NOVEL_SYS),
                   temperature=0.7, max_tokens=3000)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    novel = (raw or "").strip()
    if not novel:
        return {"ok": False, "error": "模型未返回小说文本"}
    return {"ok": True, "novel": novel}


def generate_style_keywords(style_text):
    """风格→英文关键词：中文风格描述 → AGNES 生成一组英文关键词（库驱动）。"""
    if not style_text or not str(style_text).strip():
        return {"ok": False, "error": "请输入风格描述"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    try:
        raw = chat(str(style_text), system=lib_prompt("style", default=STYLE_SYS),
                   temperature=0.3, max_tokens=800)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    text = (raw or "").strip()
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"ok": False, "error": "模型未返回 JSON", "raw": text[:400]}
    try:
        kw = json.loads(text[s:e + 1])
    except Exception as ex:
        return {"ok": False, "error": "JSON 解析失败: " + str(ex), "raw": text[:400]}
    return {"ok": True, "keywords": kw.get("keywords", []),
            "cn": kw.get("cn", ""), "raw": text[s:e + 1]}


def generate_outline(req_card, novel=""):
    """剧本大纲：需求卡 + 小说 → AGNES 产大纲 JSON（库驱动）。"""
    if not req_card:
        return {"ok": False, "error": "请先确认需求卡"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    user_msg = json.dumps(req_card, ensure_ascii=False, indent=2)
    if novel and str(novel).strip():
        user_msg += "\n\n附·原始小说文本：\n" + str(novel).strip()
    try:
        # 【T5 Thinking·老板 0811】大纲生成开思考模式提升结构质量
        raw = chat(user_msg, system=lib_prompt("outline", default=OUTLINE_SYS),
                   temperature=0.5, max_tokens=3000, thinking=True)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    text = (raw or "").strip()
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return {"ok": False, "error": "模型未返回 JSON", "raw": text[:400]}
    try:
        outline = json.loads(text[s:e + 1])
    except Exception as ex:
        return {"ok": False, "error": "JSON 解析失败: " + str(ex), "raw": text[:400]}
    return {"ok": True, "outline": outline}


def test_prompt_sandbox(ptype, sample_input):
    """测试沙盒：用 library 中 ptype 的 system 提示词 + sample_input 生成一份样本文本。
    快速迭代提示词：改库→跑测试→看输出，不用走全流程。"""
    if not sample_input or not str(sample_input).strip():
        return {"ok": False, "error": "请输入测试样本输入"}
    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
    from agnes_client import chat
    try:
        raw = chat(str(sample_input), system=lib_prompt(ptype, default=""),
                   temperature=0.6, max_tokens=2000)
    except Exception as e:
        return {"ok": False, "error": "AGNES 调用失败: " + str(e)}
    return {"ok": True, "output": (raw or "").strip(), "type": ptype}


def _run_agent_task(tid, prompt, prev_plan, history):
    """后台线程跑 agent_plan，写回任务状态；带服务端超时兜底，避免任务永远 running。"""
    try:
        future = AGENT_EXECUTOR.submit(agent_plan, prompt, prev_plan, history)
        res = future.result(timeout=200)   # 与 chat() 2×120s 封顶对齐，留冗余
    except concurrent.futures.TimeoutError:
        res = {"ok": False, "error": "引擎规划超时（LLM 响应过慢，请重试）"}
    except Exception as e:
        res = {"ok": False, "error": "异常: " + str(e)}
    with AGENT_TASKS_LOCK:
        t = AGENT_TASKS.get(tid)
        if t:
            t.update({
                "status": "done" if res.get("ok") else "error",
                "plan": res.get("plan"),
                "error": res.get("error"),
                "revised": res.get("revised"),
                "finished": time.time(),
            })


def reconcile_project():
    """分镜→参考图/关键帧 自动关联：补齐缺失的 references 引用（打磨 #3）。"""
    refs = SPEC.setdefault("references", {})
    n = 0
    for s in SPEC.get("shots", []):
        rk = s.get("ref")
        if rk and rk not in refs:
            refs[rk] = {"img_prompt": s.get("video_prompt", ""), "identity_token": ""}
            n += 1
    _save_spec()
    return {"ok": True, "added_refs": n}


def distribute(final_path, platforms=None):
    """P0 分发自动化：按平台规格缩放 + 烧录 AI 生成标识 + 产出变现元数据。"""
    if not final_path or not os.path.isfile(final_path):
        return {"ok": False, "error": "无成片可分发"}
    platforms = platforms or ["抖音", "快手", "视频号"]
    specs = {"抖音": {"w": 1080, "h": 1920}, "快手": {"w": 1080, "h": 1920}, "视频号": {"w": 1080, "h": 1920}}
    font = os.path.join(HERE, "simhei.ttf")
    if not os.path.isfile(font):
        src = os.path.normpath(os.path.join(HERE, "..", "simhei.ttf"))
        if os.path.isfile(src):
            shutil.copy(src, font)
    pdir = os.path.dirname(os.path.abspath(final_path))
    dist_dir = os.path.join(pdir, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    out_meta = []
    label = "本片由AI生成"
    for p in platforms:
        sp = specs.get(p, {"w": 1080, "h": 1920})
        out = os.path.join(dist_dir, p + ".mp4")
        vf = (f"scale={sp['w']}:{sp['h']}:force_original_aspect_ratio=decrease,"
              f"pad={sp['w']}:{sp['h']}:(ow-iw)/2:(oh-ih)/2,"
              f"drawtext=text='{label}':fontfile='simhei.ttf':fontcolor=white@0.85:"
              f"fontsize={int(sp['h'] * 0.028)}:x=(w-tw)/2:y=h-th-30")
        cmd = ["ffmpeg", "-y", "-i", final_path, "-vf", vf, "-c:a", "copy", out]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=600, cwd=HERE)
            ok = r.returncode == 0 and os.path.isfile(out)
            out_meta.append({"platform": p, "spec": sp, "out": out if ok else None,
                             "ok": ok, "error": None if ok else (r.stderr[-300:] if r.stderr else "ffmpeg fail")})
        except Exception as e:
            out_meta.append({"platform": p, "ok": False, "error": str(e)})
    meta = {"project": ACTIVE, "generated_at": now_iso(),
            "platforms": out_meta,
            "monetization": {"model": "IAA+IAP",
                             "note": "前3集免费最精彩；付费卡点放悬念最紧；按各平台规范挂载"},
            "compliance": "含 AI 生成标识（依《微短剧创作生产及内容审核技术规范》"}
    mpath = os.path.join(dist_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return {"ok": any(m.get("ok") for m in out_meta), "dist_dir": dist_dir,
            "manifest": mpath, "outputs": out_meta}


def _sim_storyboard():
    """模拟模式用的极小分镜（不调 AGNES，纯验证编排/进度逻辑）。"""
    pid = "ep_sim_" + datetime.now().strftime("%m%d_%H%M%S")
    pdir = os.path.join(PROJECTS_ROOT, pid)
    for sub in ("references", "audio", "video"):
        os.makedirs(os.path.join(pdir, "assets", sub), exist_ok=True)
    base = {"duration": 5, "num_frames": 121, "ui_shot": False, "video_prompt": "x",
            "subtitle": "", "voice": "narrator", "emotion": "", "last_frame_prompt": "end",
            "transition_in": "fade", "transition_out": "fade", "status": "pending",
            "asset_image": "", "asset_video": "", "asset_audio": "",
            "asset_frame_start": "", "asset_frame_end": ""}
    sb = {"episode": "SIM", "title": "模拟项目", "resolution": {"width": 1080, "height": 1920},
          "global_style": "cinematic", "voice_roles": {},
          "references": {"hero": {"img_prompt": "a young man", "identity_token": ""}},
          "shots": [{**base, "id": 1, "ref": "hero", "gen_strategy": "keyframes"},
                    {**base, "id": 2, "ref": "hero", "gen_strategy": "reference"}]}
    json.dump(sb, open(os.path.join(pdir, "storyboard.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    reg = load_registry()
    reg.append({"id": pid, "name": "模拟项目", "spec": f"{pid}/storyboard.json",
                "created": now_iso(), "last_opened": now_iso()})
    save_registry(reg)
    return pid


def run_pipeline(params):
    """一键全流程：选题→分镜→参考图→关键帧→视频→配音→合成→质检→诊断(闭环)→分发。
    后台线程执行，通过 PIPELINE_STATE 暴露进度。"""
    global SPEC, ACTIVE, ACTIVE_SERIES
    sim = bool(params.get("simulate"))
    series_id = params.get("series_id")
    ACTIVE_SERIES = series_id  # 跨集锁脸：后续 _ref_anchor 复用剧集锚点库

    def _persist():
        """模拟模式禁止写盘：sim 只验证编排，绝不能污染真实项目的资产字段。"""
        if not sim:
            _save_spec()
    skip_pre = bool(params.get("skip_pre"))
    with PIPE_LOCK:
        if PIPELINE_STATE["running"]:
            return
        PIPELINE_STATE.update({
            "running": True, "stage": "init", "stage_idx": 0, "stages_total": 0,
            "current": 0, "total": 0, "log": [], "result": None, "error": None,
            "started_at": now_iso(), "finished_at": None, "project": None,
            "simulate": sim, "stop_requested": False,
        })
    PIPELINE_STOP["flag"] = False
    stages = ["选题分析", "分镜生成", "参考图", "关键帧", "视频生成", "配音",
              "合成", "质检", "AI诊断", "分发导出"]
    with PIPE_LOCK:
        PIPELINE_STATE["stages_total"] = len(stages)
        PIPELINE_STATE["stages_cache"] = stages
    try:
        # 0 选题
        _pip_set(stage=stages[0], stage_idx=1)
        topic_seed = (params.get("topic_seed") or "").strip()
        if not skip_pre and topic_seed:
            _pip_log(f"选题分析：{topic_seed[:40]}…")
            tr = analyze_topic_real(topic_seed)
            if tr.get("ok"):
                b = tr["brief"]
                _pip_log(f"选题结论：{b.get('topic')} | 平台 {b.get('target_platform')} | 变现 {b.get('monetization')}")
            else:
                _pip_log(f"选题分析失败：{tr.get('error')}（继续）", "warn")
        # 1 分镜
        novel = (params.get("novel") or "").strip()
        _pip_set(stage=stages[1], stage_idx=2)
        if skip_pre:
            pid = params.get("project") or ACTIVE
            if not pid:
                raise RuntimeError("skip_pre 模式需指定 project")
            load_spec(pid)
            _pip_log(f"[断点续跑] 载入已有项目 {pid}，跳过 选题/分镜/参考图/关键帧")
        elif novel:
            if sim:
                pid = _sim_storyboard()
                _pip_log("[sim] 用模拟分镜（2 镜）验证编排")
            else:
                _pip_log("小说→分镜（B）生成中…")
                sb = generate_storyboard_from_novel(novel, params.get("title", ""), params.get("episode", ""),
                                                  series_id=series_id)
                if not sb.get("ok"):
                    raise RuntimeError("分镜生成失败：" + str(sb.get("error")))
                pid = sb["project_id"]
                _pip_log(f"新项目 {pid}：{sb['shots']} 镜 / {sb['references']} 参考")
            load_spec(pid)
        else:
            pid = params.get("project") or ACTIVE
            if not pid:
                raise RuntimeError("未提供 novel 也未指定 project")
            load_spec(pid)
            _pip_log(f"载入项目 {pid}：{len(SPEC.get('shots', []))} 镜")
        with PIPE_LOCK:
            PIPELINE_STATE["project"] = ACTIVE

        rec = reconcile_project()
        if rec.get("added_refs"):
            _pip_log(f"自动补全 {rec['added_refs']} 个参考图引用")

        work = list(SPEC.get("shots", []))   # 全镜（含 ui_shot 真视频镜，不再排除）
        limit = int(params.get("limit") or 0)
        if limit > 0:
            work = work[:limit]
        total = len(work)
        _pip_log(f"待生成视频镜数：{total}（含 ui_shot 真视频镜）")
        if PIPELINE_STOP["flag"]:
            raise RuntimeError("用户中止")

        # 2 参考图
        _pip_set(stage=stages[2], stage_idx=3)
        if sim:
            _pip_log("[sim] 跳过参考图 AGNES 调用")
        elif skip_pre:
            _pip_log("[断点续跑] 复用已有参考图")
        else:
            man = generate_references_real()
            for s in SPEC.get("shots", []):
                rk = s.get("ref")
                if rk and man.get(rk):
                    s["asset_image"] = man[rk]
            _persist()
            _pip_log(f"参考图完成：{sum(1 for v in man.values() if v)} 张")

        # 3 关键帧
        _pip_set(stage=stages[3], stage_idx=4, current=0, total=total)
        if sim:
            for s in work:
                pass   # [sim] 不写真实 spec 字段，避免污染已生成资产
            _persist()
            _pip_log("[sim] 跳过关键帧 AGNES 调用")
        elif skip_pre:
            _pip_log("[断点续跑] 复用已有关键帧")
        else:
            for i, s in enumerate(work):
                if PIPELINE_STOP["flag"]:
                    break
                try:
                    generate_keyframes_real(s["id"])
                except Exception as e:
                    _pip_log(f"关键帧 #{s['id']} 失败：{e}", "warn")
                _pip_set(current=i + 1)
            _pip_log("关键帧完成")

        # 4 视频
        _pip_set(stage=stages[4], stage_idx=5, current=0, total=total)
        max_retry = int(params.get("max_retry") or 1)
        for i, s in enumerate(work):
            if PIPELINE_STOP["flag"]:
                break
            sid = s["id"]
            # 断点续跑：已有成片则跳过，只补缺失镜（避免重复消耗免费额度）
            if (not sim) and s.get("asset_video") and os.path.isfile(asset_abs(s["asset_video"])):
                _pip_log(f"视频 #{sid} 已存在，跳过")
                _pip_set(current=i + 1, current_sub=s.get("subtitle", ""))
                continue
            for attempt in range(1, max_retry + 1):
                if sim:
                    r = {"ok": True, "sim": True}   # [sim] 只走编排，不写 asset_video
                else:
                    r = _gen_video_with_timeout(sid, timeout=1200)
                if r.get("ok"):
                    _pip_log(f"视频 #{sid} 完成（策略 {s.get('gen_strategy')}）")
                    break
                _pip_log(f"视频 #{sid} 第{attempt}次失败：{str(r.get('error', ''))[:120]}", "warn")
            else:
                # for…else：循环自然结束（未 break=全部重试均失败）→ 本镜确实没出片
                _pip_log(f"视频 #{sid} 连续 {max_retry} 次失败，本镜跳过（合成将缺此镜，可重跑补生成）", "error")
            _pip_set(current=i + 1, current_sub=s.get("subtitle", ""))
        _persist()
        _pip_log("视频阶段完成")

        # 5 配音（MiniMax 按老板指示后置；原生音画同步已在视频内）
        _pip_set(stage=stages[5], stage_idx=6)
        if os.environ.get("MINIMAX_API_KEY"):
            try:
                generate_audio_real()
                _pip_log("MiniMax 配音完成")
            except Exception as e:
                _pip_log(f"MiniMax 配音失败：{e}", "warn")
        else:
            _pip_log("跳过 MiniMax 配音（未配置；AGNES 原生音画同步已含音轨，按老板指示后置）", "info")

        # 6 合成
        _pip_set(stage=stages[6], stage_idx=7)
        if sim:
            final = os.path.join(PROJECTS_ROOT, ACTIVE, "final_sim.mp4")
            asm = {"ok": True, "sim": True, "final": final}
            _pip_log("[sim] 跳过合成（占位）")
        else:
            asm = do_assemble({"bgm": True})
            _pip_log("合成：" + ("成功" if asm.get("ok") else "失败 " + str(asm.get("error")))
                      + "（已混入程序化 BGM，商用前替换为授权音乐）")
        final = asm.get("final") or os.path.join(PROJECTS_ROOT, ACTIVE, "final.mp4")

        # 7 质检
        _pip_set(stage=stages[7], stage_idx=8)
        qc = None
        if sim or not os.path.isfile(final):
            _pip_log("[sim] 跳过质检")
        else:
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
                from quality_check import run_quality
                sbp = os.path.join(PROJECTS_ROOT, ACTIVE, "storyboard.json")
                qc = run_quality(final, storyboard=sbp if os.path.isfile(sbp) else None)
                t = qc.get("technical", {})
                _pip_log("质检：" + ("通过" if not t.get("tech_bad") else
                          f"问题 黑{t.get('black_count',0)}/静{t.get('silence_count',0)}/静帧{t.get('freeze_count',0)}"))
            except Exception as e:
                _pip_log(f"质检失败：{e}", "warn")

        # 8 AI诊断 + 自动修复闭环
        _pip_set(stage=stages[8], stage_idx=9)
        autofix = bool(params.get("diagnose_autofix", True))
        deep = bool(params.get("deep", False))
        diag_all = []
        rerendered = False
        if sim or not os.path.isfile(final):
            _pip_log("[sim] 跳过诊断")
        else:
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
                from diagnosis import diagnose_clip
                for i, s in enumerate(work):
                    _pip_set(current=i + 1, current_sub=(s.get("subtitle") or "")[:30])
                    if s.get("ui_shot"):
                        continue   # ui_shot 真视频镜不进多模态诊断（无人物/动作维度，避免误低分触发重渲）
                    vid = s.get("asset_video")
                    if not vid:
                        continue
                    vabs = vid if os.path.isabs(vid) else asset_abs(vid)
                    if not os.path.isfile(vabs):
                        continue
                    d = _diag_average(vabs, runs=DIAG_AGG_RUNS,
                                     face_check=params.get("face_check", True),
                                     storyboard=os.path.join(PROJECTS_ROOT, ACTIVE, "storyboard.json"),
                                     deep=deep)
                    # 写回 spec 前剥掉 raw_runs（逐次原始结果），避免污染 storyboard.json
                    s["diagnosis"] = {k: v for k, v in d.items() if k != "raw_runs"}
                    overall = d.get("overall")
                    if d.get("ok") is False or not isinstance(overall, (int, float)):
                        # 诊断失败绝不能默认满分（会让 autofix 永不触发、问题镜静默过关）
                        _pip_log(f"诊断 #{s['id']} 失败：{str(d.get('error') or d.get('summary'))[:120]}", "warn")
                        diag_all.append([s["id"], None])
                        continue
                    spread = d.get("spread")
                    _pip_log(f"诊断 #{s['id']}：均值overall={overall}（{d.get('runs')}次聚合"
                             + (f"，离散度{spread}" if spread is not None else "") + f"） verdict={d.get('verdict')}")
                    diag_all.append([s["id"], overall])
                    if autofix and overall < DIAG_PASS_THRESHOLD and not sim:
                        for attempt in range(1, max_retry + 1):
                            if PIPELINE_STOP["flag"]:
                                break
                            # 先按诊断低分维度改写 prompt，再重渲（否则只是重抽卡，实测涨不动分）
                            weak = _prompt_fix_from_diagnosis(s, s.get("diagnosis"), threshold=DIAG_PASS_THRESHOLD)
                            if weak:
                                _persist()
                                _pip_log(f"#{s['id']} 按诊断修正 prompt：{'/'.join(weak)}", "info")
                            _pip_log(f"#{s['id']} 评分{overall}<{DIAG_PASS_THRESHOLD}，自动重渲(第{attempt}次)…", "warn")
                            rr = _gen_video_with_timeout(s["id"], timeout=1200)
                            if rr.get("ok"):
                                nd = _diag_average(asset_abs(s["asset_video"]), runs=DIAG_AGG_RUNS,
                                                   face_check=params.get("face_check", True),
                                                   storyboard=os.path.join(PROJECTS_ROOT, ACTIVE, "storyboard.json"),
                                                   deep=deep)
                                s["diagnosis"] = {k: v for k, v in nd.items() if k != "raw_runs"}
                                rerendered = True
                                no = nd.get("overall")
                                _pip_log(f"#{s['id']} 重渲后均值overall={no}（{nd.get('runs')}次聚合，修正维度 {'/'.join(weak) or '无'}，"
                                         f"{'↑改善' if isinstance(no,(int,float)) and no > overall else '未改善'}）")
                                if s.get("fix_history"):
                                    s["fix_history"][-1]["after_overall"] = no
                                break
                    _persist()
            except Exception as e:
                _pip_log(f"诊断失败：{e}", "warn")

        # 8.5 重渲闭环：若诊断阶段有镜被重渲成功，重建 final 再分发（让自动修复真正端到端）
        if rerendered and os.path.isfile(final):
            _pip_log("检测到重渲镜，重建 final.mp4 以吃进重渲结果…", "info")
            try:
                asm2 = do_assemble({"bgm": True})
                if asm2.get("ok"):
                    final = asm2.get("final") or final
                    _pip_log("重渲后重建合成：成功")
                else:
                    _pip_log("重渲后重建合成失败：" + str(asm2.get("error")), "warn")
            except Exception as e:
                _pip_log(f"重渲后重建合成异常：{e}", "warn")

        # 9 分发
        _pip_set(stage=stages[9], stage_idx=10)
        dist = None
        if params.get("distribute", True) and os.path.isfile(final):
            dist = distribute(final, params.get("platforms"))
            outs = [m["platform"] for m in dist.get("outputs", []) if m.get("ok")]
            _pip_log("分发导出：" + ("完成 " + str(outs) if dist.get("ok") else "失败"))
        else:
            _pip_log("[跳过] 不分发")

        with PIPE_LOCK:
            PIPELINE_STATE["result"] = {
                "project": ACTIVE, "shots": len(work),
                "assemble_ok": bool(asm.get("ok")),
                # 与日志判定保持一致（tech_bad 缺失视为通过），此前用 `is False` 会把 None 判成不通过
                "quality_pass": (not qc.get("technical", {}).get("tech_bad")) if qc else None,
                "diagnoses": diag_all, "rerendered": rerendered,
                "distribute_ok": bool(dist and dist.get("ok")),
                "final": final if os.path.isfile(final) else None,
            }
        _pip_log("✅ 全流程完成", "ok")
        # O2 完成通知：长任务收尾提醒（本地 JSONL + 可选 webhook + 尽力桌面提示）
        try:
            sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
            from notify import notify
            res = PIPELINE_STATE.get("result") or {}
            notify("成片完成", f"项目 {ACTIVE} 全流程完成，{len(work)} 镜，"
                              f"质检{'通过' if res.get('quality_pass') else '未过'}"
                              f"{'，已重渲' if res.get('rerendered') else ''}", "ok")
        except Exception:
            pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        with PIPE_LOCK:
            PIPELINE_STATE["error"] = str(e)
        _pip_log(f"❌ 流程异常：{e}", "error")
        # O2 失败通知
        try:
            sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
            from notify import notify
            notify("流程异常", f"项目 {ACTIVE} 失败：{e}", "error")
        except Exception:
            pass
    finally:
        with PIPE_LOCK:
            PIPELINE_STATE["running"] = False
            PIPELINE_STATE["finished_at"] = now_iso()
            PIPELINE_STATE["stage"] = "done" if not PIPELINE_STATE.get("error") else "error"


def run_batch(params):
    """批量/夜间队列：顺序遍历项目列表，逐个 skip_pre 跑流水线，跑完一个再下一个。
    每个子项目复用 run_pipeline（断点续跑只补缺失镜 + 合成 + 分发），进度经 PIPELINE_STATE 暴露，
    批量自身进度经 BATCH_STATE 暴露。免费档排队靠单镜/诊断超时兜底，不会卡死整批。"""
    global SPEC, ACTIVE

    def _stopped():
        # run_pipeline 每次启动会把 PIPELINE_STOP 复位，故批量以 BATCH_STATE.stop_requested 为准
        return BATCH_STATE.get("stop_requested") or PIPELINE_STOP["flag"]

    projects = params.get("projects") or []
    if not projects:
        # 默认：PROJECTS_ROOT 下所有含 storyboard.json 的项目
        try:
            projects = sorted([d for d in os.listdir(PROJECTS_ROOT)
                               if os.path.isdir(os.path.join(PROJECTS_ROOT, d))
                               and os.path.isfile(os.path.join(PROJECTS_ROOT, d, "storyboard.json"))])
        except Exception:
            projects = []
    with BATCH_LOCK:
        BATCH_STATE.update({"running": True, "total": len(projects), "idx": 0,
                            "projects": projects, "current": None, "done": False,
                            "stop_requested": False})
    _pip_log(f"🌙 批量启动：{len(projects)} 个项目将依次断点续跑", "ok")
    for i, pid in enumerate(projects):
        if _stopped():
            _pip_log("批量：用户中止", "warn")
            break
        with BATCH_LOCK:
            BATCH_STATE["idx"] = i
            BATCH_STATE["current"] = pid
        # 等当前流水线空闲（上一个项目跑完）
        waited = 0
        while PIPELINE_STATE["running"]:
            if _stopped():
                break
            time.sleep(3); waited += 3
            if waited % 90 == 0:
                _pip_log(f"批量等待 {pid} 完成… 已 {waited}s", "info")
        if _stopped():
            break
        pp = dict(params)
        pp["project"] = pid
        pp["skip_pre"] = True          # 批量只补缺失镜，不重做参考图/关键帧
        pp["series_id"] = params.get("series_id")  # O1 跨集锁脸：批量多集共用剧集锚点
        pp["simulate"] = bool(params.get("simulate"))
        pp.pop("projects", None)
        pp.pop("topic_seed", None)
        pp.pop("novel", None)
        threading.Thread(target=run_pipeline, args=(pp,), daemon=True).start()
        # 等这个项目跑完
        waited = 0
        while PIPELINE_STATE["running"]:
            if _stopped():
                break
            time.sleep(3); waited += 3
            if waited % 120 == 0:
                _pip_log(f"批量：{pid} 运行中… 已 {waited}s", "info")
    with BATCH_LOCK:
        BATCH_STATE["done"] = True
        BATCH_STATE["running"] = False
        BATCH_STATE["stop_requested"] = bool(BATCH_STATE.get("stop_requested") or PIPELINE_STOP["flag"])
    done = not BATCH_STATE.get("stop_requested")
    _pip_log("✅ 批量全部完成" if done else "批量已中止", "ok")
    # O2 批量完成通知
    try:
        sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
        from notify import notify
        notify("批量完成" if done else "批量中止",
               f"{len(projects)} 个项目批量任务{'已完成' if done else '已中止'}", "ok" if done else "warn")
    except Exception:
        pass


def queue_executor(job):
    """把队列任务映射到 server 已有生成函数；在 BatchQueue.exec_lock 内串行执行。
    支持类型：render_shot / pipeline_project / tune_project / rebuild。
    注意：pipeline_project/tune_project 会同步跑完整个 run_pipeline（skip_pre 断点续跑），
    同一时刻生成管线只有一个（exec_lock 保证），与 /api/pipeline/run 互斥由 run_pipeline 自身守卫。"""
    jt = job.get("type")
    pl = job.get("payload") or {}
    pid = pl.get("project") or job.get("project") or ACTIVE

    if jt == "render_shot":
        sid = pl.get("id")
        if not sid:
            raise RuntimeError("render_shot 需指定 payload.id")
        if pid:
            load_spec(pid)
        r = _gen_video_with_timeout(sid, timeout=int(pl.get("timeout", 1200)))
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "render 失败")
        return {"shot": sid, "video": r.get("video")}

    if jt in ("pipeline_project", "tune_project"):
        if not pid:
            raise RuntimeError(f"{jt} 需指定 project")
        pp = dict(pl)
        pp["project"] = pid
        pp["series_id"] = pl.get("series_id")  # O1 跨集锁脸：队列任务也可带剧集
        pp["skip_pre"] = True            # 批量只补缺失镜 + 合成 + 质检 + 诊断闭环
        pp["simulate"] = bool(pl.get("simulate"))
        pp.setdefault("diagnose_autofix", True)
        pp.setdefault("distribute", True)
        pp["deep"] = bool(pl.get("deep", False))  # 深度人脸开关透传到诊断闭环
        run_pipeline(pp)                 # 在 worker 线程内同步跑完
        res = PIPELINE_STATE.get("result") or {}
        return {"project": pid, "pipeline_done": True, "rerendered": res.get("rerendered")}

    if jt == "rebuild":
        if pid:
            load_spec(pid)
            sb_series = SPEC.get("series_id")
            if sb_series:
                global ACTIVE_SERIES
                ACTIVE_SERIES = sb_series  # 恢复剧集上下文，保证锚点复用
        asm = do_assemble()
        if not asm.get("ok"):
            raise RuntimeError(asm.get("error") or "assemble 失败")
        return {"final": asm.get("final")}

    raise RuntimeError(f"未知队列任务类型: {jt}")


# ===== HTTP Handler =====

class Handler(BaseHTTPRequestHandler):

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,PUT,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self._req_t0 = time.time()
        p = urlparse(self.path)
        # 静态资源路径必须做 percent-decoding：参考图文件名是中文角色名（林小满.png），
        # 浏览器发出的是 %E6%9E%97...，不解码直接拼盘符路径 → 永远 404 →
        # 「素材库图片看不见预览」。ASCII 命名的 shot001.mp4 恰好躲过，掩盖了这个 bug。
        p = p._replace(path=unquote(p.path))
        if p.path in ("/", "/studio.html"):
            self._serve_file("studio.html", "text/html; charset=utf-8")
        elif p.path == "/api/projects":
            reg = load_registry()
            for p_ in reg:
                p_["active"] = (p_["id"] == ACTIVE)
                p_.setdefault("status", "active")  # 老项目默认 active
            self._send(200, {"active": ACTIVE, "projects": reg})
        elif p.path == "/api/logs":
            # 日志查看：仅开发模式开放（LOG_LEVEL=DEBUG/INFO）；正式发布 WARNING 时 403 关闭
            if LOG_LEVEL in ("WARNING", "ERROR", "CRITICAL"):
                self._send(403, {"ok": False, "error": "logs disabled: production mode"})
                return
            qs = parse_qs(p.query or "")
            date = (qs.get("date") or [""])[0] or "today"
            lines = int((qs.get("lines") or ["500"])[0])
            files = []
            try:
                files = sorted(fn for fn in os.listdir(LOG_DIR) if fn.startswith("server.log"))
            except Exception:
                pass
            target = "server.log"
            if date != "today":
                cand = "server.log." + date
                if cand in files:
                    target = cand
            content = ""
            fp = os.path.join(LOG_DIR, target)
            if os.path.exists(fp):
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    content = ""
            tail = "\n".join(content.splitlines()[-lines:])
            self._send(200, {"ok": True, "date": date, "file": target, "files": files,
                             "content": tail, "lines": lines})
            return
        elif p.path == "/api/generate/keyframes/status":
            # 关键帧后台任务状态查询（前端轮询）：done/failed/running/pending/unknown
            qs = parse_qs(p.query or "")
            try:
                sid = int((qs.get("shot") or ["0"])[0])
            except Exception:
                sid = 0
            st = kf_status(sid)
            self._send(200, {"ok": True, "shot_id": sid, **st})
            return
        elif p.path == "/api/generate/status":
            # 视频生成后台任务状态查询（前端轮询）：done/failed/running/pending/unknown
            qs = parse_qs(p.query or "")
            try:
                sid = int((qs.get("shot") or ["0"])[0])
            except Exception:
                sid = 0
            st = video_status(sid)
            self._send(200, {"ok": True, "shot_id": sid, **st})
            return
        elif p.path == "/api/spec":
            # 契约：前端读 d.spec / d.real / d.project。历史上这里直接回裸 SPEC，
            # 导致 studio.html 的 `if (d.spec)` 恒 false —— 分镜列表永远空、
            # real 永远 false（永远显示「草稿模式」）。同时补上 ?project= 切换支持。
            qs = parse_qs(p.query or "")
            want = (qs.get("project") or [""])[0].strip()
            if want:
                # 关键修复：只要显式指定 project，就重新载入它的 SPEC。
                # 旧逻辑用 `want != ACTIVE` 短路，导致「生成刚切到新项目、ACTIVE 已是新项目」时
                # 不重新 load，把全局仍指向旧项目的 SPEC 返回前端 → 数据不展示。
                try:
                    load_spec(want)
                except Exception as e:
                    self._send(200, {"ok": False, "error": f"载入项目失败: {e}",
                                     "project": ACTIVE, "real": REAL, "spec": SPEC})
                    return
            # 权威成片字段：只信后端磁盘真相，避免前端靠猜路径 + video @error 误判
            # （headless/无 H.264 codec 的浏览器会误触 @error 把整块成片藏掉）。
            _final_abs = os.path.join(PROJECTS_ROOT, ACTIVE, "final.mp4")
            _final_url = None
            _final_size = 0
            if os.path.isfile(_final_abs):
                _final_url = f"/projects/{ACTIVE}/final.mp4"
                try:
                    _final_size = os.path.getsize(_final_abs)
                except Exception:
                    _final_size = 0
            self._send(200, {"ok": True, "project": ACTIVE, "real": REAL, "spec": SPEC,
                             "meta": META, "final_url": _final_url, "final_size": _final_size})
        elif p.path == "/api/pipeline/progress":
            self._send(200, _pipeline_snapshot())
        elif p.path == "/api/pipeline/stream":
            self._stream_pipeline()
        elif p.path == "/api/agnes/last":
            # 【0811 排障】AGNES 最近调用原始响应（环形缓存 20 条）：出问题看现场
            try:
                sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
                from agnes_client import last_calls
                self._send(200, {"ok": True, "calls": last_calls(20)})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})
        elif p.path == "/api/key-pool":
            # P2：密钥池状态（读类端点统一用 GET；POST 亦支持）
            try:
                sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
                from agnes_client import key_pool_status
                self._send(200, {"ok": True, **key_pool_status()})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})
        elif p.path == "/api/agent":
            # 需求卡异步任务状态轮询（POST 提交后由前端定时查询）
            qs = parse_qs(p.query or "")
            tid = (qs.get("task_id") or [""])[0].strip()
            with AGENT_TASKS_LOCK:
                t = dict(AGENT_TASKS.get(tid, {}))
            if not t:
                self._send(404, {"ok": False, "error": "任务不存在或已过期"})
                return
            elapsed = (t.get("finished") or time.time()) - t.get("started", time.time())
            self._send(200, {"ok": True, "status": t.get("status"), "plan": t.get("plan"),
                             "error": t.get("error"), "revised": t.get("revised"),
                             "elapsed": round(elapsed, 1)})
        elif p.path == "/api/prompt/library":
            # 设置·提示词库：读取按类型提示词模板 + 可配置优化元提示（中文）
            try:
                self._send(200, {"ok": True, "library": load_prompt_library(),
                                 "labels": PROMPT_TYPE_LABELS})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})
        elif p.path == "/api/export":
            # Gap C：导出。默认回 final.mp4（没有先合成）；?zip=1 打包整个项目目录为 ZIP。
            import io, zipfile
            qs = parse_qs(p.query or "")
            want_zip = (qs.get("zip") or ["0"])[0] == "1"
            proj_dir = os.path.join(PROJECTS_ROOT, ACTIVE)
            final = os.path.join(proj_dir, "final.mp4")
            if want_zip:
                if not os.path.isdir(proj_dir):
                    self._send(404, {"ok": False, "error": "项目目录不存在"})
                    return
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for root, _, files in os.walk(proj_dir):
                        for f in files:
                            fp = os.path.join(root, f)
                            z.write(fp, os.path.relpath(fp, proj_dir))
                data = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition",
                                 'attachment; filename="%s_project.zip"' % ACTIVE)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            # 单文件成片：没有先合成
            if not os.path.isfile(final):
                try:
                    do_assemble({"transition": "none", "subtitle": True,
                                 "ai_watermark": True, "bgm": True})
                except Exception as e:
                    self._send(500, {"ok": False, "error": "合成失败: " + str(e)})
                    return
            if os.path.isfile(final):
                with open(final, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition",
                                 'attachment; filename="%s_final.mp4"' % ACTIVE)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send(500, {"ok": False, "error": "成片不存在且合成失败"})
        elif p.path.startswith("/assets/"):
            # 旧式相对路径：依赖后端「当前激活项目」隐式状态，仅作兼容保留。
            rel = p.path[len("/assets/"):].replace("..", "")
            self._serve_file(os.path.join("assets", *[s for s in rel.split("/") if s]), None)
        elif p.path.startswith("/projects/"):
            # 托管项目级文件（成片 /projects/<id>/final.mp4、参考图、分镜视频）。
            # 前端统一走这条显式路径，避免多标签页切项目时素材串到别的项目。
            rel = p.path[len("/projects/"):].replace("..", "")
            path = os.path.join(PROJECTS_ROOT, *[seg for seg in rel.split("/") if seg])
            if not os.path.isfile(path):
                self._send(404, {"error": f"{rel} missing"})
                return
            ctype, _ = mimetypes.guess_type(path)
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            # 资产文件内容不可变（重渲会换文件名/项目），给足缓存，手机端不必反复拉视频。
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif p.path.startswith("/vendor/"):
            rel = p.path[len("/vendor/"):].replace("..", "")
            self._serve_file(os.path.join("vendor", *[seg for seg in rel.split("/") if seg]), None)
        elif p.path.startswith("/api/queue/"):
            # O3：GET 也支持查看队列列表（方便浏览器直接访问和调试）
            if BATCH_QUEUE is None:
                self._send(500, {"ok": False, "error": "队列调度器未加载"})
                return
            from datetime import datetime
            jobs = BATCH_QUEUE.list(status=None)
            with PIPE_LOCK:
                ps = dict(PIPELINE_STATE)
            now = time.time()
            for j in jobs:
                if j.get("status") == "running":
                    st = ps.get("stage_idx") or 0
                    tot = ps.get("stages_total") or 0
                    j["progress"] = int(round(100 * st / tot)) if tot else 0
                    sa = j.get("started_at")
                    if sa:
                        try: j["elapsed_sec"] = int((now - datetime.fromisoformat(sa)).total_seconds())
                        except Exception: pass
                elif j.get("status") == "done":
                    j["progress"] = 100
            self._send(200, {"ok": True, "jobs": jobs, "paused": QUEUE_WORKER_STOP["flag"]})
        else:
            self._send(404, {"error": "not found"})

    def do_PUT(self):
        self._req_t0 = time.time()
        p = urlparse(self.path)
        if p.path == "/api/spec":
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            try:
                data = json.loads(body.decode("utf-8"))
                global SPEC
                reg = load_registry()
                entry = next((p_ for p_ in reg if p_["id"] == ACTIVE), None)
                sb_path = os.path.join(PROJECTS_ROOT, entry["spec"]) if entry else None

                # ===== 防数据丢失三道闸 =====
                # 惨痛教训：这里原来是无脑 `SPEC = data` + 直接覆盖写盘，零校验零备份。
                # 前端在「项目切换竞态 / 加载失败」时会把一个空壳 spec（0 镜）PUT 上来，
                # 于是一整集辛苦生成的分镜元数据被瞬间抹平，且不可恢复（已真实发生过一次）。
                incoming_shots = len(data.get("shots") or []) if isinstance(data, dict) else -1
                if not isinstance(data, dict) or incoming_shots < 0:
                    self._send(400, {"ok": False, "error": "spec 必须是对象"})
                    return
                # 闸一：跨项目写入拦截——body 里带的 project 与当前活跃项目不符，一律拒绝
                body_pid = (data.get("project") or data.get("project_id") or "").strip()
                if body_pid and ACTIVE and body_pid != ACTIVE:
                    self._send(409, {"ok": False, "error": f"拒绝跨项目写入：body.project={body_pid} ≠ 活跃项目={ACTIVE}"})
                    return
                # 闸二：清零式覆盖拦截——盘上有分镜、来的却是 0 镜，判定为空壳误写
                disk_shots = 0
                if sb_path and os.path.isfile(sb_path):
                    try:
                        disk_shots = len(json.load(open(sb_path, encoding="utf-8")).get("shots") or [])
                    except Exception:
                        disk_shots = 0
                if incoming_shots == 0 and disk_shots > 0 and not data.get("force_overwrite"):
                    self._send(409, {"ok": False, "refused": True,
                                     "error": f"拒绝清空分镜：磁盘已有 {disk_shots} 镜，收到 0 镜。"
                                              f"疑似前端空壳误写；确需清空请带 force_overwrite=true"})
                    return
                # 闸三：滚动备份——任何覆盖前先留一份上一版，纵使写坏也能一键回滚
                if sb_path and os.path.isfile(sb_path) and disk_shots > 0:
                    try:
                        import shutil as _sh
                        _sh.copyfile(sb_path, sb_path.replace(".json", ".bak.json"))
                    except Exception as e:
                        print(f"[WARN] storyboard 备份失败: {e}")

                SPEC = data
                if sb_path:
                    try:
                        with open(sb_path, "w", encoding="utf-8") as f:
                            json.dump(SPEC, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        self._send(500, {"ok": False, "error": str(e)})
                        return
                self._send(200, {"ok": True, "shots": len(SPEC.get("shots", [])), "project": ACTIVE})
            except Exception as e:
                self._send(400, {"ok": False, "error": str(e)})
        elif p.path == "/api/prompt/library":
            # 设置·提示词库：保存人工编辑后的提示词模板 + 优化元提示
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            try:
                data = json.loads(body.decode("utf-8"))
                lib = save_prompt_library(data)
                self._send(200, {"ok": True, "library": lib})
            except Exception as e:
                self._send(400, {"ok": False, "error": str(e)})
        elif p.path == "/api/meta":
            # 保存项目元数据（source_mode/source_text/novel/visual_style/outline）
            # 额外支持 project_name：自动重命名项目（用于首次确认需求卡时从标题取名）
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            try:
                data = json.loads(body.decode("utf-8"))
                # 项目改名
                if data.get("project_name") and ACTIVE:
                    reg = load_registry()
                    for p_ in reg:
                        if p_["id"] == ACTIVE:
                            p_["name"] = data["project_name"]
                            save_registry(reg)
                            break
                    data.pop("project_name", None)  # 不写进 meta.json
                _save_meta(data)
                self._send(200, {"ok": True, "meta": META})
            except Exception as e:
                self._send(400, {"ok": False, "error": str(e)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        self._req_t0 = time.time()
        p = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}
        if p.path == "/api/log":
            # 前端错误/调试上报：{level: error|warn|info|debug, msg, url} → 写入服务端日志
            lvl = str(data.get("level") or "info").lower()
            if lvl not in ("debug", "info", "warn", "warning", "error"):
                lvl = "info"
            msg = str(data.get("msg") or "")[:2000]
            url = str(data.get("url") or "")[:300]
            _log.log(getattr(logging, lvl.upper(), logging.INFO),
                     "[frontend:%s] %s @%s", lvl, msg, url)
            self._send(200, {"ok": True})
            return

        if p.path == "/api/generate/shot":
            shot_id = data.get("id")
            shot = find_shot(shot_id)
            if not shot:
                self._send(404, {"ok": False, "error": f"shot {shot_id} not found"})
                return
            # 上下文记忆迭代：前端回传的字段合并（不含已生成资产），重渲即承接最新修改。
            if data.get("shot"):
                for k, v in data["shot"].items():
                    if k not in ("asset_video", "asset_image", "status", "engine"):
                        shot[k] = v
            if REAL:
                # 【老板 0810】视频生成改后台任务：立即返回 accepted（同步长请求经 CF 必 524），
                # 前端轮询 /api/generate/status 明确等待/失败。参考图补全在后台任务内做。
                try:
                    video_submit(shot_id, force=bool(data.get("force")), payload=data.get("shot"))
                    self._send(200, {"ok": True, "accepted": True, "shot_id": shot_id})
                except Exception as e:
                    self._send(500, {"ok": False, "shot_id": shot_id, "error": str(e)})
            else:
                # dry-run：仅模拟，不写假资产 URL（否则 stage 会去加载不存在的视频，反而盖掉真实参考图）。
                # 保留真实参考图作为画面，状态标「待渲染」；昂贵的视频渲染留到 REAL=1 才真正发起。
                payload = build_agnes_payload(shot)
                shot["status"] = "ready"
                self._send(200, {"ok": True, "dry_run": True, "shot_id": shot_id, "payload": payload,
                                 "note": "dry-run：保留真实参考图，未发起昂贵视频渲染；REAL=1 才真出视频"})

        elif p.path == "/api/asset/prompt":
            # 资产设计·中文结构化 → 英文 img_prompt（库驱动 reference/scene/prop 类型，可迭代）
            atype = data.get("type")
            cn = data.get("cn_prompt") or {}
            if atype not in ("role", "scene", "prop"):
                self._send(400, {"ok": False, "error": "type 必须是 role/scene/prop"})
                return
            cn_text = _cn_prompt_to_text(atype, cn)
            if not cn_text.strip():
                self._send(400, {"ok": False, "error": "cn_prompt 所有字段为空，请先填写中文描述"})
                return
            lib_key = CN_ASSET_LIB_KEY[atype]
            sys_p = lib_prompt(lib_key)
            if not sys_p:
                self._send(500, {"ok": False, "error": f"提示词库缺 {lib_key} 类型（设置·提示词库检查）"})
                return
            try:
                if not REAL:
                    # dry-run：不烧 token，返回占位提示词让前端链路可走通
                    self._send(200, {"ok": True, "img_prompt": "(dry-run) " + cn_text[:120],
                                     "type": atype, "cn_text": cn_text, "dry_run": True})
                    return
                sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
                from agnes_client import chat
                out = chat(cn_text, system=sys_p, temperature=0.4, max_tokens=2000) or ""
                out = out.strip()
                # 清理模型 markdown 装饰：优先提取 ``` 代码块内容，否则去掉开头 **标题** 行
                if "```" in out:
                    import re as _re
                    blocks = _re.findall(r"```(?:[a-zA-Z0-9_-]*)?\s*\n?(.*?)```", out, _re.S)
                    if blocks:
                        out = blocks[-1].strip()
                    else:
                        out = out.replace("```", "").strip()
                elif out.startswith("**"):
                    lines = [l for l in out.split("\n") if not l.strip().startswith("**")]
                    out = "\n".join(lines).strip()
                self._send(200, {"ok": True, "img_prompt": out, "type": atype, "cn_text": cn_text})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/asset/extract":
            # 资产设计·反向提取：英文 img_prompt → 中文结构化 cn_prompt（库驱动，可迭代）
            # 用途：从大纲进入资产设计时，分镜里只有英文提示词 → 自动生成中文描述供用户编辑/确认。
            atype = data.get("type")
            en = (data.get("img_prompt") or "").strip()
            if atype not in ("role", "scene", "prop"):
                self._send(400, {"ok": False, "error": "type 必须是 role/scene/prop"})
                return
            if not en:
                self._send(400, {"ok": False, "error": "img_prompt 为空，无法提取"})
                return
            sys_p = lib_prompt("extract")
            if not sys_p:
                # 库缺 extract 类型时回退默认提取提示词（不阻断主流程）
                sys_p = ("你是一位中文影视资产描述整理师。用户给你一段英文图像生成提示词，"
                         "请把它拆解回中文结构化描述，严格按字段输出，不要解释、不要代码块。")
            try:
                if not REAL:
                    # dry-run：不烧 token，返回字段为空的占位结构
                    self._send(200, {"ok": True, "cn_prompt": {f: "" for f, _ in CN_FIELD_LABELS[atype]},
                                     "type": atype, "dry_run": True})
                    return
                sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
                from agnes_client import chat
                prompt = (
                    f"字段模板（{atype}，只填这些字段，缺失的填空字符串）：\n"
                    + "\n".join(f"- {k}（{label}）" for k, label in CN_FIELD_LABELS[atype])
                    + "\n\n请按 JSON 对象输出这些字段，值用中文。英文提示词如下：\n" + en
                )
                out = chat(prompt, system=sys_p, temperature=0.3, max_tokens=1500) or ""
                out = out.strip()
                if "```" in out:
                    import re as _re
                    blocks = _re.findall(r"```(?:[a-zA-Z0-9_-]*)?\s*\n?(.*?)```", out, _re.S)
                    if blocks:
                        out = blocks[-1].strip()
                    else:
                        out = out.replace("```", "").strip()
                import json as _json
                try:
                    cn = _json.loads(out)
                except Exception:
                    # 不是合法 JSON 时退化为按行解析 key：value
                    cn = {}
                    for ln in out.split("\n"):
                        if ":" in ln:
                            k, _, v = ln.partition(":")
                            k = k.strip().strip('"').strip("'").strip("-").strip(" ")
                            v = v.strip().strip('"').strip("'")
                            if k in dict(CN_FIELD_LABELS[atype]):
                                cn[k] = v
                # 归一化：只保留模板字段，缺失补空
                norm = {}
                for k, _ in CN_FIELD_LABELS[atype]:
                    v = cn.get(k)
                    norm[k] = str(v).strip() if v else ""
                self._send(200, {"ok": True, "cn_prompt": norm, "type": atype})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/generate/references":
            if REAL:
                try:
                    manifest = generate_references_real()
                    # 写回 spec 的 asset_image
                    for s in SPEC.get("shots", []):
                        if manifest.get(s.get("ref")):
                            s["asset_image"] = manifest[s["ref"]]
                    self._send(200, {"ok": True, "manifest": manifest})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出参考图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/generate/reference":
            # 单角色参考图重生成：先保存前端编辑过的 img_prompt，再只出这一张（人物资产②可改提示词重生成）。
            if REAL:
                try:
                    key = data.get("ref_key")
                    prompt = data.get("prompt")
                    if not key:
                        self._send(400, {"ok": False, "error": "ref_key required"})
                        return
                    ref = SPEC.get("references", {}).get(key)
                    if not isinstance(ref, dict):
                        self._send(400, {"ok": False, "error": "unknown ref_key: " + str(key)})
                        return
                    if prompt:
                        ref["img_prompt"] = prompt
                    if not ref.get("identity_token"):
                        ref["identity_token"] = _build_identity_token(ref.get("cn") or ref.get("img_prompt"))
                    sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
                    from agnes_client import generate_image
                    url = None
                    for size in ("768x1344", "1024x1024"):
                        try:
                            url = generate_image(ref["img_prompt"], size=size)
                            break
                        except Exception:
                            url = None
                    if not url:
                        self._send(500, {"ok": False, "error": "AGNES 出图失败"})
                        return
                    fn = os.path.join(asset_abs("assets/references"), f"{key}.png")
                    local = f"assets/references/{key}.png" if fetch_image(url, fn) else url
                    ref["remote_url"] = url
                    # 写回所有引用该角色的镜头 asset_image（首帧来源），保证视频复用同一张锁脸锚点
                    for s in SPEC.get("shots", []):
                        if s.get("ref") == key and not s.get("asset_image"):
                            s["asset_image"] = local
                    _save_spec()
                    self._send(200, {"ok": True, "ref_key": key, "url": url, "local": local})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/generate/scenes":
            # Gap B：批量出全部场景图
            if REAL:
                try:
                    m = _gen_image_assets_real(SPEC.get("scenes", []), "scenes")
                    self._send(200, {"ok": True, "manifest": m})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出场景图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/generate/scene":
            # 单场景重生成：先保存编辑过的 img_prompt，再只出这一张
            if REAL:
                try:
                    key = data.get("scene_key")
                    prompt = data.get("prompt")
                    item = next((x for x in SPEC.get("scenes", [])
                                 if (x.get("key") or x.get("name")) == key), None)
                    if not item:
                        self._send(400, {"ok": False, "error": "unknown scene_key: " + str(key)})
                        return
                    if prompt:
                        item["img_prompt"] = prompt
                    m = _gen_image_assets_real([item], "scenes")
                    if not m or all(v is None for v in m.values()):
                        self._send(200, {"ok": False, "error": "AGNES 拒绝该场景提示词（可能含文字/标识触发内容策略），请修改中文描述或英文提示词",
                                         "manifest": m, "hint": "场景提示词避免请求画面内文字/标语/招牌"})
                    else:
                        self._send(200, {"ok": True, "manifest": m})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出场景图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/generate/props":
            # Gap B：批量出全部道具图
            if REAL:
                try:
                    m = _gen_image_assets_real(SPEC.get("props", []), "props")
                    self._send(200, {"ok": True, "manifest": m})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出道具图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/generate/prop":
            # 单道具重生成
            if REAL:
                try:
                    key = data.get("prop_key")
                    prompt = data.get("prompt")
                    item = next((x for x in SPEC.get("props", [])
                                 if (x.get("key") or x.get("name")) == key), None)
                    if not item:
                        self._send(400, {"ok": False, "error": "unknown prop_key: " + str(key)})
                        return
                    if prompt:
                        item["img_prompt"] = prompt
                    m = _gen_image_assets_real([item], "props")
                    if not m or all(v is None for v in m.values()):
                        self._send(200, {"ok": False, "error": "AGNES 拒绝该道具提示词（可能含文字触发内容策略），请修改中文描述或英文提示词",
                                         "manifest": m})
                    else:
                        self._send(200, {"ok": True, "manifest": m})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出道具图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/shot/rework":
            # Gap D：单镜自然语言返工（PAVO 护城河：单镜局部改，不动全项目）。
            # 记录返工要求 + 增强视频提示词，置 ready；REAL=1 时直接重渲该镜。
            sid = data.get("id")
            instr = (data.get("instruction") or "").strip()
            sh = find_shot(sid)
            if not sh:
                self._send(404, {"ok": False, "error": "shot not found: " + str(sid)})
                return
            if not instr:
                self._send(400, {"ok": False, "error": "请填写返工要求"})
                return
            sh["rework_note"] = instr
            base = sh.get("video_prompt") or sh.get("action") or ""
            sh["video_prompt"] = (base + " | 返工要求：" + instr).strip()
            sh["status"] = "ready"
            _save_spec()
            # no_render：只登记返工要求 + 增强提示词，不立刻重渲。
            # 真实模式下重渲单镜要 5~20 分钟且同步阻塞，用户想「先把好几镜的返工意见一次性填完，
            # 晚上再挂批量流水线统一重渲」时，这个开关必不可少；回归测试也靠它秒验状态机。
            if data.get("no_render"):
                self._send(200, {"ok": True, "reworked": True, "regenerated": False,
                                 "status": sh["status"],
                                 "note": "已登记返工要求并置为待渲染；未立即重渲（no_render）"})
                return
            if REAL:
                try:
                    r = _gen_video_with_timeout(sid, timeout=1200)
                    sh["status"] = "done" if (r and r.get("ok")) else "failed"
                    _save_spec()
                    self._send(200, {"ok": True, "reworked": True, "regenerated": True, "status": sh["status"]})
                except Exception as e:
                    sh["status"] = "failed"
                    _save_spec()
                    self._send(200, {"ok": True, "reworked": True, "regenerated": False, "error": str(e)})
            else:
                self._send(200, {"ok": True, "reworked": True, "regenerated": False,
                                 "note": "dry-run：已记录返工要求并增强提示词；生成视频需 REAL=1"})

        elif p.path == "/api/generate/audio":
            if REAL:
                self._send(200, generate_audio_real())
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 + MINIMAX_API_KEY 才真配音（dry-run 不花 MiniMax 额度）"})

        elif p.path == "/api/generate/audio/shot":
            if REAL:
                self._send(200, generate_single_audio(data.get("id")))
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 + MINIMAX_API_KEY 才真配音"})

        elif p.path == "/api/prompt/optimize":
            # 提示词优化：用可配置优化元提示 + agnes-2.5-flash 优化任意提示词。
            # 文本调用不依赖 REAL（仅图像/视频消耗额度），但需 AGNES_API_KEY 在线。
            text = (data.get("text") or "").strip()
            ptype = data.get("type") or None
            if not text:
                self._send(400, {"ok": False, "error": "text 不能为空"})
                return
            try:
                optimized = optimize_prompt_text(text, ptype)
                self._send(200, {"ok": True, "text": text, "optimized": optimized, "type": ptype})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/generate/keyframes":
            if REAL:
                try:
                    self._send(200, generate_keyframes_all())
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                self._send(200, {"ok": False, "note": "需 REAL=1 才真出关键帧图；当前 dry-run 不调用 AGNES"})

        elif p.path == "/api/generate/keyframes/shot":
            if REAL:
                try:
                    sid = data.get("id")
                    if sid is None:
                        self._send(400, {"ok": False, "error": "id 必填"})
                        return
                    # 【老板 0810】改后台任务：立即返回 accepted，前端轮询 status 明确等待/失败
                    kf_submit(sid, force=bool(data.get("force")))
                    self._send(200, {"ok": True, "accepted": True, "shot_id": sid})
                except Exception as e:
                    self._send(500, {"ok": False, "error": str(e)})
            else:
                shot = find_shot(data.get("id"))
                payload = build_agnes_payload(shot) if shot else {}
                self._send(200, {"ok": True, "dry_run": True, "shot_id": data.get("id"),
                                 "payload": payload,
                                 "note": "dry-run：预览首尾针 payload，REAL=1 才真出尾帧图"})

        elif p.path == "/api/generate/storyboard":
            try:
                res = generate_storyboard_from_novel(data.get("novel", ""),
                                                     data.get("title", ""), data.get("episode", ""),
                                                     script_json=data.get("script"),
                                                     series_id=data.get("series_id"),
                                                     req=data.get("req"),
                                                     project_id=data.get("project_id"))
                # 生成落的是「当前激活项目」（新建项目后在其内生成）或新项目，都必须把它置为激活
                # 并把它的 storyboard.json 载入全局 SPEC，否则 /api/spec 返回的是上一次项目的旧 SPEC
                # → 前端看到的是旧数据/空数据（这就是「编写分镜失败、数据不展示」的根因）。
                if res.get("ok") and res.get("project_id"):
                    global ACTIVE
                    ACTIVE = res["project_id"]
                    load_spec(ACTIVE)   # 关键修复：把目标项目载入全局 SPEC
                    _persist_active(ACTIVE)
                self._send(200, res)
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/project/new":
            # 新建一个空白（已初始化）项目：建目录+空 storyboard+注册+激活+载入 SPEC。
            # 这是「新建初始化项目」按钮的后端支撑——让用户在干净项目上从①开始，不会被旧项目数据干扰。
            try:
                pid = "ep_" + datetime.now().strftime("%m%d_%H%M%S")
                pdir = os.path.join(PROJECTS_ROOT, pid)
                for sub in ("references", "scenes", "audio", "video"):
                    os.makedirs(os.path.join(pdir, "assets", sub), exist_ok=True)
                sb = {"episode": pid, "title": "未命名项目", "frame_rate": 24,
                      "references": {}, "scenes": [], "props": [], "shots": []}
                with open(os.path.join(pdir, "storyboard.json"), "w", encoding="utf-8") as f:
                    json.dump(sb, f, ensure_ascii=False, indent=2)
                reg = load_registry()
                reg.append({"id": pid, "name": "未命名项目",
                            "spec": f"{pid}/storyboard.json", "created": now_iso(), "last_opened": now_iso()})
                save_registry(reg)
                load_spec(pid)        # 载入全局 SPEC 并把 ACTIVE 置为该新项目
                _persist_active(pid)
                self._send(200, {"ok": True, "project_id": pid})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/generate/topic":
            try:
                self._send(200, analyze_topic_real(data.get("seed", "")))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/generate/script":
            try:
                self._send(200, generate_script_real(data.get("brief") or data.get("seed") or "",
                                                     int(data.get("episode", 1) or 1)))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/agent":
            # 改为异步任务：立即返回 task_id，前端轮询 /api/agent?task_id= 拿结果。
            # 这样 LLM 慢/抖动时前端能实时显示进度，且代理 900s 超时不再影响（POST 秒回）。
            prompt = (data.get("prompt") or "").strip()
            if not prompt:
                self._send(200, {"ok": False, "error": "请输入一句话需求"})
                return
            tid = uuid.uuid4().hex
            with AGENT_TASKS_LOCK:
                AGENT_TASKS[tid] = {"status": "running", "plan": None, "error": None,
                                    "revised": False, "started": time.time(), "finished": None}
                # 防止长会话无限增长：保留最近 100 个已完成任务
                if len(AGENT_TASKS) > 120:
                    old = [k for k, v in AGENT_TASKS.items()
                           if v.get("finished") and k != tid]
                    for k in sorted(old, key=lambda k: AGENT_TASKS[k]["finished"])[:len(AGENT_TASKS) - 100]:
                        AGENT_TASKS.pop(k, None)
            threading.Thread(target=_run_agent_task,
                             args=(tid, prompt, data.get("prev_plan"), data.get("history")),
                             daemon=True).start()
            self._send(200, {"ok": True, "task_id": tid, "status": "running"})

        elif p.path == "/api/project/reconcile":
            try:
                self._send(200, reconcile_project())
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/pipeline/run":
            # 一键全流程：后台线程跑，前端轮询 /api/pipeline/progress
            with PIPE_LOCK:
                if PIPELINE_STATE["running"]:
                    self._send(200, {"ok": False, "running": True, "note": "已有流程在跑，请先停止"})
                    return
            threading.Thread(target=run_pipeline, args=(data,), daemon=True).start()
            self._send(200, {"ok": True, "started": True,
                             "note": "流水线已在后台启动，轮询 /api/pipeline/progress 查看进度"})

        elif p.path == "/api/pipeline/stop":
            PIPELINE_STOP["flag"] = True
            with BATCH_LOCK:
                BATCH_STATE["stop_requested"] = True   # 批量也要停：子流水线会重置 PIPELINE_STOP
            self._send(200, {"ok": True, "note": "已请求中止（当前阶段完成后停止）"})

        elif p.path == "/api/pipeline/batch":
            # 批量/夜间队列：顺序跑多个项目（默认全部），前端轮询 /api/pipeline/progress
            with BATCH_LOCK:
                if BATCH_STATE["running"]:
                    self._send(200, {"ok": False, "running": True, "note": "批量已在跑，请先停止"})
                    return
            data.setdefault("skip_pre", True)
            threading.Thread(target=run_batch, args=(data,), daemon=True).start()
            self._send(200, {"ok": True, "started": True,
                             "note": "批量流水线已启动，轮询 /api/pipeline/progress 查看进度"})

        elif p.path == "/api/project/switch":
            pid = data.get("id")
            reg = load_registry()
            if not any(p_["id"] == pid for p_ in reg):
                self._send(404, {"ok": False, "error": f"project {pid} not found"})
                return
            load_spec(pid)
            self._send(200, {"ok": True, "active": ACTIVE, "spec": SPEC})

        elif p.path == "/api/project/archive":
            # 归档：仅改状态标记（active→archived），数据零改动，可随时恢复
            pid = data.get("id")
            reg = load_registry()
            hit = next((p_ for p_ in reg if p_["id"] == pid), None)
            if not hit:
                self._send(404, {"ok": False, "error": f"project {pid} not found"})
                return
            hit["status"] = "archived"
            save_registry(reg)
            self._send(200, {"ok": True, "id": pid, "status": "archived"})

        elif p.path == "/api/project/restore":
            # 恢复归档：archived→active，数据原样保留
            pid = data.get("id")
            reg = load_registry()
            hit = next((p_ for p_ in reg if p_["id"] == pid), None)
            if not hit:
                self._send(404, {"ok": False, "error": f"project {pid} not found"})
                return
            hit["status"] = "active"
            save_registry(reg)
            self._send(200, {"ok": True, "id": pid, "status": "active"})

        elif p.path == "/api/project/delete":
            # 删除归档项目（安全闸：仅允许删 archived，活跃项目不可删；前端已二次确认）
            # 注意：do_POST 内 /api/generate/storyboard 已声明 global ACTIVE（方法级生效），此处不再重复声明
            pid = data.get("id")
            reg = load_registry()
            hit = next((p_ for p_ in reg if p_["id"] == pid), None)
            if not hit:
                self._send(404, {"ok": False, "error": f"project {pid} not found"})
                return
            if (hit.get("status") or "active") != "archived":
                self._send(409, {"ok": False, "error": "仅允许删除已归档项目（先归档再删除）"})
                return
            import shutil
            pdir = os.path.join(PROJECTS_ROOT, pid)
            if os.path.isdir(pdir):
                shutil.rmtree(pdir, ignore_errors=True)
            reg = [p_ for p_ in reg if p_["id"] != pid]
            save_registry(reg)
            # 若删的是激活项目，切换回剩余第一个
            if ACTIVE == pid:
                if reg:
                    load_spec(reg[0]["id"])
                else:
                    ACTIVE = None
                    _persist_active("")
            self._send(200, {"ok": True, "id": pid, "deleted": True,
                             "note": "归档项目已彻底删除（数据不可恢复）"})

        elif p.path == "/api/assemble":
            self._send(200, do_assemble())

        elif p.path == "/api/finalize":
            # 成片精修：转场 + BGM + 字幕 + AI标识（本地 ffmpeg，不花 token）
            try:
                self._send(200, do_assemble({
                    "transition": data.get("transition", "none"),
                    "subtitle": data.get("subtitle", True),
                    "ai_watermark": data.get("ai_watermark", True),
                    "bgm": data.get("bgm", True),
                }))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/quality":
            # 去 stub：真调 quality_check.run_quality（黑场/静音/静帧/编码/内容结构，纯本地 ffmpeg）
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
                from quality_check import run_quality
                vid = data.get("video")
                sid = data.get("id")
                if sid:
                    shot = find_shot(sid)
                    vid = shot.get("asset_video") if shot else vid
                video_abs = None
                if vid:
                    video_abs = vid if os.path.isabs(vid) else asset_abs(vid)
                else:
                    # 优先项目根 final.mp4（assemble.py 的成片落点），其次 assets/video 下任一片段
                    cand = os.path.join(PROJECTS_ROOT, ACTIVE, "final.mp4")
                    if not os.path.isfile(cand):
                        cand = asset_abs("assets/video/final.mp4")
                    if not os.path.isfile(cand):
                        vdir = asset_abs("assets/video")
                        if os.path.isdir(vdir):
                            for fn in sorted(os.listdir(vdir)):
                                if fn.endswith(".mp4"):
                                    cand = os.path.join(vdir, fn)
                                    break
                    video_abs = cand if os.path.isfile(cand) else None
                if not video_abs:
                    self._send(200, {"ok": False, "note": "无可用视频资产；先生成/合成成片再质检"})
                    return
                sb_path = os.path.join(PROJECTS_ROOT, ACTIVE, "storyboard.json")
                report = run_quality(video_abs, storyboard=sb_path if os.path.isfile(sb_path) else None)
                self._send(200, {"ok": True, "dry_run": False, "video": os.path.basename(video_abs), "report": report})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/diagnose":
            # AGNES 多模态语义诊断（替代 MiniMax）：抽帧->agnes-2.0-flash->4维评分->写回 shot.diagnosis
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
                from diagnosis import diagnose_clip
                vid = data.get("video")
                sid = data.get("id")
                if sid:
                    shot = find_shot(sid)
                    if shot is None:
                        self._send(404, {"ok": False, "error": f"shot {sid} not found"})
                        return
                    vid = shot.get("asset_video") or vid
                if not vid:
                    # 兜底：诊断整集成片
                    fin = os.path.join(PROJECTS_ROOT, ACTIVE, "final.mp4")
                    if os.path.isfile(fin):
                        vid = fin
                    else:
                        self._send(200, {"ok": False, "note": "该镜/项目尚无视频资产，先生成视频"})
                        return
                video_abs = vid if os.path.isabs(vid) else asset_abs(vid)
                if not os.path.isfile(video_abs):
                    self._send(200, {"ok": False, "note": f"视频不存在: {vid}"})
                    return
                runs = int(data.get("runs", 1))
                fc = data.get("face_check", True)
                dp = bool(data.get("deep", False))
                sb_for_face = os.path.join(PROJECTS_ROOT, ACTIVE, "storyboard.json")
                if runs > 1:
                    # 诊断方差治理：手动诊断也支持多次聚合取均值
                    res = _diag_average(video_abs, runs=runs, face_check=fc, storyboard=sb_for_face, deep=dp)
                    res.pop("raw_runs", None)
                else:
                    res = diagnose_clip(video_abs, n_frames=int(data.get("frames", 4)),
                                        face_check=fc, storyboard=sb_for_face, deep=dp)
                if res.get("ok") and sid and shot is not None:
                    shot["diagnosis"] = res  # 写回 SceneSpec.diagnosis
                    # 【0811 修复】必须落盘！否则只写内存，前端 refreshSpec() 重载磁盘即丢（"诊断结果马上消失"）
                    try:
                        _save_spec()
                    except Exception as _se:
                        _log.error("[diagnose] 诊断结果落盘失败: %s", _se)
                self._send(200, res)
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/vision/review":
            # 【视觉审查·老板 0811】AGNES 2.5-flash 多模态审查（免费 3000 次/天）：
            # quality 单帧画质 / identity 角色一致性(锚点vs生成帧) / continuity 镜头连贯(上镜尾帧vs本镜首帧)
            # / layout UI布局 / text 文字合规 / content 内容初审 / emotion 情绪表演。
            # 结果写回 shot.vision_review（verdict/issues/confidence），前端徽标展示。
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "diag")))
                from vision_review import review as vr_review
                pid = data.get("project_id") or ACTIVE
                sid = data.get("shot_id")
                kind = data.get("kind") or "quality"
                ctx = data.get("context") or ""
                if pid:
                    load_spec(pid)
                shot = find_shot(sid) if sid else None
                if shot is None:
                    self._send(404, {"ok": False, "error": "shot not found: %s" % sid})
                    return
                paths = []
                if kind in ("quality", "text", "content"):
                    # 单帧：首帧图优先，其次尾帧，其次视频抽帧（首帧即足够第一版）
                    for f in ("asset_frame_start", "asset_frame_end"):
                        v = shot.get(f) or ""
                        if v:
                            paths.append(_vr_to_local(v))
                            break
                    if not paths and shot.get("asset_video"):
                        paths.append(_vr_to_local(shot["asset_video"], video=True))
                elif kind == "identity":
                    # 角色一致性：锚点(ref 图) vs 首帧生成图
                    ref = SPEC.get("references", {}).get(shot.get("ref") or "") or {}
                    anchor = ref.get("remote_url") or ref.get("asset_image") or shot.get("remote_image_ref") or ""
                    if anchor:
                        paths.append(_vr_to_local(anchor))
                    ff = shot.get("asset_frame_start") or shot.get("asset_image") or ""
                    if ff:
                        paths.append(_vr_to_local(ff))
                elif kind == "continuity":
                    # 镜头连贯：上镜尾帧 vs 本镜首帧（同场景才审）
                    prev = _prev_shot(shot)
                    if prev and prev.get("asset_frame_end"):
                        paths.append(_vr_to_local(prev["asset_frame_end"]))
                    ff = shot.get("asset_frame_start") or ""
                    if ff:
                        paths.append(_vr_to_local(ff))
                if len(paths) < 1:
                    self._send(200, {"ok": False, "note": "该镜无可审查的图像资产（先生成首尾帧或视频）"})
                    return
                res = vr_review(paths, kind=kind, context=ctx)
                if res.get("ok"):
                    shot["vision_review"] = {"kind": kind, "verdict": res.get("verdict"),
                                             "issues": res.get("issues"),
                                             "confidence": res.get("confidence"),
                                             "ts": now_iso()}
                    _save_spec()
                res["project_id"] = pid
                res["shot_id"] = sid
                self._send(200, res)
            except Exception as e:
                self._log.error("[vision] 审查失败: %s", e)
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/faceqc":
            # P3 · 深度人脸一致性身份质检：SFace 余弦相似度 vs 角色参考图锚点
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
                from face_identity import score_project
                pid = data.get("project") or ACTIVE
                pdir = os.path.join(PROJECTS_ROOT, pid)
                sb_path = os.path.join(pdir, "storyboard.json")
                if not os.path.isfile(sb_path):
                    self._send(200, {"ok": False, "note": f"项目 {pid} 无 storyboard"})
                    return
                report = score_project(pdir, storyboard=sb_path)
                # 写回每个 shot 的 face_identity（供 UI / 诊断聚合展示）
                if report.get("ok"):
                    sb = json.load(open(sb_path, encoding="utf-8"))
                    for ps in report.get("per_shot", []):
                        sh = next((s for s in sb.get("shots", []) if s.get("id") == ps.get("shot")), None)
                        if sh:
                            sh["face_identity"] = ps.get("identity")
                            sh["face_ok"] = ps.get("face_ok")
                    json.dump(sb, open(sb_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                self._send(200, report)
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/facefix":
            # P3 · 自动纠偏：对身份分低于阈值的 shot，加强参考图权重 + 负向词后重新生成
            try:
                sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "scripts", "edit")))
                from face_identity import score_project, TH_WARN, TH_FAIL
                pid = data.get("project") or ACTIVE
                pdir = os.path.join(PROJECTS_ROOT, pid)
                sb_path = os.path.join(pdir, "storyboard.json")
                if not os.path.isfile(sb_path):
                    self._send(200, {"ok": False, "note": f"项目 {pid} 无 storyboard"})
                    return
                report = score_project(pdir, storyboard=sb_path)
                if not report.get("ok"):
                    self._send(200, report)
                    return
                # 选低于 warn 阈值的 shot
                targets = [ps["shot"] for ps in report.get("per_shot", [])
                           if ps.get("identity") is not None and ps["identity"] < TH_WARN]
                if not targets:
                    self._send(200, {"ok": True, "fixed": [], "msg": "全部 shot 身份达标，无需纠偏",
                                    "report": report})
                    return
                if not REAL:
                    self._send(200, {"ok": True, "dry_run": True, "targets": targets,
                                    "msg": "SIM 模式不重渲；切 REAL=1 后调用即真实重渲", "report": report})
                    return
                # 真纠偏：逐 shot 增强 prompt（参考图权重↑ + 角色串脸负向词）后重新生成
                results = []
                for sid in targets:
                    sh = find_shot(sid)
                    if not sh:
                        continue
                    ref = sh.get("ref_key") or (sh.get("characters") or [None])[0]
                    base = sh.get("video_prompt") or sh.get("action") or ""
                    enhance = (f"{base} | 身份一致性强化：严格锁定角色「{ref}」的参考图外观（脸型/五官/发色/"
                                f"年龄），禁止任何串脸或脸型漂移；保持与该角色其他镜头完全一致。")
                    sh["video_prompt"] = enhance
                    sh["status"] = "ready"
                    _save_spec()
                    try:
                        ok = _gen_video_with_timeout(sid, timeout=1200)
                        results.append({"shot": sid, "regen": ok, "prompt_enhanced": True})
                    except Exception as e:
                        results.append({"shot": sid, "regen": False, "error": str(e)})
                # 重渲后复测
                report2 = score_project(pdir, storyboard=sb_path)
                self._send(200, {"ok": True, "fixed": results, "report_before": report,
                                "report_after": report2})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path.startswith("/api/queue/"):
            # 批量队列调度器端点（#75）
            if BATCH_QUEUE is None:
                self._send(500, {"ok": False, "error": "队列调度器未加载"})
                return
            sub = p.path[len("/api/queue/"):]
            if sub == "enqueue" and self.command == "POST":
                job = BATCH_QUEUE.enqueue(
                    data.get("type"), payload=data.get("payload", {}),
                    schedule=data.get("schedule", "immediate"), run_at=data.get("run_at"),
                    project=data.get("project"), max_attempts=data.get("max_attempts", 1),
                    note=data.get("note", ""))
                self._send(200, {"ok": True, "job": job})
            elif sub == "list":
                jobs = BATCH_QUEUE.list(status=data.get("status"))
                # O3：运行中的任务从 PIPELINE_STATE 注入实时进度/耗时，便于 UI 展示
                with PIPE_LOCK:
                    ps = dict(PIPELINE_STATE)
                now = time.time()
                for j in jobs:
                    if j.get("status") == "running":
                        st = ps.get("stage_idx") or 0
                        tot = ps.get("stages_total") or 0
                        prog = int(round(100 * st / tot)) if tot else 0
                        if ps.get("stage") == "视频生成" and ps.get("total"):
                            prog = int(round(100 * (ps.get("current", 0)) / ps["total"]))
                        j["progress"] = prog
                        sa = j.get("started_at")
                        if sa:
                            try:
                                el = int((now - datetime.fromisoformat(sa)).total_seconds())
                                j["elapsed_sec"] = el
                            except Exception:
                                pass
                    elif j.get("status") == "done":
                        j["progress"] = 100
                self._send(200, {"ok": True, "jobs": jobs, "paused": QUEUE_WORKER_STOP["flag"]})
            elif sub == "cancel" and self.command == "POST":
                ok = BATCH_QUEUE.cancel(data.get("id"))
                self._send(200, {"ok": ok, "id": data.get("id")})
            elif sub == "stop" and self.command == "POST":
                # pause=true 暂停 worker（已消费任务跑完，新任务空转不消费）；pause=false 恢复
                QUEUE_WORKER_STOP["flag"] = bool(data.get("pause", True))
                self._send(200, {"ok": True, "paused": QUEUE_WORKER_STOP["flag"]})
            else:
                self._send(404, {"error": "unknown queue op"})

        elif p.path == "/api/key-pool":
            # P2：密钥池健康 + 自动切换计数（免费KEY池，触发式轮换，替代额度护栏）
            try:
                sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
                from agnes_client import key_pool_status
                self._send(200, {"ok": True, **key_pool_status()})
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/novel/generate":
            # 主题→小说：一句话 → AGNES 扩写为完整短剧小说（库驱动，提示词在提示词库）
            theme = (data.get("theme") or "").strip()
            if not theme:
                self._send(400, {"ok": False, "error": "theme 不能为空"})
                return
            try:
                self._send(200, generate_novel_from_theme(theme))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/style/keywords":
            # 风格→英文关键词：中文描述 → AGNES 产 JSON{keywords[],cn}（库驱动）
            style = (data.get("style") or "").strip()
            if not style:
                self._send(400, {"ok": False, "error": "style 不能为空"})
                return
            try:
                self._send(200, generate_style_keywords(style))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/outline/generate":
            # 剧本大纲：需求卡 → AGNES 大纲 JSON（库驱动）
            try:
                self._send(200, generate_outline(data.get("req_card") or {},
                                                  data.get("novel") or ""))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path == "/api/prompt/test":
            # 测试沙盒：用库中提示词跑一次生成，不落盘，纯预览，快速迭代
            ptype = (data.get("type") or "").strip()
            sample = (data.get("sample_input") or "").strip()
            if not ptype:
                self._send(400, {"ok": False, "error": "type 不能为空"})
                return
            if not sample:
                self._send(400, {"ok": False, "error": "sample_input 不能为空"})
                return
            try:
                self._send(200, test_prompt_sandbox(ptype, sample))
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})

        elif p.path.startswith("/api/series/"):
            # O1：查看某剧集的跨集锚点库（角色→脸图URL）
            sid = (data.get("series_id", "") if isinstance(data, dict) else "")
            if not sid and "series_id=" in p.path:
                qs = parse_qs(urlparse(p.path).query)
                sid = (qs.get("series_id") or [""])[0]
            store = _series_anchor_load(sid) if sid else {}
            self._send(200, {"ok": True, "series_id": sid, "anchors": store, "count": len(store)})

        else:
            self._send(404, {"error": "not found"})

    def _stream_pipeline(self):
        """SSE 事件流：把流水线进度以 text/event-stream 实时推给前端（替代 1s 轮询的延迟感）。

        每 0.3s 取一次 _pipeline_snapshot()，仅在状态变化时推送；running 结束后多推一帧再关闭。
        ThreadingHTTPServer 下每个连接独占线程，断开由客户端（前端看到 running=false 即关 EventSource）或 BrokenPipe 触发。"""
        self.protocol_version = "HTTP/1.1"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last = ""
        sent_final = False
        try:
            while True:
                snap = _pipeline_snapshot()
                payload = json.dumps(snap, ensure_ascii=False)
                if payload != last:
                    last = payload
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                if not snap.get("running"):
                    if sent_final:
                        break
                    sent_final = True
                    time.sleep(1.0)
                    continue
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _serve_file(self, rel, ctype):
        rel = rel.replace("\\", "/")
        path = asset_abs(rel) if rel.startswith("assets/") else os.path.join(HERE, rel)
        if not os.path.isfile(path):
            self._send(404, {"error": f"{rel} missing"})
            return
        if ctype is None:
            ctype, _ = mimetypes.guess_type(path)
            ctype = ctype or "application/octet-stream"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        # 缓存策略：页面/内联 JS 必须 no-store，否则手机浏览器会一直吃旧版 studio.html，
        # 前端修了也看不到（老板刷新仍是旧逻辑）。vendor 第三方库不变，长缓存提速。
        if rel.startswith("vendor/"):
            self.send_header("Cache-Control", "public, max-age=604800, immutable")
        elif ctype.startswith("text/html") or rel.endswith(".html"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

    # 每次响应出口统一记日志（BaseHTTPRequestHandler 在 send_response 后回调）：
    # 方法 / 路径 / 状态码 / 耗时 → 出问题可沿时间线回溯
    def log_request(self, code="-", size="-"):
        try:
            ms = (time.time() - getattr(self, "_req_t0", time.time())) * 1000
            p = urlparse(self.path)
            qs = parse_qs(p.query or "")
            proj = (qs.get("project") or [""])[0]
            extra = f" project={proj}" if proj else ""
            if code == 500:
                _log.error("HTTP %s %s -> %s %.0fms%s", self.command, unquote(p.path), code, ms, extra)
            else:
                _log.info("HTTP %s %s -> %s %.0fms%s", self.command, unquote(p.path), code, ms, extra)
        except Exception:
            pass


if __name__ == "__main__":
    ensure_projects()
    load_spec()
    # 启动批量队列常驻 worker（cron 语义：immediate / nightly 02-06 / run_at 精确触发）
    if BATCH_QUEUE is not None:
        threading.Thread(target=BATCH_QUEUE.run_worker,
                         args=(queue_executor, 3, None, _queue_worker_stop),
                         daemon=True).start()
        print(f"批量队列调度器已启动 -> {QUEUE_FILE}")
    mode = "REAL(调AGNES+MiniMax)" if REAL else "dry-run(不花token)"
    print(f"Storyboard Studio 后端启动 [{mode}] -> http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
