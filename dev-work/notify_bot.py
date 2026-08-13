#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notify_bot.py - 飞书自定义机器人推送（任务完成通知）

用法:
    python notify_bot.py "任务标题" "摘要内容"

凭证从 ~/.workbuddy/.env 读取（绝不写死在脚本/仓库）:
    FEISHU_WEBHOOK = https://open.feishu.cn/open-apis/bot/v2/hook/xxxx
    FEISHU_SECRET   = （可选）开启签名校验后拿到的 secret

实现说明:
    - 底层用 urllib 直连，配 ProxyHandler({}) 强制不走任何代理，
      并清掉进程代理环境变量（本机 AGNES 代理 127.0.0.1:10808 会劫持
      open.feishu.cn 返回 404；Windows 上 curl 还会读系统 WinHTTP 代理，
      所以 curl 子进程方案不稳，改用已实测返回 code:0 的 urllib 直连）。
    - 支持可选签名校验（开启后更安全）；签名值做 URL 编码，避免 base64 中的
      '/'、'=' 被网关当路径分隔符导致 404。
    - 返回飞书 JSON：{"code":0,"msg":"success"} 即成功。
"""
import sys
import os
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import urllib.request

ENV_FILE = os.path.expanduser("~/.workbuddy/.env")

# 强制不走代理：清掉所有可能存在的代理环境变量
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
    os.environ.pop(_k, None)


def get_env(key: str) -> str:
    """从 .env 读取键值；读不到再回落到进程环境变量。"""
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(key + "="):
                    val = line[len(key) + 1:].strip()
                    return val.strip('"').strip("'")
    except FileNotFoundError:
        pass
    return os.environ.get(key, "")


def main() -> int:
    title = sys.argv[1] if len(sys.argv) > 1 else "任务完成通知"
    content = sys.argv[2] if len(sys.argv) > 2 else "（无摘要）"

    webhook = get_env("FEISHU_WEBHOOK")
    secret = get_env("FEISHU_SECRET")

    if not webhook:
        print(f"ERROR: FEISHU_WEBHOOK 未配置（应在 {ENV_FILE}）", file=sys.stderr)
        return 2

    text = f"{title}\n\n{content}"
    payload = json.dumps(
        {"msg_type": "text", "content": {"text": text}},
        ensure_ascii=False,
    ).encode("utf-8")

    url = webhook
    if secret:
        ts = str(int(time.time()))
        s = f"{ts}\n{secret}"
        # 飞书签名：HMAC-SHA256(key=string_to_sign, msg=b"")，base64
        sign = base64.b64encode(
            hmac.new(s.encode("utf-8"), b"", hashlib.sha256).digest()
        ).decode("utf-8")
        # 签名值含 '/'、'='，必须 URL 编码，否则网关按路径解析返回 404
        url = f"{url}?timestamp={urllib.parse.quote(ts)}&sign={urllib.parse.quote(sign)}"

    # urllib 直连，ProxyHandler({}) 强制不走代理
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with opener.open(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
        print(body)
        try:
            return 0 if json.loads(body).get("code") == 0 else 1
        except Exception:
            return 1
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode('utf-8', 'ignore')}",
              file=sys.stderr)
        return 1
    except Exception as e:
        print(f"PUSH ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
