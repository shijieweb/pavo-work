# -*- coding: utf-8 -*-
"""一键发布 publish.py（老板 0811 全自动交付）：
改完代码后一条命令完成「语法检查 → fast 回归 → git 提交 → 推送 → 远端校验」。
任一环节失败即停并报错，绝不把坏代码推上去。

用法：
  python scripts/diag/publish.py "提交信息"      # 自定义提交信息
  python scripts/diag/publish.py                  # 自动生成提交信息（git diff 摘要）

依赖：仓库根 git（已配置远端 origin main）、gh CLI（已登录，用于远端校验）。
"""
import json, os, re, subprocess, sys, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
REPO = "shijieweb/pavo-work"
PY = sys.executable

def sh(cmd, cwd=ROOT, timeout=120, silent=False):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if not silent:
        out = (r.stdout or "").strip()
        if out:
            print("  " + out.replace("\n", "\n  ")[:800])
        if r.returncode != 0 and (r.stderr or "").strip():
            err = r.stderr.strip()
            if "warning:" not in err:
                print("  ! " + err.replace("\n", "\n  ! ")[:600])
    return r

def api(path):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8777" + path, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return None

def step(name):
    print("\n[%s] %s ..." % ("STEP", name))

def main():
    print("=" * 60)
    print("publish.py · 一键发布（语法 → 回归 → 提交 → 推送 → 远端校验）")
    print("=" * 60)

    # 0) 工作区检查
    step("检查工作区")
    st = sh("git status --porcelain", silent=True)
    if not (st.stdout or "").strip():
        print("  ✅ 工作区干净，无需发布")
        return 0
    # 敏感文件守卫
    bad = [l for l in st.stdout.splitlines()
           if re.search(r"\.env|logs/|projects/|\.workbuddy|_archive", l)]
    if bad:
        print("  ❌ 检测到敏感/大文件被改动，拒绝发布：")
        for b in bad[:5]:
            print("     " + b)
        return 2

    # 1) 语法检查
    step("语法检查")
    srv = os.path.join("short_drama_workflow", "html_prototype", "server.py").replace(os.sep, "/")
    ok = sh('%s -m py_compile %s' % (PY, srv))
    if ok.returncode != 0:
        print("  ❌ server.py 语法错误，终止"); return 3

    # 2) fast 回归（无 AGNES，秒级）
    step("fast 回归（qa_regression.py fast）")
    qa = sh("%s qa_regression.py fast" % PY, cwd=os.path.join(ROOT, "short_drama_workflow", "html_prototype"),
            timeout=120, silent=True)
    out = qa.stdout or ""
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    passed = out.count("PASS")
    total = passed + len(fails)
    print("  结果: %d 通过 / %d 失败" % (passed, len(fails)))
    if fails:
        for f in fails[:5]:
            print("     " + f)
        print("  ❌ fast 回归未全绿，终止"); return 4
    if total < 10:
        print("  ⚠️ fast 用例数异常（%d），终止" % total); return 5

    # 3) 生成提交信息
    step("git 提交")
    msg = sys.argv[1] if len(sys.argv) > 1 else ""
    if not msg:
        diff = sh("git diff --stat", silent=True)
        files = [l.split("|")[0].strip() for l in (diff.stdout or "").splitlines() if "|" in l][:5]
        msg = "自动发布：" + "、".join(files) if files else "自动发布：工作区更新"
    r = sh('git add -A && git commit -m "%s"' % msg.replace('"', "'"))
    if r.returncode != 0:
        print("  ❌ commit 失败，终止"); return 6

    # 4) 推送
    step("git push（origin main）")
    r = sh("git push origin main", timeout=120)
    if r.returncode != 0:
        print("  ⚠️ push 失败（网络？）——可稍后手动 `git push` 重试")
        return 7

    # 5) gh 远端校验
    step("远端校验（gh）")
    local = sh("git rev-parse HEAD", silent=True).stdout.strip()
    try:
        rr = subprocess.run(["gh", "api", "repos/%s/commits?per_page=1" % REPO, "--jq", ".[0].sha"],
                            capture_output=True, text=True, timeout=30, cwd=ROOT)
        remote = (rr.stdout or "").strip()
        if remote and remote.startswith(local[:7]):
            print("  ✅ 远端 HEAD == 本地 %s" % local[:7])
        else:
            print("  ⚠️ 远端 %s vs 本地 %s（稍后人工核对）" % (remote[:7] if remote else "?", local[:7]))
    except Exception as e:
        print("  ⚠️ gh 校验失败: %s" % e)

    print("\n✅ 发布完成：%s" % msg[:80])
    return 0

if __name__ == "__main__":
    sys.exit(main())
