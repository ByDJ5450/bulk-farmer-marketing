#!/bin/bash
# 맥 → 오라클 서버 복사. 맥에서 실행한다.
#
#   ./copy_to_server.sh ubuntu@<서버IP> [SSH키경로]
#
# 복사만 한다 — 맥에서 지우는 것은 없다 (--delete 없음). 재실행하면 갱신 복사.
set -euo pipefail

DEST="${1:?사용법: ./copy_to_server.sh ubuntu@서버IP [SSH키경로]}"
KEY="${2:-}"

SSHCMD="ssh"
[ -n "$KEY" ] && SSHCMD="ssh -i $KEY"

SRC="$HOME/Desktop/벌크농부/00_벌크농부 마케팅 에이전트팀"
MEM="$HOME/.claude/projects/-Users-idongjin-Desktop------00---------------/memory"
CFG="$HOME/.config/bulkfarmer"

[ -d "$SRC" ] || { echo "작업공간을 찾을 수 없습니다: $SRC"; exit 1; }
[ -d "$MEM" ] || { echo "메모리 폴더를 찾을 수 없습니다: $MEM"; exit 1; }
[ -d "$CFG" ] || { echo "자격증명 폴더를 찾을 수 없습니다: $CFG"; exit 1; }

echo "▸ 서버 연결 확인..."
RHOME=$($SSHCMD "$DEST" 'echo $HOME')
RDIR="$RHOME/벌크농부/00_벌크농부 마케팅 에이전트팀"

# 서버 쪽 Claude Code 메모리 경로 — 프로젝트 경로의 영숫자 외 문자를 '-'로 치환한 이름
MUNGED=$(python3 -c "import re,sys; print(re.sub(r'[^A-Za-z0-9]', '-', sys.argv[1]))" "$RDIR")
RMEM="$RHOME/.claude/projects/$MUNGED/memory"

$SSHCMD "$DEST" "mkdir -p \"$RDIR\" \"$RMEM\" \"$RHOME/.config/bulkfarmer\""

echo "▸ 작업공간 복사 (219MB — 수 분 걸릴 수 있음)..."
rsync -az --exclude ".DS_Store" -e "$SSHCMD" "$SRC/" "$DEST:'$RDIR/'"

echo "▸ Claude 메모리 복사..."
rsync -az --exclude ".DS_Store" -e "$SSHCMD" "$MEM/" "$DEST:'$RMEM/'"

# ⚠️ 2026-08-13 전환 완료 후에는 서버 state.json이 실운영본이다. 맥의 옛 상태로
# 덮어쓰면 텔레그램 오프셋이 되감겨 이중 발행된다. 최초 이전 때만 FORCE_STATE=1로 켠다.
if [ "${FORCE_STATE:-0}" = "1" ]; then
  echo "▸ 워커 실행 상태 복사 (FORCE_STATE=1)..."
  STATE_SRC="$HOME/Library/Application Support/bulkfarmer"
  if [ -d "$STATE_SRC" ]; then
    $SSHCMD "$DEST" "mkdir -p \"$RHOME/.local/state/bulkfarmer\""
    rsync -az -e "$SSHCMD" "$STATE_SRC/" "$DEST:'$RHOME/.local/state/bulkfarmer/'"
  fi
else
  echo "▸ 워커 실행 상태는 건너뜀 (서버가 실운영본 — 필요 시 FORCE_STATE=1)"
fi

echo "▸ 자격증명 복사 (telegram·meta·r2)..."
rsync -az -e "$SSHCMD" "$CFG/" "$DEST:'$RHOME/.config/bulkfarmer/'"
$SSHCMD "$DEST" "chmod 700 \"$RHOME/.config/bulkfarmer\" && chmod 600 \"$RHOME/.config/bulkfarmer\"/*.env && chmod +x \"$RDIR/_server\"/*.sh \"$RDIR/_class/security_check.sh\""

echo ""
echo "✅ 복사 완료. 다음 단계 — 서버에서:"
echo "   $SSHCMD $DEST"
echo "   cd \"\$HOME/벌크농부/00_벌크농부 마케팅 에이전트팀/_server\" && ./setup_server.sh"
