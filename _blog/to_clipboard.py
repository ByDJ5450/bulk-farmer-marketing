#!/usr/bin/env python3
"""블로그 글을 서식 그대로 클립보드에 올린다. 스마트에디터에 Cmd+V 하면 끝.

  /usr/bin/python3 to_clipboard.py <글폴더> [--notify]

네이버 블로그 **글쓰기 API는 2020-05-06 종료**됐다. 광고성 글 대량 발행 때문에
네이버가 닫았고, 개발자센터 '사용 API' 목록에 블로그 자체가 없다.
그래서 발행은 자동화할 수 없고, 붙여넣기를 1초로 줄이는 것이 최선이다.

macOS 클립보드에 HTML 플레이버(public.html)로 올리므로 제목·표·굵기가 그대로 붙는다.
평문으로 붙는다면 스마트에디터가 아니라 다른 곳에 붙여넣은 것이다.

글 폴더 구조
  _blog/{slug}/
    title.txt      제목 한 줄
    content.html   본문 HTML
"""
import argparse, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

TG_CFG = Path("~/.config/bulkfarmer/telegram.env").expanduser()


def env(p):
    d = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def notify(text):
    tg = env(TG_CFG)
    if not tg.get("TELEGRAM_BOT_TOKEN"):
        return
    body = urllib.parse.urlencode({"chat_id": tg.get("TELEGRAM_CHAT_ID"), "text": text}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{tg['TELEGRAM_BOT_TOKEN']}/sendMessage", data=body), timeout=30)
    except Exception as e:
        print(f"(텔레그램 전송 실패: {e})", file=sys.stderr)


def set_html_clipboard(html):
    """AppleScript의 «data HTML…» 형식은 16진 문자열을 받는다."""
    hexed = html.encode("utf-8").hex()
    subprocess.run(["osascript", "-e", f"set the clipboard to «data HTML{hexed}»"], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post_dir")
    ap.add_argument("--notify", action="store_true", help="텔레그램으로 제목·체크리스트 전송")
    a = ap.parse_args()

    d = Path(a.post_dir)
    title_f, content_f = d / "title.txt", d / "content.html"
    if not title_f.exists() or not content_f.exists():
        sys.exit(f"{d}에 title.txt / content.html 이 필요합니다")

    title = title_f.read_text(encoding="utf-8").strip()
    html = content_f.read_text(encoding="utf-8").strip()
    if not title or not html:
        sys.exit("제목 또는 본문이 비어 있습니다")

    set_html_clipboard(html)

    print(f"제목  {title}")
    print(f"본문  {len(html):,}자 — 서식 그대로 클립보드에 올렸습니다\n")
    print("1. blog.naver.com 글쓰기 열기")
    print("2. 제목 칸에 위 제목 붙여넣기 (아래 명령으로 제목만 다시 복사 가능)")
    print(f"   printf %s {title!r} | pbcopy")
    print("3. 본문 칸에 Cmd+V")
    print("4. 발행 전 확인: 카테고리 / 태그 / 공개설정")

    if a.notify:
        notify(f"📝 블로그 글 준비됨\n\n{title}\n\n"
               f"본문은 맥 클립보드에 있습니다. blog.naver.com 글쓰기에서 Cmd+V 하세요.")


if __name__ == "__main__":
    main()
