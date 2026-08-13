-- 강의·차시 제목의 em-dash( — )를 중점( · )으로 교체
-- 라이브 강의 카드/커리큘럼 제목은 courses.data(jsonb) 안에 들어 있어
-- HTML만 고쳐선 안 바뀐다. Supabase SQL 편집기에서 한 번 실행한다.
--
-- 대상: "벌크업 마스터 클래스 — 12주 완성", "인바디 읽는 법 — 골격근량이 전부다" 등
-- tagline·outcomes 에는 ' — ' 가 없어 영향 없음.

update public.courses
set data = replace(data::text, ' — ', ' · ')::jsonb
where data::text like '% — %';

-- 확인
-- select id, data->>'title' as title from public.courses order by created_at;
