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

# ---- 软身份词（V4/V5 用·0811 第一轮经验固化）：只锁服装/配饰/气质，不写死脸型 ----
# 经验：AGNES prompt 描述优先级 > 参考图——写死面部细节会覆盖参考图脸型；
#       锁脸靠锚点帧图，身份词只做"软锁"（服装/配饰一致，脸交给参考图）。
SOFT_IDENTITY_BOOST = (" Keep the man's clothing and accessories consistent with the reference image: "
                       "white button-up shirt with rolled sleeves, black trousers, worn black backpack. "
                       "Same overall mood and body language. For the face, follow the reference image exactly.")

# ---- 身份强化词（V2/V3 用·第一轮已证伪：写死脸型反而破坏）：保留作对照 ----
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


def build_variants(shot, ref, template="camera_move_v2"):
    """按类型模板构造变体（0811 第一轮经验固化为模板）。

    camera_move_v2（运镜类·第二轮）：基于第一轮发现——锚点帧锁脸有效、硬身份词破坏脸型。
      v0 基准          2帧+原prompt                 （对照）
      v1 锚点帧        3帧[空景,锚点,尾帧]          （第一轮视觉唯一 pass，继续验证）
      v4 锚点+软词     3帧 + SOFT_IDENTITY_BOOST    （图锚+软锁组合，期望硬门槛全过）
      v5 软词          2帧 + SOFT_IDENTITY_BOOST    （单独验证软身份词是否够）
    """
    first = shot.get("asset_frame_start") or ""
    last = shot.get("asset_frame_end") or ""
    anchor = (ref or {}).get("remote_url") or (ref or {}).get("asset_image") or shot.get("remote_image_ref") or ""
    base_p = (shot.get("video_prompt") or "").strip()

    first_img = _datauri(server.asset_abs(first)) if first.startswith("assets/") else first
    imgs2 = [first_img, last]                      # 两帧
    imgs3 = [first_img, anchor, last]              # 插入角色锚点脸（中间关键帧）
    # 关键帧图明细（看板展示实际图：角色标签 + 可访问 src）
    kf2 = [{"role": "起点空景", "src": first}, {"role": "尾帧", "src": last}]
    kf3 = [{"role": "起点空景", "src": first}, {"role": "角色锚点", "src": anchor}, {"role": "尾帧", "src": last}]

    if template == "camera_move_v1":
        # 第一轮模板（硬身份词，已证伪保留对照）
        return {
            "v0": {"images": imgs2, "keyframes": kf2, "prompt": base_p, "hyp": "基准：现状 2 帧 + 原 prompt"},
            "v1": {"images": imgs3, "keyframes": kf3, "prompt": base_p, "hyp": "中间锚点：3 帧插值经过锚点脸 → 早锚定"},
            "v2": {"images": imgs2, "keyframes": kf2, "prompt": base_p + IDENTITY_BOOST, "hyp": "身份强化：prompt 写死外貌细节"},
            "v3": {"images": imgs3, "keyframes": kf3, "prompt": base_p + IDENTITY_BOOST, "hyp": "双管齐下：锚点帧 + 身份强化词"},
        }
    # camera_move_v2（默认·第二轮）：软身份词方向
    base_ref = ("AGNES keyframes 官方语义（多图=插值控制点）；第一轮 exp_0811_1755 机制发现："
                "prompt 角色描述优先级>参考图，锁脸靠锚点帧图主导")
    return {
        "v0": {"images": imgs2, "keyframes": kf2, "prompt": base_p, "hyp": "基准：现状 2 帧 + 原 prompt（对照）",
               "goal": "量化基线：验证现状写法的真实水平（对照组）", "reference": "基线=生产默认写法",
               "implement": "关键帧 2 帧[起点空景,尾帧中景]+原 prompt，无任何增强"},
        "v1": {"images": imgs3, "keyframes": kf3, "prompt": base_p, "hyp": "锚点帧：3 帧插值经过锚点脸（第一轮视觉唯一 pass）",
               "goal": "验证锚点帧锁脸是否可重复（第一轮曾 pass）", "reference": "第一轮 exp_0811_1755 v1",
               "implement": "关键帧 3 帧[起点空景,角色锚点图,尾帧中景]，prompt 不变"},
        "v4": {"images": imgs3, "keyframes": kf3, "prompt": base_p + SOFT_IDENTITY_BOOST, "hyp": "锚点+软词：图锚锁脸 + 服装软锁",
               "goal": "锚点帧+软身份词组合，期望硬门槛全过", "reference": base_ref,
               "implement": "3 帧 + SOFT_IDENTITY_BOOST（服装/配饰/气质软锁，不写死脸型）"},
        "v5": {"images": imgs2, "keyframes": kf2, "prompt": base_p + SOFT_IDENTITY_BOOST, "hyp": "软词：仅服装/配饰软锁",
               "goal": "单独验证软身份词是否足够锁角色", "reference": base_ref,
               "implement": "2 帧 + SOFT_IDENTITY_BOOST（无锚点帧）"},
    }


