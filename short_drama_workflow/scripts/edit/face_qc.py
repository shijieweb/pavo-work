#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人脸画质客观质检：双维度客观指标，补 AGNES 主观诊断的方差。

维度一 · 一致性(consistency)：OpenCV haar cascade 检测人脸 bbox，裁剪后灰度 SSIM 量化
    跨镜相似度，判定镜内跳变(intra)与跨镜串脸(cross)。加 profile 侧脸级联兜底提升侧脸/CG 检出。

维度二 · 画质(quality)：不依赖人脸检测，对每镜抽帧计算
    - sharpness  清晰度：Laplacian 方差（越高越清晰）
    - brightness 曝光：平均亮度，越界判过曝/欠曝
    - noise      噪声：中值滤波残差方差（越低越干净）
    → 即使检测不到脸（CG/风格化角色），整帧画质仍可客观打分，补此前"全跳过"的坑。

输出（face_consistency / qc_video）：
  ok / error
  face_score   0-10（越高越一致；无脸视频默认 10 安全通过）
  face_bad     bool
  quality_score 0-10（画质综合分）
  qc_score     0-10（consistency+quality 综合，仅 qc_video 返回）
  issues       [{shot, type, detail, value}]
  per_shot     [{shot, has_face, intra_ssim, cross_ssim, quality:{sharpness,brightness,noise}, duration}]
  quality      {avg_sharpness, avg_brightness, max_noise, worst_shot}

