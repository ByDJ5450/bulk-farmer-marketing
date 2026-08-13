-- 벌크농부 클래스 — 이름(실명) / 닉네임 분리
-- 무중단 배포를 위해 2단계로 나눠 실행한다.
--   PART 1 : 지금 실행 (컬럼·트리거·회원목록 추가 — 기존/신규 프론트 둘 다 정상)
--   → 그다음 새 프론트 배포
--   PART 2 : 배포 후 실행 (실명·이메일 컬럼 접근 차단 — 공개로는 닉네임만)
--
-- 설계: name(실명)=비공개(본인·코치만, 이메일찾기 매칭) / nickname(닉네임)=공개 표시

-- ============================================================
-- PART 1 — 먼저 실행 (추가만, 하위호환 안전)
-- ============================================================

-- 1) 닉네임 컬럼 + 기존 회원 백필(닉네임 = 기존 이름)
alter table public.profiles add column if not exists nickname text;
update public.profiles set nickname = name where nickname is null or nickname = '';

-- 1-1) 공개 읽기 권한 — 이 프로젝트는 컬럼 단위 grant가 걸려 있어 nickname을 명시 허용해야 한다
grant select (nickname) on public.profiles to anon, authenticated;

-- 2) 가입 트리거 — 실명·닉네임 둘 다 기록
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, name, nickname, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    coalesce(new.raw_user_meta_data->>'nickname', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.email
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

-- 3) 코치용 회원 목록 — 실명 + 닉네임 + 이메일
drop function if exists public.get_members();
create or replace function public.get_members()
returns table (id uuid, name text, nickname text, email text, role text, joined timestamptz)
language plpgsql
security definer set search_path = public
as $$
begin
  if not public.is_coach() then
    raise exception '코치만 회원 목록을 볼 수 있습니다';
  end if;
  return query
    select p.id, p.name, p.nickname, p.email, p.role, p.joined
    from public.profiles p
    order by p.joined desc;
end;
$$;
revoke all on function public.get_members() from public, anon;
grant execute on function public.get_members() to authenticated;

-- ============================================================
-- PART 2 — 새 프론트 배포 후에 실행 (실명 공개 차단)
--   기존 컬럼권한에서 name 만 회수한다. 본인 실명은 앱이 메타데이터에서 읽으므로 영향 없음.
-- ============================================================

-- revoke select (name) on public.profiles from anon, authenticated;

-- 확인:
--   select id, nickname, role from public.profiles limit 5;   -- 닉네임만
--   select public.get_members();                              -- 코치 세션: 실명까지
