-- 벌크농부 클래스 — 수강 권한 접근제어
-- 사용법: Supabase SQL Editor 에 붙여넣고 Run
--
-- 목표:
--  · 무료 강의(price=0): 로그인 회원이 스스로 수강 가능
--  · 유료 강의(price>0): 스스로 못 열고 → 코치가 권한 부여 OR 결제 웹훅이 부여
--  · 코치: 아무 회원에게나 강의 권한 부여/회수 가능

-- 1) 무료 강의 판별 함수
create or replace function public.is_free_course(cid text)
returns boolean
language sql stable security definer set search_path = public
as $$
  select coalesce((data->>'price')::numeric, 0) = 0
  from public.courses where id = cid;
$$;

-- 2) enrollments 정책 재구성 (기존 통합 정책 제거 후 세분화)
drop policy if exists "enrollments_own" on public.enrollments;
drop policy if exists "enrollments_coach_read" on public.enrollments;
drop policy if exists "enroll_select_own_or_coach" on public.enrollments;
drop policy if exists "enroll_insert_self_free" on public.enrollments;
drop policy if exists "enroll_insert_coach" on public.enrollments;
drop policy if exists "enroll_delete_own_or_coach" on public.enrollments;

-- 조회: 본인 것 또는 코치는 전체
create policy "enroll_select_own_or_coach" on public.enrollments
  for select using (auth.uid() = user_id or public.is_coach());

-- 등록(본인): 무료 강의만 스스로 가능
create policy "enroll_insert_self_free" on public.enrollments
  for insert with check (
    auth.uid() = user_id and public.is_free_course(course_id)
  );

-- 등록(코치): 아무 회원에게나 부여 가능 (여러 insert 정책은 OR로 평가됨)
create policy "enroll_insert_coach" on public.enrollments
  for insert with check (public.is_coach());

-- 회수: 본인 또는 코치
create policy "enroll_delete_own_or_coach" on public.enrollments
  for delete using (auth.uid() = user_id or public.is_coach());
-- 참고: 결제사 웹훅은 service_role 키로 동작하며 RLS를 우회하므로 별도 정책 불필요.

-- 3) 진도(progress)도 유료 강의는 미수강자가 못 쌓게 — 수강 여부로 제한
drop policy if exists "progress_own" on public.progress;
drop policy if exists "progress_select_own" on public.progress;
drop policy if exists "progress_write_enrolled" on public.progress;
drop policy if exists "progress_delete_own" on public.progress;

create policy "progress_select_own" on public.progress
  for select using (auth.uid() = user_id or public.is_coach());

create policy "progress_write_enrolled" on public.progress
  for insert with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.enrollments e
      where e.user_id = auth.uid() and e.course_id = progress.course_id
    )
  );

create policy "progress_delete_own" on public.progress
  for delete using (auth.uid() = user_id);

-- 4) 회원 목록 함수에 id 추가 (코치가 권한 부여할 때 대상 식별용)
drop function if exists public.get_members();
create or replace function public.get_members()
returns table (id uuid, name text, email text, role text, joined timestamptz)
language plpgsql
security definer set search_path = public
as $$
begin
  if not public.is_coach() then
    raise exception '코치만 회원 목록을 볼 수 있습니다';
  end if;
  return query
    select p.id, p.name, p.email, p.role, p.joined
    from public.profiles p
    order by p.joined desc;
end;
$$;

revoke all on function public.get_members() from public, anon;
grant execute on function public.get_members() to authenticated;

-- 확인:
--  · 일반 회원 세션에서 유료 강의 enrollment insert → 실패(정상)
--  · 무료 강의 insert → 성공
--  · 코치 세션에서 임의 회원 enrollment insert → 성공
