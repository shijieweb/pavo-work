#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地完成通知（O2）：长任务（选题→成片 ~473s）完成/失败提醒。

- 主通道：追加写入 output/notifications.jsonl（本地持久、可查）。
- 可选：NOTIFY_WEBHOOK 环境变量 → POST 到该地址（如老板自建接收端）。
- 尽力而为：Windows 桌面气球提示（BurntToast 模块存在才弹，否则静默）。
本地-only，不依赖任何外部 SaaS。
"""
import os, json, time, urllib.request

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "output"))
NOTIFY_FILE = os.path.join(OUT_DIR, "notifications.jsonl")


def notify(title, message, level="info"):
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "title": title,
           "message": message, "level": level}
    # 1) 本地 JSONL 日志（始终）
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(NOTIFY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # 2) 可选 webhook
    wh = os.environ.get("NOTIFY_WEBHOOK")
    if wh:
        try:
            req = urllib.request.Request(wh, data=json.dumps(rec).encode("utf-8"), method="POST")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
    # 3) 尽力而为的 Windows 桌面提示（BurntToast 模块存在才弹，否则静默）
    try:
        import subprocess
        ps = ('powershell -NoProfile -Command "'
              'if (Get-Module -ListAvailable -Name BurntToast) {'
              "Import-Module BurntToast; "
              "New-BurntToastNotification -Text '短剧工作流', '" + title + ": " + message + "'}}")
        subprocess.run(ps, shell=True, timeout=8, capture_output=True)
    except Exception:
        pass
    return rec


if __name__ == "__main__":
    print(notify("测试", "通知模块可用", "ok"))
