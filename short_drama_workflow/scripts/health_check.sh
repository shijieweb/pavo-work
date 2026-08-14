#!/usr/bin/env bash
# health_check.sh - 短剧项目一键健康核查（只读，无任何写操作）
# 用法: bash short_drama_workflow/scripts/health_check.sh
# 用途: 全局回顾 / 服务存活巡检。固化自 T-13 全局回顾只读核查。
set -u

TRAIN_DIR=/c/Users/67972/projects/short-drama-training

echo "===== 短剧项目健康核查 $(date '+%F %T') ====="
echo
echo "===== [1] 三服务 HTTP 探针 ====="
for p in http://localhost:8787 http://localhost:8777 http://localhost:8787/board http://localhost:8787/soundsfree http://localhost:8787/board/docs; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$p")
  echo "$p -> $code"
done
echo
echo "===== [2] 端口监听 8787/8777/8788 ====="
netstat -ano 2>/dev/null | grep LISTENING | grep -E ':8787|:8777|:8788' || echo "（无监听）"
echo
echo "===== [3] Python 进程树 ====="
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId, CommandLine | Format-Table -AutoSize | Out-String -Width 200"
echo
echo "===== [4] 训练项目 batch-001 产出 ====="
if [ -d "$TRAIN_DIR" ]; then
  echo "PNG 总数: $(find "$TRAIN_DIR" -type f -iname '*.png' 2>/dev/null | wc -l)"
  echo "prompts.csv: $(find "$TRAIN_DIR" -iname 'prompts.csv' 2>/dev/null | head -1)"
  echo "各阶段文件数:"
  for s in 01_配方训练 02_裁判校准 03_接入生成链 04_采纳区; do
    echo "  $s: $(find "$TRAIN_DIR/$s" -type f 2>/dev/null | wc -l)"
  done
else
  echo "（训练目录不存在: $TRAIN_DIR）"
fi
echo
echo "===== 核查结束（只读，无任何写操作） ====="
