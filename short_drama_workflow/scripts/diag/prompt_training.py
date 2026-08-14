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
import yaml
import logging

logger = logging.getLogger("prompt_training")
# 确保 warning 级别有可见输出（自挂 handler，不依赖调用方/其它模块的 logging 配置）
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.WARNING)

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(HERE, "templates")
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
    """从 YAML 模板加载变体：注入变量 → 渲染 keyframes/prompt → 返回变体字典。
    默认 template=camera_move_v2（原默认 fallthrough 分支）。不改动训练/生成逻辑，
    main() 仍消费 v["prompt"]/v["images"]/v.get("num_frames")/v.get("frame_rate")，
    看板用 v["keyframes"] 的 {role,src} 列表。"""
    tpl_path = os.path.join(TEMPLATES_DIR, "%s.yaml" % template)
    if not os.path.isfile(tpl_path):
        raise FileNotFoundError("模板不存在: %s.yaml" % template)
    with open(tpl_path, encoding="utf-8") as f:
        tpl = yaml.safe_load(f) or {}
    # ── T-14 #4 S4：YAML 缺字段明确告警（不再静默返回空/{}）──
    if not isinstance(tpl, dict):
        logger.warning("YAML 模板 %s 解析结果非字典（疑似内容为空或格式错误），variants 将为空", template)
    for _key in ("name", "variables", "constants", "variants"):
        if _key not in tpl:
            logger.warning("YAML 模板 %s 缺少关键字段 '%s'：将按默认值处理（variables={}, constants={}, variants={}），渲染可能为空", template, _key)
    variables = _resolve_variables(tpl.get("variables", {}), shot, ref)
    ctx = {**variables, **(tpl.get("constants") or {})}
    variants = {name: _render_variant(vdef, ctx)
                for name, vdef in (tpl.get("variants") or {}).items()}
    if not variants:
        logger.warning("YAML 模板 %s 未渲染出任何变体（variants 缺失或为空），请检查 variants 字段", template)
    return variants


def _locked_seed(writing_name, explicit_seed=None):
    """seed 锁定：复刻 main() 的派生逻辑。

    - explicit_seed 给定 -> 直接用（用户指定锁定）；
    - 否则 -> 由写法号确定性派生（main() 现状）：1000 + Σord(c) % 9000，
      保证同一写法号在跨生成/跨进程间可复现（seed 不随机漂移）。
    返回 int 或 None(随机)。
    """
    if explicit_seed is not None:
        try:
            return int(explicit_seed)
        except (TypeError, ValueError):
            return None
    return 1000 + sum(ord(c) for c in writing_name) % 9000


def cross_seed_consistency_report(shot, ref, template="camera_move_v2", seed_strategies=None):
    """P0-4 跨 seed 一致性校验（L0 静态/dry-run，不调 AGNES，不烧 VIP）。

    ★ 定义（写入 design.md）：
      - 跨 seed 指什么：对同一写法（写法号 / YAML variant，如 v0/v1/v4/v5）分别用多种
        seed 策略做"生成"——['name-locked'(按写法号派生,默认), 'explicit-42'(用户指定),
        'explicit-999'(用户指定), 'random'(不锁)]——校验写法本身渲染出的角色关键属性
        是否随 seed 策略漂移。
      - 角色关键属性（3 项）：① 人物描述(prompt) ② seed 锁定(seed) ③ 关键帧(keyframes)。
      - 一致性判据：写法渲染出的 prompt / keyframes 内容在所有 seed 策略下**逐字符一致**
        （AGNES seed 只影响生成随机性，不应改变写法本身的角色关键属性）；且 name-locked
        seed 对同一写法号在多次生成间可复现（确定性）。

    ★ 说明：build_variants 渲染 prompt/keyframes 不接收 seed（seed 仅在 gen_video 提交时生效），
      故"跨 seed 渲染一致性"= 验证上述不变式：seed 策略改变不应让写法本身漂移。本检查为 L0
      静态对比，不调用 AGNES/不烧 VIP，符合 I-2 例外（仅 L0 静态/dry-run 不改生成逻辑）。

    返回 dict：{template, strategies, writings:[...], all_consistent}
    """
    if seed_strategies is None:
        seed_strategies = [("name-locked", None), ("explicit-42", 42),
                           ("explicit-999", 999), ("random", "random")]
    variants = build_variants(shot, ref, template)
    writings = list(variants.keys())
    report_writings = []
    all_consistent = True
    for w in writings:
        rendered = {}
        seeds = {}
        for sname, sval in seed_strategies:
            vv = build_variants(shot, ref, template)[w]  # seed 不影响渲染（不变式待验证）
            rendered[sname] = {
                "prompt": vv.get("prompt", ""),
                "keyframes": json.dumps(vv.get("keyframes", []), ensure_ascii=False, sort_keys=True),
                "images": json.dumps(vv.get("images", []), ensure_ascii=False, sort_keys=True),
            }
            seeds[sname] = _locked_seed(w, None if sval == "random" else sval)
        base_prompt = rendered[seed_strategies[0][0]]["prompt"]
        base_kf = rendered[seed_strategies[0][0]]["keyframes"]
        drift = []
        prompt_consistent = True
        keyframes_consistent = True
        for sname, _ in seed_strategies[1:]:
            if rendered[sname]["prompt"] != base_prompt:
                prompt_consistent = False
                drift.append("prompt@%s 与 %s 不同" % (sname, seed_strategies[0][0]))
            if rendered[sname]["keyframes"] != base_kf:
                keyframes_consistent = False
                drift.append("keyframes@%s 与 %s 不同" % (sname, seed_strategies[0][0]))
        # seed 锁定可复现：name-locked 两次调用一致
        seed_locked = (seeds["name-locked"] == _locked_seed(w, None))
        if not seed_locked:
            drift.append("name-locked seed 不可复现")
        ok = prompt_consistent and keyframes_consistent and seed_locked
        if not ok:
            all_consistent = False
        report_writings.append({
            "writing": w,
            "prompt_consistent": prompt_consistent,
            "keyframes_consistent": keyframes_consistent,
            "seed_locked": seed_locked,
            "seeds": seeds,
            "drift": drift,
            "consistent": ok,
        })
    return {
        "template": template,
        "strategies": [s[0] for s in seed_strategies],
        "writings": report_writings,
        "all_consistent": all_consistent,
    }


