#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 · 深度人脸一致性引擎：用 OpenCV YuNet(检测) + SFace(识别) 做 *真实身份* 度量。

为什么需要它：
    旧 face_qc.py 用「灰度 64x64 SSIM」猜一致性。SSIM 比的是像素结构相似度，
    对 *身份* 不敏感——两个脸型相近的不同人可能 SSIM 很高，同一个人换光/换角度就很低。
    影视一致性要的是「这镜里的人和角色参考图是不是同一个人」，这是 *身份* 问题，不是 *画质* 问题。

本模块提供 *身份级* 度量：
    1. identity_score(shot_face, anchor_face) = SFace 余弦相似度（>=0.363 判同一人，OpenCV 官方推荐）。
    2. 每个 shot 对其 ref_key 角色参考图(即 _ref_anchor)的身份分 → 判「脸对不对」。
    3. 同角色跨镜 pairwise 身份矩阵 → 判「串脸/跨镜漂移」。
    4. 自动纠偏建议：身份分低于阈值的 shot，给出 prompt 增强方向（参考图权重↑ / 负向词）。

依赖：opencv-python-headless>=4.11（含 contrib，FaceDetectorYN/FaceRecognizerSF 在 cv2 主模块）。
模型权重：models/face/yunet.onnx + models/face/sface.onnx（离线就绪）。
本文件沿用 face_qc.py 的方式把 venv site-packages 插 sys.path，使 server.py 可 import。
"""
import os, sys, json, subprocess, tempfile, statistics, threading, hashlib

# 关键：在 import cv2 之前钉死底层并行框架线程数。
# OpenCV dnn 调 ONNX 时内部走 OpenMP/TBB/MKL/OpenBLAS 的并行 FP 求和，
# 求和顺序随线程调度变化 → 同一张图每次嵌入不同 → 身份分抖动。
# 这些环境变量必须在 cv2 加载前设定才生效。
for _ev in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "TBB_NUM_THREADS",
            "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
            "TF_NUM_INTRAOP_THREADS", "TF_NUM_INTEROP_THREADS"):
    os.environ.setdefault(_ev, "1")

VENV_SITE = r"C:\Users\67972\.workbuddy\binaries\python\envs\default\Lib\site-packages"
if VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

# 关键：锁死 DNN 线程数，消除 OpenCV 多线程推理的非确定性（否则同一张图每次身份分抖动 0.7~0.98）
try:
    cv2.setNumThreads(0)
    cv2.dnn.setNumThreads(1)
except Exception:
    pass

FFMPEG = r"C:\Users\67972\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(ROOT, "models", "face")
YUNET_PATH = os.path.join(MODEL_DIR, "yunet.onnx")
SFACE_PATH = os.path.join(MODEL_DIR, "sface.onnx")

# 身份阈值（SFace 余弦相似度）
SFACE_SAME = 0.363          # OpenCV 官方「同一人」判据
TH_WARN = 0.40              # 低于此 → 需注意（参考图权重可能不足）
TH_FAIL = 0.30              # 低于此 → 明确失败（疑似串脸/脸不对）
CROSS_WARN = 0.45           # 同角色跨镜 pairwise 低于此 → 跨镜漂移


# ---------- 结果缓存：按「资产签名」命中，使同资产跨进程/跨重启分数完全一致且免重复推理 ----------
def _file_sig(path):
    """轻量文件签名：文件名+大小+修改时间。资产不变则签名不变。"""
    if not path or not os.path.isfile(path):
        return None
    st = os.stat(path)
    return f"{os.path.basename(path)}|{st.st_size}|{int(st.st_mtime)}"


def _cache_path(project_dir):
    return os.path.join(project_dir, ".faceid_cache.json")


def _load_cache(project_dir):
    p = _cache_path(project_dir)
    if os.path.isfile(p):
        try:
            c = json.load(open(p, encoding="utf-8"))
            c.setdefault("shots", {})
            c.setdefault("anchors", {})
            return c
        except Exception:
            pass
    return {"shots": {}, "anchors": {}}


def _save_cache(project_dir, cache):
    try:
        json.dump(cache, open(_cache_path(project_dir), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e:
        print(f"[face_identity] cache 写入失败: {e}", file=sys.stderr)

_DET = None
_REC = None
_MODELS_LOADED = False
_INF_LOCK = threading.Lock()  # 共享 DNN 模型非线程安全，推理加锁防服务端并发竞态抖分


def load_models(force=False):
    """惰性加载 YuNet 检测器 + SFace 识别器（全局缓存）。返回 (detector, recognizer) 或 None。"""
    global _DET, _REC, _MODELS_LOADED
    if _MODELS_LOADED and not force:
        return _DET, _REC
    _MODELS_LOADED = True
    if not (os.path.isfile(YUNET_PATH) and os.path.isfile(SFACE_PATH)):
        print(f"[face_identity] 模型缺失: {YUNET_PATH} / {SFACE_PATH}", file=sys.stderr)
        return None, None
    try:
        _DET = cv2.FaceDetectorYN.create(YUNET_PATH, "", (320, 320), 0.6, 0.3, 5000)
        _REC = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
        print("[face_identity] 模型加载 OK (YuNet + SFace)", file=sys.stderr)
        # 冷启动 warmup：先跑一次空推理，消除首次调用的线程/缓存抖动（否则第 1 次打分与后续不一致）
        try:
            _DET.setInputSize((64, 64))
            _DET.detect(np.zeros((64, 64, 3), dtype=np.uint8))
        except Exception:
            pass
        return _DET, _REC
    except Exception as e:
        print(f"[face_identity] 模型加载失败: {e}", file=sys.stderr)
        _DET, _REC = None, None
        return None, None


def _extract_frame(video, t, out_path, width=320):
    # 精确 seek：-ss 放在 -i 之后（从开头解码到 t），保证每次抽到同一帧，避免快进跳帧导致的身份分抖动
    r = subprocess.run([FFMPEG, "-y", "-i", video, "-ss", f"{t:.2f}", "-frames:v", "1",
                        "-vf", f"scale={width}:-1", "-q:v", "3", out_path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return os.path.isfile(out_path)


def _imread(path):
    """Windows 上 cv2.imread 对中文/非 ASCII 路径会静默失败，改用 imdecode 读字节绕过。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            data = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _detect_largest(img):
    """YuNet 检测最大人脸，返回 (bbox[x,y,w,h], score) 或 None。img 为 BGR。
    OpenCV YuNet.detect() 返回 (retval, faces)；faces 为 (N,15) 或 (0,15)/None。"""
    global _DET
    if _DET is None:
        return None
    h, w = img.shape[:2]
    _DET.setInputSize((w, h))
    results = _DET.detect(img)
    faces = results[1] if isinstance(results, tuple) else results
    if faces is None or (hasattr(faces, "shape") and faces.shape[0] == 0):
        return None
    # 取置信度最高的人脸（第 15 维为 score）
    best = max(faces, key=lambda d: d[14] if faces.shape[1] > 14 else 0)
    x, y, bw, bh = [int(v) for v in best[:4]]
    score = float(best[14]) if faces.shape[1] > 14 else 1.0
    return (x, y, bw, bh), score


