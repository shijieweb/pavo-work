#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
截图识别工具：把本地图片发送给视觉模型，返回图片内容描述。
引擎（老板 0811 实测对比）：AGNES agnes-2.5-flash 优先（免费 3000 次/天、输出 5 段结构化
+自带瑕疵/质量评估），失败自动回退 MiniMax M3。
用途：老板截图发我排障时，我用它"看图"（本助手后端为纯文本模型，需借视觉模型识别）。

用法：
    python read_screenshot.py <图片路径> [追问提示词] [--engine agnes|minimax|auto]
示例：
    python read_screenshot.py /tmp/boss_screenshot.png "详细描述界面上的所有元素、文字、按钮和状态，用于排查问题"
"""
import base64, json, os, sys, urllib.request

DEFAULT_BASE = "https://api.minimaxi.com/v1/chat/completions"
# M3 原生多模态；若不可用可换 MiniMax-VL-01
MODELS = ["MiniMax-M3", "MiniMax-VL-01", "MiniMax-VL-02"]


def _load_env():
    """从 ~/.workbuddy/.env 读 MINIMAX_API_KEY / MINIMAX_GROUP_ID（若未在环境变量）"""
    if not (os.environ.get("MINIMAX_API_KEY") and os.environ.get("MINIMAX_GROUP_ID")):
        env_path = os.path.expanduser("~/.workbuddy/.env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k in ("MINIMAX_API_KEY", "MINIMAX_GROUP_ID") and not os.environ.get(k):
                            os.environ[k] = v


def _img_to_datauri(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
    return f"data:{mime};base64,{b64}"


def _agnes(path, question):
    """AGNES agnes-2.5-flash 视觉识别（免费 3000 次/天）。失败返回 None（触发回退）。"""
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        import agnes_client as ac
        return ac.chat(question, images=[_img_to_datauri(path)], model="agnes-2.5-flash",
                       temperature=0.2, max_tokens=1200, timeout=120)
    except Exception as e:
        print("AGNES 识别失败: %s" % str(e)[:150], file=sys.stderr)
        return None


def _minimax(path, question):
    """MiniMax M3 视觉识别（兜底）。"""
    _load_env()
    key = os.environ.get("MINIMAX_API_KEY")
    gid = os.environ.get("MINIMAX_GROUP_ID")
    if not key or not gid:
        print("缺少 MINIMAX_API_KEY / MINIMAX_GROUP_ID（~/.workbuddy/.env）", file=sys.stderr)
        return None
    if not os.path.exists(path):
        print(f"图片不存在: {path}", file=sys.stderr)
        return None
    payload = {
        "model": MODELS[0],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": _img_to_datauri(path)}},
            ],
        }],
        "max_tokens": 1200,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Group-Id": gid,
    }
    last_err = None
    for model in MODELS:
        payload["model"] = model
        try:
            req = urllib.request.Request(DEFAULT_BASE, data=json.dumps(payload).encode("utf-8"),
                                         headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode("utf-8"))
            choices = j.get("choices") or []
            if choices and choices[0].get("message"):
                return choices[0]["message"].get("content") or "(空回复)"
            last_err = f"模型 {model} 无有效回复: {str(j)[:200]}"
        except Exception as e:
            last_err = f"模型 {model} 失败: {e}"
            continue
    print(f"全部视觉模型失败: {last_err}", file=sys.stderr)
    return None


def recognize(path, question="请详细描述这张图片的内容：界面元素、文字、按钮、状态、报错信息等，用于排查软件问题。",
              engine="auto"):
    """AGNES 优先（免费+结构化），失败回退 MiniMax。engine: agnes|minimax|auto"""
    if not os.path.exists(path):
        print(f"图片不存在: {path}", file=sys.stderr)
        return None
    if engine in ("agnes", "auto"):
        try:
            out = _agnes(path, question)
            if out:
                return out
        except Exception as e:
            print("AGNES 识别失败: %s" % e, file=sys.stderr)
        if engine == "agnes":
            return None
    return _minimax(path, question)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python read_screenshot.py <图片路径> [追问提示词] [--engine agnes|minimax|auto]", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    args = sys.argv[2:]
    engine = "auto"
    if "--engine" in args:
        i = args.index("--engine")
        if i + 1 < len(args):
            engine = args[i + 1]
        args = args[:i] + args[i + 2:]
    q = " ".join(args) if args else None
    out = recognize(path, q, engine) if q else recognize(path, engine=engine)
    if out:
        print(out)
