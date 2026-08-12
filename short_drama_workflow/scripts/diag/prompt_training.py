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

# ---- 负面词（官方推荐：避免不需要的内容；精选有效项，冗余词无效）----
NEG_PROMPT = ("text, watermark, logo, subtitles, morphing, deformed hands, extra fingers, "
              "blurry face, frame jump, identity change, clothing change")

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

    if template == "camera_move_v3":
        # 【第三轮·老板方向】多帧控制点 + 官方过渡关系 prompt（官方：描述过渡关系+保持身份）
        halfbody = ""
        _hb = os.path.join(HERE, "experiments", "frame3_halfbody.txt")
        if os.path.isfile(_hb):
            halfbody = open(_hb, encoding="utf-8").read().strip()
        kf4 = [{"role": "起点空景", "src": first}, {"role": "角色脸锚", "src": anchor},
               {"role": "角色半身", "src": halfbody}, {"role": "尾帧", "src": last}]
        imgs4 = [first_img, anchor, halfbody, last]
        _OFFICIAL = (" Generate a smooth transition between the keyframes: keep the character's appearance "
                     "unchanged (no face morphing), keep the camera angle consistent (no shaking), "
                     "achieve natural motion between scenes (no jumps).")
        trans4 = ("Smooth continuous camera push-in across 4 keyframes of the same character and scene, "
                  "with NO jumps and NO clothing or identity changes between frames: "
                  "Frame 1: empty urban street at midnight, glass office building, cold street lamp. "
                  "Frame 2: the Chinese male programmer appears, front view, same face and clothing as the reference "
                  "(white button-up shirt with rolled sleeves, black trousers, worn black backpack). "
                  "Frame 3: same man in full body standing under the street lamp, same face, hairstyle and clothing, tired posture. "
                  "Frame 4: same man in medium shot, same face and clothing, tired expression, cold blue night. "
                  "Keep the character's face, hairstyle, and clothing IDENTICAL across all frames. "
                  "Keep camera and scene consistent. Photorealistic, cinematic, 24fps." + _OFFICIAL)
        trans3 = ("Smooth continuous camera push-in across 3 keyframes of the same character and scene, "
                  "with NO jumps and NO clothing or identity changes: "
                  "Frame 1: empty urban street at midnight, glass office building, cold street lamp. "
                  "Frame 2: the Chinese male programmer, same face and clothing as the reference "
                  "(white button-up shirt with rolled sleeves, black trousers, worn black backpack). "
                  "Frame 3: same man in medium shot, same face and clothing, tired expression. "
                  "Keep the character's face, hairstyle, and clothing IDENTICAL across all frames. "
                  "Keep camera and scene consistent. Photorealistic, cinematic, 24fps." + _OFFICIAL)
        return {
            "v6": {"images": imgs4, "keyframes": kf4, "prompt": trans4, "hyp": "4帧+过渡prompt：官方推荐写法"},
            "v7": {"images": imgs4, "keyframes": kf4, "prompt": base_p + " Keep the same character face and clothing across all four frames, smooth transition, no jumps.",
                   "hyp": "4帧+场景prompt：对照——同图数但 prompt 仍场景描述"},
            "v8": {"images": imgs3, "keyframes": kf3, "prompt": trans3, "hyp": "3帧+过渡prompt：对照——同写法少一个控制点"},
        }

    # camera_move_v2（默认·第二轮）：软身份词方向
    base_ref = ("AGNES keyframes 官方语义（多图=插值控制点）；第一轮 exp_0811_1755 机制发现："
                "prompt 角色描述优先级>参考图，锁脸靠锚点帧图主导")
    if template == "camera_move_v4":
        # 【第四轮·老板方向】验证开头闪帧根因
        # v9: 回归官方 2 帧 [空景→尾帧]（无中间锚点帧，避免模型误解时间顺序）
        # v10: 3 帧但锚点帧用远景人物（非特写脸，避免被误当起点）
        # v11: 3 帧 + 强化空景约束 prompt（明示 Frame 1 无人物）
        anchor_far = anchor
        _af = os.path.join(HERE, "experiments", "anchor_far.txt")
        if os.path.isfile(_af):
            anchor_far = open(_af, encoding="utf-8").read().strip()
        v9_prompt = ("Generate a smooth cinematic transition between the two keyframes, "
                     "maintaining visual consistency and natural camera movement. "
                     "Frame 1: empty urban street at midnight, cold blue night, street lamp. "
                     "Frame 2: the Chinese male programmer in medium shot, tired expression. "
                     "Keep camera slowly pushing in across the transition. "
                     "Keep the character's face, hairstyle, and clothing IDENTICAL.")
        v11_prompt = ("Smooth continuous camera push-in across 3 keyframes of the same scene. "
                      "Frame 1 MUST BE empty urban street with NO person visible at all. "
                      "The character appears starting from Frame 2. "
                      "Frame 2: the Chinese male programmer appears, same face and clothing as reference. "
                      "Frame 3: same man in medium shot, same face and clothing. "
                      "Keep the character's face, hairstyle, and clothing IDENTICAL across frames. "
                      "Keep camera consistent. NO jumps, NO clothing changes.")
        return {
            "v9": {"images": imgs2, "keyframes": kf2,
                   "prompt": v9_prompt,
                   "hyp": "2帧+过渡prompt：回归官方推荐[空景→尾帧]，无中间锚点帧"},
            "v10": {"images": [first_img, anchor_far, last],
                    "keyframes": [{"role": "起点空景", "src": first},
                                  {"role": "角色远景小(非特写)", "src": anchor_far},
                                  {"role": "尾帧", "src": last}],
                    "prompt": v9_prompt.replace("two keyframes", "three keyframes").replace(
                        "Frame 1: empty urban street at midnight, cold blue night, street lamp. ",
                        "Frame 1: empty urban street at midnight, cold blue night, street lamp. "
                        "Frame 2: the same man in a small far figure, walking towards the camera. "),
                    "hyp": "3帧+过渡prompt：锚点帧用远景小人物（非特写脸）"},
            "v11": {"images": imgs3, "keyframes": kf3,
                    "prompt": v11_prompt,
                    "hyp": "3帧+空景约束prompt：明示Frame 1无人物，人物从Frame 2出现"},
            "v12": {"images": [first_img, anchor_far, last],
                    "keyframes": [{"role": "起点空景", "src": first},
                                  {"role": "角色远景小(非特写)", "src": anchor_far},
                                  {"role": "尾帧", "src": last}],
                    "prompt": v9_prompt.replace("two keyframes", "three keyframes").replace(
                        "Frame 1: empty urban street at midnight, cold blue night, street lamp. ",
                        "Frame 1: empty urban street at midnight, cold blue night, street lamp. "
                        "Frame 2: the same man in a small far figure, walking towards the camera. "),
                    "frame_rate": 30,
                    "hyp": "v10写法+30fps：官方更流畅运动（对比24fps）"},
        }
    if template == "camera_move_v5":
        # 【第五轮·老板拍板】2帧首尾帧 + 短时长（81帧≈3.4s）+ 简单过渡描述
        # 单镜只做"首帧→尾帧简单过渡"，复杂运镜靠镜头拆解（多镜连接），不塞进单镜
        # v13: 2帧[空景→人物中景] + 81帧 + 简单过渡
        # v14: 2帧[空景→人物远景小] + 81帧 + 简单过渡（运镜推近拆成2镜：远景镜+中景镜）
        anchor_far = anchor
        _af = os.path.join(HERE, "experiments", "anchor_far.txt")
        if os.path.isfile(_af):
            anchor_far = open(_af, encoding="utf-8").read().strip()
        simple2 = ("Smooth transition from keyframe 1 to keyframe 2 of the same scene. "
                   "Animate: the man walks forward with natural gait, subtle breathing, hair moving gently, "
                   "background lights flickering softly. "
                   "Frame 1: empty urban street at midnight, cold blue night, street lamp, glass office building. "
                   "Frame 2: the Chinese male programmer in medium shot, tired expression, same white shirt and black backpack. "
                   "Keep stable: character's face, hairstyle, and clothing fully consistent, "
                   "consistent camera angle, natural motion, no jumps, no morphing.")
        simple2_far = ("Smooth transition from keyframe 1 to keyframe 2 of the same scene. "
                       "Animate: the man walks toward the camera from the distance, getting slightly closer, "
                       "hair moving gently in the night wind, background lights flickering softly. "
                       "Frame 1: empty urban street at midnight, cold blue night, street lamp, glass office building. "
                       "Frame 2: the same man walking toward the camera in far shot, small figure, "
                       "same white shirt and black backpack, tired posture. "
                       "Keep stable: character's face, hairstyle, and clothing fully consistent, "
                       "consistent camera angle, natural motion, no jumps, no morphing.")
        kf2b = [{"role": "起点空景", "src": first}, {"role": "尾帧人物中景", "src": last}]
        return {
            "v13": {"images": imgs2, "keyframes": kf2b,
                    "prompt": simple2, "num_frames": 81,
                    "hyp": "2帧[空景→中景]+81帧(3.4s)+简单过渡：单镜只做简单过渡"},
            "v14": {"images": [first_img, anchor_far], "keyframes": [
                        {"role": "起点空景", "src": first}, {"role": "尾帧人物远景小", "src": anchor_far}],
                    "prompt": simple2_far, "num_frames": 81,
                    "hyp": "2帧[空景→远景小]+81帧+简单过渡：运镜推近拆解的第一镜"},
            "v15": {"images": [first_img, anchor_far], "keyframes": [
                        {"role": "起点空景", "src": first}, {"role": "尾帧人物远景小", "src": anchor_far}],
                    "prompt": ("从第一个关键帧到第二个关键帧平滑过渡。"
                               "运动：男人从远景缓慢走向镜头，脚步逐渐清晰靠近，"
                               "头发被夜风轻轻吹动，背景路灯灯光微微闪烁，冷蓝夜色不变。"
                               "保持稳定：角色面容、发型、白衬衫和背包完全一致，镜头角度不变，"
                               "场景过渡自然，无跳变无变形。"),
                    "num_frames": 81,
                    "hyp": "2帧+中文官方格式：状态A→状态B+光效细节（知识库中文例子）"},
        }
    if template == "camera_move_v6":
        # 【第六轮·老板导演思维】首尾帧必须同场景/同光效/同机位才可过渡，差异大→拆镜
        # v16 = 镜A：空景 → 空景微变（同场景双帧，雾气/灯光微动，无人物）
        # v17 = 镜B：人物中景 → 人物微变（同人同场景同机位，姿态微变）
        sceneA_2 = anchor_far if False else ""
        _sa2 = os.path.join(HERE, "experiments", "sceneA_2.txt")
        if os.path.isfile(_sa2):
            sceneA_2 = open(_sa2, encoding="utf-8").read().strip()
        _sb2 = os.path.join(HERE, "experiments", "sceneB_2.txt")
        sceneB_2 = ""
        if os.path.isfile(_sb2):
            sceneB_2 = open(_sb2, encoding="utf-8").read().strip()
        v16_prompt = ("Smooth transition from keyframe 1 to keyframe 2 of the same empty street scene. "
                      "Animate: thin mist drifting slowly across the wet asphalt, streetlight glow gently "
                      "brightening, distant building windows flickering softly. "
                      "Keep stable: same glass office building, same street lamp position, same cold blue "
                      "night tone, same camera angle, no people appearing, no jumps.")
        v17_prompt = ("Smooth transition from keyframe 1 to keyframe 2 of the same man in the same scene. "
                      "Animate: he raises his head slightly, shoulders relax, subtle breathing, hair moving "
                      "gently in the night wind, a faint exhale visible. "
                      "Keep stable: same face, same white shirt, same black trousers and backpack, same "
                      "midnight street background, same camera angle, no jumps, no morphing.")
        kfA = [{"role": "镜A首帧·空景", "src": first},
               {"role": "镜A尾帧·空景微变", "src": sceneA_2}]
        kfB = [{"role": "镜B首帧·人物中景", "src": last},
               {"role": "镜B尾帧·人物微变", "src": sceneB_2}]
        return {
            "v16": {"images": [first_img, sceneA_2], "keyframes": kfA,
                    "prompt": v16_prompt, "num_frames": 81,
                    "hyp": "镜A拆解：空景→空景微变（同场景双帧，雾气/灯光微动）"},
            "v17": {"images": [last, sceneB_2], "keyframes": kfB,
                    "prompt": v17_prompt, "num_frames": 81,
                    "hyp": "镜B拆解：人物中景→人物微变（同人同机位，姿态微动）"},
        }
    if template == "camera_move_v7":
        # 【第七轮·老板修正】首尾帧图本身必须符合物理/空间规律（图1状态→图2状态可衔接）
        # v18 = 镜A：真空景双帧（文生图无人物 + i2i微变无人物）——验证真空景过渡
        # v19 = 镜B：人物由远走近（远景小→走近中景，同机位同场景，物理连贯）
        anchor_far = anchor
        _af7 = os.path.join(HERE, "experiments", "anchor_far.txt")
        if os.path.isfile(_af7):
            anchor_far = open(_af7, encoding="utf-8").read().strip()
        empty1 = ""
        _e1 = os.path.join(HERE, "experiments", "sceneA_empty1.txt")
        if os.path.isfile(_e1):
            empty1 = open(_e1, encoding="utf-8").read().strip()
        empty2 = ""
        _e2 = os.path.join(HERE, "experiments", "sceneA_empty2.txt")
        if os.path.isfile(_e2):
            empty2 = open(_e2, encoding="utf-8").read().strip()
        # v19 修复：用 close2（真中近景，强制人物变大）而非 close1（人物没变）
        close1 = ""
        _c2 = os.path.join(HERE, "experiments", "sceneB_close2.txt")
        if os.path.isfile(_c2):
            close1 = open(_c2, encoding="utf-8").read().strip()
        v18_prompt = ("Smooth transition between the two keyframes of the same empty street. "
                      "Animate: thin mist drifting slowly across the wet asphalt, streetlight glow gently "
                      "pulsing, distant window lights flickering softly. "
                      "Keep stable: no people, same building, same lamp position, same camera angle, "
                      "same cold blue night, no jumps.")
        # v19 prompt 与图实际一致（人物全身→中近景，prompt 描述"走近"对应图的人物变大）
        v19_prompt = ("Smooth transition of the same man in the same street. "
                      "Animate: he takes a few steps forward (camera moves closer), subtle breathing, "
                      "hair moving gently in night wind, backpack straps shifting slightly. "
                      "Keep stable: same face, white shirt, black trousers, black backpack, same building and "
                      "lamp behind, same camera angle, no jumps, no morphing.")
        kfA2 = [{"role": "镜A首帧·真空景", "src": empty1},
                {"role": "镜A尾帧·空景微变", "src": empty2}]
        kfB2 = [{"role": "镜B首帧·人物远景", "src": anchor_far},
                {"role": "镜B尾帧·人物中近景（明显变大）", "src": close1}]
        # v20 极值：远景小人物(占1/3) → 中近景特写（人物明显变大，物理规律显著）
        distant_small = anchor_far
        _ds = os.path.join(HERE, "experiments", "sceneB_distantsmall.txt")
        if os.path.isfile(_ds):
            distant_small = open(_ds, encoding="utf-8").read().strip()
        v20_prompt = ("Smooth transition of the same man in the same street. "
                      "Animate: he walks toward the camera filling more and more of the frame, "
                      "subtle breathing, hair moving gently, backpack straps shifting. "
                      "Keep stable: same face, white shirt, black trousers, black backpack, same building and "
                      "lamp behind, same camera angle, no jumps, no morphing.")
        kfB3 = [{"role": "镜B极值首帧·人物远景小(1/3)", "src": distant_small},
                {"role": "镜B极值尾帧·人物中近景特写", "src": close1}]
        return {
            "v18": {"images": [empty1, empty2], "keyframes": kfA2,
                    "prompt": v18_prompt, "num_frames": 81,
                    "hyp": "镜A真空景双帧：文生图无人物+i2i微变（物理：同场景时间推移）"},
            "v19": {"images": [anchor_far, close1], "keyframes": kfB2,
                    "prompt": v19_prompt, "num_frames": 81,
                    "hyp": "镜B走近修复：远景→中近景（prompt与图一致，真走近）"},
            "v20": {"images": [distant_small, close1], "keyframes": kfB3,
                    "prompt": v20_prompt, "num_frames": 81,
                    "hyp": "镜B极值：远景小(1/3)→中近景特写（物理规律显著）"},
        }
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