def get_embedding(source, is_path=False):
    """从图像(BGR ndarray)或图片路径提取 SFace 身份嵌入。无脸返回 (None, None)。
    返回 (feature_vector[1,N], bbox)。feature_vector 用于 pairwise 余弦相似度。"""
    global _REC
    if _REC is None:
        return None, None
    img = _imread(source) if is_path else source
    if img is None:
        return None, None
    with _INF_LOCK:
        det = _detect_largest(img)
        if det is None:
            return None, None
        (x, y, bw, bh), score = det
        x, y = max(0, x), max(0, y)
        try:
            # alignCrop 吃 YuNet 完整检测行(含 5 点 landmarks)，直接传 best 行
            aligned = _REC.alignCrop(img, np.array([x, y, bw, bh, score], dtype=np.float32))
            feat = _REC.feature(aligned)
            return feat, (x, y, bw, bh)
        except Exception as e:
            print(f"[face_identity] align/feature 失败: {e}", file=sys.stderr)
            return None, None


def identity_similarity(feat_a, feat_b):
    """两个 SFace 嵌入的余弦相似度（0~1，越高越像）。任一为 None 返回 None。"""
    global _REC
    if feat_a is None or feat_b is None or _REC is None:
        return None
    return float(_REC.match(feat_a, feat_b, cv2.FaceRecognizerSF_FR_COSINE))


def _video_duration(video):
    try:
        pr = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", video],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return float(pr.stdout.strip() or 0)
    except Exception:
        return 0.0


