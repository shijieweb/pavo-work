#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提示词训练营 prompt_training.py（老板 0811：找最佳提示词写法→固化规则）

假设驱动变体实验：对同一镜头，按理论依据构造 N 种提示词/关键帧写法变体，
逐个真实生成视频 → 统一质检（AGNES 4维诊断 + face + identity 视觉审查）→ 对比表。
赢家写法固化进规则（写入 learned_experiments.json + 提示词规则沉淀）。

用法：python prompt_training.py --project ep_0811_145935 --shot 1 [--variants v0,v1,v2,v3]
实验视频存 experiments/<project>/shot<id>/v{0-3}/，不污染生产项目。
"""
import base64, json, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.join(HERE, "..", "..", "html_prototype")
sys.path.insert(0, PROJ_ROOT)
sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "edit"))

import server
from agnes_client import _submit_video
from diagnosis import diagnose_clip

EXPDIR = os.path.join(HERE, "experiments")
# 看板数据目录（8787 训练看板读取）：workbuddy 根 / experiments_data
BOARD_DATA = os.path.join(os.path.abspath(os.path.join(HERE, "..", "..", "..")), "experiments_data")

# ---- 身份强化词（V2/V3 用）：写死与锚点完全一致的外貌 ----
IDENTITY_BOOST = (" The man is IDENTICAL to the reference image: same 28-year-old Asian male face, "
                  "same messy short black hair, same white button-up shirt with rolled sleeves, "
                  "same black trousers, same worn black backpack. Keep face, hairstyle, and clothing "
                  "exactly the same as the reference throughout the whole clip. No identity change.")


def _datauri(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
    return f"data:{mime};base64,{b64}"


def build_variants(shot, ref):
    """按假设构造变体（V0 基准 / V1 中间锚点 / V2 身份强化 / V3 双管齐下）。"""
    first = shot.get("asset_frame_start") or ""
    last = shot.get("asset_frame_end") or ""
    anchor = (ref or {}).get("remote_url") or (ref or {}).get("asset_image") or shot.get("remote_image_ref") or ""
    base_p = (shot.get("video_prompt") or "").strip()

    first_img = _datauri(server.asset_abs(first)) if first.startswith("assets/") else first
    imgs2 = [first_img, last]                      # 现状两帧
    imgs3 = [first_img, anchor, last]              # 插入角色锚点脸（中间关键帧）

    return {
        "v0": {"images": imgs2, "prompt": base_p, "hyp": "基准：现状 2 帧 + 原 prompt"},
        "v1": {"images": imgs3, "prompt": base_p, "hyp": "中间锚点：3 帧插值经过锚点脸 → 早锚定"},
        "v2": {"images": imgs2, "prompt": base_p + IDENTITY_BOOST, "hyp": "身份强化：prompt 写死外貌细节"},
        "v3": {"images": imgs3, "prompt": base_p + IDENTITY_BOOST, "hyp": "双管齐下：锚点帧 + 身份强化词"},
    }


def gen_video(prompt, images, out_dir, sid, shot):
    """提交 keyframes 视频 → 轮询 → 下载到 out_dir/shot<sid>.mp4。返回本地路径。"""
    os.makedirs(out_dir, exist_ok=True)
    w, h = server._video_size()
    from agnes_client import wait_for_video
    task = _submit_video(prompt, images=images, width=w, height=h, num_frames=server._shot_nf(shot))
    vid = task.get("video_id") or task.get("id") or task.get("task_id")
    print("  提交 video_id=%s 轮询中（最长 15 分钟）…" % str(vid)[:20])
    url = wait_for_video(vid, timeout=900, interval=10)
    if not url:
        raise RuntimeError("视频生成超时/失败")
    fp = os.path.join(out_dir, "shot%d.mp4" % sid)
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    with open(fp, "wb") as f:
        f.write(data)
    return fp


def main():
    args = sys.argv[1:]
    pid = None
    sid = 1
    vset = ("v0", "v1", "v2", "v3")
    if "--project" in args:
        pid = args[args.index("--project") + 1]
    if "--shot" in args:
        sid = int(args[args.index("--shot") + 1])
    if "--variants" in args:
        vset = tuple(args[args.index("--variants") + 1].split(","))
    if not pid:
        print("用法: python prompt_training.py --project <id> --shot <n> [--variants v0,v1,v2,v3]", file=sys.stderr)
        sys.exit(1)

    server.load_spec(pid)
    shot = server.find_shot(sid)
    if shot is None:
        print("shot %d 不存在" % sid, file=sys.stderr)
        sys.exit(1)
    ref = (server.SPEC.get("references") or {}).get(shot.get("ref") or "") or {}
    anchor = (ref or {}).get("remote_url") or (ref or {}).get("asset_image") or shot.get("remote_image_ref") or ""

    variants = build_variants(shot, ref)
    out_root = os.path.join(EXPDIR, pid, "shot%d" % sid)
    os.makedirs(out_root, exist_ok=True)

    report = []
    for name in vset:
        v = variants[name]
        print("\n===== 变体 %s：%s =====" % (name, v["hyp"]))
        out_dir = os.path.join(out_root, name)
        try:
            fp = gen_video(v["prompt"], v["images"], out_dir, sid, shot)
            print("  视频就绪: %s (%.0f KB)" % (fp, os.path.getsize(fp) // 1024))
        except Exception as e:
            print("  ❌ 变体 %s 生成失败: %s" % (name, str(e)[:150]))
            report.append({"variant": name, "hyp": v["hyp"], "ok": False, "error": str(e)[:150]})
            continue
        # 质检：AGNES 4 维诊断 + face
        try:
            d = diagnose_clip(fp, n_frames=4, face_check=True,
                              storyboard=os.path.join(server.PROJECTS_ROOT, pid, "storyboard.json"),
                              deep=False)
            scores = (d.get("scores") or {}) if isinstance(d, dict) else {}
            print("  诊断:", json.dumps(scores, ensure_ascii=False), "| verdict:", (d or {}).get("verdict"))
        except Exception as e:
            scores = {}
            print("  诊断失败: %s" % str(e)[:100])
        # identity 视觉审查（AGNES 2.5-flash 双图：锚点 vs 视频首帧）
        vid_ok = False
        try:
            vf = os.path.join(out_dir, "shot%d.mp4" % sid)
            frame = os.path.join(out_dir, "frame1.png")
            r = subprocess.run(["ffmpeg", "-y", "-i", vf, "-frames:v", "1", frame],
                               capture_output=True, timeout=90)
            if r.returncode == 0 and os.path.isfile(frame):
                sys.path.insert(0, os.path.join(HERE, "..", "diag"))
                from vision_review import review
                vr = review([anchor, frame], kind="identity")
                print("  identity 审查:", vr.get("verdict"), "| issues:", len(vr.get("issues") or []),
                      "|", (vr.get("issues") or [{}])[0].get("desc", "")[:50] if vr.get("issues") else "")
                report.append({"variant": name, "hyp": v["hyp"], "ok": True,
                               "diagnosis": scores, "verdict": (d or {}).get("verdict"),
                               "identity_review": vr.get("verdict"),
                               "identity_issues": (vr.get("issues") or [])[:3],
                               "video": vf})
                vid_ok = True
        except Exception as e:
            print("  identity 审查失败: %s" % str(e)[:100])
        if not vid_ok:
            report.append({"variant": name, "hyp": v["hyp"], "ok": True,
                           "diagnosis": scores, "verdict": (d or {}).get("verdict")})

    # 对比表
    print("\n" + "=" * 70)
    print("实验对比（%s · 镜%d）" % (pid, sid))
    print("=" * 70)
    print("%-6s %-6s %-8s %-8s %-8s %-8s %-8s %-6s" % ("变体", "verdict", "连贯", "物理", "角色", "首尾", "face", "identity"))
    for r0 in report:
        sc = r0.get("diagnosis") or {}
        print("%-6s %-6s %-8s %-8s %-8s %-8s %-8s %-6s" % (
            r0.get("variant", "?"), r0.get("verdict", "-"),
            sc.get("continuity", "-"), sc.get("physical", "-"), sc.get("character", "-"),
            sc.get("first_last", "-"), sc.get("face", "-"),
            (r0.get("identity_review") or "-")))
    # 保存（双写：本地 + 看板目录 experiments_data/，供 8787 训练看板读取）
    winner = None
    best = -1
    for r0 in report:
        sc = r0.get("diagnosis") or {}
        s = sum(v for v in sc.values() if isinstance(v, (int, float)))
        if r0.get("ok") and s > best:
            best, winner = s, r0.get("variant")
    # 【v2 训练科学】分层达标：硬门槛 verdict=pass + face>=8 + character>=8 必须全过
    for r0 in report:
        sc = r0.get("diagnosis") or {}
        hp = {"verdict": r0.get("verdict") == "pass",
              "face": (sc.get("face") is not None and sc.get("face") >= 8),
              "character": (sc.get("character") is not None and sc.get("character") >= 8)}
        r0["hard_pass"] = all(hp.values())
        r0["hard_detail"] = hp
    etype = ""
    if "--type" in args:
        etype = args[args.index("--type") + 1]
    out = {
        "id": "exp_%s" % time.strftime("%m%d_%H%M%S"),
        "schema": "v2",
        "type": etype or "未分类镜头",
        "goal": "该类型训练目标：硬门槛全过 = verdict pass + face >=8 + 角色一致 >=8；软指标（连贯/物理/首尾）尽量好",
        "sample": "镜%d：%s" % (sid, (shot.get("cn_story") or "")[:60]),
        "project": pid, "shot": sid, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "done",                 # running/done/candidate/adopted/rejected（看板状态流）
        "candidate": winner,              # 我标记的候选赢家变体（待老板审查）
        "candidate_note": "",             # 候选方案说明（由分析补充）
        "threshold": {"hard": ["verdict", "face", "character"], "soft": ["continuity", "physical", "first_last"]},
        "variants": report,
        "progress": "%s类训练：样本待统计" % etype,
        "qc_lesson": "",
        "key_finding": "",
        "rules_draft": [],
        "input": {"prompt": shot.get("video_prompt", "")[:200], "ref": shot.get("ref")},
    }
    os.makedirs(EXPDIR, exist_ok=True)
    with open(os.path.join(EXPDIR, "learned_experiments.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.makedirs(BOARD_DATA, exist_ok=True)
    with open(os.path.join(BOARD_DATA, out["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n结果已存: experiments/learned_experiments.json + experiments_data/%s.json（看板可读）" % out["id"])
    print("候选赢家: %s（待老板看板审查确认后才固化进工作台）" % (winner or "无"))


if __name__ == "__main__":
    main()