def _get_by_path(shot, ref, path):
    """dotted path 取值：ref.x / shot.x / 直接 shot key。"""
    if path.startswith("ref."):
        return (ref or {}).get(path[4:], "")
    if path.startswith("shot."):
        return (shot or {}).get(path[5:], "")
    return (shot or {}).get(path, "")


def _resolve_variables(var_defs, shot, ref):
    """从 shot/ref 按路径取值，或读 file: 标记的实验文件（缺失优雅 fallback）。"""
    ctx = {}
    for name, spec in (var_defs or {}).items():
        if isinstance(spec, dict):
            if "file" in spec:
                fp = os.path.join(HERE, spec["file"]) if not os.path.isabs(spec["file"]) else spec["file"]
                val = open(fp, encoding="utf-8").read().strip() if os.path.isfile(fp) else spec.get("default", "")
                ctx[name] = _render_template(val, ctx) if "{{" in str(val) else val
            elif "shot" in spec:
                val = (shot or {}).get(spec["shot"], "")
                if spec.get("data_uri") and isinstance(val, str) and val.startswith("assets/"):
                    val = _datauri(server.asset_abs(val))
                ctx[name] = val
            elif "ref" in spec:
                ctx[name] = (ref or {}).get(spec["ref"], "")
            else:
                ctx[name] = ""
        else:
            ctx[name] = _get_by_path(shot, ref, spec)
    return ctx


def _render_template(text, ctx):
    """简单 {{var}} 替换（零依赖，不用 Jinja2）；缺失变量替换为空串。"""
    if not isinstance(text, str):
        text = str(text)
    for k, v in (ctx or {}).items():
        text = text.replace("{{%s}}" % k, str(v if v is not None else ""))
    return text.strip()


def _resolve_images(token, ctx):
    """解析单个 keyframe src 标记，返回结构化结果 {"mode", "raw"}（raw 为未转 data_uri 的干净值）。

    语义（AC-1.5）：
      - text:xxx  → 文生图 text_to_image（首帧，无源图，用 prompt 生成图）
      - i2i:xxx   → 图生图 image_to_image（尾帧，基于上一帧）
      - file:xxx  → 读实验文件（mode=file）
      - 其它（camera_move 的 {{first}}/{{last}}/{{anchor}} 真实图路径/URL）→ mode=image
        （assets/ 前缀帧图在 _render_variant 收集 images 时转 data URI，复刻旧版 first 帧逻辑）
    """
    s = _render_template(token, ctx)
    if s.startswith("text:"):
        return {"mode": "text_to_image", "raw": s[len("text:"):].strip()}
    if s.startswith("i2i:"):
        return {"mode": "image_to_image", "raw": s[len("i2i:"):].strip()}
    if s.startswith("file:"):
        p = s[len("file:"):]
        fp = os.path.join(HERE, p) if not os.path.isabs(p) else p
        content = open(fp, encoding="utf-8").read().strip() if os.path.isfile(fp) else ""
        return {"mode": "file", "raw": content}
    return {"mode": "image", "raw": s}