依赖：opencv-python-headless==4.11.0.86（装在隔离 venv）。本文件顶部把 venv site-packages 插入
sys.path，使 server.py（managed python 3.13.12）可 import cv2，不污染用户全局环境。
"""
import os, sys, json, subprocess, tempfile, urllib.request

VENV_SITE = r"C:\Users\67972\.workbuddy\binaries\python\envs\default\Lib\site-packages"
if VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

FFMPEG = r"C:\Users\67972\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
HAAR_DIR = cv2.data.haarcascades
HAAR_FRONTAL = os.path.join(HAAR_DIR, "haarcascade_frontalface_default.xml")
HAAR_PROFILE = os.path.join(HAAR_DIR, "haarcascade_profileface.xml")

# 可选深度人脸检测（#89）：OpenCV Yunet DNN。需 opencv-contrib-python-headless + 模型权重，
# 离线默认缺失时自动回退 haar，功能不阻塞。
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_PATH = os.path.join(HAAR_DIR, "face_detection_yunet_2023mar.onnx")
_DEEP_DETECTOR = None   # None=未尝试, False=不可用, 否则为 Yunet 检测器实例
_DEEP_TRIED = False      # 避免每次抽帧都重试导入/下载

# 一致性阈值
INTRA_JUMP_TH = 0.50   # 同镜首末帧相似度低于此 → 疑似镜内换脸/跳变
CROSS_DRIFT_TH = 0.40  # 相邻人物镜首帧相似度低于此 → 疑似跨镜串脸

# 画质阈值
SHARPNESS_REF = 200.0   # Laplacian 方差参考值（对应画质分 10）
SHARPNESS_MIN = 40.0    # 低于此 → 模糊 issue（扣分上限 4）
BRIGHT_LO, BRIGHT_HI = 40.0, 210.0   # 曝光可接受亮度区间
NOISE_WARN = 600.0     # 噪声残差方差警告阈值（超过 → 噪点 issue，扣分上限 2）


def _extract_frame_at(video, t, out_path, width=320):
    r = subprocess.run([FFMPEG, "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", f"scale={width}:-1", "-q:v", "3", out_path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return os.path.isfile(out_path)


def _haar_faces(gray):
    """多尺度 + 兜底重试的 haar 人脸检测：覆盖正脸/侧脸/小脸/CG 风格。
    返回人脸 bbox 列表（空=未检出）。优先正脸级联，多 scaleFactor 扫描；
    次选侧脸级联（profile）补侧脸；最后放宽 minNeighbors 重试一次捞小脸/风格化脸。"""
    cands = []
    frontal = cv2.CascadeClassifier(HAAR_FRONTAL)
    for sf in (1.15, 1.3, 1.5):
        cands.append(frontal.detectMultiScale(gray, sf, 5))
    if os.path.isfile(HAAR_PROFILE):
        prof = cv2.CascadeClassifier(HAAR_PROFILE)
        for sf in (1.1, 1.3):
            cands.append(prof.detectMultiScale(gray, sf, 5))
    # 兜底：放宽 minNeighbors（更易误检但能捞风格化/CG 脸）
    cands.append(frontal.detectMultiScale(gray, 1.2, 3))
    if os.path.isfile(HAAR_PROFILE):
        cands.append(prof.detectMultiScale(gray, 1.2, 3))
    found = [f for f in cands if len(f) > 0]
    if not found:
        return []
    # 多组都命中时，取命中最多的一组，最大化召回
    return max(found, key=lambda f: len(f))


def _detect_face(img, deep=False):
    """返回最大人脸的灰度裁剪图（已 resize 到 64x64 便于比较），无脸返回 None。
    deep=True 优先用 Yunet DNN（检出率更高，覆盖更多姿态/CG），失败/缺失回退 haar 级联。"""
    if img is None:
        return None
    if deep:
        det = _load_yunet()
        if det is not None:
            f = _detect_face_deep(img, det)
            if f is not None:
                return f
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _haar_faces(gray)
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return cv2.resize(gray[y:y + h, x:x + w], (64, 64))


def _load_yunet(autodownload=True):
    """惰性加载 Yunet 深度检测器；缺 opencv-contrib 或权重时返回 None（调用方回退 haar）。
    用 _DEEP_TRIED 避免每次抽帧都重试导入/下载；返回 None 表示不可用（调用方判 `is not None`）。"""
    global _DEEP_DETECTOR, _DEEP_TRIED
    if _DEEP_TRIED:
        return _DEEP_DETECTOR if _DEEP_DETECTOR else None
    _DEEP_TRIED = True
    try:
        from cv2 import face as _cvface  # opencv-contrib-python-headless 才有
        if not os.path.isfile(YUNET_PATH):
            if not autodownload:
                return None
            print("[face_qc] 下载 Yunet 模型 ->", YUNET_PATH)
            urllib.request.urlretrieve(YUNET_URL, YUNET_PATH)
        if os.path.isfile(YUNET_PATH):
            _DEEP_DETECTOR = _cvface.createFaceDetector("YUNET", YUNET_PATH)
            return _DEEP_DETECTOR
    except Exception as e:
        print(f"[face_qc] Yunet 不可用（需 opencv-contrib + 联网）: {e}")
    _DEEP_DETECTOR = False  # 标记已尝试，避免重复报错
    return None


def _detect_face_deep(img, detector):
    """Yunet 检测最大人脸并返回 64x64 灰度裁剪；无脸返回 None。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    results = detector.detect(gray)
    if not results or results[0] is None or len(results[0]) == 0:
        return None
    dets = results[0]
    if dets.shape[0] == 0:
        return None
    x, y, w, h = [int(v) for v in dets[0][:4]]
    x, y = max(0, x), max(0, y)
    return cv2.resize(gray[y:y + h, x:x + w], (64, 64))


def _ssim(a, b):
    """简化 SSIM（结构相似度，0~1，1 为完全相同）。输入为 64x64 灰度图。"""
    if a is None or b is None:
        return None
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    mu_a, mu_b = a.mean(), b.mean()
    sig_a, sig_b = a.var(), b.var()
    sig_ab = ((a - mu_a) * (b - mu_b)).mean()
    c1, c2 = 0.01, 0.03
    num = (2 * mu_a * mu_b + c1) * (2 * sig_ab + c2)
    den = (mu_a ** 2 + mu_b ** 2 + c1) * (sig_a + sig_b + c2)
    if den == 0:
        return 1.0 if num == 0 else 0.0
    return float(np.clip(num / den, -1.0, 1.0))


def _frame_quality(img):
    """单帧画质指标：清晰度/曝光/噪声。img 为 BGR 或灰度图。"""
    if img is None:
        return None
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    gray = gray.astype(np.float64)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    median = cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float64)
    noise = float(np.var(gray - median))
    return {"sharpness": round(sharp, 1), "brightness": round(bright, 1), "noise": round(noise, 1)}


