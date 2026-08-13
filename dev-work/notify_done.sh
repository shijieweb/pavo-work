#!/usr/bin/env bash
# notify_done.sh — 任务完成后推送通知到微信（Server酱 / Pushplus）
# 用法: ./notify_done.sh "标题" "正文(可选, 支持Server酱 markdown)"
#
# 凭证存放: 读取 ~/.workbuddy/.env（绝不写进脚本/仓库）
#   NOTIFY_PROVIDER=serverchan | pushplus
#   NOTIFY_SENDKEY=  (Server酱 SendKey)
#   NOTIFY_TOKEN=    (Pushplus Token)
set -euo pipefail

KEY_FILE="$HOME/.workbuddy/.env"
if [ -f "$KEY_FILE" ]; then
  set -a
  . "$KEY_FILE"
  set +a
fi

PROVIDER="${NOTIFY_PROVIDER:-serverchan}"
TITLE="${1:-任务完成}"
CONTENT="${2:-阿编已完成你交代的任务，请回电脑查看详情。}"

if [ "$PROVIDER" = "serverchan" ]; then
  SENDKEY="${NOTIFY_SENDKEY:-${SENDKEY:-}}"
  [ -z "$SENDKEY" ] && { echo "ERR: 缺少 NOTIFY_SENDKEY (在 ~/.workbuddy/.env 配置)"; exit 1; }
  curl -s --noproxy '*' -X POST "https://sctapi.ftqq.com/${SENDKEY}.send" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "text=$TITLE" \
    --data-urlencode "desp=$CONTENT"
elif [ "$PROVIDER" = "pushplus" ]; then
  TOKEN="${NOTIFY_TOKEN:-${TOKEN:-}}"
  [ -z "$TOKEN" ] && { echo "ERR: 缺少 NOTIFY_TOKEN (在 ~/.workbuddy/.env 配置)"; exit 1; }
  curl -s --noproxy '*' -X POST "https://www.pushplus.plus/send" \
    -H "Content-Type: application/json" \
    -d "{\"token\":\"$TOKEN\",\"title\":\"$TITLE\",\"content\":\"$CONTENT\"}"
else
  echo "ERR: 未知 NOTIFY_PROVIDER=$PROVIDER (可选 serverchan|pushplus)"; exit 1
fi
