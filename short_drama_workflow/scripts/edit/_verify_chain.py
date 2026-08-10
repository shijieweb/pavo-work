# -*- coding: utf-8 -*-
"""REAL 验证 第一批：A1 选题→成片 全链路 / A2 分发 / A3 BGM。
跑完自动清理临时项目，绝不污染 ep01。"""
import os, sys, json, shutil, glob, time

os.environ["REAL"] = "1"          # 关键：真调 AGNES
os.environ["MINIMAX_API_KEY"] = os.environ.get("MINIMAX_API_KEY", "")  # 不强制，没就走原生

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))   # short_drama_workflow
sys.path.insert(0, os.path.join(ROOT, "html_prototype"))

import server
PROJECTS_ROOT = server.PROJECTS_ROOT

SEED = "霸道总裁破产流落街头，被单亲妈妈误当保安雇去带娃，孩子却一眼认出他是首富"
NOVEL = ("陆沉曾是首富，一场阴谋让他一无所有。暴雨夜，他蜷在便利店门口，"
         "被急着上班的单亲妈妈林晚误认成物业派来的临时保姆。林晚把三岁的儿子小宝塞给他："
         "『下午六点前别让娃哭，回来给你双倍工钱。』小宝却盯着他袖口的定制袖扣："
         "『叔叔，这个扣子我爸爸也有，你也是首富吗？』陆沉一怔——这孩子，竟是当年救过自己的恩人之子。")

pid_created = None
log = []
def ok(cond, msg):
    log.append(("PASS" if cond else "FAIL", msg))
    print(("✅" if cond else "❌"), msg)
    return cond

