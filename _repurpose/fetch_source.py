#!/usr/bin/env python3
"""유튜브 롱폼 → 리퍼포징 원천 소재 수집.

  /usr/bin/python3 fetch_source.py <영상ID> [영상ID ...]
  /usr/bin/python3 fetch_source.py --channel        채널 전체 롱폼

영상마다 `_repurpose/source/{id}/` 에 아래를 만든다.
  meta.json       제목·길이·조회수·업로드일
  transcript.txt  자막 전문 (타임코드 포함)
  numbers.txt     본문에서 자동 추출한 수치 — 카드뉴스·블로그의 뼈대가 된다

영상 파일은 받지 않는다. 용량이 크고, 프레임이 필요한 시점에
`extract_frames.py` 로 그때 받는 편이 낫다.

주의: `--flat-playlist`를 쓰지 않는다. 조회수가 NA로 나오고 제목이
자동 번역본으로 바뀌어 같은 영상이 별개로 보인다.
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "source"
CHANNEL = "https://www.youtube.com/@bulk_farmer/videos"

# 벌크업 콘텐츠에서 의미 있는 수치 — 체중·둘레·중량·기간·비율
NUM = re.compile(
    r"[^.?!\n]*?\d+(?:\.\d+)?\s*(?:kg|킬로|cm|센치|센티|%|퍼센트|주|개월|달|년|세|회|세트|개)[^.?!\n]*")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def vtt_to_text(vtt):
    """VTT → 타임코드 + 대사. 자동자막 특유의 중복 줄을 걷어낸다."""
    out, last = [], None
    stamp = None
    for line in vtt.splitlines():
        line = line.strip()
        if "-->" in line:
            stamp = line.split("-->")[0].strip().split(".")[0]
            continue
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        text = re.sub(r"<[^>]+>", "", line).strip()
        if not text or text == last:
            continue
        last = text
        out.append(f"[{stamp}] {text}" if stamp else text)
    return "\n".join(out)


def fetch(vid):
    d = SRC / vid
    d.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={vid}"

    r = run(["yt-dlp", "-j", "--no-warnings", "--socket-timeout", "30", url])
    if r.returncode != 0:
        print(f"  ✗ {vid}  메타데이터 실패: {r.stderr.strip()[:120]}")
        return False
    m = json.loads(r.stdout)
    meta = {k: m.get(k) for k in
            ("id", "title", "duration", "view_count", "like_count", "upload_date", "description")}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    r = run(["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
             "--sub-langs", "ko", "--sub-format", "vtt", "--socket-timeout", "30",
             "-o", str(d / "sub"), url])
    vtts = list(d.glob("sub*.vtt"))
    if not vtts:
        print(f"  ⚠ {vid}  자막 없음 — {meta['title'][:40]}")
        return False

    text = vtt_to_text(vtts[0].read_text(encoding="utf-8"))
    (d / "transcript.txt").write_text(text, encoding="utf-8")
    for v in vtts:
        v.unlink()

    bare = re.sub(r"\[\d+:\d+:\d+\] ", "", text)
    hits = []
    for s in NUM.findall(bare):
        s = s.strip()
        if 6 <= len(s) <= 90 and s not in hits:
            hits.append(s)
    (d / "numbers.txt").write_text("\n".join(hits), encoding="utf-8")

    mm, ss = divmod(meta["duration"], 60)
    print(f"  ✓ {vid}  {mm:>2}:{ss:02d}  자막 {len(text):>6,}자  수치 {len(hits):>3}개  {meta['title'][:34]}")
    return True


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    if args[0] == "--channel":
        r = run(["yt-dlp", "-j", "--no-warnings", "--ignore-errors",
                 "--socket-timeout", "30", CHANNEL])
        ids = [json.loads(l)["id"] for l in r.stdout.splitlines() if l.strip()]
        print(f"채널 롱폼 {len(ids)}개")
    else:
        ids = args

    ok = sum(fetch(v) for v in ids)
    print(f"\n{ok}/{len(ids)}개 수집 완료 → {SRC}")


if __name__ == "__main__":
    main()
