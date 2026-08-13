// 벌크농부 클래스 — 서버 설정
//
// [로컬 모드]  아래 두 값을 비워두면 모든 데이터가 이 브라우저(localStorage)에만 저장된다.
// [서버 모드]  Supabase 프로젝트를 만들고 아래 두 값을 채우면
//             회원가입·로그인·게시판·수강 진도가 서버에 저장되어 모든 회원이 공유한다.
//
// 설정 방법: README.md 의 "서버 모드로 전환하기 (Supabase)" 참조
// 1) https://supabase.com 에서 프로젝트 생성
// 2) sql/supabase_schema.sql 내용을 SQL Editor에 붙여넣고 실행
// 3) Project Settings → API 에서 URL과 anon public 키를 복사해 아래에 붙여넣기
'use strict';

window.BULK_CONFIG = {
  SUPABASE_URL: 'https://ofqenoojssaorpycccjv.supabase.co',
  SUPABASE_ANON_KEY: 'sb_publishable_fk_axS9Vo_fvKo80-FQGlg_GUJzAtoK', // publishable 키 — 공개되어도 되는 키

  // [봇 차단] Cloudflare Turnstile 사이트 키 (공개용). 비워두면 기존 캔버스 보안문자로 폴백한다.
  // 켜는 법:
  //  1) https://dash.cloudflare.com → Turnstile → 위젯 추가(도메인 bulkfarmer.co.kr)
  //     → 사이트 키(공개)와 시크릿 키(비공개)를 발급받는다
  //  2) 사이트 키를 아래에 붙여넣는다
  //  3) Supabase 대시보드 → Authentication → Attack Protection → Enable CAPTCHA →
  //     Provider "Turnstile" 선택 → 시크릿 키 붙여넣기 (시크릿은 절대 여기 넣지 말 것)
  //  두 곳(아래 사이트 키 + Supabase 시크릿)이 함께 설정돼야 로그인·가입이 정상 동작한다.
  TURNSTILE_SITE_KEY: '0x4AAAAAAEHLgTkfyzr76CVp'
};
