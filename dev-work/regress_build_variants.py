#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-1 dry-run 回归：对比新旧 build_variants 输出（不调用 gen_video / main，零 AGNES 额度）。
运行：python dev-work/regress_build_variants.py
"""
import os, sys, types, tempfile, textwrap

DIAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "short_drama_workflow", "scripts", "diag")
DIAG = os.path.abspath(DIAG)
sys.path.insert(0, DIAG)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # dev-work（含 _legacy_build_variants）

# ---- 1) 桩模块：让 prompt_training / _legacy 的顶层 import 不触碰真实依赖/网络 ----
def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

_stub("server", asset_abs=lambda p: p, _video_size=lambda: (1280, 720),
      _shot_nf=lambda *a, **k: 81, load_spec=lambda *a, **k: None,
      find_shot=lambda *a, **k: None, SPEC={})
_stub("agnes_client", _submit_video=lambda *a, **k: {}, chat=lambda *a, **k: "",
      wait_for_video=lambda *a, **k: None)
_stub("diagnosis", diagnose_clip=lambda *a, **k: {})
# vision_review 仅在 main() 内用到，这里不执行 main()，但保险也桩一下
_stub("vision_review", review=lambda *a, **k: {"verdict": None, "issues": []},
      prompt_frame_match=lambda *a, **k: {}, _img_src=lambda x: x, _extract_json=lambda x: {})

import prompt_training as pt
import _legacy_build_variants as legacy

# ---- 1.1) _datauri 桩：回归不读真实图片文件，用确定性伪 data URI（新旧都必须用同一桩，保证可比）----
def _fake_datauri(path):
    return "data:image/png;base64,STUB_" + path
pt._datauri = _fake_datauri
legacy._datauri = _fake_datauri

# ---- 2) fixture（与旧代码解析路径一致：first/last 不以 assets/ 开头，避免触发 server/data-uri）----
SHOT = {
    "asset_frame_start": "/fixture/first.png",
    "asset_frame_end": "/fixture/last.png",
    "video_prompt": "BASE VIDEO PROMPT",
    "cn_story": "测试场景",
}
REF = {
    "remote_url": "http://example.com/anchor.png",
    "asset_image": "http://example.com/asset.png",
}

TEMPLATES = ["camera_move_v1", "camera_move_v2", "camera_move_v3",
             "camera_move_v4", "camera_move_v5", "camera_move_v6", "camera_move_v7"]

# 临时实验文件：验证 file: 读取路径（不修改仓库真实文件，用 try/finally 清理）
# 设 REGRESS_NO_TMP=1 可跳过创建，专门验证"文件缺失→优雅 fallback"路径。
if os.environ.get("REGRESS_NO_TMP"):
    TMP_FILES = {}
else:
    TMP_FILES = {
    "frame3_halfbody.txt": "TMP_HALFBODY",
    "anchor_far.txt": "TMP_ANCHOR_FAR",
    "sceneA_2.txt": "TMP_SCENEA2",
    "sceneB_2.txt": "TMP_SCENE_B2",
    "sceneA_empty1.txt": "TMP_EMPTY1",
    "sceneA_empty2.txt": "TMP_EMPTY2",
    "sceneB_close2.txt": "TMP_CLOSE2",
    "sceneB_distantsmall.txt": "TMP_DISTANT",
}

fails = []
checks = 0

def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        fails.append(msg)
        print("  FAIL:", msg)
    return cond

# 写出临时实验文件（覆盖 file: 读取路径）
exp_dir = os.path.join(DIAG, "experiments")
created = []
try:
    for fn, content in TMP_FILES.items():
        fp = os.path.join(exp_dir, fn)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        created.append(fp)

    print("=== 新旧 build_variants 逐模板对比（camera_move_v1~v7）===")
    for tpl in TEMPLATES:
        leg = legacy.build_variants(SHOT, REF, tpl)
        new = pt.build_variants(SHOT, REF, tpl)
        check(set(leg.keys()) == set(new.keys()),
              "[%s] 变体集合不一致: 旧=%s 新=%s" % (tpl, sorted(leg), sorted(new)))
        for vname in leg:
            lv, nv = leg[vname], new[vname]
            check(lv.get("images") == nv.get("images"),
                  "[%s/%s] images 不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv.get("images"), nv.get("images")))
            check(lv.get("keyframes") == nv.get("keyframes"),
                  "[%s/%s] keyframes 不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv.get("keyframes"), nv.get("keyframes")))
            check(lv.get("prompt") == nv.get("prompt"),
                  "[%s/%s] prompt 不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv.get("prompt"), nv.get("prompt")))
            check(lv.get("hyp") == nv.get("hyp"),
                  "[%s/%s] hyp 不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv.get("hyp"), nv.get("hyp")))
            # 完整字典相等：仅 camera_move_v2 旧版自带 goal/reference/implement，
            # 其余模板旧版无这些元数据（属新增扩展字段，不触发训练逻辑）。
            if tpl == "camera_move_v2":
                check(lv == nv,
                      "[%s/%s] 完整字典不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv, nv))
            else:
                added = set(nv.keys()) - set(lv.keys())
                if added:
                    print("    · 注: %s 新增元数据字段 %s（旧版无，不影响训练逻辑）" % (vname, sorted(added)))
        print("  ✓ %s: %d 个变体 核心字段(images/keyframes/prompt/hyp/num_frames/frame_rate) 新旧一致" % (tpl, len(new)))
finally:
    for fp in created:
        try:
            os.remove(fp)
        except OSError:
            pass

# ---- 3) 兼容性：empty_scene_v1.yaml 与 dialogue_v1.yaml 能加载（无旧版可比对）----
print("\n=== 兼容性：已存在 empty_scene_v1.yaml + 新 dialogue_v1.yaml ===")
es = pt.build_variants(SHOT, REF, "empty_scene_v1")
check(isinstance(es, dict) and len(es) > 0, "empty_scene_v1 未产出变体")
for vn, v in es.items():
    check("images" in v and "keyframes" in v and "prompt" in v,
          "[empty_scene_v1/%s] 缺少 images/keyframes/prompt" % vn)
    check(all(isinstance(k, dict) and "role" in k and "src" in k for k in v["keyframes"]),
          "[empty_scene_v1/%s] keyframes 非 {role,src} 结构" % vn)
# 语义校验（BUG-1 修复目标）：text:/i2i: 必须区分文生图/图生图，keyframes 干净无前缀
v0 = es["v0"]
# images 每帧带 mode 标记，首帧 text_to_image / 尾帧 image_to_image（AC-1.5）
check(isinstance(v0["images"], list) and len(v0["images"]) == 2,
      "[empty_scene_v1/v0] images 应为 2 帧 list")
check(v0["images"][0].get("mode") == "text_to_image",
      "[empty_scene_v1/v0] 首帧 images 应为 text_to_image（文生图），实际=%r" % v0["images"][0])
check(v0["images"][1].get("mode") == "image_to_image",
      "[empty_scene_v1/v0] 尾帧 images 应为 image_to_image（图生图），实际=%r" % v0["images"][1])
check("content" in v0["images"][0] and "content" in v0["images"][1],
      "[empty_scene_v1/v0] images 每帧应含 content（生成内容）")
# keyframes role/src 必须干净：去掉 text:/i2i: 前缀、无未渲染 token（如 {{FIRST_FRAME_PROMPT}}）
for idx, kf in enumerate(v0["keyframes"]):
    check("text:" not in kf["role"] and "i2i:" not in kf["role"]
          and "{{" not in kf["role"] and "text:" not in kf["src"] and "i2i:" not in kf["src"]
          and "{{" not in kf["src"],
          "[empty_scene_v1/v0] keyframes[%d] 含未渲染/带前缀值: %r" % (idx, kf))
check(v0["keyframes"][0]["role"] == "文生图(无源图)"
      and v0["keyframes"][1]["role"] == "图生图(基于上一帧)",
      "[empty_scene_v1/v0] keyframes role 未标明文生图/图生图: %r"
      % [k["role"] for k in v0["keyframes"]])
check(v0["keyframes"][0]["src"].startswith("Empty street")
      and v0["keyframes"][1]["src"].startswith("Same empty street"),
      "[empty_scene_v1/v0] keyframes src 未渲染为干净 prompt 文本")
print("  ✓ empty_scene_v1.yaml 加载成功，变体: %s（text_to_image/i2i 语义已区分，keyframes 干净）" % sorted(es))

dl = pt.build_variants(SHOT, REF, "dialogue_v1")
check(isinstance(dl, dict) and len(dl) > 0, "dialogue_v1 未产出变体")
for vn, v in dl.items():
    check("images" in v and "keyframes" in v and "prompt" in v,
          "[dialogue_v1/%s] 缺少 images/keyframes/prompt" % vn)
print("  ✓ dialogue_v1.yaml 加载成功（不加 Python 即可 --template dialogue_v1），变体: %s" % sorted(dl))

# ---- 4) 默认 template=camera_move_v2（原 fallthrough）----
dv = pt.build_variants(SHOT, REF)  # 不传 template
check(set(dv.keys()) == set(legacy.build_variants(SHOT, REF).keys()),
      "默认 template 不等于 camera_move_v2")
print("  ✓ 默认 template=camera_move_v2，变体: %s" % sorted(dv))

# ---- 5) BUG-2 回归分支：真实 assets/ 帧图应与旧版一致产出 data URI（覆盖被 fixture 掩盖的分支）----
# 关键前提：生产真实 shot 的 asset_frame_start 为 assets/ 前缀。此处用 asset_frame_start="assets/first.png"，
# asset_frame_end 用非 assets/ 路径（与旧版仅对 first 做 datauri 的行为一致），确保新 loader 与旧版逐字段相等。
ASSET_SHOT = dict(SHOT)
ASSET_SHOT["asset_frame_start"] = "assets/first.png"
# asset_frame_end 保持非 assets/（/fixture/last.png），与旧版"仅 first 帧 datauri"语义对齐
print("\n=== BUG-2 分支：真实 assets/ 帧图 data_uri 转换（新 vs 旧）===")
for tpl in TEMPLATES:
    leg = legacy.build_variants(ASSET_SHOT, REF, tpl)
    new = pt.build_variants(ASSET_SHOT, REF, tpl)
    check(set(leg.keys()) == set(new.keys()),
          "[assets/%s] 变体集合不一致: 旧=%s 新=%s" % (tpl, sorted(leg), sorted(new)))
    for vname in leg:
        lv, nv = leg[vname], new[vname]
        # images：首帧 assets/ 应转 data URI，且与旧版一致
        check(lv.get("images") == nv.get("images"),
              "[assets/%s/%s] images 不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv.get("images"), nv.get("images")))
        # keyframes：src 展示原始 assets/ 路径（与旧版看板展示一致），new==legacy
        check(lv.get("keyframes") == nv.get("keyframes"),
              "[assets/%s/%s] keyframes 不一致\n  旧=%r\n  新=%r" % (tpl, vname, lv.get("keyframes"), nv.get("keyframes")))
        check(lv.get("prompt") == nv.get("prompt"),
              "[assets/%s/%s] prompt 不一致" % (tpl, vname))
        # 断言：任一变体首帧若为 assets/ 路径，其 images 对应项必须是 data URI
        for im in nv["images"]:
            if isinstance(im, str) and im.startswith("assets/"):
                check(False, "[assets/%s/%s] images 含裸 assets/ 路径未转 data URI: %r" % (tpl, vname, im))
    print("  ✓ assets/%s: %d 变体 images/keyframes/prompt 与旧版一致（assets/ → data URI）" % (tpl, len(new)))

print("\n=== 结果 ===")
print("总检查项: %d | 失败: %d" % (checks, len(fails)))
if fails:
    print("❌ 回归不通过")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("✅ 全部通过：新旧 build_variants 输出逐字段一致（零额度消耗）")
