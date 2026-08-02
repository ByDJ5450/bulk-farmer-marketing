#!/usr/bin/env python3
"""블로그 글을 텔레그램으로 보내 승인을 받는다.

  /usr/bin/python3 send_for_approval.py <글폴더> [--category N] [--open all]

제목과 본문 미리보기를 보내고 [발행]/[버림] 버튼을 붙인다.
실제 발행은 _threads/approve_worker.py 가 버튼 콜백을 받아서 수행한다.
"""
import argparse, html, json, re, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PENDING = ROOT / "pending"
TG_CFG = Path("~/.config/bulkfarmer/telegram.env").expanduser()
PREVIEW = 1200


def env(p):
    d = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


TG = env(TG_CFG)
BASE = f"https://api.telegram.org/bot{TG['TELEGRAM_BOT_TOKEN']}"


def call(method, payload):
    req = urllib.request.Request(f"{BASE}/{method}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def to_text(h):
    """HTML 본문을 텔레그램 미리보기용 평문으로. 태그만 걷어낸다."""
    t = re.sub(r"<br\s*/?>|</p>|</h[1-6]>|</li>", "\n", h, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post_dir")
    ap.add_argument("--category")
    ap.add_argument("--open", dest="open_type", default="closed",
                    choices=["all", "closed", "neighbor", "agreedNeighbor"])
    a = ap.parse_args()

    d = Path(a.post_dir).resolve()
    title_f, content_f = d / "title.txt", d / "content.html"
    if not title_f.exists() or not content_f.exists():
        sys.exit(f"{d}에 title.txt / content.html 이 필요합니다")

    title = title_f.read_text(encoding="utf-8").strip()
    body = to_text(content_f.read_text(encoding="utf-8"))
    slug = d.name
    chat_id = int(TG["TELEGRAM_CHAT_ID"])

    PENDING.mkdir(exist_ok=True)
    rec = PENDING / f"{slug}.json"
    if rec.exists() and json.loads(rec.read_text(encoding="utf-8")).get("status") == "published":
        sys.exit(f"이미 발행된 글입니다: {slug}")

    preview = body if len(body) <= PREVIEW else body[:PREVIEW] + "\n…(생략)"
    open_label = {"all": "전체공개", "closed": "비공개", "neighbor": "이웃공개",
                  "agreedNeighbor": "서로이웃공개"}[a.open_type]
    msg = call("sendMessage", {
        "chat_id": chat_id,
        "text": (f"📝 네이버 블로그 발행 대기 ({open_label})\n{slug}\n\n"
                 f"제목  {title}\n본문  {len(body):,}자\n\n{preview}"),
        "reply_markup": {"inline_keyboard": [[
            {"text": "✅ 블로그 발행", "callback_data": f"nvpub:{slug}"},
            {"text": "🗑 버림", "callback_data": f"nvdel:{slug}"}]]}})
    if not msg.get("ok"):
        sys.exit(f"전송 실패: {msg}")

    rec.write_text(json.dumps({
        "slug": slug, "post_dir": str(d), "title": title,
        "category": a.category, "open_type": a.open_type, "status": "pending"},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"전송 완료 — 승인 대기: {slug}")


if __name__ == "__main__":
    main()
