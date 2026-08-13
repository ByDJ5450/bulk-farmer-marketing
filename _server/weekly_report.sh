#!/bin/bash
# 주간 채널 리포트 — 매주 월 09:07. 맥 launchd com.bulkfarmer.weekly-report 이관.
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
cd "$DIR" || { notify "⚠️ 주간 리포트 실패: 프로젝트 폴더에 접근할 수 없습니다."; exit 1; }
PROMPT=$(cat _analytics/weekly_report_prompt.txt 2>&1) || {
  notify "⚠️ 주간 리포트 실패: 프롬프트 파일을 읽지 못했습니다.
$PROMPT"; exit 1; }
command -v claude >/dev/null || { notify "⚠️ 주간 리포트 실패: claude CLI를 찾을 수 없습니다 (PATH 문제)."; exit 1; }
command -v yt-dlp >/dev/null || notify "⚠️ 경고: yt-dlp를 찾을 수 없습니다. 수집이 실패할 수 있습니다."

# 일시 장애 대비 최대 2분 대기
for i in $(seq 1 8); do
  curl -s -m 5 -o /dev/null https://api.anthropic.com/ && break
  sleep 15
done

# 성공 판정은 결과 파일로 한다 — 종료 코드 0이어도 리포트가 없을 수 있다 (2026-08-03 실증)
OUT="_analytics/$(date +%F)_channel_report.md"
RC=1
for TRY in 1 2; do
  [ -s "$OUT" ] && { RC=0; break; }
  [ $TRY -gt 1 ] && sleep 60
  claude -p "$PROMPT" --model claude-sonnet-5 --permission-mode acceptEdits \
    --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch
  [ -s "$OUT" ] && { RC=0; break; }
  echo "[$(date +%T)] 리포트 시도 $TRY 실패 — 결과 파일 없음" >&2
done

if [ $RC -ne 0 ]; then
  notify "⚠️ 주간 리포트 실패 (종료 코드 $RC)
마지막 오류:
$(tail -c 400 _analytics/cron.err.log 2>/dev/null)"
fi
exit $RC
