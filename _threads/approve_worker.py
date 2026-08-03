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


IMAGES = ROOT / "images"


def host_image(path):
    """R2에 올려 공개 URL을 돌려준다. (URL, 삭제용 키) 또는 (None, 오류)."""
    import re as _re
    sys.path.insert(0, str(ROOT.parent / "_cardnews"))
    import r2_upload as r2

    p = Path(path)
    if not p.is_absolute():
        p = IMAGES / p
    if not p.exists():
        return None, f"이미지 없음: {p}"
    # 키는 ASCII로 유지한다. 한글 경로는 인코딩 사고를 부른다.
    slug = _re.sub(r"[^A-Za-z0-9._-]+", "-", p.name).strip("-") or "img.jpg"
    key = f"threads/{date.today()}-{slug}"
    code, err = r2.request("PUT", key, p.read_bytes(), "image/jpeg")
    if code != 200:
        return None, f"R2 업로드 실패 {code}: {err}"
    base = (r2.cfg().get("R2_PUBLIC_URL", "") or "").rstrip("/")
    return f"{base}/{urllib.parse.quote(key, safe='/')}", key


def drop_image(key):
    """발행 후 정리. Meta가 이미지를 가져가 저장하므로 원본은 필요 없다."""
    try:
        sys.path.insert(0, str(ROOT.parent / "_cardnews"))
        import r2_upload as r2
        r2.request("DELETE", key)
    except Exception:
        pass


def publish(text, image=None):
    """Threads 2단계 발행. image가 있으면 IMAGE 게시물. (성공여부, 결과) 반환."""
    uid, tok = META.get("THREADS_USER_ID"), META.get("THREADS_TOKEN")
    if not uid or not tok:
        return False, "meta.env에 THREADS_USER_ID / THREADS_TOKEN 없음"

    body = {"media_type": "TEXT", "text": text, "access_token": tok}
    key = None
    if image:
        url, key = host_image(image)
        if not url:
            # 이미지 때문에 글 자체를 못 내보내는 건 손해다. 텍스트로라도 낸다.
            notify(f"⚠️ 스레드 이미지 첨부 실패 — 텍스트만 발행합니다\n{key}")
            key = None
        else:
            body = {"media_type": "IMAGE", "image_url": url, "text": text, "access_token": tok}

    r = api(f"https://graph.threads.net/v1.0/{uid}/threads", body)
    if "error" in r or "id" not in r:
        if key:
            drop_image(key)
        return False, f"컨테이너 생성 실패: {r.get('error', {}).get('message', r)}"
    cid = r["id"]

    # 컨테이너가 처리될 시간을 준다. 이미지는 Meta가 받아 가는 시간이 더 걸린다.
    for attempt in range(6 if key else 3):
        time.sleep(2 if attempt == 0 else 5)
        p = api(f"https://graph.threads.net/v1.0/{uid}/threads_publish",
                {"creation_id": cid, "access_token": tok})
        if "id" in p:
            if key:
                drop_image(key)
            return True, p["id"]
        msg = p.get("error", {}).get("message", "")
        if "not ready" not in msg.lower() and attempt >= 2:
            if key:
                drop_image(key)
            return False, f"발행 실패: {msg}"
    if key:
        drop_image(key)
    return False, "발행 실패: 컨테이너 준비 시간 초과"


def permalink(post_id):
    """발행된 스레드 글의 공개 주소. 실패해도 발행 자체는 성공이므로 빈 문자열."""
    tok = META.get("THREADS_TOKEN")
    if not tok:
        return ""
    r = api(f"https://graph.threads.net/v1.0/{post_id}?fields=permalink&access_token={tok}")
    return r.get("permalink", "")


def queue_status():
    """지금 예약 상태를 사람이 읽을 수 있는 한 덩어리로."""
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    q = approved_queue()
    today = date.today().isoformat()

    done = []
    for f in sorted(PENDING.glob("*.json")):
        for d in json.loads(f.read_text(encoding="utf-8")).get("drafts", []):
            if d.get("status") == "published" and str(d.get("published_at", "")).startswith(today):
                done.append(d)

    lines = [f"📋 스레드 현황  {date.today():%m/%d}"]
    lines.append(f"오늘 발행 {len(done)}개 · 예약 대기 {len(q)}개")

    if done:
        lines.append("\n[발행 완료]")
        for d in done:
            t = str(d.get("published_at", ""))[11:16]
            lines.append(f"  ✅ {t}  {d.get('summary', '')[:34]}")
    if q:
        lines.append("\n[예약]")
        for i, (_, _, d) in enumerate(q):
            lines.append(f"  🕒 {next_slot(st, i):%m/%d %H:%M}  {d.get('summary', '')[:34]}")

    pend = sum(1 for f in PENDING.glob("*.json")
               for d in json.loads(f.read_text(encoding="utf-8")).get("drafts", [])
               if d.get("status") == "pending")
    if pend:
        lines.append(f"\n미승인 초안 {pend}개가 남아 있습니다.")
    return "\n".join(lines)


CARDNEWS = ROOT.parent / "_cardnews"

