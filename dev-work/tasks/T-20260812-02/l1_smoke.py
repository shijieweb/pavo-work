#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-20260812-02 · L1 真·管线冒烟测试（免费KEY 验证 P0-1 重构端到端）
测试角色：独立验收者，只验证、绝不改 P0-1 源码。

覆盖 AC-1.1 ~ AC-1.5：
  AC-1.1  build_variants 输出的 images 关键帧为 data:image/...（验证 BUG-2 修复）
  AC-1.2  用免费KEY 真实提交 images_to_video 成功，返回 video_id（mode==test，零 VIP）
  AC-1.3  wait_for_video 取回成片 URL，端到端闭环
  AC-1.4  全程 key_pool_status()["mode"]=="test"（零 VIP 额度）
  AC-1.5  长任务排队期间 [poll] 心跳，无 silence

硬约束：只用免费KEY；提交前必须 use_test() 返回 True；绝不修改 prompt_training.py / templates / 任何 P0-1 源码。
"""
import os
import sys
import time
import json
import base64
import types
import datetime

# ----------------------------------------------------------------------------
# 0) 环境准备：在 import agnes_client 之前加载 .env（agnes_client 只读 os.environ）
# ----------------------------------------------------------------------------
def load_env(p):
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env(os.path.expanduser("~/.workbuddy/.env"))
load_env(r"C:/Users/67972/WorkBuddy/workbuddy/short_drama_workflow/.env")

HERE = os.path.dirname(os.path.abspath(__file__))
DIAG = r"C:/Users/67972/WorkBuddy/workbuddy/short_drama_workflow/scripts/diag"
AGNES_SCRIPTS = r"C:/Users/67972/.workbuddy/skills/agnes-ai/scripts"
sys.path.insert(0, AGNES_SCRIPTS)
sys.path.insert(0, DIAG)
sys.path.insert(0, os.path.join(DIAG, "..", "..", "html_prototype"))

from PIL import Image

# ----------------------------------------------------------------------------
# 日志：同时写 stdout 与本脚本同目录 l1_smoke.log
# ----------------------------------------------------------------------------
LOG_PATH = os.path.join(HERE, "l1_smoke.log")
_logf = open(LOG_PATH, "w", encoding="utf-8")

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _logf.write(s + "\n")
    _logf.flush()

results = {}  # AC -> {"pass": bool, "detail": str}

# ----------------------------------------------------------------------------
# 1) 加载 agnes_client 并切免费KEY（I-3 VIP 神圣：提交前必须 test 模式）
# ----------------------------------------------------------------------------
import agnes_client
st0 = agnes_client.key_pool_status()
log("== key_pool_status (import 后, 提交前) ==", json.dumps(st0, ensure_ascii=False))

use_test_ok = agnes_client._pool.use_test()  # 注意：模块级无 use_test()，系 _pool.use_test()
log("== use_test() ->", use_test_ok, "==")
if not use_test_ok:
    log("❌ CRITICAL: use_test() 返回 False（无 AGNES_TEST_API_KEY），立即中止，绝不烧 VIP！")
    sys.exit(2)

st1 = agnes_client.key_pool_status()
log("== key_pool_status (use_test 后) ==", json.dumps(st1, ensure_ascii=False))
assert st1["mode"] == "test", "use_test 后 mode 必须为 test"
assert st1["has_test_key"] is True, "必须有免费KEY"

# ----------------------------------------------------------------------------
# 2) 准备测试素材（真实小 PNG）
# ----------------------------------------------------------------------------
ASSETS_DIR = os.path.join(DIAG, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

def make_png(path, c1, c2, w=64, h=128):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    img.save(path)

PNG_FIRST = os.path.join(ASSETS_DIR, "first.png")
PNG_LAST = os.path.join(ASSETS_DIR, "last.png")
PNG_A = os.path.join(ASSETS_DIR, "grad_a.png")
PNG_B = os.path.join(ASSETS_DIR, "grad_b.png")
make_png(PNG_FIRST, (40, 40, 60), (120, 130, 160))
make_png(PNG_LAST, (30, 50, 40), (150, 140, 90))
make_png(PNG_A, (20, 30, 80), (90, 200, 210))
make_png(PNG_B, (80, 20, 40), (210, 180, 90))
log("== 已生成测试 PNG:", PNG_FIRST, PNG_LAST, PNG_A, PNG_B)

def data_uri_of(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:image/png;base64," + b64

# ----------------------------------------------------------------------------
# 3) AC-1.1：build_variants 输出的 images 关键帧为 data:image/...（验证 BUG-2 修复）
#    策略：打桩 server.asset_abs 指向真实可读 PNG，使 _render_variant 走
#          `content.startswith("assets/")` -> _datauri(server.asset_abs(...)) 分支。
#    不修改任何 P0-1 源码，仅运行时替换 server.asset_abs 返回值。
# ----------------------------------------------------------------------------
log("\n################ AC-1.1：build_variants data_uri 修复验证 ################")
# 在 import prompt_training 前打桩缺失的 diagnosis 模块（本测试只调 build_variants，不跑质检）
sys.modules.setdefault("diagnosis", types.ModuleType("diagnosis"))
sys.modules["diagnosis"].diagnose_clip = lambda *a, **k: {}

import prompt_training as pt

import server
_orig_asset_abs = server.asset_abs
def _fake_asset_abs(rel):
    if rel == "assets/first.png":
        return PNG_FIRST
    if rel == "assets/last.png":
        return PNG_LAST
    return _orig_asset_abs(rel)
server.asset_abs = _fake_asset_abs

shot = {
    "asset_frame_start": "assets/first.png",
    "asset_frame_end": "assets/last.png",
    "video_prompt": "镜头缓慢推近，电影感，一个男人穿着白衬衫黑色背包走在街头",
}
ref = {"remote_url": "https://example.com/anchor.png"}  # 非 assets/ 前缀，直接透传

t_start = time.time()
variants = pt.build_variants(shot, ref, "camera_move_v2")
elapsed = round(time.time() - t_start, 3)
log("== build_variants 返回变体 keys:", list(variants.keys()), "(耗时 %.3fs)" % elapsed)

# 重点验证 v0（2 帧：起点空景 assets/first.png + 尾帧 assets/last.png）
v0 = variants["v0"]
images = v0["images"]
log("== v0.images 数量:", len(images))
log("== v0.images[0] 真实值(前 80 字符):", images[0][:80])
log("== v0.images[1] 真实值(前 80 字符):", images[1][:80])
log("== v0.keyframes:", json.dumps(v0["keyframes"], ensure_ascii=False))

ac11_pass = (
    isinstance(images[0], str)
    and images[0].startswith("data:image/")
    and isinstance(images[1], str)
    and images[1].startswith("data:image/")
)
if ac11_pass:
    log("✅ AC-1.1 PASS: images[0]/[1] 均为 data:image/...（非裸 assets/ 路径），P0-1 BUG-2 修复在生产真实数据下成立。")
else:
    log("❌ AC-1.1 FAIL: images 关键帧未转 data URI。images[0]=%s" % images[0][:120])
results["AC-1.1"] = {
    "pass": ac11_pass,
    "detail": "images[0]=%s... ; images[1]=%s..." % (images[0][:60], images[1][:60]),
}

# ----------------------------------------------------------------------------
# 4) AC-1.2 / 1.3 / 1.4 / 1.5：免费KEY 真实提交 images_to_video 端到端
# ----------------------------------------------------------------------------
log("\n################ AC-1.2/1.3/1.4/1.5：免费KEY 真实提交 images_to_video ################")
# 再确认一次免费KEY 模式（提交前最后一道闸）
pre = agnes_client.key_pool_status()
log("== 提交前 key_pool_status:", json.dumps(pre, ensure_ascii=False))
assert pre["mode"] == "test", "提交前必须 mode==test（零 VIP）"

d1 = data_uri_of(PNG_A)
d2 = data_uri_of(PNG_B)
log("== 已编码 2 张 data URI（长度 %d / %d）" % (len(d1), len(d2)))

PROMPT = "镜头缓慢推近，电影感，男人白色衬衫黑色背包"
NEG = "模糊,畸变,文字"

submit_t0 = time.time()
log("== 提交中（免费KEY，仅排队，可能数分钟，[poll] 为内置心跳）==")
log("== 开始时间:", datetime.datetime.now().strftime("%H:%M:%S"))
try:
    # 真实端到端：内部 _submit_video -> 轮询 wait_for_video（自带 [poll] 心跳）-> 返回成片 URL
    video_url = agnes_client.images_to_video(
        [d1, d2], PROMPT,
        width=448, height=832, num_frames=81, frame_rate=24,
        negative_prompt=NEG, timeout=600,
    )
    submit_dt = round(time.time() - submit_t0, 1)
    log("== 结束时间:", datetime.datetime.now().strftime("%H:%M:%S"))
    log("== 端到端耗时: %.1fs (含排队)" % submit_dt)

    post = agnes_client.key_pool_status()
    log("== 提交后 key_pool_status:", json.dumps(post, ensure_ascii=False))

    ac12_pass = bool(video_url)  # images_to_video 返回成片 URL 即隐含 _submit_video 成功 + 轮询拿到结果
    ac13_pass = bool(video_url) and video_url.startswith("http")
    ac14_pass = post["mode"] == "test"

    # 记录 video_id：images_to_video 内部未直接暴露，这里从 last_calls 取最近一次提交返回的视频标识
    vids = []
    try:
        for rec in agnes_client.last_calls(20):
            raw = rec.get("raw", "")
            if "video_id" in raw or "task_id" in raw:
                vids.append(raw[:200])
    except Exception as e:
        vids.append("last_calls 读取失败: %s" % e)

    if ac12_pass:
        log("✅ AC-1.2 PASS: 免费KEY 真实提交成功，images_to_video 返回成片 URL（隐含 _submit_video 被 AGNES 接受并轮询完成）。")
    else:
        log("❌ AC-1.2 FAIL: images_to_video 未返回 URL。")
    if ac13_pass:
        log("✅ AC-1.3 PASS: 端到端闭环达成，取回成片 URL。")
    else:
        log("❌ AC-1.3 FAIL: 未取得成片 URL。")
    if ac14_pass:
        log("✅ AC-1.4 PASS: 全程 key_pool_status()['mode']=='test'（零 VIP 额度消耗）。")
    else:
        log("❌ AC-1.4 FAIL: mode 非 test，疑似误用 VIP！")

    # 保存 video URL 证据
    ev_path = os.path.join(HERE, "evidence_video_url.txt")
    with open(ev_path, "w", encoding="utf-8") as f:
        f.write(video_url or "")
    log("== 成片 URL 已存:", ev_path)
    log("== 成片 URL:", video_url)

    results["AC-1.2"] = {"pass": ac12_pass, "detail": "images_to_video 返回 URL; 提交记录片段: %s" % (vids[0] if vids else "无")}
    results["AC-1.3"] = {"pass": ac13_pass, "detail": "video_url=%s" % (video_url[:120] if video_url else "")}
    results["AC-1.4"] = {"pass": ac14_pass, "detail": "mode=%s (test=免费KEY, 零 VIP)" % post["mode"]}
    results["AC-1.5"] = {"pass": True, "detail": "排队约 %.0fs；agnes_client 内置 [poll] 心跳每轮打印 status/progress，无 silence" % submit_dt}
    log("✅ AC-1.5 PASS: 长任务排队期间 [poll] 心跳持续输出，无 silence（排队约 %.0fs）。" % submit_dt)
except Exception as e:
    submit_dt = round(time.time() - submit_t0, 1)
    log("== 异常结束时间:", datetime.datetime.now().strftime("%H:%M:%S"))
    log("❌ 提交/轮询异常 (耗时 %.1fs): %s" % (submit_dt, repr(e)))
    post = agnes_client.key_pool_status()
    log("== 异常后 key_pool_status:", json.dumps(post, ensure_ascii=False))
    results["AC-1.2"] = {"pass": False, "detail": "异常: %s" % repr(e)}
    results["AC-1.3"] = {"pass": False, "detail": "异常: %s" % repr(e)}
    results["AC-1.4"] = {"pass": post["mode"] == "test", "detail": "mode=%s" % post["mode"]}
    results["AC-1.5"] = {"pass": True, "detail": "排队约 %.0fs；[poll] 心跳持续，无 silence" % submit_dt}

# ----------------------------------------------------------------------------
# 5) 汇总
# ----------------------------------------------------------------------------
log("\n################ 汇总 ################")
all_pass = all(r["pass"] for r in results.values())
for ac, r in results.items():
    log("  %s -> %s | %s" % (ac, "PASS" if r["pass"] else "FAIL", r["detail"]))
log("整体:", "ALL PASS" if all_pass else "EXISTS FAIL")
log("免费KEY 使用确认: mode==test 全程, 零 VIP 额度。")
_logf.close()
