#!/usr/bin/env python3
"""네이버 블로그 글 발행.

  /usr/bin/python3 publish_post.py <글폴더> [--publish] [--category N] [--open closed]

`--publish` 없이 실행하면 **드라이런**: 토큰 확인과 본문 검증까지만 하고
실제 발행은 하지 않는다. 기본값이 드라이런인 이유는 오발행을 막기 위해서다.

글 폴더 구조
  _blog/{slug}/
    title.txt      제목 한 줄
    content.html   본문 (네이버 블로그는 HTML 본문을 받는다)
    images/        선택 — 있으면 파일명 순서대로 첨부

첫 발행은 반드시 `--open closed`(비공개)로 한 번 올려서 네이버 에디터에서
실제 렌더링을 눈으로 확인한 뒤 공개로 바꾸는 것을 권한다. HTML 태그 지원 범위가
에디터마다 달라서, API 응답이 성공이어도 본문이 깨질 수 있다.
"""
import argparse, json, sys, urllib.parse, urllib.request, urllib.error, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import naver_auth

API = "https://openapi.naver.com/blog/writePost.json"
TG_CFG = Path("~/.config/bulkfarmer/telegram.env").expanduser()
MAX_TITLE = 100
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif"}


def env(path):
    d = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


TG = env(TG_CFG)


def notify(text):
    if not TG.get("TELEGRAM_BOT_TOKEN"):
        return
    body = urllib.parse.urlencode({"chat_id": TG.get("TELEGRAM_CHAT_ID"), "text": text}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{TG['TELEGRAM_BOT_TOKEN']}/sendMessage", data=body), timeout=30)
    except Exception:
        pass


def multipart(fields, files):
    """(content_type, body) 반환. 이미지가 없으면 files는 빈 리스트."""
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
                     + str(v).encode("utf-8") + b"\r\n")
    for p in files:
        ct = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        parts.append(
            f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{p.name}"\r\n'
            f"Content-Type: {ct}\r\n\r\n".encode() + p.read_bytes() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return f"multipart/form-data; boundary={b}", b"".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post_dir")
    ap.add_argument("--publish", action="store_true", help="실제 발행 (없으면 드라이런)")
    ap.add_argument("--category", help="카테고리 번호 (listCategory로 확인)")
    ap.add_argument("--open", dest="open_type", default="closed",
                    choices=["all", "closed", "neighbor", "agreedNeighbor"],
                    help="공개 범위 (기본 closed — 비공개로 올려서 확인 후 공개 권장)")
    a = ap.parse_args()

    d = Path(a.post_dir)
    title_f, content_f = d / "title.txt", d / "content.html"
    if not title_f.exists() or not content_f.exists():
        sys.exit(f"{d}에 title.txt / content.html 이 필요합니다")

    title = title_f.read_text(encoding="utf-8").strip()
    contents = content_f.read_text(encoding="utf-8").strip()
    if not title or not contents:
        sys.exit("제목 또는 본문이 비어 있습니다")
    if len(title) > MAX_TITLE:
        sys.exit(f"제목 {len(title)}자 — 상한 {MAX_TITLE}자 초과")

    images = sorted(p for p in (d / "images").glob("*") if p.suffix.lower() in IMG_EXT) \
        if (d / "images").is_dir() else []

    print(f"제목   {title}")
    print(f"본문   {len(contents):,}자")
    print(f"이미지 {len(images)}장" + (f" ({', '.join(p.name for p in images)})" if images else ""))
    print(f"공개   {a.open_type}")

    token = naver_auth.ensure_token()

    if not a.publish:
        print("\n드라이런 — 실제 발행하지 않았습니다. 발행하려면 --publish 를 붙이세요.")
        return

    fields = {"title": title, "contents": contents, "options.openType": a.open_type}
    if a.category:
        fields["categoryNo"] = a.category

    ct, body = multipart(fields, images)
    req = urllib.request.Request(API, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": ct})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        notify(f"⚠️ 네이버 블로그 발행 실패 (HTTP {e.code})\n{detail}")
        sys.exit(f"발행 실패 HTTP {e.code}: {detail}")

    msg = res.get("message", {})
    if msg.get("status") != "success":
        notify(f"⚠️ 네이버 블로그 발행 실패\n{json.dumps(res, ensure_ascii=False)[:400]}")
        sys.exit(f"발행 실패: {json.dumps(res, ensure_ascii=False)[:400]}")

    r_ = msg.get("result", {})
    blog_id, post_id = r_.get("blogId", ""), r_.get("postId", "")
    link = f"https://blog.naver.com/{blog_id}/{post_id}" if blog_id and post_id else ""
    print(f"\n✅ 발행 완료  {post_id}  {link}")
    note = "" if a.open_type == "all" else f"\n※ {a.open_type} 상태입니다 — 확인 후 공개로 바꾸세요"
    notify(f"✅ 네이버 블로그 발행 완료\n{title}\n{link}{note}")


if __name__ == "__main__":
    main()
