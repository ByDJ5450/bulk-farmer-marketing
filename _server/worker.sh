#!/bin/bash
# 승인 워커 cron 래퍼 — 매분 실행. 맥 launchd com.bulkfarmer.threads-worker 이관.
# 텔레그램 폴링(승인 버튼·작업 지시) + 예약 발행. 실체는 approve_worker.py.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
set -a
[ -f "$HOME/.config/bulkfarmer/claude.env" ] && source "$HOME/.config/bulkfarmer/claude.env"
set +a
exec /usr/bin/python3 "$HOME/벌크농부/00_벌크농부 마케팅 에이전트팀/_threads/approve_worker.py"
