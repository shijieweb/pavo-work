#!/usr/bin/env bash
# judge_subagent.sh — 子角色产出独立判定器（主理人读盘，不靠子角色文本 claim）
#
# 设计原则（见 SOP §3.6 外部可观测性铁律）：
#   子角色永非真相源。本脚本只做「磁盘 + 进程」的事实检查，零破坏——
#   不杀进程、不改文件、不碰生产。判定权永远在主会话手里。
#
# 退出码： 0 = PASS（可勾验收→完成）
#          1 = 打回（假完成 / 假跑 / 静默空返回）
#          2 = WARN（产物达标，但需主理人留意，如未提交改动 / 可疑残留进程）
#
# 用法：
#   bash ops/judge_subagent.sh --artifact <path> \
#        [--expect <regex>]      # 产物内容必须含此标记（如 'https://.*\.mp4' 或 'AC-1.1'）
#        [--forbid <regex>]      # 产物内容禁止含此标记（如 'Traceback'）——含则打回
#        [--commit-dir <dir>]     # 代码类任务：核验该目录 git 最新 commit + 未提交改动
#        [--within <min=1440>]    # 产物新鲜窗口（分钟，默认1天）。查 run.log 时传小值(如30)以抓「旧失败版未覆盖」；年龄仅为软信号(WARN)，内容才是硬闸
#        [--task-id <id>]         # 仅记录进审计输出，脚本不查 Agent 运行时
set -u

ARTIFACT=""; EXPECT=""; FORBID=""; COMMIT_DIR=""; WITHIN=1440; TASK_ID="(未提供)"
while [ $# -gt 0 ]; do
  case "$1" in
    --artifact)    ARTIFACT="$2"; shift 2;;
    --expect)      EXPECT="$2";   shift 2;;
    --forbid)      FORBID="$2";   shift 2;;
    --commit-dir)  COMMIT_DIR="$2"; shift 2;;
    --within)      WITHIN="$2";   shift 2;;
    --task-id)     TASK_ID="$2";  shift 2;;
    -h|--help)     grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "未知参数: $1（用 -h 看用法）"; exit 1;;
  esac
done

if [ -z "$ARTIFACT" ]; then
  echo "用法: bash ops/judge_subagent.sh --artifact <path> [--expect <regex>] [--forbid <regex>] [--commit-dir <dir>] [--within <min>] [--task-id <id>]"
  exit 1
fi

reasons=(); warns=(); pass=true

echo "=== judge_subagent 判定 ==="
echo "task_id : $TASK_ID"
echo "artifact : $ARTIFACT"

# 1) 存在
if [ ! -f "$ARTIFACT" ]; then
  reasons+=("无产物文件（artifact 不存在 → 子角色静默空返回/假完成）"); pass=false
else
  echo "  存在: ✅"
  # 2) 非空
  if [ ! -s "$ARTIFACT" ]; then
    reasons+=("空产物（0 字节 → 未完成）"); pass=false
  else
    echo "  非空: ✅"
    # 3) 新鲜窗口
    now=$(date +%s); mtime=$(stat -c %Y "$ARTIFACT"); age=$(( (now - mtime) / 60 ))
    if [ "$age" -gt "$WITHIN" ]; then
      warns+=("产物陈旧（=${age}min > ${WITHIN}min，可能旧失败版未覆盖；内容已另行核验）")
    else
      echo "  新鲜: ✅ (${age}min ≤ ${WITHIN}min)"
    fi
    # 4) 预期标记（内容必须含）
    if [ -n "$EXPECT" ]; then
      if grep -qE "$EXPECT" "$ARTIFACT"; then
        echo "  预期标记: ✅ (grep '$EXPECT')"
      else
        reasons+=("内容缺预期标记（$EXPECT）"); pass=false
      fi
    fi
    # 5) 崩溃痕迹（内容禁止含）
    if [ -n "$FORBID" ]; then
      if grep -qE "$FORBID" "$ARTIFACT"; then
        reasons+=("内容含崩溃痕迹（$FORBID → 真测未跑通）"); pass=false
      else
        echo "  崩溃痕迹: ✅ 无 (grep -v '$FORBID')"
      fi
    fi
  fi
fi

# 6) git 核验（代码类任务）
if [ -n "$COMMIT_DIR" ]; then
  if git -C "$COMMIT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    last=$(git -C "$COMMIT_DIR" log -1 --format='%h @ %ci' 2>/dev/null)
    dirty=$(git -C "$COMMIT_DIR" status --short 2>/dev/null | wc -l | tr -d ' ')
    echo "  git: 最新 commit $last | 未提交改动: $dirty"
    [ "$dirty" -gt 0 ] && warns+=("有 $dirty 个未提交改动（可能没 commit 交付物）")
  else
    echo "  git: (非 git 仓库，跳过)"
  fi
fi

# 7) 残留进程扫描（只读，不杀；用 PowerShell 取真实命令行再排除常驻指纹，避免 tasklist 无命令行导致的误报）
res=$(powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match 'python|curl' } | ForEach-Object { \$_.CommandLine }" 2>/dev/null | grep -viE "hermes|shared_board|agnes_proxy|jianying|html_prototype|server.py|board|check_wip|judge_subagent|powershell|Get-CimInstance" || true)
if [ -n "$res" ]; then
  warns+=("可能有卡死/残留进程（非已知常驻，需主理人 TaskOutput/TaskStop 接管）:")
  while IFS= read -r line; do [ -n "$line" ] && warns+=("    $line"); done <<< "$res"
else
  echo "  残留进程: ✅ 无异常（已排除常驻 hermes/board/proxy/jianying/studio）"
fi

echo "---"
if [ "$pass" = false ]; then
  echo "判定: ❌ 打回（原因:）"
  [ ${#reasons[@]} -gt 0 ] && for r in "${reasons[@]}"; do echo "  - $r"; done
  [ ${#warns[@]} -gt 0 ] && { echo "  警示:"; for w in "${warns[@]}"; do echo "  - $w"; done; }
  exit 1
elif [ ${#warns[@]} -gt 0 ]; then
  echo "判定: ⚠️ WARN（产物达标，但需主理人留意:）"
  for w in "${warns[@]}"; do echo "  - $w"; done
  exit 2
else
  echo "判定: ✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成）"
  exit 0
fi