def _cn_translate(prompt_en, timeout=60):
    """把英文视频 prompt 翻成中文（老板看板看中文，执行仍用英文原版）。失败返回空。"""
    try:
        import agnes_client as ac
        cn = ac.chat("把下面这段英文视频提示词翻译成流畅的中文，只输出翻译结果，不要解释：\n" + prompt_en,
                     model="agnes-2.5-flash", temperature=0.1, max_tokens=600, timeout=timeout)
        return (cn or "").strip()[:300]
    except Exception:
        return ""


def gen_video(prompt, images, out_dir, sid, shot, seed=None, frame_rate=24, num_frames=None):
    """提交 keyframes 视频 → 轮询 → 下载到 out_dir/shot<sid>.mp4。返回本地路径。
    seed: 固定随机种子（官方推荐可复现；训练实验传 seed 可对照排除随机性）。
    frame_rate: 帧率（官方：更流畅运动用 24 或 30）。
    num_frames: 覆盖帧数（官方：8n+1；短时长实验如 81=3.4s）；None 走 _shot_nf。"""
    os.makedirs(out_dir, exist_ok=True)
    w, h = server._video_size()
    from agnes_client import wait_for_video
    nf = num_frames or server._shot_nf(shot)
    task = _submit_video(prompt, images=images, width=w, height=h, num_frames=nf,
                         frame_rate=frame_rate, negative_prompt=NEG_PROMPT, seed=seed)
    vid = task.get("video_id") or task.get("id") or task.get("task_id")
    print("  提交 video_id=%s 轮询中（%d 帧 ≈ %.1f 秒 @%dfps，seed=%s）…" % (
        str(vid)[:20], nf, nf / float(frame_rate), frame_rate, seed if seed is not None else "随机"))
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
    if vset and all(variants[x].get("num_frames") for x in vset):
        nf = variants[vset[0]]["num_frames"]  # 短时长实验：变体级 num_frames 覆盖
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
        # 每个变体固定 seed（官方推荐可复现；确定性算法，跨进程一致）
        seed = 1000 + sum(ord(c) for c in name) % 9000
        out_dir = os.path.join(out_root, name)
        try:
            fp = gen_video(v["prompt"], v["images"], out_dir, sid, shot, seed=seed,
                           frame_rate=v.get("frame_rate", 24),
                           num_frames=v.get("num_frames"))
            print("  视频就绪: %s (%.0f KB)" % (fp, os.path.getsize(fp) // 1024))
        except Exception as e:
            print("  ❌ 变体 %s 生成失败: %s" % (name, str(e)[:150]))
            report.append({"name": name, "variant": name, "hyp": v["hyp"], "ok": False,
                           "error": str(e)[:150],
                           "params": {"prompt": v["prompt"][:400], "prompt_cn": _cn_translate(v["prompt"]),
                                      "keyframes": v.get("keyframes", []), "images": len(v["images"]),
                                      "num_frames": nf, "size": "%dx%d" % (w, h),
                                      "frame_rate": v.get("frame_rate", 24), "mode": "keyframes",
                                      "model": "agnes-video-v2.0", "negative": NEG_PROMPT, "seed": seed, "duration_s": round(nf / float(v.get("frame_rate", 24)), 1)}})
            continue
        # 质检：AGNES 4 维诊断 + face
        try:
            # 【0812 修复】单镜诊断必须传"只含当前镜"的 storyboard——face_consistency 按时间线累计
            # 抽帧，传完整 10 镜 storyboard 会让 scale≈0.067，抽帧点全挤在开头 0.34s → 人脸误检 intra_jump
            _single_sb = {"shots": [{"id": sid, "duration": nf / float(v.get("frame_rate", 24))}]}
            d = diagnose_clip(fp, n_frames=4, face_check=True,
                              storyboard=_single_sb,
                              deep=False)
            scores = (d.get("scores") or {}) if isinstance(d, dict) else {}
            print("  诊断:", json.dumps(scores, ensure_ascii=False), "| verdict:", (d or {}).get("verdict"))
        except Exception as e:
            scores = {}
            print("  诊断失败: %s" % str(e)[:100])
        # 【0812 老板方法论】提示词-帧匹配检查：开场场景 vs 首帧 + 结束状态 vs 尾帧
        pfm = {"overall": None, "opening": {}, "ending": {}}
        try:
            from vision_review import prompt_frame_match
            _f0 = os.path.join(out_dir, "pfm_first.jpg")
            _f1 = os.path.join(out_dir, "pfm_last.jpg")
            subprocess.run(["ffmpeg", "-y", "-i", vf, "-frames:v", "1", _f0],
                           capture_output=True, timeout=90)
            subprocess.run(["ffmpeg", "-y", "-sseof", "-0.2", "-i", vf, "-frames:v", "1", _f1],
                           capture_output=True, timeout=90)
            if os.path.isfile(_f0) and os.path.isfile(_f1):
                _pfm = prompt_frame_match(v["prompt"], _f0, _f1)
                pfm = {"overall": _pfm.get("overall"), "opening": _pfm.get("opening") or {},
                       "ending": _pfm.get("ending") or {}}
                print("  提示词-帧匹配:", pfm.get("overall"), "| 开场:", (pfm["opening"] or {}).get("verdict"),
                      "| 结束:", (pfm["ending"] or {}).get("verdict"))
        except Exception as e:
            print("  prompt-帧匹配失败: %s" % str(e)[:80])
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
                # 【0812 老板方法论】空镜免检：prompt 描述 no people/空景时，尾帧无人物，
                # 拿空镜帧比锚点脸必 fail 属误报——直接标记 N/A（免检）
                _p_low = (v.get("prompt") or "").lower()
                _is_empty = ("no people" in _p_low or "no person" in _p_low
                             or "empty " in _p_low or "without any people" in _p_low)
                if _is_empty:
                    vr = {"verdict": "n/a", "issues": [],
                          "note": "空镜镜头（prompt 无人物），免检尾帧脸型"}
                    print("  identity 审查(尾帧): n/a（空镜免检）")
                else:
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
                # 【开头闪帧·0811 老板新盲区】抽视频前 0/0.4/1.0s + 尾帧，检查开头异常闪现
                ifl = {"verdict": None, "issues": []}
                try:
                    ifl_imgs = []
                    for t in ["0", "0.4", "1.0", "2.0"]:
                        op = os.path.join(out_dir, "open_%s.png" % t.replace(".", "_"))
                        subprocess.run(["ffmpeg", "-y", "-ss", t, "-i", vf, "-frames:v", "1", op],
                                       capture_output=True, timeout=60)
                        if os.path.isfile(op):
                            ifl_imgs.append(op)
                    ifl_imgs.append(frame)
                    if len(ifl_imgs) >= 3:
                        iflr = review(ifl_imgs, kind="intro_flash")
                        ifl = {"verdict": iflr.get("verdict"), "issues": (iflr.get("issues") or [])[:2]}
                        print("  开头闪帧:", ifl.get("verdict"), "|",
                              (ifl.get("issues") or [{}])[0].get("desc", "")[:44] if ifl.get("issues") else "正常平滑")
                except Exception as _e:
                    print("  开头闪帧审查失败: %s" % str(_e)[:80])
                report.append({"name": name, "variant": name, "hyp": v["hyp"], "ok": True,
                               "diagnosis": scores, "verdict": (d or {}).get("verdict"),
                               "identity_review": vr.get("verdict"),
                               "identity_issues": (vr.get("issues") or [])[:3],
                               "internal_consistency": ic,
                               "intro_flash": ifl,
                               "prompt_frame_match": pfm,
                               "video": vf,
                               "params": {"prompt": v["prompt"][:400], "prompt_cn": _cn_translate(v["prompt"]),
                                          "keyframes": v.get("keyframes", []), "images": len(v["images"]),
                                          "num_frames": nf, "size": "%dx%d" % (w, h),
                                          "frame_rate": v.get("frame_rate", 24), "mode": "keyframes",
                                          "model": "agnes-video-v2.0", "negative": NEG_PROMPT, "seed": seed, "duration_s": round(nf / float(v.get("frame_rate", 24)), 1)}})
                vid_ok = True
        except Exception as e:
            print("  identity 审查失败: %s" % str(e)[:100])
        if not vid_ok:
            report.append({"name": name, "variant": name, "hyp": v["hyp"], "ok": True,
                           "diagnosis": scores, "verdict": (d or {}).get("verdict"),
                           "params": {"prompt": v["prompt"][:400], "prompt_cn": _cn_translate(v["prompt"]),
                                      "keyframes": v.get("keyframes", []), "images": len(v["images"]),
                                      "num_frames": nf, "size": "%dx%d" % (w, h),
                                      "frame_rate": v.get("frame_rate", 24), "mode": "keyframes",
                                      "model": "agnes-video-v2.0", "negative": NEG_PROMPT, "seed": seed, "duration_s": round(nf / float(v.get("frame_rate", 24)), 1)}})

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
