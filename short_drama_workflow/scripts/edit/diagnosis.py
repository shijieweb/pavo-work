#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断语义引擎（AGNES 文本多模态替代 MiniMax M3）。

把成片均匀抽 N 帧，base64 喂给 agnes-2.0-flash（已实测可吃图），
按 rubric 要求 JSON 返回 4 维语义评分：
  - continuity    连续性（动作/镜头衔接是否连贯）
  - physical      物理合理性（是否符合物理规律）
  - character     人物一致性（同一角色脸/服饰/体型跨帧稳定）
  - first_last    首尾帧衔接（首末帧是否自然、无跳变）
每维 0-10 分 + 理由；overall 加权 + verdict(pass/fail) + summary。

用法：
  python diagnosis.py --video path/to/final.mp4 --frames 4
"""
import os, sys, json, base64, subprocess, tempfile, re, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from quality_check import FFMPEG, run  # 复用 ffmpeg 路径

AGNES_SCRIPTS = os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts")
DEFAULT_MODEL = os.environ.get("AGNES_TEXT_MODEL", "agnes-2.5-flash")
FRAME_W = 480  # 抽帧缩放宽度，控制 base64 大小

DEFAULT_RUBRIC = """你是一位严格的竖屏短剧成片质检专家。下面是一段短剧视频均匀抽取的若干帧（按时间顺序）。
请从以下 4 个语义维度逐维打分（0-10，10 为最佳），并给每维一句中文理由：
1. continuity（连续性）：镜头/动作衔接是否连贯自然，有无突兀跳变或时序错乱。
2. physical（物理合理性）：画面是否符合基本物理规律（重力、遮挡、光影、人体结构），有无明显穿帮。
3. character（人物一致性）：同一角色的脸部、发型、服饰、体型在跨帧间是否稳定一致，有无变形/换脸/多人混脸。
4. first_last（首尾帧衔接）：首帧与末帧是否自然衔接、有无硬切/内容断层。
只输出一个 JSON 对象，不要任何额外解释，格式严格如下：
{
  "scores": {"continuity": <int>, "physical": <int>, "character": <int>, "first_last": <int>},
  "reasons": {"continuity": "<一句中文>", "physical": "<一句中文>", "character": "<一句中文>", "first_last": "<一句中文>"},
  "overall": <int 0-10>,
  "verdict": "pass" 或 "fail",
  "summary": "<不超过40字的中文总评>"
}"""


def extract_frames_even(video, n=4, out_dir=None, width=FRAME_W):
    """均匀抽 n 帧（含首末帧），缩放至 width，返回绝对路径列表。"""
    ffprobe = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
    out_dir = out_dir or tempfile.mkdtemp(prefix="diag_")
    os.makedirs(out_dir, exist_ok=True)
    probe = run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video])
    dur_s = probe.stdout.strip()
    try:
        dur = float(dur_s)
    except Exception:
        dur = 0.0
    # 避开首尾淡入淡出：末帧取 dur 会 seek 到 EOF 抽不出图（实测 n=4 只回 3 帧），
    # 且 t=0 常落在 fade-in 全黑帧上，导致 first_last 被误判。故内缩一个 margin。
    if dur <= 0:
        times = [i / max(n, 1) for i in range(n)]
    elif n == 1:
        times = [dur / 2]
    else:
        margin = min(0.5, dur * 0.05) if dur > 2 else 0.0
        lo, hi = margin, max(dur - margin, margin)
        times = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    frames = []
    for i, t in enumerate(times):
        out = os.path.join(out_dir, f"frame_{i:02d}.jpg")
        cmd = [FFMPEG, "-y", "-ss", f"{t:.2f}", "-i", video,
               "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "3", out]
        run(cmd)
        if os.path.isfile(out):
            frames.append(out)
    return frames


def extract_frames_smart(video, out_dir=None, width=FRAME_W, interval=0.5, tail_margin=0.2):
    """【0812 老板方法论】智能抽帧：首帧(0s)必抽 + 尾帧(duration-tail_margin)必抽 + 中段按 interval 秒间隔。
    相比 extract_frames_even 均匀抽帧：之前 3.4s 视频抽 4 帧=0.4/1.1/1.8/2.5s，首尾根本没抽到，
    导致 intro_flash/尾帧脸型要单独抽帧。本函数保证两端覆盖 + 中段细节。返回 [(path, t), ...]。"""
    ffprobe = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
    out_dir = out_dir or tempfile.mkdtemp(prefix="diag_")
    os.makedirs(out_dir, exist_ok=True)
    probe = run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video])
    dur_s = probe.stdout.strip()
    try:
        dur = float(dur_s)
    except Exception:
        dur = 0.0
    if dur <= 0:
        return []
    # 时间点：首帧 0 必抽；尾帧 dur-tail_margin 必抽（避开 EOF 抽不出）；中段按 interval
    times = [0.0]
    t = interval
    while t < dur - tail_margin - 1e-6:
        times.append(t)
        t += interval
    if dur - tail_margin > 0:
        times.append(max(dur - tail_margin, times[-1] + 0.05) if times else dur - tail_margin)
    # 去重+排序
    times = sorted(set(round(x, 2) for x in times))
    frames = []
    for i, t in enumerate(times):
        out = os.path.join(out_dir, f"frame_{i:02d}.jpg")
        cmd = [FFMPEG, "-y", "-ss", f"{t:.2f}", "-i", video,
               "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "3", out]
        run(cmd)
        if os.path.isfile(out):
            frames.append((out, t))
    return frames


def b64_image(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8", "ignore")


def _extract_json(text):
    """从模型文本里抠出第一个 {...} JSON 块（兼容 ```json 围栏与前后多余文字）。"""
    if not text:
        return None
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
    if m:
        t = m.group(1)
    else:
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e != -1 and e > s:
            t = t[s:e + 1]
    try:
        return json.loads(t)
    except Exception:
        return None


def diagnose_clip(video, rubric=None, n_frames=4, model=DEFAULT_MODEL, out_dir=None,
                 face_check=False, storyboard=None, deep=False):
    """端到端：抽帧 -> AGNES 多模态 -> 解析 4 维语义评分；可选 face_check 叠加人脸客观质检。返回 dict。
    0812 老板方法论：抽帧改 smart（首帧0s必抽 + 尾帧必抽 + 中段按0.5s间隔）——均匀抽帧漏首尾。"""
    # smart 抽帧返回 [(path, t), ...]；兼容旧返回纯 path 列表
    _smart = extract_frames_smart(video, out_dir=out_dir)
    frames = [p for p, _t in _smart] if _smart else []
    if not frames:
        return {"ok": False, "error": "抽帧失败（ffmpeg/视频不可用）", "video": video}
    imgs = [b64_image(f) for f in frames]
    sys.path.insert(0, AGNES_SCRIPTS)
    from agnes_client import chat
    prompt = rubric or DEFAULT_RUBRIC
    try:
        raw = chat(prompt, images=imgs, model=model)
    except Exception as e:
        return {"ok": False, "error": f"AGNES 调用失败: {e}", "frames": len(frames)}
    parsed = _extract_json(raw)
    if parsed is None:
        return {"ok": True, "parsed": False, "raw": raw[:800], "frames": len(frames),
                "scores": {}, "verdict": "unknown", "summary": "AGNES 未返回可解析 JSON"}
    parsed["ok"] = True
    parsed["parsed"] = True
    parsed["frames"] = len(frames)
    parsed["model"] = model
    parsed.setdefault("scores", {})
    parsed.setdefault("verdict", "unknown")
    if face_check:
        try:
            sys.path.insert(0, HERE)
            from face_qc import qc_video
            fc = qc_video(video, storyboard=storyboard, use_deep=deep)
            parsed["face"] = fc
            if fc.get("ok"):
                fscore = int(fc.get("face_score", 10))
                qscore = int(fc.get("quality_score", 10))
                parsed["scores"]["face"] = fscore
                parsed["scores"]["quality"] = qscore
                vals = [v for v in parsed["scores"].values() if isinstance(v, (int, float))]
                if vals:
                    parsed["overall"] = round(sum(vals) / len(vals))
                qc_bad = fc.get("qc_bad") or fc.get("face_bad")
                face_issues = [i for i in fc.get("issues", []) if i.get("type") in ("intra_jump", "cross_drift")]
                qual_issues = [i for i in fc.get("issues", []) if i.get("type") not in ("intra_jump", "cross_drift")]
                if qc_bad:
                    parsed["verdict"] = "fail"
                    tags = []
                    if face_issues:
                        tags.append("疑似换脸/跳变")
                    if qual_issues:
                        tags.append("画质缺陷(模糊/曝光/噪声)")
                    summary = (parsed.get("summary") or "")
                    parsed["summary"] = (summary + " [人脸客观质检:" + "、".join(tags) + "]")[:40]
                parsed["face_quality_detail"] = {
                    "face_score": fscore, "quality_score": qscore,
                    "qc_score": fc.get("qc_score"),
                    "quality_summary": fc.get("quality"),
                    "per_shot": fc.get("per_shot"),
                }
            else:
                parsed.setdefault("warnings", []).append("face_check: " + str(fc.get("error", "failed")))
        except Exception as e:
            parsed.setdefault("warnings", []).append(f"face_check失败: {e}")
    return parsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = diagnose_clip(args.video, n_frames=args.frames, model=args.model, out_dir=args.out)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
