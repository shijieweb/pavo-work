# -*- coding: utf-8 -*-
"""全流程生成一版视频（老板：清空项目 → 浏览器再生成，发现问题优化）
覆盖：新建→需求卡→大纲→分镜→场景图→关键帧(运镜)→视频3镜→合成。
真实 AGNES（免费 key），只生成 3 镜视频，跑完保留项目给老板过目。
"""
import json, time, re
from playwright.sync_api import sync_playwright

PROXY = "document.querySelector('#app').__vue_app__._container._vnode.component.proxy"
BASE = "http://127.0.0.1:8787/studio"

NOVEL = ("深夜十一点，加班的程序员阿凯终于走出写字楼。街角那家通宵营业的面馆还亮着灯，"
         "老板娘陈姐像往常一样给他留了一碗热汤面。阿凯坐下，看到对面坐着同样加班到现在的"
         "女孩小满。两人相视一笑，谁也没说话。陈姐又端来两碟小菜，说：加班的命也是命，慢慢吃。")

results = []
def check(l, ok, det=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + l + ("  | " + det if det else ""))

def gp(pg, k):
    return pg.evaluate("() => (" + PROXY + ")['" + k + "']")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1500, 'height': 950})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:150]))
    pg.on('console', lambda m: errs.append('C:' + m.text[:120]) if m.type == 'error' and 'favicon' not in m.text and '404' not in m.text else None)
    pg.goto(BASE, wait_until='networkidle')
    pg.wait_for_timeout(1800)
    # 清 localStorage 防旧草稿
    pg.evaluate("() => { for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i); if(k.includes('studio:')) localStorage.removeItem(k);} }")
    pg.reload(wait_until='networkidle')
    pg.wait_for_timeout(1500)

    # 1) 新建项目
    pg.evaluate("async () => { await (" + PROXY + ").newProject(); }")
    pid_ok = False
    for _ in range(25):
        time.sleep(1)
        pid = gp(pg, "projectId")
        if pid and str(pid).startswith("ep_") and not gp(pg, "loading"):
            pid_ok = True
            break
    check("新建项目", pid_ok, str(pid))
    rc0 = gp(pg, "reqCard") or {}
    check("reqCard 已清空", not (rc0.get("title") or "").strip(), repr(rc0.get("title")))

    # 2) ①贴小说 → AI 需求卡 → 确认
    pg.evaluate("n => { const x = (" + PROXY + "); x.novelInput=n; if (typeof x.buildReqFromNovel==='function') x.buildReqFromNovel(); }", NOVEL)
    done = False
    for _ in range(50):
        time.sleep(3)
        rc = gp(pg, "reqCard")
        if rc and (rc.get("title") or "").strip() and not gp(pg, "loading"):
            done = True
            break
    check("①需求卡 AI 生成", done, (gp(pg, "reqCard") or {}).get("title", "")[:24] if done else "超时")
    if done:
        pg.evaluate("() => { const x = (" + PROXY + "); if (typeof x.confirmReq==='function') x.confirmReq(); }")
        pg.wait_for_timeout(600)
        # 服务端验证需求卡
        d = pg.evaluate("async p => await fetch('/api/spec?project=' + p).then(r=>r.json())", pid)
        rc = (d.get("meta") or {}).get("req_card") or {}
        check("需求卡服务端落盘", bool(rc.get("title")), repr(rc.get("title"))[:30])

    # 3) ②大纲（thinking）
    pg.evaluate("() => { const x = (" + PROXY + "); x.activeModule='outline'; }")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const x = (" + PROXY + "); if (typeof x.genOutline==='function') x.genOutline(); }")
    ol_ok = False
    ol_det = ""
    for _ in range(50):
        time.sleep(3)
        if not gp(pg, "loading"):
            od = gp(pg, "outlineData") or {}
            if od.get("episodes") or od.get("characters"):
                ol_ok = True
                ol_det = "chars:%d ep:%d" % (len(od.get("characters") or []), len(od.get("episodes") or []))
                break
    check("②大纲生成(thinking)", ol_ok, ol_det or "无数据")
    if ol_ok:
        pg.evaluate("() => { const x = (" + PROXY + "); if (typeof x.confirmOutline==='function') x.confirmOutline(); }")
        pg.wait_for_timeout(500)

    # 4) 分镜生成
    pg.evaluate("() => { const x = (" + PROXY + "); x.activeModule='storyboard'; }")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const x = (" + PROXY + "); if (typeof x.genStoryboard==='function') x.genStoryboard(); }")
    sb_ok = False
    for _ in range(80):
        time.sleep(3)
        sp = gp(pg, "spec") or {}
        if not gp(pg, "loading") and (sp.get("shots") or []):
            sb_ok = True
            break
    shots = (gp(pg, "spec") or {}).get("shots") or []
    check("分镜生成", sb_ok and len(shots) >= 4, "shots:" + str(len(shots)))
    if not sb_ok:
        print("!! 分镜失败，终止（问题留给后端日志）")
        b.close()
        raise SystemExit(1)
    # 检查运镜镜头 first_frame_prompt 源头是否生成
    cam_shots = [s for s in shots if any(k in str(s.get("camera") or "") for k in ["推", "拉", "移", "环", "跟", "穿"])]
    cam_ffp = [s for s in cam_shots if (s.get("first_frame_prompt") or "").strip()]
    print("  运镜镜头:", len(cam_shots), "个 | 源头带 first_frame_prompt:", len(cam_ffp), "个")
    check("运镜镜头源头带首帧描述", len(cam_shots) == 0 or len(cam_ffp) >= 1, "%d/%d" % (len(cam_ffp), len(cam_shots)))

    # 5) 资产：场景图（第一场景）+ 角色锚点批量前自动补
    pg.evaluate("() => { const x = (" + PROXY + "); x.activeModule='image'; }")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const x = (" + PROXY + "); const s = (x.spec.scenes||[])[0]; if (s) x.regenAssetImage('scene', s.key||s.name); }")
    for _ in range(50):
        time.sleep(3)
        busy = pg.evaluate("() => { const x = (" + PROXY + "); return Object.values(x.assetBusy||{}).some(v=>v==='image'); }")
        sc = (gp(pg, "spec") or {}).get("scenes") or []
        if not busy and sc and sc[0].get("asset_image"):
            break
    sc0 = ((gp(pg, "spec") or {}).get("scenes") or [{}])[0]
    check("场景图生成", bool(sc0.get("asset_image")), str(sc0.get("asset_image") or "")[:40])

    # 6) ④关键帧：选 3 镜（含 1 个运镜镜，若有）
    pg.evaluate("() => { const x = (" + PROXY + "); x.activeModule='keyframes'; }")
    pg.wait_for_timeout(500)
    shots = (gp(pg, "spec") or {}).get("shots") or []
    target_ids = []
    # 优先运镜镜
    for s in shots:
        if any(k in str(s.get("camera") or "") for k in ["推", "拉", "移", "环", "跟", "穿"]):
            target_ids.append(s["id"])
            break
    for s in shots:
        if s["id"] not in target_ids:
            target_ids.append(s["id"])
        if len(target_ids) >= 3:
            break
    print("  关键帧目标镜:", target_ids)
    for sid in target_ids:
        # reference 策略镜跳过首尾针等待（reference 单图驱动，无首尾帧需求）
        shot0 = next((s for s in shots if s["id"] == sid), None)
        if shot0 and shot0.get("gen_strategy") == "reference":
            print("  镜%d reference 策略（空镜），跳过首尾针等待" % sid)
            continue
        pg.evaluate("sid => { const x = (" + PROXY + "); const s = (x.spec.shots||[]).find(v=>v.id===sid); if (s) x.regenKeyframe(s); }", sid)
        pg.wait_for_timeout(2000)
        for _ in range(80):
            time.sleep(3)
            st = pg.evaluate("sid => { const x = (" + PROXY + "); const s = (x.spec.shots||[]).find(v=>v.id===sid); return s ? {start: !!s.asset_frame_start, end: !!s.asset_frame_end, src: s.frame_start_source} : null; }", sid)
            if st and st["start"] and st["end"]:
                print("  镜%d 首尾针完成 src=%s" % (sid, st["src"]))
                break
        else:
            print("  镜%d 关键帧超时！" % sid)
    shots = (gp(pg, "spec") or {}).get("shots") or []
    kf_done = [s for s in shots if s["id"] in target_ids and s.get("asset_frame_start") and s.get("asset_frame_end")]
    check("关键帧 3 镜完成", len(kf_done) >= 3, "%d/%d" % (len(kf_done), len(target_ids)))

    # 7) ⑤视频：3 镜
    pg.evaluate("() => { const x = (" + PROXY + "); x.activeModule='shots'; }")
    pg.wait_for_timeout(500)
    for sid in target_ids:
        pg.evaluate("sid => { const x = (" + PROXY + "); if (typeof x.genShot==='function') x.genShot(sid); }", sid)
        pg.wait_for_timeout(2000)
        for _ in range(100):
            time.sleep(4)
            st = pg.evaluate("sid => { const x = (" + PROXY + "); const s = (x.spec.shots||[]).find(v=>v.id===sid); return s ? !!s.asset_video : null; }", sid)
            if st:
                print("  镜%d 视频完成" % sid)
                break
        else:
            print("  镜%d 视频超时！" % sid)
    shots = (gp(pg, "spec") or {}).get("shots") or []
    vid_done = [s for s in shots if s["id"] in target_ids and s.get("asset_video")]
    check("视频 3 镜完成", len(vid_done) >= 3, "%d/%d" % (len(vid_done), len(target_ids)))

    # 8) ⑥合成（480p 测试档）
    pg.evaluate("() => { const x = (" + PROXY + "); x.activeModule='advanced'; }")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const x = (" + PROXY + "); if (typeof x.assemble==='function') x.assemble(); }")
    fin_ok = False
    for _ in range(60):
        time.sleep(3)
        if not gp(pg, "loading") and (gp(pg, "finalUrl") or ""):
            fin_ok = True
            break
    check("合成成片", fin_ok, str(gp(pg, "finalUrl") or "")[:60])

    print("\n===== 结果: %d/%d 通过 =====" % (sum(1 for r in results if r), len(results)))
    print("JS 错误:", len(errs), errs[:3])
    print("项目:", pid, "| 视频镜:", vid_done, "| 成片:", gp(pg, "finalUrl") or "")
    b.close()