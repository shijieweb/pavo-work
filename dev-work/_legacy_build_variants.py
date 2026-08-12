# 自动生成：before 提交 d50d0fa 的原 build_variants 快照（仅用于回归对比，不进生产）。
import os, base64
import server  # 回归时由调用方 stub
HERE = 'C:/Users/67972/WorkBuddy/workbuddy/short_drama_workflow/scripts/diag'

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


