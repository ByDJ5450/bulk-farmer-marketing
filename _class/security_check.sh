#!/bin/zsh
# 벌크농부 클래스 — 매일 자동 보안 점검
# launchd(com.bulkfarmer.security-check)가 매일 09:20에 실행한다.
# 이상이 발견되면 텔레그램으로 알린다. 정상이면 하루 한 줄 요약만 보낸다.
#
# 점검 항목:
#  1) 회원 이메일이 공개키로 유출되는지 (핵심 — 뚫리면 즉시 경고)
#  2) 커스텀 도메인 HTTPS 정상 + 인증서 만료 임박 여부
#  3) 사이트 가동 여부
#  4) 글쓴이 이름 표시가 과잉 차단으로 깨지지 않았는지

export PATH="/usr/local/bin:/usr/bin:/bin"

SUPA_URL="https://ofqenoojssaorpycccjv.supabase.co"
ANON_KEY="sb_publishable_fk_axS9Vo_fvKo80-FQGlg_GUJzAtoK"  # 공개(publishable) 키
DOMAIN="bulkfarmer.co.kr"
FALLBACK="bulkfarmer-class.netlify.app"

CFG="$HOME/.config/bulkfarmer/telegram.env"
[ -f "$CFG" ] && source "$CFG"
notify() {
  [ -z "$TELEGRAM_BOT_TOKEN" ] && return
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" --data-urlencode "text=$1" >/dev/null
}

# 네트워크가 올라올 때까지 최대 5분 대기 (맥이 방금 깨어난 경우)
for i in $(seq 1 20); do
  curl -s -m 5 -o /dev/null "$SUPA_URL" && break
  sleep 15
done

problems=""

# ── 1) 이메일 유출 점검 ────────────────────────────────
email_resp=$(curl -s -m 15 "$SUPA_URL/rest/v1/profiles?select=email" \
  -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY")
if echo "$email_resp" | grep -q '@'; then
  problems="$problems
🚨 [심각] 회원 이메일이 공개키로 유출됩니다! 보안 잠금이 풀렸습니다. 즉시 점검 필요."
elif ! echo "$email_resp" | grep -q '42501'; then
  problems="$problems
⚠️ 이메일 점검 응답이 예상과 다릅니다: $(echo $email_resp | head -c 120)"
fi

# ── 2) 이름·역할 조회 정상 여부 (과잉 차단 감지) ──────────
name_resp=$(curl -s -m 15 "$SUPA_URL/rest/v1/profiles?select=name,role&limit=1" \
  -H "apikey: $ANON_KEY" -H "Authorization: Bearer $ANON_KEY")
if ! echo "$name_resp" | grep -q '"name"'; then
  problems="$problems
⚠️ 글쓴이 이름 조회가 막혔습니다(과잉 차단 가능). 커뮤니티 표시가 깨질 수 있음: $(echo $name_resp | head -c 120)"
fi

# ── 3) 사이트 가동 + HTTPS ────────────────────────────
code=$(curl -s -m 15 -o /dev/null -w '%{http_code}' "https://$DOMAIN")
https_ok="yes"
if [ "$code" != "200" ]; then
  https_ok="no"
  fb=$(curl -s -m 15 -o /dev/null -w '%{http_code}' "https://$FALLBACK")
  if [ "$fb" = "200" ]; then
    problems="$problems
ℹ️ https://$DOMAIN 아직 미연결(코드 $code). netlify.app 주소는 정상 — 인증서 발급 대기 중일 수 있음."
  else
    problems="$problems
🚨 사이트 접속 불가! $DOMAIN=$code, $FALLBACK=$fb"
  fi
fi

# ── 4) 인증서 만료 임박 (30일 이내) ────────────────────
if [ "$https_ok" = "yes" ]; then
  end=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -n "$end" ]; then
    end_ts=$(date -j -f "%b %d %T %Y %Z" "$end" +%s 2>/dev/null)
    now_ts=$(date +%s)
    if [ -n "$end_ts" ]; then
      days=$(( (end_ts - now_ts) / 86400 ))
      if [ "$days" -lt 30 ]; then
        problems="$problems
⚠️ HTTPS 인증서 만료 ${days}일 남음 (보통 자동 갱신되지만 확인 권장)."
      fi
    fi
  fi
fi

# ── 결과 알림 ──────────────────────────────────────────
TODAY=$(date "+%Y-%m-%d %H:%M")
if [ -n "$problems" ]; then
  notify "🔧 벌크농부 클래스 보안 점검 ($TODAY)
$problems"
else
  notify "🔒 벌크농부 클래스 보안 점검 정상 ($TODAY)
· 회원 이메일 보호됨
· 사이트 HTTPS 정상
· 커뮤니티 표시 정상"
fi
