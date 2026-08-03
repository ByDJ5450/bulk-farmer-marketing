// 벌크농부 클래스 — 데이터 어댑터 선택
// config.js 에 Supabase 키가 있으면 서버 모드, 없으면 로컬 모드로 동작한다.
'use strict';

var API = (function () {
  var cfg = window.BULK_CONFIG || {};
  var hasKeys = cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY;

  if (hasKeys) {
    if (window.supabase && window.supabase.createClient) {
      try {
        var client = window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY);
        return makeSupaAPI(client);
      } catch (e) {
        console.error('Supabase 초기화 실패 — 로컬 모드로 동작합니다', e);
      }
    } else {
      console.warn('supabase-js 스크립트를 불러오지 못했습니다(네트워크 확인) — 로컬 모드로 동작합니다');
    }
  }
  return LocalAPI;
})();
