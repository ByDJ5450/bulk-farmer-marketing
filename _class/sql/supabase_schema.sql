-- 벌크농부 클래스 — Supabase 스키마 + 보안 정책(RLS)
-- 사용법: Supabase 대시보드 → SQL Editor → New query → 이 파일 전체 붙여넣기 → Run
-- 전부 실행해도 안전하도록 if not exists / or replace 로 작성했다.

-- ============================================================
-- 1. 프로필 (회원 정보 — auth.users 와 1:1)
-- ============================================================
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  email text,
  role text not null default 'member' check (role in ('member', 'coach')),
  joined timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_all" on public.profiles;
create policy "profiles_select_all" on public.profiles
  for select using (true);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
  for insert with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id)
  with check (auth.uid() = id and role = (select p.role from public.profiles p where p.id = auth.uid()));
-- ↑ 이름은 바꿀 수 있지만 자기 role(코치 권한)은 스스로 못 바꾼다

-- 가입 시 프로필 자동 생성 트리거
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.email
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 코치 판별 함수 (RLS 정책에서 사용)
create or replace function public.is_coach()
returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'coach');
$$;

-- ============================================================
-- 2. 강의 (강의 전체 구조를 jsonb 하나로 저장)
-- ============================================================
create table if not exists public.courses (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default now()
);

alter table public.courses enable row level security;

drop policy if exists "courses_select_all" on public.courses;
create policy "courses_select_all" on public.courses
  for select using (true);

drop policy if exists "courses_coach_insert" on public.courses;
create policy "courses_coach_insert" on public.courses
  for insert with check (public.is_coach());

drop policy if exists "courses_coach_update" on public.courses;
create policy "courses_coach_update" on public.courses
  for update using (public.is_coach()) with check (public.is_coach());

drop policy if exists "courses_coach_delete" on public.courses;
create policy "courses_coach_delete" on public.courses
  for delete using (public.is_coach());

-- ============================================================
-- 3. 커뮤니티 게시글 + 댓글
-- ============================================================
create table if not exists public.posts (
  id uuid primary key default gen_random_uuid(),
  cat text not null check (cat in ('notice', 'qna', 'free')),
  title text not null,
  body text not null,
  author_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.posts enable row level security;

drop policy if exists "posts_select_all" on public.posts;
create policy "posts_select_all" on public.posts
  for select using (true);

drop policy if exists "posts_insert_own" on public.posts;
create policy "posts_insert_own" on public.posts
  for insert with check (
    auth.uid() = author_id
    and (cat <> 'notice' or public.is_coach())  -- 공지는 코치만
  );

drop policy if exists "posts_delete_own_or_coach" on public.posts;
create policy "posts_delete_own_or_coach" on public.posts
  for delete using (auth.uid() = author_id or public.is_coach());

create table if not exists public.post_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.posts(id) on delete cascade,
  author_id uuid not null references public.profiles(id) on delete cascade,
  text text not null,
  created_at timestamptz not null default now()
);

alter table public.post_comments enable row level security;

drop policy if exists "post_comments_select_all" on public.post_comments;
create policy "post_comments_select_all" on public.post_comments
  for select using (true);

drop policy if exists "post_comments_insert_own" on public.post_comments;
create policy "post_comments_insert_own" on public.post_comments
  for insert with check (auth.uid() = author_id);

drop policy if exists "post_comments_delete_own_or_coach" on public.post_comments;
create policy "post_comments_delete_own_or_coach" on public.post_comments
  for delete using (auth.uid() = author_id or public.is_coach());

-- ============================================================
-- 4. 강의실 댓글 (강의별 질문·소통)
-- ============================================================
create table if not exists public.lecture_comments (
  id uuid primary key default gen_random_uuid(),
  course_id text not null,
  lecture_id text not null,
  author_id uuid not null references public.profiles(id) on delete cascade,
  text text not null,
  created_at timestamptz not null default now()
);

create index if not exists lecture_comments_lookup
  on public.lecture_comments (course_id, lecture_id, created_at);

alter table public.lecture_comments enable row level security;

drop policy if exists "lecture_comments_select_all" on public.lecture_comments;
create policy "lecture_comments_select_all" on public.lecture_comments
  for select using (true);

drop policy if exists "lecture_comments_insert_own" on public.lecture_comments;
create policy "lecture_comments_insert_own" on public.lecture_comments
  for insert with check (auth.uid() = author_id);

drop policy if exists "lecture_comments_delete_own_or_coach" on public.lecture_comments;
create policy "lecture_comments_delete_own_or_coach" on public.lecture_comments
  for delete using (auth.uid() = author_id or public.is_coach());

-- ============================================================
-- 5. 수강 신청 + 진도
-- ============================================================
create table if not exists public.enrollments (
  user_id uuid not null references public.profiles(id) on delete cascade,
  course_id text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, course_id)
);

alter table public.enrollments enable row level security;

drop policy if exists "enrollments_own" on public.enrollments;
create policy "enrollments_own" on public.enrollments
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "enrollments_coach_read" on public.enrollments;
create policy "enrollments_coach_read" on public.enrollments
  for select using (public.is_coach());

create table if not exists public.progress (
  user_id uuid not null references public.profiles(id) on delete cascade,
  course_id text not null,
  lecture_id text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, course_id, lecture_id)
);

alter table public.progress enable row level security;

drop policy if exists "progress_own" on public.progress;
create policy "progress_own" on public.progress
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ============================================================
-- 완료. 이후 할 일:
-- 1) Authentication → Sign In / Up → Email 에서 "Confirm email" 끄기 (선택 — 켜두면 가입 시 메일 인증 필요)
-- 2) 본인 계정으로 사이트에서 회원가입
-- 3) 아래 쿼리로 본인을 코치로 지정 (이메일만 바꿔서 실행):
--    update public.profiles set role = 'coach' where email = '여기에_본인_이메일';
-- ============================================================