def _video_duration(video):
    try:
        pr = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", video],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return float(pr.stdout.strip() or 0)
    except Exception:
        return 0.0


def _quality_issue(shot, q):
    """单镜画质返回 issue（或 None）。"""
    if q is None:
        return None
    if q["sharpness"] < SHARPNESS_MIN:
        return {"shot": shot, "type": "blurry", "detail": "画面模糊（清晰度不足）",
                "value": q["sharpness"]}
    if q["brightness"] > BRIGHT_HI:
        return {"shot": shot, "type": "over_exposed", "detail": "画面过曝（亮度过高）",
                "value": q["brightness"]}
    if q["brightness"] < BRIGHT_LO:
        return {"shot": shot, "type": "under_exposed", "detail": "画面欠曝（亮度过低）",
                "value": q["brightness"]}
    if q["noise"] > NOISE_WARN:
        return {"shot": shot, "type": "noisy", "detail": "画面噪点明显", "value": q["noise"]}
    return None


def _quality_score(shots_q):
    """由每镜画质列表汇总综合画质分 0-10。"""
    if not shots_q:
        return 10
    worst_sharp = min(q["sharpness"] for q in shots_q if q)
    avg_bright = sum(q["brightness"] for q in shots_q if q) / max(1, len([q for q in shots_q if q]))
    max_noise = max((q["noise"] for q in shots_q if q), default=0)
    q = 10.0
    if worst_sharp < SHARPNESS_MIN:
        q -= min(4.0, (SHARPNESS_MIN - worst_sharp) / SHARPNESS_MIN * 4.0)
    if avg_bright > BRIGHT_HI or avg_bright < BRIGHT_LO:
        q -= 2.0
    if max_noise > NOISE_WARN:
        q -= 2.0
    return int(max(0, min(10, round(q))))


