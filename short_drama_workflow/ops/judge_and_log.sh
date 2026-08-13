#!/usr/bin/env bash
# judge_and_log.sh — 跑 judge_subagent.sh，并把判定结论自动追加进 current_state.md 操作审计台账
#
# 设计原则（SOP §3.6 外部可观测性铁律 + 操作审计 R2）：
#   1. 判定权在主会话：先调 judge_subagent.sh 做磁盘+进程事实检查（零破坏）。
#   2. 判定结论必须进台账（current_state.md），否则等于"查了但没留痕"。
#   3. 结论来自读盘，绝不来自子角色文本 claim。
#
# 退出码：透传 judge_subagent.sh 的 0=PASS / 1=打回 / 2=WARN。
#
# 用法：
#   bash ops/judge_and_log.sh --task <T-id> --artifact <path> \
#        [--expect <regex>] [--forbid <regex>] [--commit-dir <dir>] \
#        [--within <min>] [--task-id <id>] [--note <补充>]
#
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STATE="$ROOT/dev-work/current_state.md"
JUDGE="$SCRIPT_DIR/judge_subagent.sh"
ANCHOR="JUDGE_LEDGER"          # current_state.md 内的插入锚（HTML 注释行含此 token）

TASK="(未提供)"; NOTE=""; ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --task)  TASK="$2";  shift 2;;
    --note)  NOTE="$2";  shift 2;;
    --artifact|--expect|--forbid|--commit-dir|--within|--task-id)
            ARGS+=("$1" "$2"); shift 2;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "未知参数: $1（用 -h 看用法）"; exit 1;;
  esac
done

if [ ! -f "$JUDGE" ]; then echo "❌ 找不到 $JUDGE"; exit 1; fi
if [ ! -f "$STATE" ]; then echo "❌ 找不到 $STATE"; exit 1; fi

# 1) 跑判定器，捕获 stdout + 退出码
out=$(bash "$JUDGE" "${ARGS[@]}" 2>&1); rc=$?

# 2) 抽判定结论行
verdict=$(printf '%s\n' "$out" | grep -E '^判定:' | head -1 | sed 's/^判定:[[:space:]]*//')

# 3) 拼台账行（最新置顶）
ts=$(date '+%Y-%m-%d %H:%M')
bullet="- $ts | $TASK | judge=${verdict:-<无判定行>}"
[ -n "$NOTE" ] && bullet="$bullet | $NOTE"

# 4) 追加进 current_state.md（插在锚行之后；锚缺失则追加到文件尾）
if grep -qF "$ANCHOR" "$STATE"; then
  tmp="$(mktemp)"
  awk -v b="$bullet" -v a="$ANCHOR" '{print; if($0 ~ a){print b}}' "$STATE" > "$tmp" && mv "$tmp" "$STATE"
else
  printf '\n<!-- %s -->\n%s\n' "$ANCHOR" "$bullet" >> "$STATE"
fi

# 5) 回显判定器输出 + 落账提示
printf '%s\n' "$out"
echo "（已追加判定结论到 current_state.md · 子角色判定台账）"
exit $rc
