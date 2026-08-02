#!/usr/bin/env python3
"""네이버 로그인 OAuth 2.0 — 블로그 글쓰기용 토큰 발급·갱신.

  /usr/bin/python3 naver_auth.py login     브라우저 인증 → 토큰 저장 (최초 1회)
  /usr/bin/python3 naver_auth.py refresh   access_token 갱신
  /usr/bin/python3 naver_auth.py status    남은 유효시간 확인

access_token 유효기간은 1시간이다. 그래서 발행 스크립트는 매번 ensure_token()으로
자동 갱신한 뒤 API를 호출한다. refresh_token은 갱신할 때마다 새로 내려오지 않으므로
기존 값을 유지한다.

자격증명은 ~/.config/bulkfarmer/naver.env, 토큰은 naver_token.json (권한 600).
토큰 값은 어떤 출력·로그에도 찍지 않는다.
"""
import http.server, json, os, sys, threading, urllib.parse, urllib.request, urllib.error, webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

CFG = Path("~/.config/bulkfarmer/naver.env").expanduser()
TOKEN = Path("~/.config/bulkfarmer/naver_token.json").expanduser()
AUTHORIZE = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
# access_token 만료 조금 전에 미리 갱신한다
REFRESH_MARGIN = timedelta(minutes=5)


def cfg():
    if not CFG.exists():
        sys.exit(f"{CFG} 없음 — _blog/naver_setup.md 를 먼저 따라 하세요")
    d = {}
    for line in CFG.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "NAVER_REDIRECT_URI"):
        if not d.get(k):
            sys.exit(f"naver.env에 {k} 없음")
    return d


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def save(tok):
    tok["obtained_at"] = datetime.now(timezone.utc).isoformat()
    TOKEN.write_text(json.dumps(tok, indent=2), encoding="utf-8")
    os.chmod(TOKEN, 0o600)


def load():
    return json.loads(TOKEN.read_text(encoding="utf-8")) if TOKEN.exists() else None


def expires_at(tok):
    got = datetime.fromisoformat(tok["obtained_at"])
    return got + timedelta(seconds=int(tok.get("expires_in", 3600)))


def login():
    e = cfg()
    redirect = e["NAVER_REDIRECT_URI"]
    parsed = urllib.parse.urlparse(redirect)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        sys.exit("이 스크립트는 localhost 콜백만 처리합니다. "
                 "네이버 개발자센터에 http://localhost:8765/callback 을 등록하세요")
    port = parsed.port or 80

    state = os.urandom(12).hex()
    url = f"{AUTHORIZE}?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": e["NAVER_CLIENT_ID"],
        "redirect_uri": redirect, "state": state})

    got, done = {}, threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            done.set()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = "code" in got and got.get("state") == state
            self.wfile.write(("<h2>" + ("인증 완료 — 터미널로 돌아가세요"
                                        if ok else "인증 실패 — 터미널을 확인하세요")
                              + "</h2>").encode())

        def log_message(self, *a):
            pass

    try:
        srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    except OSError as ex:
        sys.exit(f"{port} 포트를 열 수 없습니다: {ex}")

    threading.Thread(target=srv.handle_request, daemon=True).start()
    print(f"브라우저에서 네이버 로그인 창을 엽니다. 열리지 않으면 아래 주소를 직접 여세요.\n{url}\n")
    webbrowser.open(url)

    if not done.wait(timeout=180):
        sys.exit("3분 안에 인증이 완료되지 않았습니다")
    if got.get("state") != state:
        sys.exit("state 불일치 — 인증을 다시 시도하세요")
    if "code" not in got:
        sys.exit(f"인증 거부: {got.get('error_description', got)}")

    tok = get(f"{TOKEN_URL}?" + urllib.parse.urlencode({
        "grant_type": "authorization_code", "client_id": e["NAVER_CLIENT_ID"],
        "client_secret": e["NAVER_CLIENT_SECRET"], "code": got["code"], "state": state}))
    if "access_token" not in tok:
        sys.exit(f"토큰 발급 실패: {tok.get('error_description', tok)}")
    save(tok)
    print(f"토큰 저장 완료 → {TOKEN}  (유효 {tok.get('expires_in')}초)")


def refresh(quiet=False):
    e, tok = cfg(), load()
    if not tok or not tok.get("refresh_token"):
        sys.exit("저장된 refresh_token이 없습니다 — naver_auth.py login 먼저 실행하세요")
    new = get(f"{TOKEN_URL}?" + urllib.parse.urlencode({
        "grant_type": "refresh_token", "client_id": e["NAVER_CLIENT_ID"],
        "client_secret": e["NAVER_CLIENT_SECRET"], "refresh_token": tok["refresh_token"]}))
    if "access_token" not in new:
        sys.exit(f"갱신 실패: {new.get('error_description', new)}")
    # 갱신 응답에는 refresh_token이 빠져 있을 수 있다 — 기존 값을 유지한다
    new.setdefault("refresh_token", tok["refresh_token"])
    save(new)
    if not quiet:
        print(f"갱신 완료 (유효 {new.get('expires_in')}초)")
    return new


def ensure_token():
    """발행 직전에 호출한다. 만료가 임박했으면 조용히 갱신하고 access_token을 돌려준다."""
    tok = load()
    if not tok:
        sys.exit("토큰 없음 — naver_auth.py login 먼저 실행하세요")
    if datetime.now(timezone.utc) + REFRESH_MARGIN >= expires_at(tok):
        tok = refresh(quiet=True)
    return tok["access_token"]


def status():
    tok = load()
    if not tok:
        print("토큰 없음 — naver_auth.py login 실행 필요")
        return
    left = expires_at(tok) - datetime.now(timezone.utc)
    mins = int(left.total_seconds() // 60)
    print(f"access_token {'만료됨' if mins < 0 else f'{mins}분 남음'} "
          f"/ refresh_token {'있음' if tok.get('refresh_token') else '없음'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"login": login, "refresh": refresh, "status": status}.get(cmd, lambda: sys.exit(__doc__))()
