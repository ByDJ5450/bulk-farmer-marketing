// 벌크농부 클래스 — Supabase 어댑터 (서버 모드)
// config.js 에 SUPABASE_URL / SUPABASE_ANON_KEY 가 채워져 있을 때 사용된다.
// 스키마: sql/supabase_schema.sql (profiles / courses / posts / post_comments /
//         lecture_comments / enrollments / progress + RLS 정책)
'use strict';

function makeSupaAPI(client) {
  var profile = null; // { id, name, email, role }

  function mapAuthor(row) {
    var a = row && row.author;
    return {
      name: a && a.name ? a.name : '(탈퇴 회원)',
      coach: !!(a && a.role === 'coach')
    };
  }

  function loadProfile(user) {
    return client.from('profiles').select('id,name,email,role').eq('id', user.id).maybeSingle()
      .then(function (r) {
        if (r.error) throw r.error;
        if (r.data) { profile = r.data; return profile; }
        // 프로필이 없으면(트리거 미적용 등) 가입 메타데이터로 생성
        var name = (user.user_metadata && user.user_metadata.name) || String(user.email).split('@')[0];
        return client.from('profiles')
          .upsert({ id: user.id, name: name, email: user.email }, { onConflict: 'id' })
          .then(function (r2) {
            if (r2.error) throw r2.error;
            profile = { id: user.id, name: name, email: user.email, role: 'member' };
            return profile;
          });
      });
  }

  function koAuthMsg(msg) {
    msg = String(msg || '');
    if (/already registered/i.test(msg)) return '이미 가입된 이메일입니다. 로그인해주세요.';
    if (/invalid login credentials/i.test(msg)) return '이메일 또는 비밀번호가 올바르지 않습니다.';
    if (/email not confirmed/i.test(msg)) return '이메일 인증이 아직 안 됐습니다. 받은 메일함을 확인해주세요.';
    if (/at least 6/i.test(msg) || /password/i.test(msg)) return '비밀번호는 6자 이상이어야 합니다.';
    if (/rate limit/i.test(msg)) return '요청이 너무 잦습니다. 잠시 후 다시 시도해주세요.';
    return '요청에 실패했습니다: ' + msg;
  }

  return {
    mode: 'supabase',

    init: function () {
      return client.auth.getSession().then(function (r) {
        var session = r.data ? r.data.session : null;
        if (!session) { profile = null; return; }
        return loadProfile(session.user);
      }).catch(function (e) {
        console.error('세션 확인 실패', e);
        profile = null;
      });
    },

    me: function () { return profile; },

    signup: function (name, email, pw) {
      name = String(name).trim();
      email = String(email).trim().toLowerCase();
      if (name.length < 2) return Promise.resolve({ ok: false, msg: '이름(닉네임)은 2자 이상 입력해주세요.' });
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return Promise.resolve({ ok: false, msg: '이메일 형식이 올바르지 않습니다.' });
      if (String(pw).length < 6) return Promise.resolve({ ok: false, msg: '비밀번호는 6자 이상이어야 합니다.' });

      return client.auth.signUp({ email: email, password: pw, options: { data: { name: name } } })
        .then(function (r) {
          if (r.error) return { ok: false, msg: koAuthMsg(r.error.message) };
          if (!r.data.session) {
            // 이메일 인증이 켜져 있는 프로젝트 — 메일 확인 후 로그인해야 한다
            return { ok: true, needConfirm: true };
          }
          return loadProfile(r.data.user).then(function () { return { ok: true }; });
        });
    },

    login: function (email, pw) {
      return client.auth.signInWithPassword({ email: String(email).trim().toLowerCase(), password: pw })
        .then(function (r) {
          if (r.error) return { ok: false, msg: koAuthMsg(r.error.message) };
          return loadProfile(r.data.user).then(function () { return { ok: true }; });
        });
    },

    logout: function () {
      profile = null;
      return client.auth.signOut();
    },

    /* 강의 — courses 테이블에 강의 전체를 jsonb 로 저장 */
    courses: function () {
      return client.from('courses').select('id,data,created_at').order('created_at', { ascending: true })
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) {
            var c = row.data || {};
            c.id = row.id;
            return c;
          });
        });
    },

    saveCourse: function (course) {
      return client.from('courses').upsert({ id: course.id, data: course })
        .then(function (r) { if (r.error) throw r.error; });
    },

    deleteCourse: function (id) {
      return client.from('courses').delete().eq('id', id)
        .then(function (r) { if (r.error) throw r.error; });
    },

    /* 수강·진도 */
    myEnrollments: function () {
      if (!profile) return Promise.resolve([]);
      return client.from('enrollments').select('course_id').eq('user_id', profile.id)
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) { return row.course_id; });
        });
    },

    enroll: function (courseId) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      return client.from('enrollments')
        .upsert({ user_id: profile.id, course_id: courseId }, { onConflict: 'user_id,course_id' })
        .then(function (r) { if (r.error) throw r.error; });
    },

    myProgress: function (courseId) {
      if (!profile) return Promise.resolve([]);
      return client.from('progress').select('lecture_id')
        .eq('user_id', profile.id).eq('course_id', courseId)
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) { return row.lecture_id; });
        });
    },

    setDone: function (courseId, lecId, done) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      if (done) {
        return client.from('progress')
          .upsert({ user_id: profile.id, course_id: courseId, lecture_id: lecId },
                  { onConflict: 'user_id,course_id,lecture_id' })
          .then(function (r) { if (r.error) throw r.error; });
      }
      return client.from('progress').delete()
        .eq('user_id', profile.id).eq('course_id', courseId).eq('lecture_id', lecId)
        .then(function (r) { if (r.error) throw r.error; });
    },

    /* 강의실 댓글 */
    lectureComments: function (courseId, lecId) {
      return client.from('lecture_comments')
        .select('id,text,created_at,author:profiles(name,role)')
        .eq('course_id', courseId).eq('lecture_id', lecId)
        .order('created_at', { ascending: true })
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) {
            var a = mapAuthor(row);
            return { id: row.id, name: a.name, coach: a.coach, text: row.text, ts: Date.parse(row.created_at) };
          });
        });
    },

    addLectureComment: function (courseId, lecId, text) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      return client.from('lecture_comments')
        .insert({ course_id: courseId, lecture_id: lecId, author_id: profile.id, text: text })
        .then(function (r) { if (r.error) throw r.error; });
    },

    /* 커뮤니티 */
    posts: function () {
      return client.from('posts')
        .select('id,cat,title,body,created_at,author:profiles(name,role),comments:post_comments(id,text,created_at,author:profiles(name,role))')
        .order('created_at', { ascending: false })
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) {
            var a = mapAuthor(row);
            var comments = (row.comments || []).map(function (c) {
              var ca = mapAuthor(c);
              return { id: c.id, name: ca.name, coach: ca.coach, text: c.text, ts: Date.parse(c.created_at) };
            }).sort(function (x, y) { return x.ts - y.ts; });
            return {
              id: row.id, cat: row.cat, title: row.title, body: row.body,
              name: a.name, coach: a.coach, ts: Date.parse(row.created_at),
              comments: comments
            };
          });
        });
    },

    addPost: function (cat, title, body) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      return client.from('posts').insert({ cat: cat, title: title, body: body, author_id: profile.id })
        .then(function (r) { if (r.error) throw r.error; });
    },

    addPostComment: function (postId, text) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      return client.from('post_comments').insert({ post_id: postId, author_id: profile.id, text: text })
        .then(function (r) { if (r.error) throw r.error; });
    },

    /* 관리자 */
    members: function () {
      return client.from('profiles').select('name,email,role,joined').order('joined', { ascending: false })
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) {
            return { name: row.name, email: row.email, role: row.role, joined: Date.parse(row.joined) };
          });
        });
    }
  };
}
