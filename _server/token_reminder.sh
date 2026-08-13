#!/bin/bash
# Claude OAuth 토큰(1년 유효) 만료 알림 — 매달 1일 실행.
# 발급 330일이 지나면 텔레그램으로 갱신을 재촉한다. 만료되면 모든 자동화가 멈추기 때문.
CFG="$HOME/.config/bulkfarmer"
set -a
[ -f "$CFG/telegram.env" ] && source "$CFG/telegram.env"
[ -f "$CFG/claude.env" ] && source "$CFG/claude.env"
set +a
[ -z "$CLAUDE_TOKEN_ISSUED" ] && exit 0

DAYS=$(( ( $(date +%s) - $(date -d "$CLAUDE_TOKEN_ISSUED" +%s) ) / 86400 ))
if [ "$DAYS" -ge 330 ]; then
  LEFT=$(( 365 - DAYS ))
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
    --data-urlencode "text=🔑 Claude 토큰 만료 임박 — 약 ${LEFT}일 남음
만료되면 서버의 모든 Claude 자동화가 멈춥니다.
맥에서 'claude setup-token' 재발급 → 서버 ~/.config/bulkfarmer/claude.env 갱신
(_server/README.md 마지막 섹션 참조)" >/dev/null
fi