def score_project(project_dir, storyboard=None, use_video_frames=True, prefer_video=False,
                   votes=3):
    """对整集做身份一致性打分。
    project_dir: 项目根（含 storyboard.json + assets/）。
    storyboard: dict 或路径；缺省读 project_dir/storyboard.json。
    返回：
      ok / error
      per_shot   [{shot, ref_key, has_face, identity, face_ok, source}]
      cross      [{a, b, ref_key, identity}]  同角色相邻镜 pairwise
      overall    {min_identity, avg_identity, worst_shot, identity_pass_rate}
      issues     [{shot, type, detail, value}]
      thresholds
    """
    if storyboard is None:
        sb_path = os.path.join(project_dir, "storyboard.json")
        if not os.path.isfile(sb_path):
            return {"ok": False, "error": f"无 storyboard: {sb_path}"}
        storyboard = json.load(open(sb_path, encoding="utf-8"))
    elif isinstance(storyboard, str) and os.path.isfile(storyboard):
        storyboard = json.load(open(storyboard, encoding="utf-8"))

    load_models()
    if _DET is None or _REC is None:
        return {"ok": False, "error": "SFace/YuNet 模型不可用"}

    shots = storyboard.get("shots", [])
    refs = storyboard.get("references", {})
    if not shots:
        return {"ok": False, "error": "无 shots"}

    cache = _load_cache(project_dir)

    # 预提取各角色参考图嵌入（带缓存，按文件签名命中）
    anchor_feats = {}
    anchor_meta = {}
    for rk, rv in refs.items():
        img_path = rv.get("image", "")
        abs_p = os.path.join(project_dir, img_path) if img_path else ""
        sig = _file_sig(abs_p)
        cached_a = cache.get("anchors", {}).get(rk)
        if sig and cached_a and cached_a.get("sig") == sig and cached_a.get("feat"):
            anchor_feats[rk] = np.array(cached_a["feat"], dtype=np.float32)
            anchor_meta[rk] = {"bbox": cached_a.get("bbox"), "src": img_path}
        elif abs_p and os.path.isfile(abs_p):
            feat, bbox = get_embedding(abs_p, is_path=True)
            if feat is not None:
                anchor_feats[rk] = feat
                anchor_meta[rk] = {"bbox": bbox, "src": img_path}
                cache.setdefault("anchors", {})[rk] = {"sig": sig, "feat": feat.tolist(),
                                                       "bbox": (list(bbox) if bbox else None), "src": img_path}

    tmp = tempfile.mkdtemp(prefix="faceid_")
    per_shot = []
    shot_feats = {}  # sid -> (feat, ref_key)
    issues = []

    # 每镜多帧投票 + 结果缓存：关键帧 + 成片若干抽帧，取中位数身份分。
    # 缓存按「资产签名」命中 —— 同资产跨进程/跨重启分数 100% 一致，且免重复推理。
    for sc in shots:
        sid = sc.get("id")
        rk = sc.get("ref_key") or (sc.get("characters") or [None])[0]
        kf = sc.get("asset_frame_start") or ""
        vid = sc.get("asset_video") or ""
        kf_sig = _file_sig(os.path.join(project_dir, kf)) if kf else None
        vid_sig = _file_sig(os.path.join(project_dir, vid)) if vid else None
        a_sig = cache.get("anchors", {}).get(rk, {}).get("sig") if rk in anchor_feats else None
        shot_key = f"{kf_sig}|{vid_sig}|{rk}|{a_sig}"
        cached_s = cache.get("shots", {}).get(str(sid))
        if cached_s and cached_s.get("key") == shot_key and cached_s.get("feat"):
            identity = cached_s["identity"]
            per_shot.append({"shot": sid, "ref_key": rk, "has_face": True,
                             "identity": identity, "face_ok": identity >= TH_WARN,
                             "votes": cached_s.get("votes", 0), "source": cached_s.get("source", "cached")})
            shot_feats[sid] = (np.array(cached_s["feat"], dtype=np.float32), rk)
        else:
            candidates = []  # (img, src)
            if kf and os.path.isfile(os.path.join(project_dir, kf)):
                candidates.append((_imread(os.path.join(project_dir, kf)), f"keyframe:{kf}"))
            if vid and os.path.isfile(os.path.join(project_dir, vid)):
                dur = _video_duration(os.path.join(project_dir, vid))
                for frac in (0.25, 0.5, 0.75):
                    ft = os.path.join(tmp, f"s{sid}_{int(frac*100)}.jpg")
                    _extract_frame(os.path.join(project_dir, vid), max(0.1, dur * frac), ft)
                    if os.path.isfile(ft):
                        candidates.append((_imread(ft), f"videoframe:{vid}@{frac}"))
            if not candidates:
                per_shot.append({"shot": sid, "ref_key": rk, "has_face": False,
                                 "identity": None, "face_ok": None, "source": "no-image"})
                cache.setdefault("shots", {})[str(sid)] = {"key": shot_key, "identity": None,
                                                           "has_face": False, "votes": 0, "source": "no-image"}
                continue
            sims, feats = [], []
            for img, src in candidates:
                if img is None:
                    continue
                feat, _ = get_embedding(img)
                if feat is not None and rk in anchor_feats:
                    sims.append(identity_similarity(feat, anchor_feats[rk]))
                    feats.append((feat, src))
            if not sims:
                per_shot.append({"shot": sid, "ref_key": rk, "has_face": False,
                                 "identity": None, "face_ok": None, "source": candidates[0][1]})
                issues.append({"shot": sid, "type": "no_face", "detail": "该镜未检出人脸(可能侧脸/CG风格化)", "value": None})
                cache.setdefault("shots", {})[str(sid)] = {"key": shot_key, "identity": None,
                                                           "has_face": False, "votes": 0, "source": candidates[0][1]}
                continue
            sim_med = round(statistics.median(sims), 3)
            per_shot.append({"shot": sid, "ref_key": rk, "has_face": True,
                             "identity": sim_med, "face_ok": sim_med >= TH_WARN,
                             "votes": len(sims), "source": feats[0][1]})
            if feats:
                shot_feats[sid] = (feats[0][0], rk)
                cache.setdefault("shots", {})[str(sid)] = {"key": shot_key, "identity": sim_med,
                                                           "has_face": True, "votes": len(sims),
                                                           "source": feats[0][1], "feat": feats[0][0].tolist()}
        # 判脸对错（基于中位数）
        cur = per_shot[-1]
        if cur.get("identity") is None:
            continue
        sim_med = cur["identity"]
        if rk not in anchor_feats:
            issues.append({"shot": sid, "type": "no_anchor", "detail": f"角色 {rk} 无参考图锚点", "value": None})
        elif sim_med < TH_FAIL:
            issues.append({"shot": sid, "type": "face_mismatch", "detail": f"与角色 {rk} 参考图身份不符(疑似串脸/脸不对)", "value": sim_med})
        elif sim_med < TH_WARN:
            issues.append({"shot": sid, "type": "face_weak", "detail": f"与角色 {rk} 参考图身份偏弱，建议加强参考图权重", "value": sim_med})

    _save_cache(project_dir, cache)

    # 跨镜 pairwise（同角色相邻镜）
    cross = []
    by_char = {}
    for sid, (feat, rk) in shot_feats.items():
        by_char.setdefault(rk, []).append((sid, feat))
    for rk, lst in by_char.items():
        lst.sort(key=lambda x: x[0])
        for i in range(1, len(lst)):
            a_sid, a_feat = lst[i - 1]
            b_sid, b_feat = lst[i]
            sim = identity_similarity(a_feat, b_feat)
            cross.append({"a": a_sid, "b": b_sid, "ref_key": rk, "identity": round(sim, 3)})
            if sim < CROSS_WARN:
                issues.append({"shot": b_sid, "type": "cross_drift",
                               "detail": f"角色 {rk} 镜#{a_sid}→#{b_sid} 跨镜身份漂移",
                               "value": round(sim, 3)})

    scored = [p for p in per_shot if p.get("identity") is not None]
    overall = {
        "min_identity": round(min(p["identity"] for p in scored), 3) if scored else None,
        "avg_identity": round(sum(p["identity"] for p in scored) / len(scored), 3) if scored else None,
        "worst_shot": min(scored, key=lambda p: p["identity"])["shot"] if scored else None,
        "identity_pass_rate": round(sum(1 for p in scored if p["face_ok"]) / max(1, len(scored)), 3),
    }

    return {
        "ok": True,
        "per_shot": per_shot,
        "cross": cross,
        "overall": overall,
        "issues": issues,
        "anchors": {rk: anchor_meta.get(rk, {}).get("src") for rk in anchor_feats},
        "thresholds": {"sface_same": SFACE_SAME, "warn": TH_WARN, "fail": TH_FAIL, "cross_warn": CROSS_WARN},
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="项目根目录")
    ap.add_argument("--storyboard", default=None)
    args = ap.parse_args()
    print(json.dumps(score_project(args.project, storyboard=args.storyboard), ensure_ascii=False, indent=2))
