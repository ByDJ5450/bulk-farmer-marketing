#!/usr/bin/env python3
"""텔레그램으로 받은 지시를 claude에게 넘기고 결과를 회신한다.

  /usr/bin/python3 run_command.py <작업파일.json>

`approve_worker.py`가 텍스트 메시지를 받으면 작업 파일을 쓰고 이 스크립트를
**분리된 프로세스로** 띄운다. claude 실행은 몇 분씩 걸리는데, 60초마다 도는
워커를 그동안 붙잡아 두면 승인 버튼이 먹통이 된다.

한 번에 하나만 실행한다. 동시에 두 개가 같은 파일을 고치면 결과를 예측할 수 없다.
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
QUEUE = ROOT / "queue"
LOCK = ROOT / ".running"
LOG = ROOT / "commands.log"
TIMEOUT = 900          # 15분
MAX_MSG = 3800         # 텔레그램 4096자 제한 여유분
STALE_LOCK = 1800      # 30분 넘은 잠금은 죽은 프로세스로 본다


def env(p):
    d = {}
    p = Path(p).expanduser()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


TG = env("~/.config/bulkfarmer/telegram.env")


def send(text, chat_id=None):
    """4096자 제한 때문에 길면 나눠 보낸다."""
    cid = chat_id or TG.get("TELEGRAM_CHAT_ID")
    for i in range(0, len(text) or 1, MAX_MSG):
        chunk = text[i:i + MAX_MSG] or "(빈 응답)"
        body = urllib.parse.urlencode({"chat_id": cid, "text": chunk}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"https://api.telegram.org/bot{TG['TELEGRAM_BOT_TOKEN']}/sendMessage",
                data=body), timeout=30)
        except Exception as e:
            print(f"전송 실패: {e}", file=sys.stderr)


# 텔레그램에서 온 지시라는 맥락과, 넘지 말아야 할 선을 함께 준다.
GUARD = """[텔레그램에서 온 지시다]

- 대화 상대는 지금 폰을 보고 있다. 답은 **짧게**. 코드 블록을 길게 쏟지 않는다.
- **발행하지 않는다.** 카드뉴스·스레드는 만들고 나서 `send_for_approval.py` 로
  승인 요청까지만 보낸다. 실제 발행은 사용자가 버튼을 누를 때 일어난다.
- `git push` 하지 않는다. 커밋까지만 한다.
- 확인 질문을 던지고 끝내지 않는다. 물어볼 상대가 있지만 왕복이 느리다.
  애매하면 가장 합리적인 쪽으로 정하고, 무엇을 가정했는지 답에 한 줄로 적는다.
- 결과물을 만들었으면 **파일 경로**를 답에 포함한다.

지시:
"""


def claude(prompt, cont):
    cmd = ["claude", "-p", GUARD + prompt,
           "--permission-mode", "acceptEdits",
           "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch"]
    if cont:
        cmd.insert(1, "--continue")
    r = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=TIMEOUT)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    task_file = Path(sys.argv[1])
    if not task_file.exists():
        sys.exit(f"작업 파일 없음: {task_file}")
    task = json.loads(task_file.read_text(encoding="utf-8"))
    text, cid = task["text"], task.get("chat_id")

    # 죽은 잠금 청소 — 프로세스가 중간에 죽으면 파일이 남는다
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime > STALE_LOCK:
        LOCK.unlink()
    if LOCK.exists():
        send("⏳ 앞선 작업이 아직 돌고 있습니다. 끝나면 이어서 처리하겠습니다.", cid)
        return
    LOCK.write_text(text[:200], encoding="utf-8")

    started = datetime.now()
    try:
        # "새 대화" 로 시작하면 이전 맥락을 끊는다. 계속 이어붙이면 컨텍스트가 무한정 커진다.
        fresh = text.strip().startswith(("새 대화", "새대화"))
        if fresh:
            text = text.split(maxsplit=2)[-1] if len(text.split()) > 2 else text
        rc, out, err = claude(text, cont=not fresh)
        took = (datetime.now() - started).seconds
        if rc == 0 and out:
            send(f"{out}\n\n— {took}초", cid)
        else:
            send(f"❌ 실패 (종료 코드 {rc}, {took}초)\n{(err or out)[-1500:]}", cid)
    except subprocess.TimeoutExpired:
        send(f"❌ {TIMEOUT // 60}분을 넘겨 중단했습니다.\n요청을 더 작게 쪼개주세요.", cid)
    except Exception as e:
        send(f"❌ 오류: {e}", cid)
    finally:
        LOCK.unlink(missing_ok=True)
        task_file.unlink(missing_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{started:%Y-%m-%d %H:%M}\t{text[:120]}\n")


if __name__ == "__main__":
    main()
