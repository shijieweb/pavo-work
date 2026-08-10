#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax TTS 客户端（v4 稳定版，2026-07-08 实装）

接口（来自 MiniMax 控制台实际测试）：
  POST https://api.minimax.chat/v1/t2a_v2
  Headers: Authorization: Bearer $MINIMAX_API_KEY, X-Group-Id: $MINIMAX_GROUP_ID
  Body（嵌套格式，不支持 emotion 参数）：
    {"model":"speech-2.8-hd","text":"…",
     "voice_setting":{"voice_id":"female-shaonv","speed":1.0,"vol":1.0,"pitch":0},
     "audio_setting":{"sample_rate":32000,"bitrate":128000,"format":"mp3","channel":1},
     "text_type":"txt"}
  Response: 200, {"data":{"audio":"<hex-string>","status":2},"extra_info":{...}}
  audio 字段是 HEX 编码的 MP3，需解码后保存。

可用 voice_id 参考（mini 官方列表）:
  female-shaonv, female-yujing, female-chengshu, female-tianmei
  male-qn-qingse, male-qn-jingying, male-yunjian, male-badao

用法：
    python minimax_tts.py                                   # 单段测试
    python minimax_tts.py --text "你好" --voice female-shaonv --out t.mp3
    python minimax_tts.py --demo                            # 多角色 demo
"""
import json, os, sys, time, urllib.request, urllib.error

DEFAULT_BASE = "https://api.minimax.chat"
TTS_PATH = "/v1/t2a_v2"
MODEL = "speech-2.8-hd"
DEFAULT_VOICE = "female-shaonv"


def _load_env():
    """从 .env 读取 MINIMAX_API_KEY / MINIMAX_GROUP_ID（若未在环境变量中）"""
    if os.environ.get("MINIMAX_API_KEY") and os.environ.get("MINIMAX_GROUP_ID"):
        return
    for p in (os.path.expanduser("~/.workbuddy/.env"), os.path.join(os.getcwd(), ".env")):
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "MINIMAX_API_KEY":
                    os.environ["MINIMAX_API_KEY"] = v
                elif k == "MINIMAX_GROUP_ID":
                    os.environ["MINIMAX_GROUP_ID"] = v


def tts(text, voice_id=None, model=None, speed=1.0, vol=1.0, pitch=0,
        out_path=None, timeout=60):
    """
    MiniMax TTS 主接口。
    返回 mp3 bytes；若 out_path 非空则同时落盘。
    """
    _load_env()
    if not os.environ.get("MINIMAX_API_KEY"):
        raise RuntimeError("MINIMAX_API_KEY 未配置")
    if not os.environ.get("MINIMAX_GROUP_ID"):
        raise RuntimeError("MINIMAX_GROUP_ID 未配置")

    body = {
        "model": model or MODEL,
        "text": text[:10000],
        "voice_setting": {
            "voice_id": voice_id or DEFAULT_VOICE,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "text_type": "txt",
    }

    url = DEFAULT_BASE + TTS_PATH
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {os.environ['MINIMAX_API_KEY']}",
        "Content-Type": "application/json",
        "X-Group-Id": os.environ.get("MINIMAX_GROUP_ID", ""),
    }

    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                j = json.loads(raw)
                if j.get("data") and j["data"].get("audio"):
                    audio_hex = j["data"]["audio"]
                    mp3 = bytes.fromhex(audio_hex)
                    if out_path:
                        with open(out_path, "wb") as f:
                            f.write(mp3)
                    return mp3
                else:
                    raise RuntimeError(f"MiniMax 返回错误: {j}")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503):
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(1)
            continue
    raise RuntimeError(f"MiniMax TTS 请求失败（3 次重试）: {last_err}")


# ===== 短剧批量配音 =====

LINYU_VOICE = "male-qn-qingse"
LINYU_INNER_VOICE = "male-qn-qingse"
SYSTEM_VOICE = "male-qn-jingying"
WARN_VOICE = "male-badao"
BULLET_VOICE = "female-shaonv"


def gen_episode_audio(spec_path: str, out_dir: str, *, limit: int = 0,
                      tts_fn=None, log=None):
    """按分镜批量生成音频。返回 manifest dict { shot_id: rel_path }。"""
    tts_fn = tts_fn or tts
    log = log or print

    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    os.makedirs(out_dir, exist_ok=True)

    shots = spec.get("shots", [])
    if limit:
        shots = shots[:limit]

    manifest = {}
    for i, s in enumerate(shots, 1):
        if not s.get("audio"):
            log(f"  [audio] shot {s.get('id')} 无台词，跳过")
            continue
        kind = s.get("kind", "narrator")
        voice = eval(f"{kind}_VOICE") if kind in ("narrator", "linyue_inner", "system", "warning", "bullet") else LINYU_VOICE
        rel = f"shot_{s.get('id'):03d}.mp3"
        out = os.path.join(out_dir, rel)
        try:
            tts_fn(s["audio"], voice_id=voice, out_path=out)
            manifest[s["id"]] = rel
            log(f"  [audio] shot {s['id']} -> {rel} ({voice})")
        except Exception as e:
            log(f"  [audio] shot {s['id']} 失败: {e}")
    return manifest


# ===== CLI =====

def main():
    import argparse
    ap = argparse.ArgumentParser(description="MiniMax TTS 客户端")
    ap.add_argument("--text", default=None, help="要合成的文本")
    ap.add_argument("--voice", default=None, help="voice_id")
    ap.add_argument("--out", default=None, help="输出 mp3 路径")
    ap.add_argument("--demo", action="store_true", help="多角色 demo")
    ap.add_argument("--episode", default=None, help="ep01 分镜文件名，批量配音")
    ap.add_argument("--out-dir", default=None, help="批量输出目录")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()

    _load_env()
    if not os.environ.get("MINIMAX_API_KEY"):
        print("[ERR] MINIMAX_API_KEY 未配置")
        return

    if args.episode:
        spec_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "storyboard",
            f"{args.episode}_storyboard.json"))
        out_dir = args.out_dir or os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..",
            "output", args.episode, "audio"))
        print(f"[audio] 批量配音 {args.episode}")
        manifest = gen_episode_audio(spec_path, out_dir, limit=args.limit, log=lambda m: print(m))
        print(f"[audio] 完成，共 {len(manifest)} 段")
        return

    if args.demo:
        lines = [
            ("female-shaonv", "林小满，今天是你入职第一天。"),
            ("female-shaonv", "收到，主管。"),
            ("male-qn-jingying", "本司提倡准点下班，拒绝无效加班。"),
            ("male-qn-qingse", "效率拉满，准时走人。"),
            ("female-shaonv", "这届新人有点东西！"),
        ]
        for i, (v, txt) in enumerate(lines, 1):
            out = f"demo_{i}.mp3"
            print(f"[{i}/{len(lines)}] voice={v}")
            tts(txt, voice_id=v, out_path=out)
            print(f"   -> {out}")
        print("✓ 多角色 demo 完成")
        return

    if args.text:
        out = args.out or "minimax_test.mp3"
        _load_env()
        mp3 = tts(args.text, voice_id=args.voice, out_path=out)
        print(f"✓ {out} ({len(mp3)//1024}KB, voice={args.voice or DEFAULT_VOICE})")
        return

    # 默认：连通性自检
    _load_env()
    mp3 = tts("你好老板，这是 MiniMax 语音合成测试。")
    print(f"✓ 自检通过，测试音频 {len(mp3)//1024}KB")


if __name__ == "__main__":
    main()
