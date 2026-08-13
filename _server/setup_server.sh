#!/bin/bash
# 오라클 서버 초기 설치. copy_to_server.sh 이후 서버에서 실행한다.
set -euo pipefail

DIR="$HOME/벌크농부/00_벌크농부 마케팅 에이전트팀"
CFG="$HOME/.config/bulkfarmer"
[ -d "$DIR" ] || { echo "작업공간이 없습니다. 먼저 맥에서 copy_to_server.sh를 실행하세요."; exit 1; }

echo "▸ 한국 시간대 설정 (스레드 발행 창 08~23시가 로컬 시각 기준)"
sudo timedatectl set-timezone Asia/Seoul

echo "▸ 패키지 설치"
sudo apt-get update -qq
sudo apt-get install -y -qq git curl zsh jq ffmpeg fonts-noto-cjk python3 python3-pip
sudo snap install chromium 2>/dev/null || sudo apt-get install -y -qq chromium-browser

echo "▸ yt-dlp 설치 (유튜브·틱톡 수집)"
mkdir -p "$HOME/.local/bin"
curl -sL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o "$HOME/.local/bin/yt-dlp"
chmod +x "$HOME/.local/bin/yt-dlp"

echo "▸ Claude Code 설치"
command -v claude >/dev/null 2>&1 || curl -fsSL https://claude.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"

# ── Claude 인증 토큰 (맥에서 `claude setup-token`으로 발급한 값) ──
if [ ! -f "$CFG/claude.env" ]; then
  echo ""
  echo "맥에서 발급한 토큰을 붙여넣으세요 (claude setup-token 결과, 입력이 화면에 안 보임):"
  read -rs TOKEN
  [ -n "$TOKEN" ] || { echo "토큰이 비었습니다."; exit 1; }
  umask 077
  printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\nCLAUDE_TOKEN_ISSUED=%s\n' "$TOKEN" "$(date +%F)" > "$CFG/claude.env"
  unset TOKEN
fi

echo "▸ Claude 동작 테스트"
set -a; source "$CFG/claude.env"; set +a
ANSWER=$(claude -p "설치 확인. '준비 완료'라고만 답하라." 2>&1 | tail -1) || true
echo "  → $ANSWER"

echo "▸ 서버 전용 로컬 규칙 작성 (CLAUDE.local.md — 커밋되지 않음)"
cat > "$DIR/CLAUDE.local.md" <<'EOF'
# 서버 로컬 규칙 (오라클 서버 사본)

- 여기는 **오라클 서버**다. 맥 원본이 백업이며, 이 사본이 실운영본이다.
- 크롬 헤드리스는 맥 경로 대신 `chromium`을 쓴다 (스냅: `/snap/bin/chromium`).
  플래그는 CLAUDE.md의 것을 그대로 쓴다 (`--headless --disable-gpu ...`).
- launchd는 없다. 자동화는 cron이다 — `crontab -l`로 확인, plist 문서는 무시한다.
- `git push`는 사용자가 요청할 때만 한다 (자동 백업 cron이 따로 있을 수 있음).
- 클립보드(pbcopy)가 없다. 결과물은 파일로 저장하고 경로를 알려준다.
EOF

echo "▸ cron 등록"
LOGDIR="$DIR/_server/logs"
mkdir -p "$LOGDIR"
SRV="$DIR/_server"
crontab - <<EOF
# 벌크농부 자동화 — 맥 launchd 4종을 이관 (KST)
* * * * *   "$SRV/worker.sh"           >> "$DIR/_threads/worker.log" 2>> "$DIR/_threads/worker.err.log"
13 8 * * *  "$SRV/threads_draft.sh"    >> "$DIR/_threads/draft.log"  2>&1
7 9 * * 1   "$SRV/weekly_report.sh"    >> "$DIR/_analytics/cron.log" 2>> "$DIR/_analytics/cron.err.log"
20 9 * * *  zsh "$DIR/_class/security_check.sh" >> "$LOGDIR/security.log" 2>&1
0 10 1 * *  "$SRV/token_reminder.sh"   >> "$LOGDIR/token.log" 2>&1
# 서버 커밋을 GitHub에도 백업하려면 README 6번(Deploy key) 후 아래 주석 해제
# 30 23 * * *  cd "$DIR" && git push origin main >> "$LOGDIR/push.log" 2>&1
EOF
crontab -l

# 텔레그램으로 완료 알림
if [ -f "$CFG/telegram.env" ]; then
  source "$CFG/telegram.env"
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
    --data-urlencode "text=🖥 오라클 서버 준비 완료 — 이제 24시간 대기합니다.
'현황' 또는 작업 지시를 보내 시험해보세요.
⚠️ 맥의 launchd 4종을 아직 안 내렸다면 지금 내려주세요 (README 5번)." >/dev/null
fi

echo ""
echo "✅ 설치 완료. 텔레그램에 '현황'을 보내 시험하세요."
echo "⚠️  맥의 launchd 자동화를 내렸는지 확인하세요 (동시에 돌면 이중 발행됩니다)."
