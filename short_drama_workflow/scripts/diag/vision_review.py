#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉审查引擎 vision_review.py（老板 0811 全 7 项拍板）
基于 AGNES agnes-2.5-flash 多模态（免费 3000 次/天），对生成图/视频帧/网页截图做结构化审查。

审查类型：
  quality    单帧画质（畸形/穿帮/多余物体/AI 痕迹）
  identity   角色一致性（2 图：锚点 vs 生成帧 → 脸/发型/衣服/配饰是否变）
  continuity 镜头连贯性（2 图：上镜尾帧 vs 下镜首帧 → 场景/站位/光线接戏）
  layout     UI 布局（截图：错位/重叠/溢出/空白/文字截断）
  text       文字/字幕合规（意外文字/字幕错位/AI 水印）
  content    内容初审（低俗/违规/品牌意外露出，过审前筛查）
  emotion    情绪/表演（结合剧本情绪文本，表情是否匹配）

统一返回 dict：
  {"ok": True, "kind": str, "verdict": "pass|warn|fail", "issues": [{"type","severity","desc"}],
   "confidence": 0-1, "raw": 模型原文}

用法：
  python vision_review.py <图1> [图2] --kind identity [--context "剧本情绪"]
"""
import base64, json, os, re, sys

sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))

_JSON_REQ = ('\n\n输出格式（严格 JSON，不要 markdown 代码块）：'
             '{"verdict": "pass|warn|fail", '
             '"issues": [{"type": "问题类型", "severity": "high|medium|low", "desc": "具体描述"}], '
             '"confidence": 0.9}')

PROMPTS = {
    "quality": (
        "你是 AI 短剧画质审查员。请仔细检查这张图片：人物形态（手/手指/五官是否畸形、比例是否正常）、"
        "穿帮（多余物体、悬浮物、结构错误）、AI 生成痕迹（皮肤/头发/边缘的伪影）、光影是否自然。"
        "若画面干净则 issues 为空数组、verdict=pass。"),
    "identity": (
        "你是角色一致性审查员。对比这两张图是否是【同一角色】：重点检查脸型、五官、发型发色、"
        "服装颜色与款式、配饰（背包/首饰）、肤色。任何明显不一致（如衣服颜色变了、脸型变了、"
        "发型变了）都记为 issue。两图相似则 verdict=pass。"),
    "internal": (
        "你是视频内部一致性审查员。对比这两帧画面：这是【同一段视频】的首帧和尾帧（同一角色、同一场景）。"
        "请重点检查【服装颜色和款式是否一致】：首帧角色穿什么颜色衣服（可能因远景而模糊/剪影），"
        "尾帧角色穿什么颜色衣服。如果颜色/款式明显不同（如黑色外套 vs 白色衬衫）则 verdict=fail。"
        "若两帧景别不同导致一帧看不清，以能看清角色外观的一帧为准判断服装是否一致。"
        "同时检查场景是否发生突变（本镜不应换场景）。"),
    "continuity": (
        "你是镜头连贯性审查员（接戏检查）。对比这两帧：场景是否同一、人物站位是否合理衔接、"
        "光线方向与色温是否一致、道具是否错位。这是相邻镜头（上镜尾帧 vs 下镜首帧），"
        "轻微自然变化可接受，明显跳戏/场景突变记 issue。连贯则 verdict=pass。"),
    "layout": (
        "你是网页 UI 布局审查员。检查这张网页截图：元素是否错位、重叠、溢出边界、大片空白、"
        "文字被截断、按钮/面板缺失、布局明显错乱。页面正常则 verdict=pass，否则列出具体布局问题。"),
    "text": (
        "你是画面文字合规审查员。检查这张图：画面内是否出现意外文字/字幕/标语/logo（短剧视频不应"
        "有烧录字幕除非设计如此）、字幕是否错位或乱码、AI 生成水印位置是否异常。无意外文字则 pass。"),
    "content": (
        "你是短剧内容合规初审员。检查这张图是否有：低俗/色情暗示、暴力血腥、歧视性内容、"
        "意外品牌 logo 露出、违法违规元素。合规则 verdict=pass；有问题列出 issue（此审查是过审前"
        "人工复核的辅助，不替代平台审核）。"),
    "emotion": (
        "你是短剧表演审查员。结合给定的剧本情绪要求，检查画面人物表情/姿态是否匹配该情绪"
        "（如'疲惫'应看到倦容/低头/肩部下沉；'惊喜'应看到睁眼/张嘴/身体前倾）。"
        "明显不匹配记 issue，匹配则 pass。"),
    "intro_flash": (
        "你是视频【开头闪帧审查员】。这是同一段视频的连续几帧（0秒/0.4秒/1秒/2秒/最后一帧），"
        "请判断视频开头是否出现异常闪现：① 开头帧是否出现与首帧设计意图不符的人物特写/画面突变"
        "（如首帧是空景但第0/0.4秒突然出现人物特写）；② 开头几帧是否连贯平滑，"
        "还是出现'人物闪现-消失-再现'的异常节奏；③ 人物出现时机是否符合镜头叙事"
        "（如运镜镜头人物应从远景逐渐推近，不应一开始就是中近景）。"
        "发现异常闪现记为 fail，问题记入 issues（severity high/low）。正常平滑记为 pass。"
        "输出 JSON: verdict + issues + confidence。"),
}

_KIND_REQUIRE = {"quality": 1, "identity": 2, "continuity": 2, "layout": 1,
                 "text": 1, "content": 1, "emotion": 1, "internal": 2,
                 "intro_flash": 3}


def _datauri(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
    return f"data:{mime};base64,{b64}"


def _img_src(path):
    """图片入参归一：http(s)/data URI 直接用（AGNES 支持 URL）；本地文件转 data URI。"""
    s = str(path)
    if s.startswith("http") or s.startswith("data:"):
        return s
    return _datauri(s)


def _extract_json(text):
    """从模型输出提取 JSON（去 markdown 代码块，找 { ... } 主体）。"""
    if not text:
        return None
    t = re.sub(r"```(?:json)?|```", "", text)
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        return json.loads(t[s:e + 1])
    except Exception:
        # 尝试修复常见 JSON 问题（尾逗号、单引号）
        cand = re.sub(r",\s*([}\]])", r"\1", t[s:e + 1])
        cand = cand.replace("'", '"')
        try:
            return json.loads(cand)
        except Exception:
            return None


def prompt_frame_match(prompt_en, first_path, last_path, model="agnes-2.5-flash", timeout=150):
    """【0812 老板方法论】提示词-帧匹配检查：
    ① 提示词的开场场景描述 vs 首帧图（场景/光线/环境元素，人物可后出现）
    ② 提示词的结束状态描述 vs 尾帧图（人物姿态/景别/场景）
    返回 {ok, opening:{verdict,issues}, ending:{verdict,issues}, overall}。
    场景元素缺→warn，完全冲突（如首帧有人但 prompt 写 no people）→fail。"""
    P = (
        "你是短剧【提示词-画面匹配审查员】。下面是一段视频的提示词（英文）+ 该视频的首帧图和尾帧图。\n"
        "提示词：\n" + (prompt_en or "")[:1200] + "\n\n"
        "请分别判断：\n"
        "① 开场匹配：首帧图是否与提示词描述的开场场景元素一致（场景类型/建筑/光线/氛围/时间）？\n"
        "   注意：运镜镜头首帧是空景属正常，人物不在首帧不算不匹配；但场景元素（如'玻璃幕墙''路灯''夜晚'）"
        "缺失或冲突（如提示词写 no people 但首帧有人）要标记。\n"
        "② 结束匹配：尾帧图是否与提示词描述的结束状态一致（人物姿态/景别/表情/场景）？\n"
        "   注意：尾帧应该出现提示词描述的主要人物和关键元素；景别（远景/中景/近景）、姿态、服装应匹配。\n"
        "输出 JSON：{\"opening\": {\"verdict\": \"pass|warn|fail\", "
        "\"issues\": [{\"type\": \"场景缺失|场景冲突|其他\", \"severity\": \"high|low\", \"desc\": \"具体说明\"}]},\n"
        "           \"ending\": {\"verdict\": \"pass|warn|fail\", "
        "\"issues\": [{\"type\": \"人物缺失|景别不符|姿态不符|服装不符|场景冲突\", \"severity\": \"high|low\", \"desc\": \"具体说明\"}]},\n"
        "           \"overall\": \"pass|warn|fail\"}")
    try:
        sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))
        import agnes_client as ac
        raw = ac.chat(P, images=[_img_src(first_path), _img_src(last_path)],
                      model=model, temperature=0.2, max_tokens=1200, timeout=timeout)
        j = _extract_json(raw or "")
        if not j:
            return {"ok": False, "error": "解析失败", "raw": (raw or "")[:200]}
        return {"ok": True, **j}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def review(paths, kind="quality", context="", model="agnes-2.5-flash", timeout=150):
    """执行一次视觉审查。paths: 图片路径列表；kind: 审查类型；context: 附加上下文（如情绪要求/剧本）。
    返回统一 dict（见模块 docstring）。失败时 ok=False + error。"""
    if kind not in PROMPTS:
        return {"ok": False, "error": "未知审查类型: %s" % kind}
    need = _KIND_REQUIRE[kind]
    if len(paths) < need:
        return {"ok": False, "error": "%s 需要 %d 张图，给了 %d" % (kind, need, len(paths))}
    bad = [p for p in paths
           if not (str(p).startswith("http") or str(p).startswith("data:") or os.path.exists(p))]
    if bad:
        return {"ok": False, "error": "图片不存在: %s" % bad[0]}
    prompt = PROMPTS[kind] + _JSON_REQ
    if context:
        prompt += "\n剧本情绪/上下文：" + context
    try:
        import agnes_client as ac
        raw = ac.chat(prompt, images=[_img_src(p) for p in paths],
                      model=model, temperature=0.2, max_tokens=1200, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": "AGNES 审查调用失败: %s" % str(e)[:200]}
    if not raw:
        return {"ok": False, "error": "审查返回空"}
    data = _extract_json(raw)
    if not data:
        return {"ok": True, "verdict": "warn", "issues": [{"type": "解析失败", "severity": "low",
                "desc": "模型未返回结构化 JSON，以下为原文"}], "confidence": 0.0, "raw": raw[:800]}
    verdict = data.get("verdict") if data.get("verdict") in ("pass", "warn", "fail") else "warn"
    issues = data.get("issues")
    if not isinstance(issues, list):
        issues = []
    return {"ok": True, "kind": kind, "verdict": verdict,
            "issues": issues,
            "confidence": float(data.get("confidence") or 0),
            "raw": raw[:1200]}


if __name__ == "__main__":
    args = sys.argv[1:]
    kind = "quality"
    if "--kind" in args:
        i = args.index("--kind")
        kind = args[i + 1]
        args = args[:i] + args[i + 2:]
    context = ""
    if "--context" in args:
        i = args.index("--context")
        context = args[i + 1]
        args = args[:i] + args[i + 2:]
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("用法: python vision_review.py <图1> [图2] --kind <type> [--context 文本]", file=sys.stderr)
        sys.exit(1)
    r = review(paths, kind=kind, context=context)
    print(json.dumps(r, ensure_ascii=False, indent=2))
