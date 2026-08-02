#!/usr/bin/env python3
"""카드뉴스 → 인스타그램 캐러셀 발행.

  /usr/bin/python3 publish_carousel.py <슬라이드폴더> --caption <캡션파일> [--publish]

`--publish` 없이 실행하면 **드라이런**: 변환·업로드·컨테이너 생성까지만 하고
실제 게시는 하지 않는다. 기본값이 드라이런인 이유는 오발행을 막기 위해서다.

파이프라인
  PNG → JPEG 변환(sips) → R2 업로드 → 아이템 컨테이너 → 캐러셀 컨테이너 → 발행 → R2 정리

Meta는 이미지를 가져가 자체 저장하므로, 발행 후 R2 객체는 지워도 게시물은 남는다.
"""
import argparse, json, re, subprocess, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import r2_upload as r2

META_CFG = Path("~/.config/bulkfarmer/meta.env").expanduser()
TG_CFG = Path("~/.config/bulkfarmer/telegram.env").expanduser()
GRAPH = "https://graph.instagram.com/v23.0"
MAX_SLIDES = 10   # 인스타그램 캐러셀 상한
MAX_CAPTION = 2200


def env(path):
    d = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


META, TG = env(META_CFG), env(TG_CFG)


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": {"message": f"HTTP {e.code}"}}
    except Exception as e:
        return {"error": {"message": str(e)}}


def notify(text):
    if TG.get("TELEGRAM_BOT_TOKEN"):
        post(f"https://api.telegram.org/bot{TG['TELEGRAM_BOT_TOKEN']}/sendMessage",
             {"chat_id": TG.get("TELEGRAM_CHAT_ID"), "text": text})


def to_jpeg(png, out_dir):
    """인스타그램은 PNG를 받지 않는다. JPEG로 변환한다."""
    out = out_dir / (png.stem + ".jpg")
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90",
                    str(png), "--out", str(out)],
                   check=True, capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slide_dir")
    ap.add_argument("--caption", required=True)
    ap.add_argument("--publish", action="store_true", help="실제 게시 (없으면 드라이런)")
    ap.add_argument("--keep", action="store_true", help="발행 후 R2 객체 유지")
    a = ap.parse_args()

    uid, tok = META.get("IG_USER_ID"), META.get("IG_TOKEN")
    if not uid or not tok:
        sys.exit("meta.env에 IG_USER_ID / IG_TOKEN 없음")

    slide_dir = Path(a.slide_dir)
    slides = sorted(slide_dir.glob("slide_*.png"))
    if not slides:
        sys.exit(f"{slide_dir}에 slide_*.png 없음")
    if len(slides) > MAX_SLIDES:
        sys.exit(f"슬라이드 {len(slides)}장 — 인스타그램 상한 {MAX_SLIDES}장 초과")

    caption = Path(a.caption).read_text(encoding="utf-8").strip()
    if len(caption) > MAX_CAPTION:
        sys.exit(f"캡션 {len(caption)}자 — 상한 {MAX_CAPTION}자 초과")

    # R2 키는 ASCII로 유지한다 — 한글 경로는 인코딩 사고를 부른다
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slide_dir.name).strip("-") or "set"
    stamp = f"cardnews/{date.today()}-{slug}"
    jpg_dir = slide_dir / ".jpg"
    jpg_dir.mkdir(exist_ok=True)

    # 1. 변환 + 업로드
    keys, containers = [], []
    for png in slides:
        jpg = to_jpeg(png, jpg_dir)
        key = f"{stamp}/{jpg.name}"
        code, err = r2.request("PUT", key, jpg.read_bytes(), "image/jpeg")
        if code != 200:
            sys.exit(f"R2 업로드 실패 {png.name}: {code} {err}")
        keys.append(key)
        print(f"  업로드  {png.name} → {jpg.name}")

    base = META.get("R2_PUBLIC_URL") or r2.cfg().get("R2_PUBLIC_URL", "").rstrip("/")

    # 2. 아이템 컨테이너
    for key in keys:
        res = post(f"{GRAPH}/{uid}/media",
                   {"image_url": f"{base}/{urllib.parse.quote(key, safe='/')}",
                    "is_carousel_item": "true", "access_token": tok})
        if "id" not in res:
            sys.exit(f"아이템 컨테이너 실패: {res.get('error', {}).get('message')}")
        containers.append(res["id"])
        print(f"  컨테이너 {res['id']}")

    # 3. 캐러셀 컨테이너
    car = post(f"{GRAPH}/{uid}/media",
               {"media_type": "CAROUSEL", "children": ",".join(containers),
                "caption": caption, "access_token": tok})
    if "id" not in car:
        sys.exit(f"캐러셀 컨테이너 실패: {car.get('error', {}).get('message')}")
    print(f"  캐러셀   {car['id']}  (슬라이드 {len(containers)}장)")

    if not a.publish:
        print("\n드라이런 — 실제 게시하지 않았습니다. 게시하려면 --publish 를 붙이세요.")
        print(f"업로드된 R2 키 {len(keys)}개는 정리하지 않았습니다: {stamp}/")
        return

    # 4. 발행 (컨테이너 준비 대기 포함)
    for attempt in range(6):
        time.sleep(3 if attempt == 0 else 5)
        res = post(f"{GRAPH}/{uid}/media_publish",
                   {"creation_id": car["id"], "access_token": tok})
        if "id" in res:
            media_id = res["id"]
            break
        msg = res.get("error", {}).get("message", "")
        if attempt == 5:
            notify(f"⚠️ 카드뉴스 발행 실패: {msg}")
            sys.exit(f"발행 실패: {msg}")
    else:
        sys.exit("발행 실패: 대기 시간 초과")

    link = post(f"{GRAPH}/{media_id}?fields=permalink&access_token={tok}", {}) or {}
    permalink = link.get("permalink", "")
    print(f"\n✅ 발행 완료  {media_id}  {permalink}")
    notify(f"✅ 카드뉴스 발행 완료 ({len(slides)}장)\n{permalink}")

    # 5. R2 정리 — Meta가 이미 이미지를 저장했으므로 원본 URL은 불필요
    if not a.keep:
        for key in keys:
            r2.request("DELETE", key)
        print(f"R2 객체 {len(keys)}개 정리 완료")


if __name__ == "__main__":
    main()
