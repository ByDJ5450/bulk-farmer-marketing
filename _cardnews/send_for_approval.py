#!/usr/bin/env python3
"""카드뉴스를 텔레그램으로 보내 승인을 받는다.

  /usr/bin/python3 send_for_approval.py <슬라이드폴더>

슬라이드 전체를 앨범으로 보내고, 캡션과 함께 [발행]/[버림] 버튼을 붙인다.
실제 발행은 approve_worker.py 가 버튼 콜백을 받아서 수행한다.
"""
import json, sys, urllib.request, urllib.error, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PENDING = ROOT / "pending"
TG_CFG = Path("~/.config/bulkfarmer/telegram.env").expanduser()
MAX_ALBUM = 10


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


def send_album(paths, chat_id):
    """multipart/form-data 로 사진 여러 장을 하나의 앨범으로 전송."""
    boundary = uuid.uuid4().hex
    media = [{"type": "photo", "media": f"attach://f{i}"} for i in range(len(paths))]
    parts = []

    def field(name, value):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                     .encode() + str(value).encode() + b"\r\n")

    field("chat_id", chat_id)
    field("media", json.dumps(media))
    for i, p in enumerate(paths):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="f{i}"; filename="{p.name}"\r\n'
            f'Content-Type: image/png\r\n\r\n'.encode() + p.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(f"{BASE}/sendMediaGroup", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    slide_dir = Path(sys.argv[1]).resolve()
    slides = sorted(slide_dir.glob("slide_*.png"))
    caption_file = slide_dir / "caption.txt"

    if not slides:
        sys.exit(f"{slide_dir}에 slide_*.png 없음")
    if len(slides) > MAX_ALBUM:
        sys.exit(f"슬라이드 {len(slides)}장 — 인스타그램·텔레그램 앨범 상한 {MAX_ALBUM}장 초과")
    if not caption_file.exists():
        sys.exit("caption.txt 없음")

    caption = caption_file.read_text(encoding="utf-8").strip()
    slug = slide_dir.name
    chat_id = int(TG["TELEGRAM_CHAT_ID"])

    PENDING.mkdir(exist_ok=True)
    rec = PENDING / f"{slug}.json"
    if rec.exists() and json.loads(rec.read_text(encoding="utf-8")).get("status") == "published":
        sys.exit(f"이미 발행된 세트입니다: {slug}")

    r = send_album(slides, chat_id)
    if not r.get("ok"):
        sys.exit(f"앨범 전송 실패: {r}")

    preview = caption if len(caption) <= 900 else caption[:900] + "\n…(생략)"
    msg = call("sendMessage", {
        "chat_id": chat_id,
        "text": f"📸 카드뉴스 발행 대기  ({len(slides)}장)\n{slug}\n\n{preview}",
        "reply_markup": {"inline_keyboard": [[
            {"text": "✅ 인스타 발행", "callback_data": f"igpub:{slug}"},
            {"text": "🗑 버림", "callback_data": f"igdel:{slug}"}]]}})
    if not msg.get("ok"):
        sys.exit(f"버튼 메시지 실패: {msg}")

    rec.write_text(json.dumps({
        "slug": slug, "slide_dir": str(slide_dir), "slides": len(slides),
        "caption_file": str(caption_file), "status": "pending"},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"전송 완료 — {len(slides)}장, 승인 대기: {slug}")


if __name__ == "__main__":
    main()