def _render_variant(vdef, ctx):
    """把单个变体定义渲染为 main() 消费的字典：images + keyframes(role/src) + prompt + hyp。

    关键帧语义（AC-1.5）：
      - text_to_image（首帧文生图，无源图）/ image_to_image（尾帧图生图，基于上一帧）：
        images 每帧为 {"mode":..., "content":...} dict，供下游 gen_video 区分首帧文生图/尾帧 i2i；
        keyframes 的 role/src 渲染为干净值（去掉 text:/i2i: 前缀）。
      - image（camera_move 真实图路径/URL）：images 保持字符串格式（兼容 gen_video）；
        assets/ 前缀帧图转 data URI（复刻旧版 first 帧 _datauri(server.asset_abs(...)) 逻辑）。
    """
    keyframes, images = [], []
    for kf in vdef.get("keyframes", []):
        if isinstance(kf, dict):
            role, raw = kf.get("role", ""), kf.get("src", "")
        else:
            role, raw = "", kf
        res = _resolve_images(raw, ctx)
        mode, content = res["mode"], res["raw"]
        # keyframes：role/src 渲染为干净值（去掉 text:/i2i: 前缀）；src 保持原始值（与旧版看板展示一致）
        if not role:
            role = {"text_to_image": "文生图(无源图)",
                    "image_to_image": "图生图(基于上一帧)"}.get(mode, raw)
        keyframes.append({"role": role, "src": content})
        # images：文生图/图生图 → 带 mode 标记的 dict；真实图 → 字符串（assets/ 转 data URI）
        if mode in ("text_to_image", "image_to_image"):
            images.append({"mode": mode, "content": content})
        else:
            img = _datauri(server.asset_abs(content)) if (
                isinstance(content, str) and content.startswith("assets/")) else content
            images.append(img)
    prompt = _render_template(vdef.get("prompt") or vdef.get("video_prompt") or "", ctx)
    out = {"images": images, "keyframes": keyframes, "prompt": prompt,
           "hyp": vdef.get("hypothesis", "")}
    for opt in ("goal", "reference", "implement"):
        if vdef.get(opt):
            out[opt] = _render_template(vdef[opt], ctx)
    if vdef.get("num_frames") is not None:
        out["num_frames"] = vdef["num_frames"]
    if vdef.get("frame_rate") is not None:
        out["frame_rate"] = vdef["frame_rate"]
    if vdef.get("mode"):
        out["mode"] = vdef["mode"]
    if vdef.get("negative") is not None:
        out["negative"] = _render_template(str(vdef["negative"]), ctx)
    if vdef.get("identity_check"):
        out["identity_check"] = vdef["identity_check"]
    return out


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


def _learn_block(name, verdict, hyp, diag, ifl, ic, pfm, vr, v, nf, w, h, seed):
    """【自动固化流水线·结构化经验产出】pass 变体自动生成 rules_draft/evidence/pass_reason，
    供 auto_learn.py 只读提取。模板化组装，不依赖 LLM，保证确定性。"""
    sc = diag or {}
    ok4 = all((sc.get(k) or 0) >= 7 for k in ("continuity", "physical", "character", "first_last"))
    ifl_v = (ifl or {}).get("verdict")
    ic_v = (ic or {}).get("verdict")
    pfm_v = (pfm or {}).get("overall") or ((pfm or {}).get("ending") or {}).get("verdict")
    vr_v = (vr or {}).get("verdict") if isinstance(vr, dict) else vr
    # 证据：质检数据快照（供 auto_learn 过滤与展示）
    evidence = {
        "variant": name,
        "verdict": verdict,
        "scores": {k: sc.get(k) for k in
                   ("continuity", "physical", "character", "first_last", "face", "quality")},
        "intro_flash": ifl_v, "internal_consistency": ic_v,
        "prompt_frame_match": pfm_v, "identity": vr_v,
        "num_frames": nf, "frame_rate": v.get("frame_rate", 24),
        "duration_s": round(nf / float(v.get("frame_rate", 24)), 1),
        "size": "%dx%d" % (w, h), "seed": seed,
        "negative": bool(NEG_PROMPT),         # evidence 保留布尔值（标记是否使用负面词）
        "negative_prompt": NEG_PROMPT[:200],  # P0-3 修复：同时记录实际负面词文本
    }
    # 通过原因（模板化判定）
    reasons = []
    if ok4:
        reasons.append("4维全>=7")
    if ifl_v == "pass":
        reasons.append("intro_flash pass(开头不闪)")
    if ic_v in ("pass", "warn", None):
        reasons.append("内部一致 pass/warn")
    if pfm_v in ("pass", "warn", None):
        reasons.append("prompt-帧匹配 pass/warn")
    if isinstance(vr_v, str) and vr_v in ("pass", "n/a", None):
        reasons.append("尾帧脸型 pass/n/a")
    pass_reason = "+".join(reasons) if reasons else "verdict=pass"
    # 规则草案：从假说 hyp 提炼（模板化，不编造）
    rules_draft = []
    if verdict == "pass" and ok4:
        rules_draft.append("【%s 已验证配方】%s（证据: %s）" % (name, hyp, pass_reason))
    return {"rules_draft": rules_draft, "evidence": evidence, "pass_reason": pass_reason}


