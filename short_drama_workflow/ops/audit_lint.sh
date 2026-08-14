#!/usr/bin/env bash
# audit_lint.sh — 审计对账：状态表"完成" 必须有 判定台账 PASS/WARN 印证
#
# 设计目的（对应 SOP §3.6 反模式 F1/F4）：
#   子角色永非真相源，但"主理人/主会话"也从未被审计。本脚本做独立对账——
#   不依赖任何人自觉，机器断言「状态表记完成 的任务，台账里必有 judge=PASS/WARN」。
#   反向也查：台账 PASS 但状态表未记完成 = 未闭环。
#
# 历史豁免：台账建立时点(ledger 最早日期)之前的完工任务，无 PASS 仅 WARN（非致命）。
#           台账期(含建立当日)完工却无 PASS = ❌ FAIL（致命缺口，忘了跑 judge）。
#
# 纯读盘、零破坏（不改文件、不杀进程）。
# 退出码：0=PASS（完成均有 PASS 印证）/ 1=FAIL（存在致命缺口）/ 2=WARN（仅历史豁免·无致命缺口）
#
# 用法：bash ops/audit_lint.sh [审计文件=dev-work/current_state.md]

set -u

STATE_FILE="${1:-dev-work/current_state.md}"
if [ ! -f "$STATE_FILE" ]; then
  echo "❌ FAIL: 审计文件不存在: $STATE_FILE"
  exit 1
fi

# 切分 markdown 段落：从 start_marker 起到 end_marker(不含) 为止；end 缺省读到 EOF
sec() {
  awk -v s="$2" -v e="${3:-}" 'BEGIN{f=0} $0 ~ s{f=1; next} (e!="" && $0 ~ e){f=0} f{print}' "$1"
}

STATE=$(sec "$STATE_FILE" "## 操作审计" "#### 子角色判定台账")
LEDGER=$(sec "$STATE_FILE" "<!-- JUDGE_LEDGER -->")

# 台账 judge 行；含"打回"=拒绝，其余(PASS/WARN)=通过
ledger_all=$(echo "$LEDGER" | grep -E 'judge=')
ok_ids=$(echo "$ledger_all" | grep -v '打回' | grep -oE 'T-[0-9]{8}-[0-9]+' | sort -u)
rej_ids=$(echo "$ledger_all" | grep '打回' | grep -oE 'T-[0-9]{8}-[0-9]+' | sort -u)
# 台账最早日期（判定台账建立时点）；为空=台账段尚未建立
ledger_earliest=$(echo "$LEDGER" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort | head -1)

fail=0
warn=0

echo "===== 审计对账 audit_lint ====="
echo "[状态表·完成] $(echo "$STATE" | grep -E '完成' | grep -oE 'T-[0-9]{8}-[0-9]+' | sort -u | tr '\n' ' ')"
echo "[台账·PASS]   $(echo "$ok_ids" | tr '\n' ' ')"
echo "[台账·打回]   $(echo "$rej_ids" | tr '\n' ' ')"
echo "[台账建立日]  ${ledger_earliest:-(未建立)}"
echo ""

# 完成任务 + 其完工日期（状态表行首字段）
done_pairs=$(echo "$STATE" | awk '/完成/{
  d=""; tid="";
  if (match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}/)) d=substr($0,RSTART,RLENGTH);
  if (match($0, /T-[0-9]{8}-[0-9]+/)) tid=substr($0,RSTART,RLENGTH);
  if (d!="" && tid!="") print d" "tid;
}')

while read -r d t; do
  [ -z "$t" ] && continue
  if echo "$ok_ids" | grep -qx "$t"; then
    echo "  ✅ $t  完成 ↔ PASS/WARN 一致 ($d)"
  elif echo "$rej_ids" | grep -qx "$t"; then
    echo "  ❌ $t  状态表=完成 但台账最近=打回（矛盾！）"; fail=1
  elif [ -z "$ledger_earliest" ]; then
    echo "  ⚠️ $t  完成($d) 但台账段为空（台账未建立·跳过绑定）"; warn=1
  else
    tid_date=$(echo "$t" | grep -oE '[0-9]{8}' | sed 's/\(....\)\(..\)\(..\)/\1-\2-\3/')
    if [ -n "$tid_date" ] && [ "$tid_date" \< "$ledger_earliest" ]; then
      echo "  ⚠️ $t  完成($d) 但台账无 PASS（任务建于 $tid_date，早于台账 $ledger_earliest·历史豁免）"; warn=1
    else
      echo "  ❌ $t  完成($d) 但台账期($ledger_earliest 起)无 PASS（致命缺口！请回查 judge）"; fail=1
    fi
  fi
done <<< "$done_pairs"

# 反向：台账 PASS 但状态表未记完成 = 未闭环
for t in $ok_ids; do
  if ! echo "$STATE" | grep -E '完成' | grep -q "$t"; then
    echo "  ⚠️ $t  台账=PASS 但状态表未记完成（未闭环）"; warn=1
  fi
done

# ===== 索引引用存在性检查（⑤ 2026-08-14：防索引死链/漏登记）=====
# 解析 索引总览 里反引号引用的相对路径，检查 dev-work/ 下是否存在（WARN 级，不误伤跨目录/模板引用）
IDX="dev-work/索引总览_出问题先看这里.md"
if [ -f "$IDX" ]; then
  missing=""
  while read -r p; do
    [ -z "$p" ] && continue
    case "$p" in
      http*|C:/*|~/*|*.env|*.db|ops/*|维护手册/*|short_drama_workflow/*|scripts/*|projects/*|*YYYY*|*\<*|*\>*|*\**) continue ;;
    esac
    p="${p%%#*}"
    [ -z "$p" ] && continue
    if [ ! -e "dev-work/$p" ]; then missing="$missing $p"; fi
  done <<< "$(grep -oE '\`[^\`]+\`' "$IDX" | tr -d '\`' | sort -u)"
  if [ -n "$missing" ]; then
    echo "  ⚠️ 索引引用缺失（请登记/修正索引总览）:$missing"; warn=1
  else
    echo "  ✅ 索引引用全部存在"
  fi
else
  echo "  ⚠️ 索引总览不存在（dev-work/索引总览_出问题先看这里.md）"; warn=1
fi

echo "==============================="

if [ "$fail" -eq 1 ]; then
  echo "结论: ❌ FAIL（存在 完成↔PASS 致命缺口，请回查）"
  exit 1
fi
if [ "$warn" -eq 1 ]; then
  echo "结论: ⚠️ WARN（仅历史豁免/未闭环，无致命缺口）"
  exit 2
fi
echo "结论: ✅ PASS（所有完成均有 PASS 印证）"
exit 0
