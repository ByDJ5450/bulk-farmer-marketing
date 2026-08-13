-- 벌크농부 클래스 — 이메일(아이디) 찾기 RPC
-- 사용법: Supabase 대시보드 → SQL Editor → New query → 붙여넣기 → Run
--
-- 보안 설계:
--  · 이름 + 휴대폰번호가 "둘 다" 정확히 일치해야만 조회된다 (한쪽만으론 안 됨)
--  · 반환값은 "마스킹된 이메일"뿐 (예: le****@gmail.com) — 전체 이메일은 절대 노출 안 함
--  · 일치하지 않으면 그냥 null (계정 존재 여부를 구분해 알려주지 않음)
--  · security definer 로 auth.users 를 읽되, 결과는 마스킹만 내보낸다

create or replace function public.find_email_masked(p_name text, p_phone text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email  text;
  v_local  text;
  v_domain text;
  v_phone  text;
begin
  -- 입력 정규화 (휴대폰은 숫자만, 이름은 공백 정리)
  v_phone := regexp_replace(coalesce(p_phone, ''), '[^0-9]', '', 'g');
  p_name  := btrim(coalesce(p_name, ''));

  -- 최소 조건 미달이면 조회하지 않는다 (무작위 대입 방지)
  if length(v_phone) < 10 or char_length(p_name) < 2 then
    return null;
  end if;

  -- 이름 + 휴대폰이 모두 일치하는 계정 1건
  select u.email into v_email
  from auth.users u
  where regexp_replace(coalesce(u.raw_user_meta_data->>'phone', ''), '[^0-9]', '', 'g') = v_phone
    and btrim(coalesce(u.raw_user_meta_data->>'name', '')) = p_name
  order by u.created_at
  limit 1;

  if v_email is null then
    return null;
  end if;

  -- 로컬파트 앞 2글자만 남기고 마스킹, 도메인은 그대로
  v_local  := split_part(v_email, '@', 1);
  v_domain := split_part(v_email, '@', 2);
  if char_length(v_local) <= 2 then
    return left(v_local, 1) || '*@' || v_domain;
  end if;
  return left(v_local, 2) || repeat('*', char_length(v_local) - 2) || '@' || v_domain;
end;
$$;

-- 공개 실행 권한은 회수하고, 필요한 롤에만 부여
revoke all on function public.find_email_masked(text, text) from public;
grant execute on function public.find_email_masked(text, text) to anon, authenticated;

-- 확인:
--   select public.find_email_masked('이동진', '010-1234-5678');