def gen_video(prompt, images, out_dir, sid, shot, seed=None, frame_rate=24, num_frames=None):
    """提交 keyframes 视频 → 轮询 → 下载到 out_dir/shot<sid>.mp4。返回本地路径。
    seed: 固定随机种子（官方推荐可复现；训练实验传 seed 可对照排除随机性）。
    frame_rate: 帧率（官方：更流畅运动用 24 或 30）。
    num_frames: 覆盖帧数（官方：8n+1；短时长实验如 81=3.4s）；None 走 _shot_nf。

    兼容结构化关键帧（AC-1.5）：images 元素可为 {"mode":..., "content":...} dict，
    其中 text_to_image=文生图首帧（无源图）/ image_to_image=图生图尾帧；此处还原为提交用的 content，
    保持与旧版字符串格式一致的行为。"""
    # 还原结构化关键帧为提交用内容（字符串格式不变），同时保留 mode 信息供下游扩展
    norm_images = []
    for _im in (images or []):
        if isinstance(_im, dict):
            norm_images.append(_im.get("content"))
        else:
            norm_images.append(_im)
    images = norm_images
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
    if not pid and "--cross-seed" not in args:
        print("用法: python prompt_training.py --project <id> --shot <n> [--variants v0,v1,v4,v5] [--template camera_move_v2|camera_move_v1] [--type 镜头类型] [--cross-seed]", file=sys.stderr)
        sys.exit(1)

    if pid:
        server.load_spec(pid)
        shot = server.find_shot(sid)
        if shot is None:
            print("shot %d 不存在" % sid, file=sys.stderr)
            sys.exit(1)
        ref = (server.SPEC.get("references") or {}).get(shot.get("ref") or "") or {}
    else:
        # 无 --project：用合成 shot/ref 做纯模板级一致性校验（不依赖真实 spec，L0 静态）
        shot = {"video_prompt": "A young man in a white shirt walks forward along the riverside, calm mood, soft identity lock.",
                "ref": "hero", "cn_story": "合成测试镜头(无真实 spec)", "camera": "中景跟随"}
        ref = {"remote_url": "https://example.com/anchor.png", "asset_image": "https://example.com/anchor.png"}
    anchor = (ref or {}).get("remote_url") or (ref or {}).get("asset_image") or shot.get("remote_image_ref") or ""

    # ── T-14 #3 P0-4 跨 seed 一致性校验（L0 静态/dry-run：只渲染 YAML 对比，不调 AGNES，不烧 VIP）──
    if "--cross-seed" in args:
        rep = cross_seed_consistency_report(shot, ref, tpl)
        print("\n" + "=" * 70)
        print("P0-4 跨 seed 一致性报告（模板=%s）" % tpl)
        print("=" * 70)
        for w in rep["writings"]:
            print("[%s] 一致=%s | prompt一致=%s keyframes一致=%s seed锁定=%s | 漂移=%s" % (
                w["writing"], w["consistent"], w["prompt_consistent"],
                w["keyframes_consistent"], w["seed_locked"], w["drift"] or "无"))
        print("\n结论: all_consistent=%s" % rep["all_consistent"])
        os.makedirs(EXPDIR, exist_ok=True)
        _rep_path = os.path.join(EXPDIR, "cross_seed_consistency_%s.json" % time.strftime("%m%d_%H%M%S"))
        with open(_rep_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print("报告已存: %s" % _rep_path)
        return

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
                               "learn": _learn_block(name, (d or {}).get("verdict"), v["hyp"], scores,
                                                     ifl, ic, pfm, vr, v, nf, w, h, seed),
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