def face_consistency(video, storyboard=None, fps=24, use_deep=False):
    """video: 成片路径；storyboard: dict 或 json 路径（含 shots[{id,duration}]）。

    按 shot 顺序累计时间线（考虑转场压缩：用成片总时长缩放每镜时长），抽每镜首/末帧，
    检测人脸比较 intra/cross SSIM（一致性），并对整帧计算清晰度/曝光/噪声（画质）。
    """
    if isinstance(storyboard, str) and os.path.isfile(storyboard):
        try:
            storyboard = json.load(open(storyboard, encoding="utf-8"))
        except Exception:
            storyboard = None
    shots = (storyboard or {}).get("shots", [])
    if not os.path.isfile(video):
        return {"ok": False, "error": f"视频不存在: {video}"}

    dur_s = _video_duration(video)
    total_plan = sum(float(s.get("duration", 5)) for s in shots) or 1.0
    scale = (dur_s / total_plan) if dur_s > 0 else 1.0

    tmp = tempfile.mkdtemp(prefix="faceqc_")
    per_shot = []
    issues = []
    prev_face = None
    prev_shot = None
    cum = 0.0
    shot_qs = []
    for sc in shots:
        sid = sc.get("id")
        d = float(sc.get("duration", 5)) * scale
        start, end = cum, cum + d
        cum = end
        inset = min(0.3, d * 0.2)
        t0 = start + inset
        t1 = max(t0, end - inset)
        p0 = os.path.join(tmp, f"s{sid}_0.jpg")
        p1 = os.path.join(tmp, f"s{sid}_1.jpg")
        _extract_frame_at(video, t0, p0)
        _extract_frame_at(video, t1, p1)
        i0 = cv2.imread(p0) if os.path.isfile(p0) else None
        i1 = cv2.imread(p1) if os.path.isfile(p1) else None
        f0 = _detect_face(i0, deep=use_deep)
        f1 = _detect_face(i1, deep=use_deep)
        intra = _ssim(f0, f1)
        cross = _ssim(f0, prev_face) if (prev_face is not None and f0 is not None) else None
        has_face = f0 is not None
        # 画质：两帧取较差（min sharpness / max noise / avg brightness）
        q0, q1 = _frame_quality(i0), _frame_quality(i1)
        q = None
        if q0 or q1:
            q = {
                "sharpness": min(q0["sharpness"] if q0 else 1e9, q1["sharpness"] if q1 else 1e9),
                "brightness": ((q0["brightness"] if q0 else 0) + (q1["brightness"] if q1 else 0)) / max(1, (q0 is not None) + (q1 is not None)),
                "noise": max(q0["noise"] if q0 else 0, q1["noise"] if q1 else 0),
            }
            q["sharpness"] = round(q["sharpness"], 1)
            q["brightness"] = round(q["brightness"], 1)
            q["noise"] = round(q["noise"], 1)
        per_shot.append({"shot": sid, "has_face": has_face,
                         "intra_ssim": round(intra, 3) if intra is not None else None,
                         "cross_ssim": round(cross, 3) if cross is not None else None,
                         "quality": q,
                         "duration": round(d, 2)})
        if q:
            shot_qs.append(q)
            qi = _quality_issue(sid, q)
            if qi:
                issues.append(qi)
        if has_face and f1 is not None and intra is not None and intra < INTRA_JUMP_TH:
            issues.append({"shot": sid, "type": "intra_jump",
                           "detail": "同镜首末帧人脸突变(疑似镜内换脸)", "ssim": round(intra, 3)})
        if cross is not None and cross < CROSS_DRIFT_TH:
            issues.append({"shot": sid, "type": "cross_drift",
                           "detail": f"与上一人物镜#{prev_shot} 人脸差异过大(疑似串脸)",
                           "ssim": round(cross, 3)})
        if f0 is not None:
            prev_face, prev_shot = f0, sid

    face_score = 10 - min(10, len([i for i in issues if i["type"] in ("intra_jump", "cross_drift")]) * 3)
    quality_score = _quality_score(shot_qs)
    # 画质汇总
    if shot_qs:
        worst = min(shot_qs, key=lambda q: q["sharpness"])
        quality_summary = {
            "avg_sharpness": round(sum(q["sharpness"] for q in shot_qs) / len(shot_qs), 1),
            "avg_brightness": round(sum(q["brightness"] for q in shot_qs) / len(shot_qs), 1),
            "max_noise": round(max(q["noise"] for q in shot_qs), 1),
            "worst_shot": worst.get("shot") if "shot" in worst else per_shot[shot_qs.index(worst)]["shot"],
        }
    else:
        quality_summary = {"avg_sharpness": None, "avg_brightness": None, "max_noise": None, "worst_shot": None}

    return {
        "ok": True,
        "face_score": face_score,
        "face_bad": len([i for i in issues if i["type"] in ("intra_jump", "cross_drift")]) > 0,
        "quality_score": quality_score,
        "detector_used": ("yunet" if (use_deep and _DEEP_DETECTOR) else "haar"),
        "issues": issues,
        "per_shot": per_shot,
        "quality": quality_summary,
        "thresholds": {"intra_jump": INTRA_JUMP_TH, "cross_drift": CROSS_DRIFT_TH,
                       "sharpness_min": SHARPNESS_MIN, "bright": [BRIGHT_LO, BRIGHT_HI], "noise_warn": NOISE_WARN},
    }


def qc_video(video, storyboard=None, fps=24, use_deep=False):
    """完整 D 报告：一致性 + 画质综合，返回 qc_score（0-10）。诊断引擎优先调用。"""
    fc = face_consistency(video, storyboard=storyboard, fps=fps, use_deep=use_deep)
    if not fc.get("ok"):
        return fc
    fs = fc.get("face_score", 10)
    qs = fc.get("quality_score", 10)
    # 综合：一致性占 50%、画质占 50%（无脸视频一致性按满分计，避免误杀）
    qc = int(round((fs + qs) / 2.0))
    fc["qc_score"] = qc
    fc["qc_bad"] = (fs < 7) or (qs < 7)
    return fc


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--storyboard", default=None)
    ap.add_argument("--full", action="store_true", help="输出 qc_video 完整报告")
    args = ap.parse_args()
    fn = qc_video if args.full else face_consistency
    print(json.dumps(fn(args.video, storyboard=args.storyboard), ensure_ascii=False, indent=2))