# 네이버 블로그는 승인 버튼이 없다. 글쓰기 API가 2020-05-06 종료돼 자동 발행이
# 불가능하고, 붙여넣기로만 올릴 수 있다. `_blog/to_clipboard.py` 참조.


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

    ok, res = publish(draft["text"], draft.get("image"))
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

    f.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")

    # 원본 메시지를 고치는 것만으로는 알 수가 없다. 그 메시지는 채팅 위로 올라가 있다.
    # 발행될 때마다 **새 알림**을 보낸다. 다음 예약 시각까지 같이 알려서
    # 폰만 보고도 오늘 일정이 파악되게 한다.
    if ok:
        rest = approved_queue()
        line = [f"✅ 스레드 발행 완료  {now:%H:%M}", "", draft.get("summary", "")[:60]]
        link = permalink(res)
        if link:
            line.append(link)
        if rest:
            line += ["", f"다음 예약  {next_slot(st, 0):%m/%d %H:%M}  (대기 {len(rest)}개)"]
        else:
            line += ["", "예약 대기 없음"]
        notify("\n".join(line))
    else:
        notify(f"❌ 스레드 발행 실패\n{res}\n\n{draft.get('summary','')[:60]}")


TELEGRAM = ROOT.parent / "_telegram"

HELP = """🤖 텔레그램 명령

현황        오늘 발행·예약 상태
도움말      이 안내

그 밖의 문장은 전부 작업 지시로 처리한다.
예) 재현님 소재로 카드뉴스 만들어줘
   블로그 글 하나 써서 클립보드에 올려줘
   이번 주 발행량 정리해줘

- 답까지 몇 분 걸린다. 다 되면 알림이 온다
- **발행은 하지 않는다.** 만들고 승인 요청까지만 온다
- 앞 대화를 이어서 문맥을 기억한다.
  끊고 싶으면 앞에 "새 대화" 를 붙인다
- 맥이 꺼져 있으면 켤 때 처리된다"""


def handle_message(msg):
    """텔레그램 텍스트 처리. 짧은 건 즉답, 나머지는 claude에게 넘긴다."""
    cid = msg["chat"]["id"]
    text = str(msg.get("text", "")).strip()

    # 이 봇은 저장소 전체에 쓰기 권한이 있는 실행 통로다.
    # 등록된 chat_id 외에는 무엇도 실행하지 않는다.
    if str(cid) != str(TG.get("TELEGRAM_CHAT_ID")):
        return

    if text in ("현황", "상태", "/status"):
        tg("sendMessage", chat_id=cid, text=queue_status())
        return
    if text in ("도움말", "help", "/help", "/start"):
        tg("sendMessage", chat_id=cid, text=HELP)
        return

    # 오래 걸리는 작업이다. 여기서 기다리면 60초 워커가 막혀 승인 버튼이 먹통이 된다.
    # 작업 파일을 남기고 분리된 프로세스로 띄운 뒤 즉시 빠져나간다.
    import subprocess
    q = TELEGRAM / "queue"
    q.mkdir(parents=True, exist_ok=True)
    f = q / f"{msg['message_id']}.json"
    f.write_text(json.dumps({"text": text, "chat_id": cid}, ensure_ascii=False), encoding="utf-8")

    tg("sendMessage", chat_id=cid, text=f"🤖 작업 시작합니다\n\n{text[:200]}")
    subprocess.Popen(
        ["/usr/bin/python3", str(TELEGRAM / "run_command.py"), str(f)],
        cwd=str(ROOT.parent), start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def daily_wrapup(st):
    """발행 창이 닫히는 23시 이후 하루 한 번, 그날 결과를 정리해 보낸다."""
    now = datetime.now()
    today = date.today().isoformat()
    if now.hour < WINDOW[1] or st.get("wrapup_date") == today:
        return
    st["wrapup_date"] = today
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")

    published = missed = 0
    for f in PENDING.glob("*.json"):
        for d in json.loads(f.read_text(encoding="utf-8")).get("drafts", []):
            if d.get("status") == "published" and str(d.get("published_at", "")).startswith(today):
                published += 1
            elif d.get("status") == "approved":
                missed += 1

    line = [f"🌙 오늘 스레드 {published}개 발행 완료"]
    if missed:
        line.append(f"승인해두신 {missed}개는 시간이 모자라 내일 아침 8시부터 나갑니다.")
    if published < 3:
        line.append("목표는 하루 3~5개입니다. 내일은 초안을 조금 더 승인해주세요.")
    notify("\n".join(line))


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

    upd = tg("getUpdates", offset=offset, timeout=0,
             allowed_updates=json.dumps(["callback_query", "message"]))
    if not upd.get("ok"):
        sys.exit(f"getUpdates 실패: {upd}")

    results = upd.get("result", [])
    if not results:
        drain_queue(st)   # 새 버튼이 없어도 예약분은 계속 내보내야 한다
        daily_wrapup(st)
        return

    last = st.get("last_update_id", 0)
    for u in results:
        last = max(last, u["update_id"])

        msg = u.get("message")
        if msg and str(msg.get("text", "")).strip():
            handle_message(msg)
            continue

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
    daily_wrapup(st)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notify(f"⚠️ 스레드 승인 워커 오류: {e}")
        raise
