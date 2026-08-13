#!/usr/bin/env python3
"""제보방 수집 — 사용자 계정(Telethon)으로 제보방 대화·파일을 긁어온다.

봇 API는 지난 대화를 못 읽고 20MB 넘는 파일을 못 받는다 (2026-08-13 유실 사고).
그래서 이 스크립트는 봇이 아니라 **사용자 계정**으로 접속한다.

  로그인(최초 1회)   python3 report_inbox.py login
  최근 수집          python3 report_inbox.py pull [--days 30]

- 자격증명: ~/.config/bulkfarmer/telethon.env (API_ID, API_HASH, PHONE)
- 세션:     ~/.config/bulkfarmer/telethon.session — 계정 전체 권한이므로 저장소 밖, 600
- 대상 방:  telegram.env 의 TELEGRAM_REPORT_CHAT_ID 하나만 읽는다. 다른 방은 안 건드린다
- 내려받은 파일: _org/inbox/{날짜}_{메시지id}_{파일명}  (검토 후 벤치마킹에 사용)
- 목록: _org/inbox/inbox.md 에 시간·발신·텍스트·파일 경로를 추가한다
"""
import asyncio, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONF = Path.home() / ".config" / "bulkfarmer"
ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "_org" / "inbox"


def load_env(name):
    env = {}
    p = CONF / name
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def client():
    from telethon import TelegramClient
    t = load_env("telethon.env")
    for k in ("API_ID", "API_HASH", "PHONE"):
        if not t.get(k):
            sys.exit(f"~/.config/bulkfarmer/telethon.env 에 {k}= 가 필요합니다")
    session = str(CONF / "telethon")
    return TelegramClient(session, int(t["API_ID"]), t["API_HASH"]), t["PHONE"]


async def do_login():
    c, phone = client()
    await c.start(phone=phone)   # 코드 입력을 stdin으로 물어본다
    me = await c.get_me()
    print(f"로그인 완료: {me.first_name} (@{me.username})")
    os.chmod(str(CONF / "telethon.session"), 0o600)
    await c.disconnect()


async def do_pull(days):
    c, phone = client()
    await c.start(phone=phone)
    chat_id = int(load_env("telegram.env")["TELEGRAM_REPORT_CHAT_ID"])
    entity = await c.get_entity(chat_id)
    INBOX.mkdir(parents=True, exist_ok=True)
    log = INBOX / "inbox.md"
    seen = log.read_text(encoding="utf-8") if log.exists() else ""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    new = []
    async for m in c.iter_messages(entity, offset_date=None, limit=200):
        if m.date < since:
            break
        key = f"msg:{m.id}"
        if key in seen:
            continue
        row = [f"## {key} — {m.date.astimezone().strftime('%F %H:%M')}"]
        if m.text:
            row.append(m.text)
        if m.media:
            fname = f"{m.date.astimezone():%m%d}_{m.id}"
            path = await c.download_media(m, file=str(INBOX / fname))
            if path:
                row.append(f"파일: {Path(path).name}")
                print("내려받음:", path)
        new.append("\n".join(row) + "\n")

    if new:
        with log.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(reversed(new)) + "\n")
        print(f"신규 {len(new)}건 → {log}")
    else:
        print("신규 제보 없음")
    await c.disconnect()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pull"
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 30
    asyncio.run(do_login() if cmd == "login" else do_pull(days))