def verdict_report(report, etype):
    """【输入→输出判断】自动生成样本达标报告：硬门槛各维 + 结论 + 下一轮建议。"""
    lines = []
    hard = {"verdict": "verdict", "face": "face", "character": "character"}
    for r0 in report:
        sc = r0.get("diagnosis") or {}
        hp = r0.get("hard_detail") or {}
        ok = r0.get("ok") and r0.get("hard_pass")
        tag = "✅ 达标" if ok else "❌ 未达标"
        dims = " ".join("%s%s" % (k, "✔" if hp.get(k) else "✘") for k in hard)
        lines.append("[%s] %s %s | %s | 硬门槛: %s" % (r0.get("variant", "?"), tag,
                                                      r0.get("verdict", "-"), dims, ""))
    # 总结
    passed = [r for r in report if r.get("ok") and r.get("hard_pass")]
    if passed:
        w = passed[0]["variant"]
        lines.append("\n🏆 该样本达标！候选变体：%s → 可固化为 %s 类规则（待老板看板采纳）" % (w, etype))
    else:
        worst = min([r for r in report if r.get("ok")], key=lambda r: sum(
            v for v in (r.get("diagnosis") or {}).values() if isinstance(v, (int, float)))) if any(
            r.get("ok") for r in report) else None
        lines.append("\n⏭ 该样本未达标：硬门槛未全过 → 按最差维度设计下一轮变体"
                     + ("（参考 %s 的方向继续）" % worst["variant"] if worst else ""))
    return "\n".join(lines)


    # camera_move_v3（第三轮·老板方向）：多帧控制点 + 官方过渡关系 prompt
    # 官方 images_to_video 推荐：prompt 描述"从第几帧过渡到第几帧 + 保持什么"（smooth transition, keep identity and camera）
    halfbody = ""
    _hb = os.path.join(HERE, "experiments", "frame3_halfbody.txt")
    if os.path.isfile(_hb):
        halfbody = open(_hb, encoding="utf-8").read().strip()
    kf4 = [{"role": "起点空景", "src": first}, {"role": "角色脸锚", "src": anchor},
           {"role": "角色半身", "src": halfbody}, {"role": "尾帧", "src": last}]
    imgs4 = [first_img, anchor, halfbody, last]
    # 过渡关系 prompt（官方风格：逐帧描述 + 保持身份/机位/服装，防跳变）
    trans4 = ("Smooth continuous camera push-in across 4 keyframes of the same character and scene, "
              "with NO jumps and NO clothing or identity changes between frames: "
              "Frame 1: empty urban street at midnight, glass office building, cold street lamp. "
              "Frame 2: the Chinese male programmer appears, front view, same face and clothing as the reference "
              "(white button-up shirt with rolled sleeves, black trousers, worn black backpack). "
              "Frame 3: same man in full body standing under the street lamp, same face, hairstyle and clothing, tired posture. "
              "Frame 4: same man in medium shot, same face and clothing, tired expression, cold blue night. "
              "Keep the character's face, hairstyle, and clothing IDENTICAL across all frames. "
              "Keep camera and scene consistent. Photorealistic, cinematic, 24fps.")
    trans3 = ("Smooth continuous camera push-in across 3 keyframes of the same character and scene, "
              "with NO jumps and NO clothing or identity changes: "
              "Frame 1: empty urban street at midnight, glass office building, cold street lamp. "
              "Frame 2: the Chinese male programmer, same face and clothing as the reference "
              "(white button-up shirt with rolled sleeves, black trousers, worn black backpack). "
              "Frame 3: same man in medium shot, same face and clothing, tired expression. "
              "Keep the character's face, hairstyle, and clothing IDENTICAL across all frames. "
              "Keep camera and scene consistent. Photorealistic, cinematic, 24fps.")
    return {
        "v6": {"images": imgs4, "keyframes": kf4, "prompt": trans4, "hyp": "4帧+过渡prompt：官方推荐写法（逐帧描述+保持身份服装）"},
        "v7": {"images": imgs4, "keyframes": kf4, "prompt": base_p + " Keep the same character face and clothing across all four frames, smooth transition, no jumps.",
               "hyp": "4帧+场景prompt：对比——图数同 v6 但 prompt 仍是场景描述"},
        "v8": {"images": imgs3, "keyframes": kf3, "prompt": trans3, "hyp": "3帧+过渡prompt：对比——同过渡写法但少一个控制点"},
    }


