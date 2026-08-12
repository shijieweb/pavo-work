#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-20260813-01 · l1_smoke 固化进回归套件（免费 KEY 端到端真测守卫）

目标
----
把「免费 KEY 真测（L1）」固化成一个可重复运行的回归守卫脚本：
  build_variants -> images_to_video(free KEY) -> 轮询 -> 取回成片 URL
并打印 PASS/FAIL + 成片 URL（可被 `curl -sI` 验证 HTTP/1.1 200 + video/mp4）。

红线（违反=严重）
----------------
- 禁烧 VIP：全程只走免费 KEY（test 模式），绝不进 prod/VIP 分支。
- 入口守卫：调用任何 gen_video 之前，必须断言 key_pool_status()["mode"]=="test"；
  当前若是 VIP/prod 且无法切到免费 KEY，立即非零退出，绝不烧额度。
- 只 import 复用 agnes_client / server / prompt_training，不改其既有逻辑
  （仅运行时把 server.asset_abs 打桩指向本地真实帧图，不修改任何源文件）。

用法
----
    python l1_smoke.py            # 单命令即可跑，参数有合理默认值
    python l1_smoke.py --num-frames 81 --timeout 900
"""
import argparse
import base64
import datetime
import json
import os
import struct
import sys
import time
import zlib

# ----------------------------------------------------------------------------
# 0) 环境准备：在 import agnes_client 之前加载 .env（agnes_client 只读 os.environ）
# ----------------------------------------------------------------------------
def load_env(path):
    """把 .env 里的键值注入 os.environ（仅当尚未设置），不打印任何密钥。"""
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)                       # 注：实际=short_drama_workflow(HERE 的父)，仅兼容保留
AGNES_SCRIPTS = os.path.expanduser(r"~/.workbuddy/skills/agnes-ai/scripts")
DIAG_DIR = os.path.abspath(os.path.join(HERE, "diag"))   # HERE=scripts → scripts/diag
HTML_PROTOTYPE = os.path.abspath(os.path.join(HERE, "..", "html_prototype"))

load_env(os.path.expanduser(r"~/.workbuddy/.env"))
load_env(r"C:/Users/67972/WorkBuddy/workbuddy/short_drama_workflow/.env")

# 让 agnes_client / server / prompt_training 可被 import
sys.path.insert(0, AGNES_SCRIPTS)   # agnes_client（含 _KeyPool / _pool）
sys.path.insert(0, HTML_PROTOTYPE)  # server（asset_abs 等）
sys.path.insert(0, DIAG_DIR)         # prompt_training

import agnes_client  # noqa: E402  (must be importable before prompt_training)


# ----------------------------------------------------------------------------
# 1) 入口守卫（PRD F2 / AC-1.2）：在调用任何 gen_video 之前，必须处于 test(免费KEY)模式
# ----------------------------------------------------------------------------
def ensure_test_mode():
    """硬守卫：保证 key-pool 处于 test 模式（免费 KEY），否则在 gen_video 前即非零退出。

    返回 key_pool_status() dict。逻辑：
      1. 读取当前 mode；若是 prod/VIP，尝试 _pool.use_test() 切到免费 KEY。
      2. 若没有免费 KEY（use_test()==False），直接 sys.exit(3) —— 绝不进入 VIP 分支。
      3. 最后再 assert mode=="test"：双重保险，任何情况下都不允许在 prod 下提交视频。
    """
    st = agnes_client.key_pool_status()
    if st["mode"] != "test":
        switched = agnes_client._pool.use_test()  # 注意：模块级无 use_test()，是 _pool.use_test()
        if not switched:
            sys.stderr.write(
                "❌ 入口守卫：当前 mode=%s（VIP/prod），且无 AGNES_TEST_API_KEY 可切免费 KEY；"
                "为杜绝误烧 VIP，立即非零退出，绝不进入 gen_video。\n" % st["mode"])
            sys.exit(3)
    # 切到 test 后再次硬断言：必须是 test，否则禁止 gen_video（防误烧 VIP）
    assert agnes_client.key_pool_status()["mode"] == "test", \
        "入口守卫失败：mode 非 test，禁止进入 gen_video（防误烧 VIP）"
    return agnes_client.key_pool_status()


# ----------------------------------------------------------------------------
# 2) 本地真实帧图（assets/ 前缀，复刻 P0-1 BUG-2 的 data_uri 分支，零额外依赖）
# ----------------------------------------------------------------------------
ASSETS_DIR = os.path.join(HERE, "assets")


def _write_png(path, width, height, pixels):
    """用标准库 zlib 写一个合法的 8-bit RGB PNG（不依赖 Pillow）。

    pixels: bytes，长度必须为 width*height*3（每行 RGB 连续排列）。
    这样脚本自包含、无第三方依赖即可产出可被 AGNES 解码的真实帧图。
    """
    def _chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # 每行过滤器 0（无过滤）
        raw.extend(pixels[y * width * 3:(y + 1) * width * 3])
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        fh.write(_chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        fh.write(_chunk(b"IEND", b""))


def _gradient_png(path, c_top, c_bottom, width=256, height=448):
    """生成一张竖直渐变 PNG（真实可读帧图），用于 keyframes 关键帧。"""
    px = bytearray()
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(c_top[0] + (c_bottom[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bottom[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bottom[2] - c_top[2]) * t)
        for _ in range(width):
            px.extend((r, g, b))
    _write_png(path, width, height, bytes(px))


def ensure_assets():
    """确保本地 assets/ 下有 2 张真实 PNG 帧图（首帧/尾帧），返回其相对 assets/ 路径。"""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    first = os.path.join(ASSETS_DIR, "first.png")
    last = os.path.join(ASSETS_DIR, "last.png")
    if not os.path.isfile(first):
        _gradient_png(first, (40, 40, 60), (120, 130, 160))   # 冷色渐变（起点空景）
    if not os.path.isfile(last):
        _gradient_png(last, (30, 50, 40), (150, 140, 90))     # 暖色渐变（尾帧中景）
    return "assets/first.png", "assets/last.png"


# ----------------------------------------------------------------------------
# 3) 主流程
# ----------------------------------------------------------------------------
NEG_PROMPT = ("text, watermark, logo, subtitles, morphing, deformed hands, extra fingers, "
              "blurry face, frame jump, identity change, clothing change")


def _probe(url):
    """对成片 URL 做一次 HEAD/Range 探测，返回 (http_status, content_type)。用于自证可访问。"""
    import urllib.request
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except Exception as exc:
        return None, "probe-failed: %s" % exc


def main():
    ap = argparse.ArgumentParser(description="L1 免费KEY 端到端真测冒烟（回归守卫）")
    ap.add_argument("--width", type=int, default=448)
    ap.add_argument("--height", type=int, default=832)
    ap.add_argument("--num-frames", type=int, default=81)
    ap.add_argument("--frame-rate", type=int, default=24)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--negative", type=str, default=NEG_PROMPT)
    args = ap.parse_args()

    print("== l1_smoke 开始: %s ==" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), flush=True)

    # ---- 入口守卫：必须 test 模式，否则在 gen_video 前即非零退出（防误烧 VIP）----
    st_before = ensure_test_mode()
    print("== 入口守卫通过: mode=%s (免费KEY, 零 VIP) ==" % st_before["mode"], flush=True)

    # ---- 准备本地真实帧图 ----
    rel_first, rel_last = ensure_assets()
    first_path = os.path.join(ASSETS_DIR, "first.png")
    last_path = os.path.join(ASSETS_DIR, "last.png")
    print("== 本地真实帧图: %s , %s ==" % (first_path, last_path), flush=True)

    # ---- 运行时打桩 server.asset_abs -> 指向本地真实 PNG（不改任何源文件）----
    import types  # noqa: E402
    import importlib.util as _ilu  # noqa: E402
    # 按绝对路径加载 server 模块，避免从 scripts/ 直接运行时 sys.path 找不到 server
    _server_path = os.path.abspath(os.path.join(HTML_PROTOTYPE, "server.py"))
    _spec = _ilu.spec_from_file_location("server", _server_path)
    server = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(server)
    _orig_asset_abs = server.asset_abs

    def _fake_asset_abs(rel):
        base = os.path.basename(str(rel))
        cand = os.path.join(ASSETS_DIR, base)
        if os.path.isfile(cand):
            return cand
        return _orig_asset_abs(rel)

    server.asset_abs = _fake_asset_abs
    # 桩自检（在 gen_video 之前、不调 AGNES，零 VIP）：确认桩把引用映射到真实 PNG
    for _r in (rel_first, rel_last):
        _c = server.asset_abs(_r)
        assert os.path.isfile(_c), "❌ 桩失效: %r -> %r" % (_r, _c)

    # ---- 仅 import prompt_training 需要使用 diagnosis 模块（本 smoke 不跑质检，打桩为空）----
    sys.modules.setdefault("diagnosis", types.ModuleType("diagnosis"))
    sys.modules["diagnosis"].diagnose_clip = lambda *a, **k: {}

    import prompt_training as pt  # noqa: E402

    # ---- 构造真实 shot：首/尾帧用 assets/ 前缀，触发 data_uri 分支（复刻 P0-1 BUG-2）----
    shot = {
        "asset_frame_start": rel_first,   # "assets/first.png"
        "asset_frame_end": rel_last,      # "assets/last.png"
        "video_prompt": "镜头缓慢推近，电影感，一个男人穿着白衬衫黑色背包走在街头",
    }
    ref = {"remote_url": "https://example.com/anchor.png"}  # 非 assets/ 前缀，直接透传

    variants = pt.build_variants(shot, ref, "camera_move_v2")
    print("== build_variants 变体: %s ==" % list(variants.keys()), flush=True)

    # 取 v0（2 帧：起点空景 assets/first.png + 尾帧 assets/last.png），覆盖 data_uri 分支
    v0 = variants["v0"]
    images = v0["images"]
    prompt = v0["prompt"]
    print("== v0.images 数量: %d ; 前 60 字符: %s" % (len(images), images[0][:60]), flush=True)

    # ---- AC-1.1 复刻：images 关键帧必须为 data:image/...（验证 BUG-2 修复在生产真实数据下成立）----
    data_uri_ok = all(
        isinstance(im, str) and im.startswith("data:image/") for im in images)
    if not data_uri_ok:
        print("❌ AC-1.1 FAIL: images 关键帧未转 data URI（BUG-2 回退）: %s" % images[0][:120],
              flush=True)
        sys.exit(1)
    print("✅ AC-1.1 PASS: images 关键帧均为 data:image/...（走 data_uri 分支）", flush=True)

    # ---- 提交前最后一道闸：再次确认 test 模式 ----
    pre = agnes_client.key_pool_status()
    assert pre["mode"] == "test", "提交前必须 mode==test（零 VIP）"

    # ---- AC-1.2/1.3/1.4：免费KEY 真实提交 images_to_video 端到端 ----
    print("== 提交中（免费KEY，仅排队，[poll] 为内置心跳）: %s =="
          % datetime.datetime.now().strftime("%H:%M:%S"), flush=True)
    t0 = time.time()
    try:
        video_url = agnes_client.images_to_video(
            images, prompt,
            width=args.width, height=args.height,
            num_frames=args.num_frames, frame_rate=args.frame_rate,
            negative_prompt=args.negative,
            timeout=args.timeout, interval=args.interval,
        )
        dt = round(time.time() - t0, 1)
        print("== 结束: %s (耗时 %.1fs) =="
              % (datetime.datetime.now().strftime("%H:%M:%S"), dt), flush=True)

        post = agnes_client.key_pool_status()
        print("== 提交后 key_pool_status: %s ==" % json.dumps(post, ensure_ascii=False), flush=True)

        # ---- AC-1.3 自证：成片 URL 可访问（HTTP 200 + video/mp4）----
        status, ctype = _probe(video_url)
        reachable = bool(video_url) and str(status) in ("200", "206") \
            and ("video" in str(ctype) or status in ("200", "206"))
        vip_safe = post["mode"] == "test"

        passed = bool(video_url) and video_url.startswith("http") and reachable and vip_safe
        if passed:
            print("✅ PASS | 成片 URL: %s" % video_url, flush=True)
            print("   探测: HTTP %s , Content-Type: %s" % (status, ctype), flush=True)
            print("   全程 mode=%s（免费KEY, 零 VIP 额度消耗）" % post["mode"], flush=True)
            # 落盘成片 URL 供 curl 复核
            with open(os.path.join(HERE, "l1_smoke.last_url.txt"), "w", encoding="utf-8") as fh:
                fh.write(video_url or "")
            sys.exit(0)
        else:
            print("❌ FAIL | url=%s reachable=%s vip_safe=%s" % (video_url, reachable, vip_safe),
                  flush=True)
            sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        dt = round(time.time() - t0, 1)
        post = agnes_client.key_pool_status()
        print("❌ 提交/轮询异常 (耗时 %.1fs): %s" % (dt, repr(exc)), flush=True)
        print("== 异常后 key_pool_status: %s ==" % json.dumps(post, ensure_ascii=False), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
