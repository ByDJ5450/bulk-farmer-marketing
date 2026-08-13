-- 회원 탈퇴 (자기 계정 삭제)
-- profiles·enrollments·progress·posts·comments 전부 auth.users 에 on delete cascade 로
-- 연결돼 있어, auth.users 한 줄을 지우면 개인정보가 전부 파기된다.
-- security definer 로 만들어, 로그인한 본인만 자기 계정을 지울 수 있게 한다.
-- Supabase SQL 편집기에서 한 번 실행한다.

create or replace function public.delete_own_account()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_own_account() from public, anon;
grant execute on function public.delete_own_account() to authenticated;
