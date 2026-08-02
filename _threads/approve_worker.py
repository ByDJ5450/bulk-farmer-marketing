#!/usr/bin/env python3
"""텔레그램 승인 → 스레드 발행 워커.

launchd가 5분마다 실행한다. 사용자가 직접 실행할 일은 없다.
  · 텔레그램 콜백(승인/버림)을 폴링해서 처리
  · 승인된 초안만 Threads API로 발행
  · 결과를 텔레그램으로 회신하고 발행 이력에 기록

토큰 값은 어떤 출력·로그에도 찍지 않는다.
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PENDING = ROOT / "pending"
STATE = ROOT / "state.json"
LOG = ROOT / "published.md"

# 승인 버튼을 연달아 누르면 글이 한 뭉텅이로 나간다. 스레드는 그걸 싫어하고,
# 무엇보다 타임라인에서 서로를 잡아먹는다. 그래서 승인은 "예약"이고, 실제 발행은
# 이 간격을 두고 워커가 한 건씩 내보낸다. (워커는 5분마다 돈다)
PUBLISH_GAP = timedelta(minutes=100)
WINDOW = (8, 23)   # 이 시간대에만 발행한다 (로컬 시각)


def load_env(path):
    env = {}
    p = Path(path).expanduser()
    if not p.exists():
        return env
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


TG = load_env("~/.config/bulkfarmer/telegram.env")
META = load_env("~/.config/bulkfarmer/meta.env")


def api(url, data=None, timeout=30):
    """POST(data 있을 때) 또는 GET. 실패 시 {'error': ...} 반환."""
    try:
        if data is not None:
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": {"message": f"HTTP {e.code}"}}
    except Exception as e:
        return {"error": {"message": str(e)}}


def tg(method, **params):
    return api(f"https://api.telegram.org/bot{TG.get('TELEGRAM_BOT_TOKEN','')}/{method}", params)


def notify(text):
    tg("sendMessage", chat_id=TG.get("TELEGRAM_CHAT_ID"), text=text)


def publish(text):
    """Threads 2단계 발행. (성공여부, 결과) 반환."""
    uid, tok = META.get("THREADS_USER_ID"), META.get("THREADS_TOKEN")
    if not uid or not tok:
        return False, "meta.env에 THREADS_USER_ID / THREADS_TOKEN 없음"

    r = api(f"https://graph.threads.net/v1.0/{uid}/threads",
            {"media_type": "TEXT", "text": text, "access_token": tok})
    if "error" in r or "id" not in r:
        return False, f"컨테이너 생성 실패: {r.get('error', {}).get('message', r)}"
    cid = r["id"]

    # 컨테이너가 처리될 시간을 준다 (텍스트는 보통 즉시)
    for attempt in range(3):
        time.sleep(2 if attempt == 0 else 5)
        p = api(f"https://graph.threads.net/v1.0/{uid}/threads_publish",
                {"creation_id": cid, "access_token": tok})
        if "id" in p:
            return True, p["id"]
        msg = p.get("error", {}).get("message", "")
        if "not ready" not in msg.lower() and attempt == 2:
            return False, f"발행 실패: {msg}"
    return False, "발행 실패: 컨테이너 준비 시간 초과"


CARDNEWS = ROOT.parent / "_cardnews"
BLOG = ROOT.parent / "_blog"


def handle_blog(action, slug, cq, cid, mid):
    """네이버 블로그 승인/버림. 발행은 publish_post.py 에 위임한다."""
    import subprocess
    rec = BLOG / "pending" / f"{slug}.json"
    if not rec.exists():
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="글을 찾을 수 없습니다")
        return
    doc = json.loads(rec.read_text(encoding="utf-8"))
    if doc.get("status") != "pending":
        tg("answerCallbackQuery", callback_query_id=cq["id"], text=f"이미 처리됨 ({doc['status']})")
        return

    if action == "nvdel":
        doc["status"] = "discarded"
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="버렸습니다")
        tg("editMessageText", chat_id=cid, message_id=mid, text=f"🗑 블로그 글 버림 — {slug}")
    else:
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="발행 중…")
        tg("editMessageText", chat_id=cid, message_id=mid, text=f"⏳ 블로그 발행 중 — {slug}")
        cmd = ["/usr/bin/python3", str(BLOG / "publish_post.py"), doc["post_dir"],
               "--publish", "--open", doc.get("open_type", "closed")]
        if doc.get("category"):
            cmd += ["--category", str(doc["category"])]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            doc["status"] = "published"
            link = next((w for w in out.split() if w.startswith("https://blog.naver.com")), "")
            tg("editMessageText", chat_id=cid, message_id=mid,
               text=f"✅ 블로그 발행 완료 — {slug}\n{link}")
        else:
            doc["status"] = "failed"
            doc["error"] = out[-500:]
            tg("editMessageText", chat_id=cid, message_id=mid,
               text=f"❌ 블로그 발행 실패 — {slug}\n{out[-500:]}")

    rec.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def handle_cardnews(action, slug, cq, cid, mid):
    """카드뉴스 승인/버림. 발행은 publish_carousel.py 에 위임한다."""
    import subprocess
    rec = CARDNEWS / "pending" / f"{slug}.json"
    if not rec.exists():
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="세트를 찾을 수 없습니다")
        return
    doc = json.loads(rec.read_text(encoding="utf-8"))
    if doc.get("status") != "pending":
        tg("answerCallbackQuery", callback_query_id=cq["id"], text=f"이미 처리됨 ({doc['status']})")
        return

    if action == "igdel":
        doc["status"] = "discarded"
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="버렸습니다")
        tg("editMessageText", chat_id=cid, message_id=mid, text=f"🗑 카드뉴스 버림 — {slug}")
    else:
        tg("answerCallbackQuery", callback_query_id=cq["id"], text="발행 중… 1~2분 걸립니다")
        tg("editMessageText", chat_id=cid, message_id=mid, text=f"⏳ 카드뉴스 발행 중 — {slug}")
        r = subprocess.run(
            ["/usr/bin/python3", str(CARDNEWS / "publish_carousel.py"),
             doc["slide_dir"], "--caption", doc["caption_file"], "--publish"],
            capture_output=True, text=True, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            doc["status"] = "published"
            link = next((w for w in out.split() if w.startswith("https://www.instagram.com")), "")
            tg("editMessageText", chat_id=cid, message_id=mid,
               text=f"✅ 카드뉴스 발행 완료 — {slug}\n{link}")
        else:
            doc["status"] = "failed"
            doc["error"] = out[-500:]
            tg("editMessageText", chat_id=cid, message_id=mid,
               text=f"❌ 카드뉴스 발행 실패 — {slug}\n{out[-500:]}")

    rec.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def approved_queue():
    """승인됐지만 아직 안 나간 초안들. (파일, 문서, 초안) 오래된 순."""
    out = []
    for f in sorted(PENDING.glob("*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for d in doc.get("drafts", []):
            if d.get("status") == "approved":
                out.append((f, doc, d))
    return out


def next_slot(st, position):
    """position번째(0-base) 대기 건이 나갈 예상 시각."""
    last = st.get("last_publish_at")
    base = datetime.fromisoformat(last) + PUBLISH_GAP if last else datetime.now()
    t = max(base, datetime.now()) + PUBLISH_GAP * position
    if t.hour >= WINDOW[1]:
        t = t.replace(hour=WINDOW[0], minute=0, second=0) + timedelta(days=1)
    elif t.hour < WINDOW[0]:
        t = t.replace(hour=WINDOW[0], minute=0, second=0)
    return t


def drain_queue(st):
    """예약된 초안 중 한 건을 발행한다. 간격·시간대 조건을 만족할 때만."""
    now = datetime.now()
    if not (WINDOW[0] <= now.hour < WINDOW[1]):
        return
    last = st.get("last_publish_at")
    if last and now - datetime.fromisoformat(last) < PUBLISH_GAP:
        return

    q = approved_queue()
    if not q:
        return
    f, doc, draft = q[0]

    ok, res = publish(draft["text"])
    cid, mid = draft.get("msg_chat_id"), draft.get("msg_id")
    if ok:
        draft["status"] = "published"
        draft["post_id"] = res
        draft["published_at"] = now.isoformat(timespec="minutes")
        record(draft, res)
        st["last_publish_at"] = now.isoformat()
        text = f"✅ 발행 완료 {now:%H:%M}\n\n{draft['text']}"
    else:
        draft["status"] = "failed"
        draft["error"] = res
        text = f"❌ 발행 실패\n{res}\n\n{draft['text']}"

    if cid and mid:
        tg("editMessageText", chat_id=cid, message_id=mid, text=text)
    elif not ok:
        notify(text)

    f.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def find_draft(day, idx):
    f = PENDING / f"{day}.json"
    if not f.exists():
        return None, None, None
    data = json.loads(f.read_text(encoding="utf-8"))
    for d in data.get("drafts", []):
        if d.get("index") == idx:
            return f, data, d
    return f, data, None


def record(draft, post_id):
    """발행 이력 파일에 한 줄 추가."""
    header = "" if LOG.exists() else "# 스레드 발행 이력 (자동 기록)\n\n| 발행일 | 유형 | 주제 | 소재 요약 | 게시물 ID |\n|---|---|---|---|---|\n"
    row = (f"| {date.today()} | {draft.get('type','-')} | {draft.get('topic','-')} | "
           f"{draft.get('summary','-')} | {post_id} |\n")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(header + row)


def main():
    if not TG.get("TELEGRAM_BOT_TOKEN"):
        sys.exit("telegram.env 없음")

    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    offset = st.get("last_update_id", 0) + 1

    upd = tg("getUpdates", offset=offset, timeout=0, allowed_updates=json.dumps(["callback_query"]))
    if not upd.get("ok"):
        sys.exit(f"getUpdates 실패: {upd}")

    results = upd.get("result", [])
    if not results:
        drain_queue(st)   # 새 버튼이 없어도 예약분은 계속 내보내야 한다
        return

    last = st.get("last_update_id", 0)
    for u in results:
        last = max(last, u["update_id"])
        cq = u.get("callback_query")
        if not cq:
            continue

        data = cq.get("data", "")
        cid = cq["message"]["chat"]["id"]
        mid = cq["message"]["message_id"]
        parts = data.split(":")

        if parts[0] in ("igpub", "igdel") and len(parts) == 2:
            handle_cardnews(parts[0], parts[1], cq, cid, mid)
            continue

        if parts[0] in ("nvpub", "nvdel") and len(parts) == 2:
            handle_blog(parts[0], parts[1], cq, cid, mid)
            continue

        if len(parts) != 3:
            tg("answerCallbackQuery", callback_query_id=cq["id"], text="알 수 없는 요청")
            continue

        action, day, idx = parts[0], parts[1], int(parts[2])

        f, doc, draft = find_draft(day, idx)
        if draft is None:
            tg("answerCallbackQuery", callback_query_id=cq["id"], text="초안을 찾을 수 없습니다")
            continue

        if draft.get("status") != "pending":
            tg("answerCallbackQuery", callback_query_id=cq["id"],
               text=f"이미 처리됨 ({draft.get('status')})")
            continue

        if action == "del":
            draft["status"] = "discarded"
            tg("answerCallbackQuery", callback_query_id=cq["id"], text="버렸습니다")
            tg("editMessageText", chat_id=cid, message_id=mid,
               text=f"🗑 버림 ({idx}/{doc.get('total','?')})\n\n{draft['text']}")

        elif action == "pub":
            # 즉시 발행하지 않는다. 큐에 넣고 워커가 간격을 두고 내보낸다.
            draft["status"] = "approved"
            draft["msg_chat_id"], draft["msg_id"] = cid, mid
            eta = next_slot(st, len(approved_queue()))
            tg("answerCallbackQuery", callback_query_id=cq["id"],
               text=f"예약 완료 — {eta:%H:%M} 발행 예정")
            tg("editMessageText", chat_id=cid, message_id=mid,
               text=f"🕒 발행 예약 {eta:%m/%d %H:%M} ({idx}/{doc.get('total','?')})\n\n{draft['text']}")
        else:
            tg("answerCallbackQuery", callback_query_id=cq["id"], text="알 수 없는 동작")
            continue

        f.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    st["last_update_id"] = last
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    drain_queue(st)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify(f"⚠️ 스레드 승인 워커 오류: {e}")
        raise