def _cn_translate(prompt_en, timeout=60):
    """把英文视频 prompt 翻成中文（老板看板看中文，执行仍用英文原版）。失败返回空。"""
    try:
        import agnes_client as ac
        cn = ac.chat("把下面这段英文视频提示词翻译成流畅的中文，只输出翻译结果，不要解释：\n" + prompt_en,
                     model="agnes-2.5-flash", temperature=0.1, max_tokens=600, timeout=timeout)
        return (cn or "").strip()[:300]
    except Exception:
        return ""


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
    if "--project" in args:
        pid = args[args.index("--project") + 1]
    if "--shot" in args:
        sid = int(args[args.index("--shot") + 1])
    # 变体集/模板：默认 camera_move_v2（第二轮软身份词方向）；--template 可切换 v1 旧模板
    tpl = "camera_move_v2"
    if "--template" in args:
        tpl = args[args.index("--template") + 1]
    vset = None
    if "--variants" in args:
        vset = tuple(args[args.index("--variants") + 1].split(","))
    if not pid:
        print("用法: python prompt_training.py --project <id> --shot <n> [--variants v0,v1,v4,v5] [--template camera_move_v2|camera_move_v1] [--type 镜头类型]", file=sys.stderr)
        sys.exit(1)

    server.load_spec(pid)
    shot = server.find_shot(sid)
    if shot is None:
        print("shot %d 不存在" % sid, file=sys.stderr)
        sys.exit(1)
    ref = (server.SPEC.get("references") or {}).get(shot.get("ref") or "") or {}
    anchor = (ref or {}).get("remote_url") or (ref or {}).get("asset_image") or shot.get("remote_image_ref") or ""

    variants = build_variants(shot, ref, tpl)
    if vset is None:
        vset = tuple(variants.keys())
    out_root = os.path.join(EXPDIR, pid, "shot%d" % sid)
    os.makedirs(out_root, exist_ok=True)

    report = []
    # 基础参数（目标体·变体统一基底）——v4 结构化记录
    w, h = server._video_size()
    nf = server._shot_nf(shot)
    goal_body = {
        "cn_story": (shot.get("cn_story") or "")[:120],
        "camera": shot.get("camera") or "",
        "duration": shot.get("duration"),
        "ref": shot.get("ref"),
        "expected": "硬门槛全过（判定=通过 + 人脸>=8 + 角色>=8）且软指标尽量好",
        "base_params": {"size": "%dx%d" % (w, h), "model": "agnes-video-v2.0", "num_frames": nf},
    }
    for name in vset:
        v = variants[name]
        print("\n===== 变体 %s：%s =====" % (name, v["hyp"]))
        out_dir = os.path.join(out_root, name)
        try:
            fp = gen_video(v["prompt"], v["images"], out_dir, sid, shot)
            print("  视频就绪: %s (%.0f KB)" % (fp, os.path.getsize(fp) // 1024))
        except Exception as e:
            print("  ❌ 变体 %s 生成失败: %s" % (name, str(e)[:150]))
            report.append({"name": name, "variant": name, "hyp": v["hyp"], "ok": False,
                           "error": str(e)[:150],
                           "params": {"prompt": v["prompt"][:400], "prompt_cn": _cn_translate(v["prompt"]),
                                      "keyframes": v.get("keyframes", []), "images": len(v["images"]),
                                      "num_frames": nf, "size": "%dx%d" % (w, h),
                                      "frame_rate": 24, "mode": "keyframes",
                                      "model": "agnes-video-v2.0", "negative": "文字/水印/畸形"}})
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
        # identity 视觉审查（AGNES 2.5-flash 双图：锚点 vs 视频【尾帧】——0811 口径修正：
        # 运镜镜头首帧是起点空景剪影（设计内），对比必须取尾帧（人物清晰处））
        vid_ok = False
        try:
            vf = os.path.join(out_dir, "shot%d.mp4" % sid)
            frame = os.path.join(out_dir, "lastframe.png")
            r = subprocess.run(["ffmpeg", "-y", "-sseof", "-0.2", "-i", vf, "-frames:v", "1", frame],
                               capture_output=True, timeout=90)
            if r.returncode != 0:
                r = subprocess.run(["ffmpeg", "-y", "-i", vf, "-frames:v", "1", frame],
                                   capture_output=True, timeout=90)
            if r.returncode == 0 and os.path.isfile(frame):
                sys.path.insert(0, os.path.join(HERE, "..", "diag"))
                from vision_review import review
                vr = review([anchor, frame], kind="identity")
                print("  identity 审查(尾帧):", vr.get("verdict"), "| issues:", len(vr.get("issues") or []),
                      "|", (vr.get("issues") or [{}])[0].get("desc", "")[:50] if vr.get("issues") else "")
                # 【内部一致性·0811 老板实测盲区】视频首帧 vs 尾帧：查视频自身服装/外观变化
                ic = {"verdict": None, "issues": []}
                try:
                    f1 = os.path.join(out_dir, "frame1.png")
                    subprocess.run(["ffmpeg", "-y", "-i", vf, "-frames:v", "1", f1],
                                   capture_output=True, timeout=90)
                    if os.path.isfile(f1):
                        icr = review([f1, frame], kind="internal")
                        ic = {"verdict": icr.get("verdict"), "issues": (icr.get("issues") or [])[:2]}
                        print("  内部一致(首帧vs尾帧):", ic.get("verdict"), "|",
                              (ic.get("issues") or [{}])[0].get("desc", "")[:44] if ic.get("issues") else "一致")
                except Exception as _e:
                    print("  内部一致审查失败: %s" % str(_e)[:80])
                report.append({"name": name, "variant": name, "hyp": v["hyp"], "ok": True,
                               "diagnosis": scores, "verdict": (d or {}).get("verdict"),
                               "identity_review": vr.get("verdict"),
                               "identity_issues": (vr.get("issues") or [])[:3],
                               "internal_consistency": ic,
                               "video": vf,
                               "params": {"prompt": v["prompt"][:400], "prompt_cn": _cn_translate(v["prompt"]),
                                          "keyframes": v.get("keyframes", []), "images": len(v["images"]),
                                          "num_frames": nf, "size": "%dx%d" % (w, h),
                                          "frame_rate": 24, "mode": "keyframes",
                                          "model": "agnes-video-v2.0", "negative": "文字/水印/畸形"}})
                vid_ok = True
        except Exception as e:
            print("  identity 审查失败: %s" % str(e)[:100])
        if not vid_ok:
            report.append({"name": name, "variant": name, "hyp": v["hyp"], "ok": True,
                           "diagnosis": scores, "verdict": (d or {}).get("verdict"),
                           "params": {"prompt": v["prompt"][:400], "prompt_cn": _cn_translate(v["prompt"]),
                                      "keyframes": v.get("keyframes", []), "images": len(v["images"]),
                                      "num_frames": nf, "size": "%dx%d" % (w, h),
                                      "frame_rate": 24, "mode": "keyframes",
                                      "model": "agnes-video-v2.0", "negative": "文字/水印/畸形"}})

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
    etype = ""
    if "--type" in args:
        etype = args[args.index("--type") + 1]
    print("\n" + verdict_report(report, etype or "未分类"))
    # 保存（双写：本地 + 看板目录 experiments_data/，供 8787 训练看板读取）
    # 达标判断（输入→输出）：硬门槛 verdict+face+character 全过 = 达标
    for r0 in report:
        sc = r0.get("diagnosis") or {}
        hp = {"verdict": r0.get("verdict") == "pass",
              "face": (sc.get("face") is not None and sc.get("face") >= 8),
              "character": (sc.get("character") is not None and sc.get("character") >= 8)}
        r0["hard_pass"] = all(hp.values())
        r0["hard_detail"] = hp
        # 【v4 目标达成】对照 goal_body：硬门槛全过 + 视觉脸型 pass → 目标达成
        r0["target_met"] = bool(r0.get("ok") and r0.get("hard_pass") and
                                (r0.get("identity_review") == "pass" or r0.get("identity_last", {}).get("verdict") == "pass"))
    winner = None
    best = -1
    for r0 in report:
        sc = r0.get("diagnosis") or {}
        s = sum(v for v in sc.values() if isinstance(v, (int, float)))
        if r0.get("ok") and r0.get("target_met") and s > best:
            best, winner = s, r0.get("variant")
    if winner is None:
        # 无目标达成变体：选总分最高（未达标样本也要有候选方向）
        for r0 in report:
            sc = r0.get("diagnosis") or {}
            s = sum(v for v in sc.values() if isinstance(v, (int, float)))
            if r0.get("ok") and s > best:
                best, winner = s, r0.get("variant")
    etype = ""
    if "--type" in args:
        etype = args[args.index("--type") + 1]
    out = {
        "id": "exp_%s" % time.strftime("%m%d_%H%M%S"),
        "schema": "v3",
        "type": etype or "未分类镜头",
        "goal_body": goal_body,
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
