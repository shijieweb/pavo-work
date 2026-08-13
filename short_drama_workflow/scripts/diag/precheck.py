#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-2 图视冲突预检 precheck.py（T-20260813-06）

生成前预检：镜头 prompt 描述 vs 首尾帧图实际内容的冲突（如 prompt 说近景、首帧却是远景），
提前拦截图视矛盾，避免烧视频额度后出片才发现问题（PRD P0-2 / 08 经验库 0812 老板方法论）。

只读复用（不改）：
- vision_review.prompt_frame_match：提示词开场场景 vs 首帧 + 结束状态 vs 尾帧 → match/warn/fail
- server 纯函数：_transition_prompt / _clean_video_prompt / _clean_global_style / _animate_clause /
  _identity_lock / _camera_clause / _cinema_clause / _speech_clause（渲染"真正提交给 AGNES 的最终 prompt"）
- prompt_training 空镜免检口径：prompt 含 no people/no person/empty /without any people → n/a

用法：
  # 零额度 dry-run（不调 AGNES 视觉 API）
  python precheck.py --project ep_0811_145935 --shot 1 --dry-run
  # 真跑视觉（免费 key：AGNES_TEST_MODE=1 + AGNES_TEST_API_KEY，不占 VIP）
  AGNES_TEST_MODE=1 python precheck.py --project ep_0811_145935 --shot 1
  # 直接传图/prompt（不依赖项目）
  python precheck.py --shot-id 1 --first a.png --last b.png --prompt "Wide shot, ..." --dry-run
