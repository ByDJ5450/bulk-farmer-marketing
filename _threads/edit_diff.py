#!/usr/bin/env python3
"""발행된 스레드 글 ↔ 초안 대조 — 코치가 손으로 고친 곳을 뽑아낸다.

코치는 발행 후 글을 직접 고친다. 그 수정이 곧 다음 초안의 규칙이다.
2026-08-11에 처음 전수 대조했더니 11건이 고쳐져 있었고, 거기서
"해시태그를 쓰지 않는다"(예외 0건)와 "비유 대신 실제 지표 이름"이 나왔다.
그때까지 아무도 안 보고 있었다. 그래서 매일 자동으로 본다.

  /usr/bin/python3 _threads/edit_diff.py          새로 발견된 수정만
  /usr/bin/python3 _threads/edit_diff.py --all    이미 본 것까지 전부

새로 발견된 건 한 번 보고한 뒤 기록해두고 다음부터는 조용하다.
토큰 값은 어떤 출력에도 찍지 않는다.
"""
import difflib, glob, json, os, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEEN = Path.home() / "Library/Application Support/bulkfarmer/seen_edits.json"


def env(path):
    out = {}
    p = Path(path).expanduser()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def live_posts(limit=50):
    m = env("~/.config/bulkfarmer/meta.env")
    tok = m.get("THREADS_ACCESS_TOKEN") or m.get("THREADS_TOKEN")
    uid = m.get("THREADS_USER_ID")
    if not tok or not uid:
        print("meta.env에 THREADS 자격증명 없음", file=sys.stderr)
        return {}
    url = (f"https://graph.threads.net/v1.0/{uid}/threads"
           f"?fields=id,text&limit={limit}&access_token={tok}")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Threads 조회 실패 HTTP {e.code}", file=sys.stderr)   # 본문에 토큰이 실릴 수 있어 코드만 찍는다
        return {}
    except Exception as e:
        print(f"Threads 조회 실패: {type(e).__name__}", file=sys.stderr)
        return {}
    return {p["id"]: (p.get("text") or "") for p in data.get("data", [])}


def main():
    show_all = "--all" in sys.argv
    live = live_posts()
    if not live:
        return 0

    seen = set()
    if SEEN.exists() and not show_all:
        try:
            seen = set(json.loads(SEEN.read_text(encoding="utf-8")))
        except Exception:
            seen = set()

    found, checked = [], 0
    for f in sorted(glob.glob(str(ROOT / "pending" / "*.json"))):
        try:
            doc = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for dr in doc.get("drafts", []):
            pid = str(dr.get("post_id") or "")
            if pid not in live:
                continue
            checked += 1
            if live[pid].strip() == dr["text"].strip():
                continue
            if pid in seen:
                continue
            found.append((Path(f).stem, dr["index"], pid, dr["text"], live[pid]))

    print(f"발행본 대조 {checked}건 · 새로 발견된 수정 {len(found)}건")
    for day, idx, pid, before, after in found:
        print(f"\n■ {day} #{idx}")
        for line in difflib.unified_diff(before.split("\n"), after.split("\n"),
                                         lineterm="", n=1):
            if line.startswith(("---", "+++", "@@")):
                continue
            print("  " + line)

    if found:
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(json.dumps(sorted(seen | {p for _, _, p, _, _ in found})),
                        encoding="utf-8")
    return len(found)


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
