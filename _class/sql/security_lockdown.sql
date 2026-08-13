-- 벌크농부 클래스 — 보안 강화 v2 (회원 이메일 외부 노출 차단)
-- 사용법: Supabase SQL Editor 에 붙여넣고 Run
-- 핵심: Supabase 는 테이블 전체 SELECT 를 기본 부여하므로, 컬럼 하나만 revoke 하면 무시된다.
--       → 테이블 SELECT 를 회수하고, 이메일을 뺀 컬럼만 다시 grant 해야 실제로 막힌다.

-- 1) 테이블 전체 SELECT 회수 후, email 을 제외한 컬럼만 재부여
revoke select on public.profiles from anon, authenticated;
grant  select (id, name, role, joined) on public.profiles to anon, authenticated;

-- 2) 코치의 회원 목록(이메일 포함)은 보안 함수로만 조회
create or replace function public.get_members()
returns table (name text, email text, role text, joined timestamptz)
language plpgsql
security definer set search_path = public
as $$
begin
  if not public.is_coach() then
    raise exception '코치만 회원 목록을 볼 수 있습니다';
  end if;
  return query
    select p.name, p.email, p.role, p.joined
    from public.profiles p
    order by p.joined desc;
end;
$$;

revoke all on function public.get_members() from public, anon;
grant execute on function public.get_members() to authenticated;

-- 확인:
--  · 공개키로 email 조회 → 권한 오류(정상)
--  · name, role 조회 → 정상
--  · 본인 이메일은 로그인 세션에서 읽으므로 영향 없음
