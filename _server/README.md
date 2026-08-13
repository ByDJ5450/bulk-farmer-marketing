# 오라클 서버 이전 킷

맥의 마케팅 에이전트팀을 오라클 클라우드 무료 서버로 **복사**해서 24시간 돌린다.
맥의 파일은 하나도 지우지 않는다 — 맥이 백업이다.
별도 백업: `~/Desktop/벌크농부/_백업/2026-08-05_서버이전/` (작업공간 전체 + 자격증명·메모리)

## 비용

| 항목 | 비용 |
|------|------|
| 오라클 Ampere A1 (4 OCPU / 24GB) | 평생 무료 (Always Free) |
| Claude 사용량 | Max 구독에 합산 — 추가 0원 |

## 순서

### 1. 오라클 인스턴스 만들기 (직접, 웹에서 1회)

1. cloud.oracle.com 가입 (홈 리전: South Korea Central — Seoul)
2. Compute → Instance 생성
   - Image: **Ubuntu 24.04** (aarch64)
   - Shape: **VM.Standard.A1.Flex** — 4 OCPU / 24GB (Always Free 최대치)
   - SSH 키: 자동 생성 → 프라이빗 키 다운로드해서 `~/.ssh/oracle.key`로 저장, `chmod 600`
3. "Out of capacity" 오류가 나면 → 무료 계정에서 흔하다. 시간을 바꿔 재시도하거나
   OCPU를 2개로 줄여 시도. 며칠 걸릴 수 있다.
4. 만들어지면 퍼블릭 IP를 확인한다.

> 인바운드 포트는 SSH(22) 외에 아무것도 열 필요 없다.
> 텔레그램·API 전부 서버에서 바깥으로 나가는 연결이라 방화벽 추가 설정이 없다.

### 2. 맥에서 토큰 발급 (1회)

```bash
claude setup-token
```
브라우저 로그인 후 터미널에 나오는 토큰(1년 유효)을 복사해 둔다.
Max 구독 사용량으로 계산되고 API 과금이 없다.

### 3. 맥에서 복사 실행

```bash
cd "$HOME/Desktop/벌크농부/00_벌크농부 마케팅 에이전트팀/_server"
./copy_to_server.sh ubuntu@<서버IP> ~/.ssh/oracle.key
```
작업공간 전체(219MB) + 메모리 + `~/.config/bulkfarmer` 자격증명 + 워커 실행 상태
(state.json — 텔레그램 오프셋·발행 간격)가 서버로 복사된다.
**복사만 한다. 맥에서 지우는 것은 없다.** 재실행하면 갱신 복사된다.

### 4. 맥 자동화 내리기 — 서버 설치 **전에** 한다

서버 설치(5번)가 끝나는 즉시 cron이 돌기 시작한다. 그 순간 맥 워커가 살아 있으면
같은 텔레그램 봇을 둘이 폴링해서 버튼·메시지를 서로 뺏어가고 스레드가 이중 발행된다.

```bash
# 맥에서 — 자동화 중지 (파일은 전부 그대로 남는다)
launchctl unload ~/Library/LaunchAgents/com.bulkfarmer.threads-worker.plist
launchctl unload ~/Library/LaunchAgents/com.bulkfarmer.threads-draft.plist
launchctl unload ~/Library/LaunchAgents/com.bulkfarmer.weekly-report.plist
launchctl unload ~/Library/LaunchAgents/com.bulkfarmer.security-check.plist

# 그리고 마지막 상태를 한 번 더 넘긴다 (내린 뒤에도 오프셋이 이미 움직였을 수 있다)
cd "$HOME/Desktop/벌크농부/00_벌크농부 마케팅 에이전트팀/_server"
./copy_to_server.sh ubuntu@<서버IP> ~/.ssh/oracle.key
```

### 5. 서버에서 설치 실행

```bash
ssh -i ~/.ssh/oracle.key ubuntu@<서버IP>
cd "$HOME/벌크농부/00_벌크농부 마케팅 에이전트팀/_server"
./setup_server.sh
```
- 한국 시간대, 필수 패키지(chromium·폰트·yt-dlp·zsh), Claude Code 설치
- 2번에서 복사한 토큰을 물어본다 → `~/.config/bulkfarmer/claude.env`에 저장 (600)
- cron 4종 + 토큰 만료 알림 등록 — **이 순간부터 서버가 실운영본이다**
- 끝나면 텔레그램으로 "서버 준비 완료" 알림이 온다

### 6. 검증 (하루 정도 지켜보기)

- 텔레그램에 `현황` 보내기 → 서버가 답하면 승인 워커 정상
- 텔레그램에 아무 작업 지시 보내기 → "🤖 작업 시작합니다" 후 결과 회신 확인
- 다음날 08:13 스레드 초안 8개 도착 확인

서버에 문제가 생기면 서버에서 `crontab -r`(cron 전부 제거) 후, 맥에서 4번 명령의
`unload`를 `load`로 바꿔 즉시 복귀한다.

### 7. (선택) 서버 → GitHub 자동 백업

서버에서 만든 콘텐츠 커밋을 GitHub에도 남기려면 서버에서:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/github -N ""
cat ~/.ssh/github.pub   # → GitHub 저장소 Settings → Deploy keys에 등록 (write 권한)
```
등록 후 `crontab -e`에서 자동 push 줄의 주석을 푼다.

## 서버 운영 명령

```bash
crontab -l                                  # 자동화 목록
tail -f ~/벌크농부/00_*/_threads/worker.log   # 워커 로그
tail -f ~/벌크농부/00_*/_telegram/commands.log # 텔레그램 지시 처리 로그
```

## 토큰 만료 (1년)

- 만료되면 무인 세션은 복구 불가 — 모든 Claude 작업이 멈춘다
- 발급 후 330일이 지나면 매달 1일 텔레그램으로 갱신 알림이 온다
- 갱신: 맥에서 `claude setup-token` 다시 실행 → 서버 `~/.config/bulkfarmer/claude.env`의
  `CLAUDE_CODE_OAUTH_TOKEN` 값과 `CLAUDE_TOKEN_ISSUED` 날짜를 바꾼다
