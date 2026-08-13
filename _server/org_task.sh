#!/bin/bash
# AI 조직 공용 러너 — cron이 팀별 프롬프트를 실행한다.
#
#   org_task.sh <프롬프트파일> [성공판정파일]
#
# 성공판정파일에 {date}를 쓰면 오늘 날짜(YYYY-MM-DD)로 치환된다.
# 판정 파일이 있으면 파일 생성 여부로 성공을 판단하고 1회 재시도한다.
# 없으면 1회 실행하고 종료 코드로만 오류를 알린다.
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
cd "$DIR" || { notify "⚠️ 조직 작업 실패: 폴더 접근 불가"; exit 1; }

PFILE="$1"
PROMPT=$(cat "$PFILE" 2>&1) || { notify "⚠️ 조직 작업 실패: 프롬프트 없음 — $PFILE"; exit 1; }
OUT="${2:-}"
OUT="${OUT//\{date\}/$(date +%F)}"
command -v claude >/dev/null || { notify "⚠️ 조직 작업 실패: claude CLI 없음"; exit 1; }

RC=0
for TRY in 1 2; do
  [ -n "$OUT" ] && [ -s "$OUT" ] && break
  [ $TRY -gt 1 ] && sleep 60
  claude -p "$PROMPT" --model claude-sonnet-5 --permission-mode acceptEdits \
    --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch
  RC=$?
  [ -z "$OUT" ] && break          # 파일 판정이 없는 작업은 재시도하지 않는다
  [ -s "$OUT" ] && break
  echo "[$(date +%T)] $(basename "$PFILE") 시도 $TRY 실패 — 결과 파일 없음" >&2
done

if [ -n "$OUT" ] && [ ! -s "$OUT" ]; then
  notify "⚠️ 조직 작업 실패: $(basename "$PFILE") — 결과물($OUT)이 만들어지지 않았습니다"
  exit 1
fi
if [ -z "$OUT" ] && [ $RC -ne 0 ]; then
  notify "⚠️ 조직 작업 오류: $(basename "$PFILE") (종료 코드 $RC)"
  exit $RC
fi
exit 0
