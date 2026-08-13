#!/bin/bash
# 스레드 초안 8개 생성 — 매일 08:13. 맥 launchd com.bulkfarmer.threads-draft 이관.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
DIR="$HOME/벌크농부/00_벌크농부 마케팅 에이전트팀"
set -a
[ -f "$HOME/.config/bulkfarmer/telegram.env" ] && source "$HOME/.config/bulkfarmer/telegram.env"
[ -f "$HOME/.config/bulkfarmer/claude.env" ] && source "$HOME/.config/bulkfarmer/claude.env"
set +a
notify() {
  [ -z "$TELEGRAM_BOT_TOKEN" ] && return
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" --data-urlencode "text=$1" >/dev/null
}
cd "$DIR" || { notify "⚠️ 스레드 초안 실패: 폴더 접근 불가"; exit 1; }
PROMPT=$(cat _threads/draft_prompt.txt 2>&1) || { notify "⚠️ 스레드 초안 실패: 프롬프트 읽기 불가
$PROMPT"; exit 1; }
command -v claude >/dev/null || { notify "⚠️ 스레드 초안 실패: claude CLI 없음"; exit 1; }

# 서버는 상시 온라인이지만, 일시 장애 대비 최대 2분만 기다린다
for i in $(seq 1 8); do
  curl -s -m 5 -o /dev/null https://api.anthropic.com/ && break
  sleep 15
done

TODAY=$(date +%F)
OUT="_threads/pending/$TODAY.json"

# 성공 판정은 종료 코드가 아니라 결과 파일 존재 여부로 한다 (맥 시절 검증된 방식)
TRY=0
for TRY in 1 2 3; do
  [ -s "$OUT" ] && break
  [ $TRY -gt 1 ] && sleep 90
  claude -p "$PROMPT" --model claude-sonnet-5 --permission-mode acceptEdits \
    --allowedTools Bash Read Write Edit Glob Grep
  [ -s "$OUT" ] && break
  echo "[$(date +%T)] 시도 $TRY 실패" >&2
done

if [ ! -s "$OUT" ]; then
  notify "⚠️ 스레드 초안 생성 3회 모두 실패 — 오늘 초안이 없습니다
$(tail -c 400 _threads/draft.log 2>/dev/null)"
  exit 1
fi
if [ "$TRY" -gt 1 ]; then
  N=$(/usr/bin/python3 -c "import json;print(len(json.load(open('$OUT'))['drafts']))" 2>/dev/null || echo "?")
  notify "ℹ️ 스레드 초안 생성 성공 (${TRY}회차 시도) — ${N}개"
fi
exit 0
