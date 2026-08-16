# -*- coding: utf-8 -*-
"""通用 JSON 文件读写封装（全局锁 + 原子写，防并发损坏）。

对应方案书 §5.3 的"使用全局文件锁串行化对 reads.json 的读写"。
"""
import json
import os
import tempfile
import threading
import time

_lock = threading.RLock()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _path(name):
    from app.config import DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, name)


def read_json(name, default):
    """读取 JSON；文件不存在或非法返回 default 并备份损坏文件。"""
    with _lock:
        p = _path(name)
        if not os.path.isfile(p):
            return default
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            backup = p + ".corrupt"
            try:
                os.replace(p, backup)
            except OSError:
                pass
            return default


def write_json(name, data):
    """原子写：写临时文件后 os.replace，避免半截文件。"""
    with _lock:
        p = _path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        d = os.path.dirname(p)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
