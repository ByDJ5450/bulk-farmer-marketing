# 네이버 블로그 자동 발행 세팅

한 번만 하면 된다. 소요 시간 약 10분.

---

## 1. 네이버 개발자센터에 앱 등록

https://developers.naver.com/apps/#/register

| 항목 | 입력값 |
|------|--------|
| 애플리케이션 이름 | `벌크농부 블로그` |
| 사용 API | **네이버 로그인** 체크 → 제공 정보는 `회원이름` 정도만 |
| 사용 API 추가 | **블로그** 도 함께 체크 |
| 환경 추가 | `PC웹` 선택 |
| 서비스 URL | `http://localhost:8765` |
| Callback URL | `http://localhost:8765/callback` |

> Callback URL은 **정확히** 위 문자열이어야 한다. 슬래시 하나만 달라도 인증이 거부된다.

등록하면 **Client ID / Client Secret** 이 나온다.

### 검수는 지금 필요 없다

네이버 로그인 API는 "개발 상태"에서도 **앱을 만든 본인 계정**은 그대로 쓸 수 있다.
본인 블로그에만 올릴 거라 검수 신청 없이 시작하면 된다.
혹시 권한 오류가 나면 그때 개발자센터에서 검수를 신청한다 (영업일 기준 며칠 걸린다).

---

## 2. 자격증명 저장

`~/.config/bulkfarmer/naver.env` 를 만들고 권한을 600으로 둔다.

```bash
cat > ~/.config/bulkfarmer/naver.env <<'EOF'
NAVER_CLIENT_ID=여기에_Client_ID
NAVER_CLIENT_SECRET=여기에_Client_Secret
NAVER_REDIRECT_URI=http://localhost:8765/callback
EOF
chmod 600 ~/.config/bulkfarmer/naver.env
```

값을 알려주면 대신 저장해 준다. 저장 후 값은 출력·로그·커밋 어디에도 남기지 않는다.

---

## 3. 최초 로그인 (한 번만)

```bash
/usr/bin/python3 _blog/naver_auth.py login
```

브라우저에 네이버 로그인 창이 뜬다. 로그인하고 동의하면 끝이다.
토큰은 `~/.config/bulkfarmer/naver_token.json` 에 저장된다.

- `access_token` 유효기간 **1시간** — 발행 스크립트가 매번 자동 갱신하므로 신경 쓸 필요 없다
- `refresh_token` 은 장기 유효. 만료되면 `naver_auth.py login` 을 다시 한 번 하면 된다

상태 확인:
```bash
/usr/bin/python3 _blog/naver_auth.py status
```

---

## 4. 카테고리 번호 확인

```bash
/usr/bin/python3 _blog/list_category.py
```

출력된 번호를 발행할 때 `--category` 로 넘긴다. 안 넘기면 기본 카테고리로 들어간다.

---

## 5. 발행

### 글 폴더 구조

```
_blog/{slug}/
  title.txt      제목 한 줄 (100자 이내)
  content.html   본문 HTML
  images/        선택 — 있으면 파일명 순서대로 첨부
```

### 드라이런 (권장 — 먼저 이걸로 확인)

```bash
/usr/bin/python3 _blog/publish_post.py _blog/12week_case_2026-08-02
```

### 텔레그램 승인 후 발행

```bash
/usr/bin/python3 _blog/send_for_approval.py _blog/12week_case_2026-08-02 --open closed
```

텔레그램으로 제목·본문 미리보기와 함께 `✅ 블로그 발행` / `🗑 버림` 버튼이 온다.
버튼을 누르면 5분 안에 `threads-worker` 가 처리한다 (같은 워커가 스레드·카드뉴스·블로그를 모두 담당).

### 공개 범위

`--open` 기본값은 **`closed`(비공개)** 다. 첫 발행은 반드시 비공개로 올려서
네이버 에디터에서 실제 렌더링을 눈으로 확인한 뒤 공개로 바꾸는 것을 권한다.

HTML 태그 지원 범위가 에디터 버전마다 달라서, **API 응답이 성공이어도 본문이 깨질 수 있다.**
한 번 확인해서 문제없으면 그 뒤로는 `--open all` 로 바로 올린다.

| 값 | 의미 |
|----|------|
| `closed` | 비공개 (기본값) |
| `all` | 전체공개 |
| `neighbor` | 이웃공개 |
| `agreedNeighbor` | 서로이웃공개 |

---

## 문제가 생기면

| 증상 | 원인 / 조치 |
|------|-----------|
| `naver.env 없음` | 2번 단계를 안 했다 |
| 인증 창에서 `redirect_uri` 오류 | 개발자센터 Callback URL과 `naver.env` 값이 다르다 |
| `8765 포트를 열 수 없습니다` | 다른 프로그램이 쓰고 있다. `lsof -i :8765` 로 확인 |
| 발행 시 401 / 권한 오류 | 앱에 **블로그** API가 체크돼 있는지 확인. 그래도 안 되면 검수 신청 |
| 본문이 깨져서 올라감 | HTML 태그를 단순화한다 (`p`, `br`, `strong`, `h3`, `table`, `ul` 위주) |
