-- 벌크농부 클래스 — 수강평·별점 테이블 + 보안 정책(RLS)
-- 사용법: Supabase 대시보드 → SQL Editor → New query → 이 파일 전체 붙여넣기 → Run
-- 안전하게 반복 실행 가능(if not exists / drop policy if exists).

-- ============================================================
-- 수강평 (강의별 별점 + 후기) — 1인 1강의 1후기
-- ============================================================
create table if not exists public.reviews (
  id uuid primary key default gen_random_uuid(),
  course_id text not null,
  author_id uuid not null references public.profiles(id) on delete cascade,
  rating int not null check (rating between 1 and 5),
  text text not null default '',
  created_at timestamptz not null default now(),
  unique (course_id, author_id)          -- 한 강의당 회원 1명은 후기 1개
);

create index if not exists reviews_course_lookup
  on public.reviews (course_id, created_at desc);

alter table public.reviews enable row level security;

-- 읽기: 누구나 (사회적 증거 — 비회원도 강의 상세에서 후기를 본다)
drop policy if exists "reviews_select_all" on public.reviews;
create policy "reviews_select_all" on public.reviews
  for select using (true);

-- 작성: 본인 명의 + 해당 강의를 수강한 회원만 (가짜 후기 차단)
drop policy if exists "reviews_insert_enrolled" on public.reviews;
create policy "reviews_insert_enrolled" on public.reviews
  for insert with check (
    auth.uid() = author_id
    and exists (
      select 1 from public.enrollments e
      where e.user_id = auth.uid() and e.course_id = reviews.course_id
    )
  );

-- 수정: 본인 것만 (수강 이력은 유지되어야 하므로 재확인)
drop policy if exists "reviews_update_own" on public.reviews;
create policy "reviews_update_own" on public.reviews
  for update using (auth.uid() = author_id)
  with check (
    auth.uid() = author_id
    and exists (
      select 1 from public.enrollments e
      where e.user_id = auth.uid() and e.course_id = reviews.course_id
    )
  );

-- 삭제: 본인 또는 코치(부적절 후기 관리)
drop policy if exists "reviews_delete_own_or_coach" on public.reviews;
create policy "reviews_delete_own_or_coach" on public.reviews
  for delete using (auth.uid() = author_id or public.is_coach());

-- ============================================================
-- 완료. 확인:
--   select course_id, count(*), round(avg(rating),2) from public.reviews group by course_id;
-- ============================================================
