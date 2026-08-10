#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合成（多项目通用）：归一化(缩放/烧字幕/UI叠加/AI标识) -> concat -> 淡入淡出 -> 混音 -> 成片。

用法：
  python assemble.py --storyboard projects/ep_0806_170153/storyboard.json \
                     --out projects/ep_0806_170153 --continuous
  python assemble.py --out projects/ep_0806_170153

v3 特性：
  - 逐镜 duration 拼接（分镜时长权威，对应时长对账网关）
  - UI 镜(ui_shot)用居中框样式字幕；普通镜用底部字幕
  - 成片右下角叠加「AI生成」标识（满足平台合规）
  - 字体走本地相对路径，避免 Windows 绝对路径冒号破坏 ffmpeg filter
"""
import os, json, subprocess, shutil, sys, argparse

FFMPEG = r"C:\Users\67972\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
ROOT = r"C:\Users\67972\WorkBuddy\workbuddy\short_drama_workflow"
DEFAULT_SB = os.path.join(ROOT, "projects/ep_0806_170153/storyboard.json")
DEFAULT_OUT = os.path.join(ROOT, "projects/ep_0806_170153")

FADE_IN_DUR = 0.4
FADE_OUT_DUR = 0.6


def run(cmd, label=""):
    tag = f"[{label}] " if label else ""
    print(f"{tag}RUN: {' '.join(cmd[:8])} ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = r.stderr[-2000:] if r.stderr else "(no stderr)"
        print(f"{tag}FAIL(rc={r.returncode}): {err}")
    else:
        print(f"{tag}OK")
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard", default=DEFAULT_SB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--continuous", action="store_true",
                    help="使用连续旁白音频替代逐镜拼接")
    # ── 精修参数（转场 / BGM / 字幕）──
    ap.add_argument("--transition", default="none", choices=["none", "dissolve"],
                    help="镜间转场：none=硬切(默认) / dissolve=交叉叠化(0.4s)")
    ap.add_argument("--subtitle", dest="subtitle", action="store_true", default=True,
                    help="烧录硬字幕(默认开)")
    ap.add_argument("--no-subtitle", dest="subtitle", action="store_false",
                    help="关闭硬字幕")
    ap.add_argument("--ai-watermark", dest="ai_watermark", action="store_true", default=True,
                    help="右下角叠加「AI生成」标识(默认开)")
    ap.add_argument("--no-ai-watermark", dest="ai_watermark", action="store_false")
    ap.add_argument("--global-bgm", default=None,
                    help="全局背景音乐文件(整片贯穿、低音量淡入淡出)；不填则不叠加全局BGM")
    ap.add_argument("--resolution", default=None,
                    help="成片输出分辨率 WxH（如 480x854/720x1280）；缺省用 storyboard.resolution。"
                         "测试档合成低分辨率快速验证，正式档合成高清")
    args = ap.parse_args()
    TRANS_DUR = 0.4  # 叠化转场时长

    SB = args.storyboard
    OUT = args.out
    FINAL = os.path.join(OUT, "final.mp4")
    sb = json.load(open(SB, encoding="utf-8"))
    if args.resolution:
        try:
            _w, _h = args.resolution.lower().split("x")
            sb["resolution"] = {"width": int(_w), "height": int(_h)}
        except Exception:
            pass
    W, H = sb["resolution"]["width"], sb["resolution"]["height"]

    # ── 字体（本地相对路径，避免冒号被 ffmpeg 当分隔符）──
    _LOCAL_FONT = os.path.join(OUT, "simhei.ttf")
    FONT_CANDIDATES = [
        _LOCAL_FONT,
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    FONT_FILE = ""
    for fc in FONT_CANDIDATES:
        if os.path.isfile(fc):
            FONT_FILE = fc
            break
    if FONT_FILE and not FONT_FILE.startswith(OUT):
        local_copy = os.path.join(OUT, os.path.basename(FONT_FILE))
        if not os.path.isfile(local_copy):
            shutil.copy2(FONT_FILE, local_copy)
        FONT_FILE_FFMPEG = os.path.basename(local_copy)
    elif FONT_FILE:
        FONT_FILE_FFMPEG = os.path.basename(FONT_FILE)
    else:
        FONT_FILE_FFMPEG = ""
    if not FONT_FILE:
        print("[WARN] 未找到中文字体，字幕/AI标识可能乱码")
    else:
        print(f"[FONT] {FONT_FILE} -> ffmpeg: {FONT_FILE_FFMPEG}")

    manifest = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))
    manifest.sort(key=lambda x: x["id"])
    if args.limit:
        manifest = manifest[:args.limit]

    # ── 1) 每镜归一化 + 烧字幕(UI框样式) + AI标识准备 ──
    norm_dir = os.path.join(OUT, "norm_v3")
    if os.path.isdir(norm_dir):
        shutil.rmtree(norm_dir)
    os.makedirs(norm_dir, exist_ok=True)

    norm_clips = []
    norm_durs = []
    total_dur = 0.0
    for rec in manifest:
        sid = rec["id"]
        src = os.path.normpath(rec["path"])
        dur = rec.get("duration", 5)
        total_dur += dur
        if not os.path.isfile(src):
            print(f"[SKIP] clip_{sid:02d} 不存在: {src}")
            continue
        dst = os.path.join(norm_dir, f"n_{sid:02d}.mp4")
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
              f"setsar=1,fps=24,format=yuv420p,"
              f"trim=0:{dur},setpts=PTS-STARTPTS")

        sub = (rec.get("subtitle") or "").strip()
        ui = bool(rec.get("ui_shot", False))
        if args.subtitle and sub and FONT_FILE:
            esc = sub.replace("'", "'\\''").replace(":", "\\:")
            if ui:
                vf += (f",drawtext=text='{esc}':fontfile={FONT_FILE_FFMPEG}"
                       f":fontsize=30:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=12"
                       f":x=(w-text_w)/2:y=h*0.42")
            else:
                vf += (f",drawtext=text='{esc}':fontfile={FONT_FILE_FFMPEG}"
                       f":fontsize=24:fontcolor=white:borderw=2:bordercolor=black"
                       f":x=(w-text_w)/2:y=h-90")

        cmd = [FFMPEG, "-y", "-i", src, "-vf", vf,
               "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-ar", "44100", "-ac", "2", dst]
        if not run(cmd, label=f"norm_{sid:02d}"):
            vf_fb = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
                     f"setsar=1,fps=24,format=yuv420p,trim=0:{dur},setpts=PTS-STARTPTS")
            run([FFMPEG, "-y", "-i", src, "-vf", vf_fb,
                 "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "44100", "-ac", "2", dst],
                label=f"fallback_{sid:02d}")
        norm_clips.append(dst)
        norm_durs.append(dur)

    n = len(norm_clips)
    if n == 0:
        print("[FATAL] 无可用片段")
        sys.exit(1)
    TOTAL_DUR = total_dur
    print(f"\n=== 归一化完成: {n}/{len(manifest)} 片段 | 总时长 {TOTAL_DUR:.1f}s ===\n")

    # ── 2) 音轨准备 ──
    AUDIO_DIR = os.path.join(OUT, "audio")
    audio_seg = os.path.join(OUT, "audio_seg_v3")
    if os.path.isdir(audio_seg):
        shutil.rmtree(audio_seg)
    os.makedirs(audio_seg, exist_ok=True)
    audio_full = os.path.join(audio_seg, "full.mp3")

    if args.continuous:
        cont = os.path.join(AUDIO_DIR, "narration_continuous.mp3")
        if os.path.isfile(cont) and os.path.getsize(cont) > 100:
            run([FFMPEG, "-y", "-i", cont, "-af", "apad", "-t", f"{TOTAL_DUR:.1f}",
                 "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", audio_full], label="audio_continuous")
        else:
            print("[WARN] 连续音频缺失，退回逐镜")
            args.continuous = False

    if not args.continuous:
        seg_files = []
        for rec in manifest:
            sid = rec["id"]
            dur = rec.get("duration", 5)
            mp3 = os.path.join(AUDIO_DIR, f"shot_{sid:02d}.mp3")
            bgm = os.path.join(AUDIO_DIR, f"bgm_{sid:02d}.wav")
            sfx = os.path.join(AUDIO_DIR, f"sfx_{sid:02d}.wav")
            seg = os.path.join(audio_seg, f"a_{sid:02d}.mp3")
            # 对话轨：优先 MiniMax 独立 mp3（use_minimax_audio 镜）；否则抽取分镜自带
            # 原生音画同步音轨；原生音轨也缺失才静音。这样默认（AGNES 原生音画同步）
            # 也能在成片出声，不再被静音覆盖。
            dlg = os.path.join(audio_seg, f"d_{sid:02d}.mp3")
            if os.path.isfile(mp3) and os.path.getsize(mp3) > 100:
                run([FFMPEG, "-y", "-i", mp3, "-af", "apad", "-t", str(dur), dlg],
                    label=f"dlg_{sid:02d}")
            else:
                # 抽取归一化片段里的原生音频（AGNES 音画同步，已在 step1 重编码为 aac）
                src_norm = os.path.join(norm_dir, f"n_{sid:02d}.mp4")
                if os.path.isfile(src_norm):
                    run([FFMPEG, "-y", "-i", src_norm, "-vn",
                         "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2",
                         "-t", str(dur), dlg], label=f"dlg_native_{sid:02d}")
                else:
                    run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                         "-t", str(dur), dlg], label=f"dlgsil_{sid:02d}")
            # 三层混音：对话(1.0) + BGM(0.18) + SFX(0.5)；缺失项用 anullsrc 补位
            inputs = [("-i", dlg)]
            parts = ["[0:a]volume=1.0[d]"]
            cnt = 1
            for tag, path, vol in (("b", bgm, 0.18), ("s", sfx, 0.5)):
                if os.path.isfile(path) and os.path.getsize(path) > 100:
                    inputs.append(("-i", path))
                    parts.append(f"[{cnt}:a]volume={vol}[{tag}]"); cnt += 1
                else:
                    inputs.append(("-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur}"))
                    parts.append(f"[{cnt}:a]volume=0[{tag}]"); cnt += 1
            parts.append(f"[d][b][s]amix=inputs=3:duration=first:dropout_transition=0[m]")
            flat = []
            for it in inputs:
                flat += list(it)
            run([FFMPEG, "-y"] + flat +
                ["-filter_complex", ";".join(parts), "-map", "[m]",
                 "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", seg],
                label=f"mix_{sid:02d}")
            seg_files.append(seg)
        lst = os.path.join(audio_seg, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for s in seg_files:
                f.write(f"file '{os.path.abspath(s)}'\n")
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst,
             "-c", "copy", audio_full], label="audio_concat")

    # ── 2.5) 全局 BGM（整片贯穿、低音量、淡入淡出）──
    if args.global_bgm and os.path.isfile(args.global_bgm):
        g_mix = os.path.join(audio_seg, "global_bgm_mix.mp3")
        run([FFMPEG, "-y", "-i", args.global_bgm, "-i", audio_full,
             "-filter_complex",
             f"[0:a]volume=0.12,afade=t=in:d=1.5,afade=t=out:d=2.0[g];"
             f"[1:a][g]amix=inputs=2:duration=first:dropout_transition=0[m]",
             "-map", "[m]", "-t", f"{TOTAL_DUR:.1f}",
             "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", g_mix],
            label="global_bgm")
        if os.path.isfile(g_mix) and os.path.getsize(g_mix) > 100:
            audio_full = g_mix
            print(f"[BGM] 全局背景音乐已叠加：{args.global_bgm}")

    # ── 3) Concat + 转场 + 淡入淡出 + AI标识 ──
    FADE_OUT_START = max(0, TOTAL_DUR - FADE_OUT_DUR)
    use_xfade = (args.transition == "dissolve" and n >= 2 and len(norm_durs) == n)
    if use_xfade:
        # 镜间交叉叠化（xfade）：每段重叠 TRANS_DUR，offset 累计扣除已重叠量
        offs = []
        acc = norm_durs[0]
        for i in range(1, n):
            offs.append(max(0.05, acc - TRANS_DUR))
            acc += norm_durs[i] - TRANS_DUR
        chain = f"[0:v][1:v]xfade=transition=dissolve:duration={TRANS_DUR}:offset={offs[0]:.2f}[v01]"
        for i in range(2, n):
            prev = f"[v0{i-1}]" if i > 2 else "[v01]"
            chain += f";{prev}[{i}:v]xfade=transition=dissolve:duration={TRANS_DUR}:offset={offs[i-1]:.2f}[v0{i}]"
        last = f"[v0{n-1}]"
        v_filter = chain + f";{last}fade=t=in:d={FADE_IN_DUR}[tmp];[tmp]fade=t=out:start_time={FADE_OUT_START:.1f}:d={FADE_OUT_DUR}[outv]"
    else:
        concat_parts = "".join(f"[{i}:v]" for i in range(n))
        concat_filter = f"{concat_parts}concat=n={n}:v=1:a=0[cv]"
        v_filter = (f"{concat_filter};"
                    f"[cv]fade=t=in:d={FADE_IN_DUR}[tmp];"
                    f"[tmp]fade=t=out:start_time={FADE_OUT_START:.1f}:d={FADE_OUT_DUR}[outv]")
    if FONT_FILE and args.ai_watermark:
        v_filter += (f";[outv]drawtext=text='AI生成':fontfile={FONT_FILE_FFMPEG}"
                     f":fontsize=20:fontcolor=white@0.85:x=w-tw-24:y=h-th-24[outv]")

    # 无论 xfade 还是 concat，经过 fade(淡入淡出)+AI标识 后最终视频标签恒为 [outv]
    vmap_src = "[outv]"
    cmd = [FFMPEG, "-y"]
    for c in norm_clips:
        cmd += ["-i", c]
    cmd += ["-i", audio_full, "-filter_complex", v_filter,
            "-map", vmap_src, "-map", f"{n}:a",
            "-shortest",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", FINAL]

    print("\n" + "=" * 50)
    _bgm = "全局BGM" if "global_bgm_mix" in audio_full else "无"
    print(f"最终合成: {'--continuous' if args.continuous else 'per-shot'} | 时长 {TOTAL_DUR:.1f}s | "
          f"转场={args.transition} | 字幕={'开' if args.subtitle else '关'} | "
          f"AI标识={'开' if (FONT_FILE and args.ai_watermark) else '关'} | BGM={_bgm}")
    print("=" * 50 + "\n")

    ok = run(cmd, label="FINAL_ASSEMBLE")
    if ok:
        size = os.path.getsize(FINAL)
        probe = [FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
                 "-show_entries", "format=duration,size,bit_rate",
                 "-of", "default=noprint_wrappers=1", FINAL]
        pr = subprocess.run(probe, capture_output=True, text=True)
        print(f"\n FINAL_OK -> {FINAL} ({size/1024:.1f} KB)")
        if pr.stdout:
            for line in pr.stdout.strip().split("\n"):
                if line.strip():
                    print(f"   {line}")
        verify_dir = os.path.join(OUT, "verify")
        os.makedirs(verify_dir, exist_ok=True)
        cum = 0.0
        for rec in manifest:
            dur = rec.get("duration", 5)
            mid = cum + dur / 2
            cum += dur
            frame = os.path.join(verify_dir, f"shot_{rec['id']:02d}.jpg")
            subprocess.run([FFMPEG, "-y", "-ss", f"{mid:.1f}", "-i", FINAL,
                            "-frames:v", "1", "-update", "1", "-q:v", "2", frame],
                           capture_output=True)
        print(f"   抽帧验证已输出到 {verify_dir}/")
    else:
        print("\n ASSEMBLE_FAIL — 检查上方日志")


if __name__ == "__main__":
    main()
