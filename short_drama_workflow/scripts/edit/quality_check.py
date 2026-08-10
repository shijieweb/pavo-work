#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频质检（多项目通用）：技术合规 + 内容结构 双维度。

技术维度：黑场 / 静音 / 静帧 / 编码参数
内容维度：旁白/独白/字幕覆盖、人物镜人脸稳定约束覆盖、逐镜抽帧（按真实时长定位）

用法：
  python quality_check.py --storyboard projects/ep_0806_170153/storyboard.json \
                          --out projects/ep_0806_170153 --video projects/ep_0806_170153/final.mp4 --frames
"""
import os, json, subprocess, re, argparse

FFMPEG = r"C:\Users\67972\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
ROOT = r"C:\Users\67972\WorkBuddy\workbuddy\short_drama_workflow"
DEFAULT_SB = os.path.join(ROOT, "projects/ep_0806_170153/storyboard.json")
DEFAULT_OUT = os.path.join(ROOT, "projects/ep_0806_170153")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(video):
    r = run([FFPROBE, "-v", "error", "-show_entries",
             "format=duration,size,bit_rate:stream=width,height,codec_name,avg_frame_rate",
             "-of", "default=noprint_wrappers=1", video])
    info = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def detect_black(video):
    r = run([FFMPEG, "-i", video, "-vf", "blackdetect=d=0.3:pix_th=0.10",
             "-an", "-f", "null", "-"])
    return re.findall(r"black_start:([-\d.]+).*?black_end:([-\d.]+).*?black_duration:([-\d.]+)", r.stderr)


def detect_silence(video):
    r = run([FFMPEG, "-i", video, "-af", "silencedetect=n=-40dB:d=0.5", "-f", "null", "-"])
    starts = re.findall(r"silence_start: ([-\d.]+)", r.stderr)
    ends = re.findall(r"silence_end: ([-\d.]+)", r.stderr)
    return list(zip(starts, ends))


def detect_freeze(video):
    r = run([FFMPEG, "-i", video, "-vf", "freezedetect=d=1:n=0.005", "-an", "-f", "null", "-"])
    return re.findall(r"freeze_start: ([-\d.]+).*?freeze_end: ([-\d.]+).*?freeze_duration: ([-\d.]+)", r.stderr)


def extract_frames(video, shots, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cum = 0.0
    for s in shots:
        dur = s.get("duration", 5)
        for k, t in enumerate([cum + 0.5, cum + dur / 2]):
            out = os.path.join(out_dir, f"shot_{s['id']:02d}_{k}.jpg")
            run([FFMPEG, "-y", "-ss", f"{t:.1f}", "-i", video,
                 "-frames:v", "1", "-q:v", "2", out])
        cum += dur


FACE_KW = ("stable face", "no face distortion", "consistent facial features",
           "locked character identity", "no morphing", "consistent creature design",
           "locked identity", "no distortion")
PERSON_REFS = {"male_lead", "linyue", "climax", "class3"}


def content_stats(sb, limit=None):
    shots = sb["shots"][:limit] if limit else sb["shots"]
    n = len(shots)
    narr = sum(1 for s in shots if s.get("voice") in ("narrator", "bullet"))
    inner = sum(1 for s in shots if s.get("voice") == "male_lead")
    sub = sum(1 for s in shots if (s.get("subtitle") or "").strip())
    person = [s for s in shots if s["ref"] in PERSON_REFS]
    face = sum(1 for s in person if any(k in s["video_prompt"].lower() for k in FACE_KW))
    return dict(total=n, narr=narr, male=inner, sub=sub, person=len(person), face=face)


def run_quality(video, storyboard=None, out_dir=None, with_frames=False):
    """可被后端调用的结构化质检：返回 技术+内容 维度 dict（供 /api/quality 去 stub 用）。

    返回示例：
      {"ok": True, "video": "final.mp4",
       "technical": {width,height,duration,size,bit_rate, black[],silence[],freeze[], *_count},
       "content": {total,narr,male,sub,person,face, duration_plan, duration_actual, duration_delta},
       "quality": "pass"/"fail", "technical_issue": bool}
    """
    if not os.path.isfile(video):
        return {"ok": False, "error": f"成片不存在: {video}"}
    info = probe(video)
    black = detect_black(video)
    sil = detect_silence(video)
    frz = detect_freeze(video)
    report = {
        "ok": True,
        "video": os.path.basename(video),
        "technical": {
            "width": info.get("width"),
            "height": info.get("height"),
            "duration": info.get("duration"),
            "size": info.get("size"),
            "bit_rate": info.get("bit_rate"),
            "black": [list(b) for b in black],
            "silence": [list(s) for s in sil],
            "freeze": [list(f) for f in frz],
            "black_count": len(black),
            "silence_count": len(sil),
            "freeze_count": len(frz),
        },
    }
    cs = None
    if storyboard and os.path.isfile(storyboard):
        try:
            sb = json.load(open(storyboard, encoding="utf-8"))
            cs = content_stats(sb)
            planned = sum(s.get("duration", 5) for s in sb["shots"])
            actual = float(info.get("duration", 0) or 0)
            cs["duration_plan"] = round(planned, 1)
            cs["duration_actual"] = round(actual, 1)
            cs["duration_delta"] = round(actual - planned, 1)
        except Exception as e:
            cs = {"error": str(e)}
    report["content"] = cs
    tech_bad = bool(black or sil or frz)
    report["quality"] = "fail" if tech_bad else "pass"
    report["technical_issue"] = tech_bad
    if with_frames and out_dir:
        shots = None
        if storyboard and os.path.isfile(storyboard):
            try:
                shots = json.load(open(storyboard, encoding="utf-8")).get("shots", [])
            except Exception:
                shots = None
        if shots:
            extract_frames(video, shots, out_dir)
            report["frames_dir"] = out_dir
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard", default=DEFAULT_SB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--video", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--frames", action="store_true")
    args = ap.parse_args()

    SB = args.storyboard
    OUT = args.out
    video = args.video or os.path.join(OUT, "final.mp4")
    sb = json.load(open(SB, encoding="utf-8"))

    if not os.path.isfile(video):
        print(f"[FATAL] 成片不存在: {video}")
        return

    print("=" * 60)
    print(f"视频质检报告 | {os.path.basename(video)}")
    print("=" * 60)

    info = probe(video)
    print("[技术参数]")
    for k in ("width", "height", "duration", "size", "bit_rate"):
        if k in info:
            print(f"  {k}: {info[k]}")

    black = detect_black(video)
    print(f"[黑场检测] {'无 ✅' if not black else black}")
    sil = detect_silence(video)
    print(f"[静音检测] {'无 ✅' if not sil else sil}")
    frz = detect_freeze(video)
    print(f"[静帧检测] {'无 ✅' if not frz else frz}")

    cs = content_stats(sb, args.limit)
    print("[内容结构]")
    print(f"  总镜数: {cs['total']}")
    print(f"  旁白/弹幕: {cs['narr']} ({cs['narr']/cs['total']*100:.0f}%)")
    print(f"  男主台词: {cs['male']} ({cs['male']/cs['total']*100:.0f}%)")
    print(f"  字幕覆盖: {cs['sub']} ({cs['sub']/cs['total']*100:.0f}%)")
    print(f"  人脸约束(人物镜): {cs['face']}/{cs['person']}")

    # 时长自洽：成片时长 vs 分镜计划
    planned = sum(s.get("duration", 5) for s in sb["shots"][:args.limit] if (args.limit is None or True))
    planned = sum(s.get("duration", 5) for s in (sb["shots"][:args.limit] if args.limit else sb["shots"]))
    actual = float(info.get("duration", 0) or 0)
    print(f"[时长自洽] 计划={planned}s 实际={actual:.1f}s 偏差={actual-planned:+.1f}s")

    if args.frames:
        shots = sb["shots"][:args.limit] if args.limit else sb["shots"]
        extract_frames(video, shots, os.path.join(OUT, "qc_frames"))
        print(f"[抽帧] 已输出 {len(shots)*2} 帧到 qc_frames/")


if __name__ == "__main__":
    main()
