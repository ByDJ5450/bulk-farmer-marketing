# 맥이 꺼져 있어도 돌리기 — 오라클 클라우드

## 무엇을 옮기고 무엇을 안 옮기는가

| 작업 | 옮기나 | 이유 |
|------|--------|------|
| **승인 워커** (버튼 → 발행·예약) | ✅ **1단계** | 이것만이 진짜 24시간이 필요하다. Claude를 안 쓰므로 **API 비용 0** |
| 초안 생성 (매일 08:13) | ⏸ 나중 | 맥 켜면 밀린 것 실행됨. 옮기면 API 과금 시작 |
| 주간 리포트 (월 09:07) | ⏸ 나중 | 하루 늦어도 문제없다 |
| 텔레그램 명령 처리 | ⏸ 나중 | `claude` CLI 필요 → API 키 필요 |
| 네이버 블로그 붙여넣기 | ❌ 불가 | macOS 클립보드에 의존. 사람이 하는 작업 |
| 카드뉴스 제작 | ❌ 불필요 | 어차피 눈으로 검토한다 |

**1단계만 해도 체감이 크게 달라진다.** 버튼이 항상 먹고, 예약해둔 글이 밤에도 나간다.

---

## 1단계 — 승인 워커를 오라클로

### 준비물

1. **오라클 클라우드 계정** — Always Free 티어
   Ampere A1 (ARM) 4 OCPU / 24GB / 200GB. 영구 무료. 이 작업엔 과하게 넉넉하다.
   Ubuntu 22.04 또는 24.04로 인스턴스 생성.
2. **GitHub PAT** — [github.com/settings/tokens](https://github.com/settings/tokens) 에서 `repo` 권한
   코드를 서버로 보내려면 필요하다. 지금 로컬에만 커밋이 쌓여 있다.

### 서버에서

```bash
sudo apt update && sudo apt install -y python3 python3-pip git
pip3 install --user Pillow          # sips 대체. 카드뉴스 JPEG 변환에 쓴다

git clone https://github.com/ByDJ5450/bulk-farmer-marketing.git ~/bulkfarmer
```

### 자격증명 복사 (맥에서 실행)

```bash
ssh ubuntu@<서버IP> "mkdir -p ~/.config/bulkfarmer && chmod 700 ~/.config/bulkfarmer"
scp ~/.config/bulkfarmer/{telegram,meta,r2}.env ubuntu@<서버IP>:~/.config/bulkfarmer/
ssh ubuntu@<서버IP> "chmod 600 ~/.config/bulkfarmer/*"
```

**저장소에는 절대 안 들어간다.** 파일을 직접 옮기는 것 외에 방법이 없다.

### systemd 등록

```bash
sudo cp ~/bulkfarmer/_deploy/bulkfarmer-worker.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bulkfarmer-worker.timer
systemctl status bulkfarmer-worker.timer
journalctl -u bulkfarmer-worker -f      # 로그 확인
```

### 맥 쪽 정리 — 반드시 한다

**두 곳에서 동시에 돌리면 안 된다.** 텔레그램 `getUpdates`는 한 번 읽으면 소비되므로,
서버와 맥이 서로 버튼을 뺏어간다. 절반은 처리되고 절반은 사라진다.

```bash
launchctl unload ~/Library/LaunchAgents/com.bulkfarmer.threads-worker.plist
```

> 맥의 워커를 끄면 **텔레그램 명령 처리도 같이 멈춘다.** 명령을 보내는 통로가
> 이 워커이기 때문이다. 명령 기능을 계속 쓰려면 2단계까지 옮기거나,
> 명령이 필요할 때만 맥 워커를 잠깐 켜는 식으로 쓴다.

---

## 2단계 — Claude가 필요한 작업 (선택)

초안 생성·주간 리포트·텔레그램 명령을 옮기려면 서버에서 `claude` CLI가 돌아야 한다.
맥에서는 구독 로그인을 쓰고 있는데, 서버에서는 그게 안 된다.

- `ANTHROPIC_API_KEY` 또는 `claude setup-token` 으로 만든 장기 토큰이 필요하다
- **어느 쪽이든 토큰 사용량이 과금된다.** 지금 구독 안에서 도는 것과 다르다
- 매일 초안 8개 + 주간 리포트 규모다. 실제 금액은 한 달 돌려봐야 안다

먼저 1단계만 하고, 맥을 안 켜는 날이 실제로 얼마나 불편한지 본 뒤에 정하는 편이 낫다.

---

## 확인

서버에서 워커가 도는지 보려면 텔레그램에 `현황` 을 보낸다.
맥을 꺼둔 상태에서 답이 오면 성공이다.