try:
    # ---------- A1-1：选题分析（REAL）----------
    print("\n=== A1-1 analyze_topic_real (REAL) ===")
    tr = server.analyze_topic_real(SEED)
    ok(tr.get("ok"), f"选题返回 ok | topic={tr.get('brief',{}).get('topic') if tr.get('ok') else tr.get('error')}")
    assert tr.get("ok"), tr
    brief = tr["brief"]
    ok(isinstance(brief.get("topic"), str) and brief.get("target_platform"),
       f"选题 JSON 合法（topic/platform/monetization 齐）topic={brief.get('topic')}")

    # ---------- A1-2：剧本生成（REAL，pipeline 不调它，单独验证）----------
    print("\n=== A1-2 generate_script_real (REAL) ===")
    sc = server.generate_script_real(json.dumps(brief, ensure_ascii=False), episode=1)
    ok(sc.get("ok"), f"剧本返回 ok | scenes={sc.get('scenes') if sc.get('ok') else sc.get('error')}")
    assert sc.get("ok"), sc
    ok(isinstance(sc.get("script", {}).get("scenes"), list) and len(sc["script"]["scenes"]) >= 1,
       f"剧本 JSON 合法（scenes={len(sc['script']['scenes'])}）")

    # ---------- A1-3：小说→分镜（REAL，同时进入流水线）----------
    print("\n=== A1-3 pipeline(topic_seed+novel, skip_pre=False, limit=2) (REAL) ===")
    params = {
        "topic_seed": SEED,
        "novel": NOVEL,
        "skip_pre": False,
        "limit": 2,            # 仅 2 镜出视频，控制 AGNES 视频额度
        "distribute": True,    # 顺带验证 A2
        "diagnose_autofix": False,
        "deep": False,
        "face_check": True,
    }
    t0 = time.time()
    server.run_pipeline(params)   # 同步跑（直接调用，不走 HTTP 后台线程）
    dt = time.time() - t0

    res = server.PIPELINE_STATE.get("result") or {}
    pid_created = server.PIPELINE_STATE.get("project")
    err = server.PIPELINE_STATE.get("error")
    print("pipeline result:", json.dumps(res, ensure_ascii=False)[:400])
    print("pipeline error:", err, "| elapsed=%.1fs" % dt)

    ok(err is None, f"流水线无异常 error={err}")
    ok(res.get("ok") if "ok" in res else True, f"流水线 result.ok（project={res.get('project')}）")
    assert pid_created, "未拿到 project id"

    final = os.path.join(PROJECTS_ROOT, pid_created, "final.mp4")
    ok(os.path.isfile(final), f"成片 final.mp4 产出: {final}")
    # 各镜视频是否真生成
    sbp = os.path.join(PROJECTS_ROOT, pid_created, "storyboard.json")
    sb = json.load(open(sbp, encoding="utf-8"))
    vids = [s for s in sb.get("shots", []) if s.get("asset_video") and os.path.isfile(server.asset_abs(s["asset_video"]))]
    ok(len(vids) >= 1, f"至少 1 镜视频真生成（实际 {len(vids)} 镜）")
    # 参考图（A1-3 内部 generate_references_real）应已落库
    refs_with_img = [r for r in sb.get("references", {}).values() if r.get("img_prompt")]
    ok(len(refs_with_img) >= 1, f"参考图 schema 已生成（references={len(sb.get('references', {}))}）")
    # 诊断是否跑了
    diag_written = [s for s in sb.get("shots", []) if s.get("diagnosis")]
    ok(len(diag_written) >= 1, f"诊断结果已写回 spec（{len(diag_written)} 镜）")

    # ---------- A2：分发（pipeline 末端已调，这里再显式复核产物）----------
    print("\n=== A2 distribute 产物复核 ===")
    dist_dir = os.path.join(PROJECTS_ROOT, pid_created, "dist")
    platforms = ["抖音", "快手", "视频号"]
    made = [p for p in platforms if os.path.isfile(os.path.join(dist_dir, p + ".mp4"))]
    ok(len(made) == 3, f"三平台 mp4 产出（{made}）")
    mpath = os.path.join(dist_dir, "manifest.json")
    ok(os.path.isfile(mpath), "manifest.json 产出")
    if os.path.isfile(mpath):
        m = json.load(open(mpath, encoding="utf-8"))
        ok(m.get("compliance", "").find("AI") >= 0, f"manifest 含 AI 生成标识声明：{m.get('compliance','')[:30]}…")

    # ---------- A3：BGM 默认关闭 → 显式补 BGM 重合成 ----------
    print("\n=== A3 BGM 生成 + 混音复核 ===")
    pdir = os.path.join(PROJECTS_ROOT, pid_created)
    wav = server._auto_global_bgm(pdir, dur=sum(float(s.get("duration", 5)) for s in sb.get("shots", [])))
    ok(wav and os.path.isfile(wav), f"bgm_global.wav 真生成：{wav}")
    asm2 = server.do_assemble({"bgm": True})
    ok(asm2.get("ok"), f"带 BGM 重合成 ok（final={asm2.get('final')}）")
    final2 = os.path.join(pdir, "final.mp4")
    ok(os.path.isfile(final2), "带 BGM 的 final.mp4 重建存在")

finally:
    # ---------- 清理临时项目 ----------
    print("\n=== 清理临时项目 ===")
    if pid_created:
        try:
            d = os.path.join(PROJECTS_ROOT, pid_created)
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
                print("rm project dir:", d)
            reg = server.load_registry()
            before = len(reg)
            reg = [r for r in reg if r.get("id") != pid_created]
            if len(reg) != before:
                server.save_registry(reg)
                print(f"purged registry entry {pid_created} (-> {len(reg)} entries)")
        except Exception as e:
            print("cleanup warn:", e)
    fails = [m for m, _ in log if m == "FAIL"]
    print("\n==== SUMMARY ====")
    print(f"total={len(log)} pass={len(log)-len(fails)} fail={len(fails)}")
    print("CHAIN_VERIFY", "ALL_PASS" if not fails else "HAS_FAIL")
    sys.exit(1 if fails else 0)