"""
import argparse
import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.join(HERE, "..", "..", "html_prototype")
sys.path.insert(0, PROJ_ROOT)
sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/agnes-ai/scripts"))

import server  # noqa: E402  (只读复用 asset_abs / 纯函数；import 不启动 HTTP 服务)

# ---- 空镜免检关键词（与 prompt_training.py:417-419 完全一致，防口径漂移）----
EMPTY_KEYWORDS = ("no people", "no person", "empty ", "without any people")


def is_empty_shot(prompt):
    """空镜免检判定：prompt 小写含 no people/no person/empty /without any people → True。"""
    p = (prompt or "").lower()
    return any(k in p for k in EMPTY_KEYWORDS)


def _datauri(path):
    """本地文件 → data URI（与 vision_review._datauri 同构，避免跨模块私有依赖）。"""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
    return "data:%s;base64,%s" % (mime, b64)


def _frame_src(v):
    """把首/尾帧入参归一化为 AGNES 可读：http/data URI 原样；assets/ 相对路径转 data URI。"""
    if not v:
        return ""
    s = str(v)
    if s.startswith("http") or s.startswith("data:"):
        return s
    if s.startswith("assets/"):
        abs_p = server.asset_abs(s)
        return _datauri(abs_p) if os.path.isfile(abs_p) else ""
    return _datauri(s) if os.path.isfile(s) else s


def _resolve_frames(shot, first, last):
    """首/尾帧图解析：显式传参 > shot.asset_frame_start/end > 空串。
    返回 (first_src, last_src)（http/data URI/本地 data URI）。"""
    f0 = first if first is not None else (shot.get("asset_frame_start") or "")
    f1 = last if last is not None else (shot.get("asset_frame_end") or "")
    return _frame_src(f0), _frame_src(f1)


def render_final_prompt(shot, strategy=None):
    """渲染"真正提交给 AGNES 的最终 prompt"（只读复用 server 纯函数，镜像 server.py 生成链拼装）。

    strategy 缺省取 shot.gen_strategy；与 server._gen_video 完全同构：
    - keyframes: _transition_prompt + 身份锁 + 运镜 + 电影语法 + 台词
    - reference: _clean_video_prompt + 全局风格 + Animate + 身份锁/稳定句 + 运镜 + 电影语法 + 台词
    - text2video: video_prompt + 全局风格 + 运镜 + Animate
    - ui/未知: 空串（无可比 prompt，预检标 n/a）
    """
    st = strategy or shot.get("gen_strategy") or server.GEN_POLICY_DEFAULT
    ref_key = shot.get("ref") or ""
    if st == "keyframes":
        prompt = server._transition_prompt(shot)
        if ref_key and "locked character identity" not in prompt:
            prompt = "%s, %s" % (prompt, server._identity_lock(ref_key))
        cam = server._camera_clause(shot)
        if cam and cam not in prompt and not server._cam_mentioned(prompt):
            prompt = "%s, %s" % (prompt, cam)
        cine = server._cinema_clause(shot)
        if cine:
            prompt = "%s, %s" % (prompt, cine)
        speech = server._speech_clause(shot)
        if speech:
            prompt = "%s. %s" % (prompt, speech)
        return prompt.strip()
    if st == "reference":
        prompt = server._clean_video_prompt(shot.get("video_prompt", ""))
        cgs = server._clean_global_style()
        if cgs and cgs not in prompt:
            prompt = "%s, %s" % (prompt, cgs)
        anim = server._animate_clause(shot)
        if anim:
            prompt = "%s, %s" % (prompt, anim)
        if ref_key and "locked character identity" not in prompt:
            prompt = "%s, %s" % (prompt, server._identity_lock(ref_key))
            prompt = ("%s, while keeping the face and outfit consistent, "
                      "stable character identity throughout" % prompt)
        cam = server._camera_clause(shot)
        if cam and cam not in prompt and not server._cam_mentioned(prompt):
            prompt = "%s, %s" % (prompt, cam)
        cine = server._cinema_clause(shot)
        if cine:
            prompt = "%s, %s" % (prompt, cine)
        speech = server._speech_clause(shot)
        if speech:
            prompt = "%s. %s" % (prompt, speech)
        return prompt.strip()
    if st == "text2video":
        prompt = shot.get("video_prompt", "")
        cgs = server._clean_global_style()
        if cgs and cgs not in prompt:
            prompt = "%s, %s" % (prompt, cgs)
        cam = server._camera_clause(shot)
        if cam and cam not in prompt and not server._cam_mentioned(prompt):
            prompt = "%s, %s" % (prompt, cam)
        anim = server._animate_clause(shot)
        if anim:
            prompt = "%s, %s" % (prompt, anim)
        return prompt.strip()
    return ""  # ui / 未知：无可比 prompt


def precheck_shot(shot, first=None, last=None, prompt=None,
                  model="agnes-2.5-flash", dry_run=False, timeout=150):
    """生成前图视冲突预检（AC-1.1/1.2/1.3）。

    输入：shot（storyboard 单镜 dict）+ 首尾帧图路径（http/data URI/assets/ 相对路径均可）。
    处理：
      1) 空镜免检：is_empty_shot(prompt) → n/a（不调视觉 API，零额度）
      2) ui/text2video：无关键帧图可比 → n/a（不调 API）
      3) 素材自检：prompt 空 / 首帧缺 / 尾帧缺 → warn（不调 API）
      4) dry_run=True → 只做 1)-3)，precheck="dry-run"（零 AGNES 调用）
      5) 默认：复用 vision_review.prompt_frame_match(prompt, first, last)
    输出：见 design.md §2.2（precheck: match|warn|fail|n/a|dry-run + conflicts[]）。
    """
    prompt = (prompt if prompt is not None
              else render_final_prompt(shot) or shot.get("video_prompt") or shot.get("prompt") or "")
    st = shot.get("gen_strategy") or server.GEN_POLICY_DEFAULT
    base = {
        "ok": True,
        "empty_shot": False,
        "dry_run": bool(dry_run),
        "model": model,
        "inputs": {"shot_id": shot.get("id"),
                   "strategy": st,
                   "prompt": prompt[:200],
                   "first": first or shot.get("asset_frame_start") or "",
                   "last": last or shot.get("asset_frame_end") or ""},
    }

    # 1) 空镜免检（AC-1.2）：零 API 调用
    if is_empty_shot(prompt):
        base.update({
            "precheck": "n/a",
            "empty_shot": True,
            "reason": "空镜镜头（prompt 含 no people/空景），免检",
            "prompt_frame_match": None,
            "conflicts": [],
        })
        return base

    # 2) ui / text2video：无关键帧图可比 → n/a（不调 API）
    if st in ("ui", "text2video"):
        base.update({
            "precheck": "n/a",
            "reason": "%s 策略：无首尾帧图可比（%s）" % (st, "UI 动效镜" if st == "ui" else "纯文生视频"),
            "prompt_frame_match": None,
            "conflicts": [],
        })
        return base

    # 3) 素材自检（零 API）：prompt / 首帧 / 尾帧任一缺失 → warn
    f0, f1 = _resolve_frames(shot, first, last)
    missing = []
    if not prompt:
        missing.append("prompt")
    if not f0:
        missing.append("首帧图")
    if not f1:
        missing.append("尾帧图")
    if missing:
        base.update({
            "precheck": "warn",
            "reason": "素材缺失：%s（缺首尾帧素材，请先生成关键帧）" % "、".join(missing),
            "prompt_frame_match": None,
            "conflicts": [{"stage": "input", "type": "素材缺失", "severity": "low",
                           "desc": "缺少 " + "、".join(missing)}],
        })
        return base

    # 4) dry-run（AC-1.3）：零 AGNES 调用
    if dry_run:
        base.update({
            "precheck": "dry-run",
            "reason": "dry-run：素材齐备，未调用 AGNES 视觉 API（AC-1.3 零额度验证）",
            "prompt_frame_match": None,
            "conflicts": [],
        })
        return base

    # 5) 真跑视觉：复用 prompt_frame_match（AGNES 2.5-flash 免费 3000 次/天）
    sys.path.insert(0, HERE)
    from vision_review import prompt_frame_match
    pfm = prompt_frame_match(prompt, f0, f1, model=model, timeout=timeout)
    if not pfm.get("ok"):
        base.update({
            "precheck": "warn",
            "reason": "视觉检查失败（不阻塞生成，AC-1.3）：%s" % (pfm.get("error") or "未知"),
            "prompt_frame_match": None,
            "conflicts": [{"stage": "api", "type": "视觉调用失败", "severity": "low",
                           "desc": str(pfm.get("error"))[:200]}],
        })
        return base

    overall = pfm.get("overall") or "warn"
    mapping = {"pass": "match", "warn": "warn", "fail": "fail"}
    verdict = mapping.get(overall, "warn")
    conflicts = []
    for stage in ("opening", "ending"):
        for it in (pfm.get(stage) or {}).get("issues") or []:
            conflicts.append({"stage": stage,
                              "type": it.get("type", "其他"),
                              "severity": it.get("severity", "low"),
                              "desc": it.get("desc", "")})
    base.update({
        "precheck": verdict,
        "reason": {"match": "提示词与首尾帧图一致",
                   "warn": "部分元素缺失/不明确，建议确认",
                   "fail": "提示词与首尾帧图冲突，建议修改后再生成"}.get(verdict, verdict),
        "prompt_frame_match": {"overall": overall,
                               "opening": pfm.get("opening") or {},
                               "ending": pfm.get("ending") or {}},
        "conflicts": conflicts,
    })
    return base


def main():
    ap = argparse.ArgumentParser(description="P0-2 图视冲突预检（生成前）")
    ap.add_argument("--project", help="项目 ID（如 ep_0811_145935）")
    ap.add_argument("--shot", type=int, help="镜号")
    ap.add_argument("--shot-id", type=int, help="镜号（直接传图/prompt 时用，不加载项目）")
    ap.add_argument("--first", help="首帧图路径/URL/data URI")
    ap.add_argument("--last", help="尾帧图路径/URL/data URI")
    ap.add_argument("--prompt", help="要对比的 prompt（缺省渲染最终 prompt）")
    ap.add_argument("--dry-run", action="store_true", help="零额度：不调 AGNES 视觉 API")
    ap.add_argument("--model", default="agnes-2.5-flash")
    ap.add_argument("--timeout", type=int, default=150)
    args = ap.parse_args()

    shot = {}
    if args.project and args.shot:
        server.load_spec(args.project)
        shot = server.find_shot(args.shot)
        if shot is None:
            print(json.dumps({"ok": False, "error": "shot %d 不存在" % args.shot},
                             ensure_ascii=False, indent=2))
            sys.exit(1)
    elif args.shot_id:
        shot = {"id": args.shot_id}

    prompt = args.prompt
    if prompt is None and shot:
        prompt = render_final_prompt(shot) or shot.get("video_prompt") or shot.get("prompt") or ""

    res = precheck_shot(shot, first=args.first, last=args.last, prompt=prompt,
                        model=args.model, dry_run=args.dry_run, timeout=args.timeout)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
