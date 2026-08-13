// 벌크농부 클래스 — Supabase 어댑터 (서버 모드)
// config.js 에 SUPABASE_URL / SUPABASE_ANON_KEY 가 채워져 있을 때 사용된다.
// 스키마: sql/supabase_schema.sql (profiles / courses / posts / post_comments /
//         lecture_comments / enrollments / progress + RLS 정책)
'use strict';

function makeSupaAPI(client) {
  var profile = null; // { id, name, email, role }

  function mapAuthor(row) {
    // 공개 표시는 닉네임만 사용한다 (실명은 조인으로 읽지 않는다)
    var a = row && row.author;
    return {
      name: a && a.nickname ? a.nickname : '(탈퇴 회원)',
      coach: !!(a && a.role === 'coach')
    };
  }

  function loadProfile(user) {
    // 실명(name)·이메일은 profiles 에서 읽지 않는다(공개 노출 방지 — 컬럼 권한으로도 막힘).
    // 본인 실명·닉네임은 auth.users 의 메타데이터에서 읽고, role·joined 만 profiles 에서 가져온다.
    var meta = user.user_metadata || {};
    var appMeta = user.app_metadata || {};
    var phone = meta.phone || '';
    var provider = appMeta.provider || 'email';
    // 소셜 로그인은 이름/전화/약관동의가 아직 없다 → 프로필 완성 단계가 필요하다
    var social = provider !== 'email';
    var needsProfile = social && !meta.terms_agreed;
    var providerName = meta.name || meta.full_name || meta.nickname || '';
    var realName = meta.name || providerName || String(user.email).split('@')[0];
    var nick = meta.nickname || providerName || realName;
    return client.from('profiles').select('id,nickname,role,joined').eq('id', user.id).maybeSingle()
      .then(function (r) {
        if (r.error) throw r.error;
        if (r.data) {
          profile = { id: r.data.id, name: realName, nickname: r.data.nickname || nick,
                      role: r.data.role, joined: r.data.joined, email: user.email, phone: phone,
                      provider: provider, needsProfile: needsProfile };
          return profile;
        }
        // 프로필이 없으면(트리거 미적용 등) 가입 메타데이터로 생성
        return client.from('profiles')
          .upsert({ id: user.id, name: realName, nickname: nick, email: user.email }, { onConflict: 'id' })
          .then(function (r2) {
            if (r2.error) throw r2.error;
            profile = { id: user.id, name: realName, nickname: nick, email: user.email, role: 'member',
                        phone: phone, provider: provider, needsProfile: needsProfile };
            return profile;
          });
      });
  }

  function koAuthMsg(err) {
    // err 는 supabase 에러 객체(또는 문자열) — 상태코드까지 활용해 원인을 구분한다
    var msg = String((err && (err.message || err.msg || err.error_description || err.error)) || err || '');
    var status = err && (err.status || err.statusCode || err.code);
    var ecode = String((err && (err.error_code || err.code)) || '');
    if (/already registered|already been registered/i.test(msg)) return '이미 가입된 이메일입니다. 로그인해주세요.';
    if (/invalid login credentials/i.test(msg)) return '이메일 또는 비밀번호가 올바르지 않습니다.';
    if (/email not confirmed/i.test(msg)) return '이메일 인증이 아직 안 됐습니다. 받은 메일함(스팸함 포함)을 확인해주세요.';
    if (/confirmation email|error sending|smtp|mailer/i.test(msg)) return '인증 메일 발송에 실패했습니다. 메일(SMTP) 설정을 확인해야 합니다.';
    if (/database error|saving new user/i.test(msg)) return '가입 처리 중 서버 오류가 발생했습니다. (계정 생성 트리거 확인 필요)';
    // 메시지가 비어 넘어온 500/unexpected_failure — 대개 인증메일 발송 실패다.
    if (/unexpected_failure/i.test(ecode) || (!msg && String(status) === '500')) return '인증 메일 발송에 실패했습니다. 메일(SMTP) 설정을 확인해주세요.';
    if (/rate limit|too many/i.test(msg)) return '요청이 너무 잦습니다. 잠시 후 다시 시도해주세요.';
    if (/captcha/i.test(msg)) return '보안 확인에 실패했습니다. 보안문자를 다시 확인해주세요.';
    if (/at least|password/i.test(msg)) return '비밀번호 조건을 확인해주세요.';
    return '요청에 실패했습니다' + (status ? ' (오류 ' + status + ')' : '') + (msg && msg !== '{}' ? ': ' + msg : '');
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

    signup: function (name, nickname, email, pw, code, consent) {
      name = String(name).trim();
      nickname = String(nickname).trim();
      email = String(email).trim().toLowerCase();
      var nErr = nameError(name); if (nErr) return Promise.resolve({ ok: false, msg: nErr });
      if (nickname.length < 2) return Promise.resolve({ ok: false, msg: '닉네임은 2자 이상 입력해주세요.' });
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return Promise.resolve({ ok: false, msg: '이메일 형식이 올바르지 않습니다.' });
      var pErr = pwError(pw); if (pErr) return Promise.resolve({ ok: false, msg: pErr });

      // 동의 이력을 계정 메타데이터에 남긴다 (법적 증빙)
      consent = consent || {};
      var meta = {
        name: name,
        nickname: nickname,
        phone: consent.phone || '',
        terms_agreed: true,
        privacy_agreed: true,
        marketing_agreed: !!consent.marketing,
        agreed_at: new Date().toISOString()
      };
      var suOpts = { data: meta };
      if (consent.captchaToken) suOpts.captchaToken = consent.captchaToken;
      // 인증 링크 클릭 후 돌아올 주소 — 착지 페이지에서 "인증 완료" 안내를 띄운다
      if (typeof location !== 'undefined') suOpts.emailRedirectTo = location.origin + '/?verified=1';
      return client.auth.signUp({ email: email, password: pw, options: suOpts })
        .then(function (r) {
          if (r.error) return { ok: false, msg: koAuthMsg(r.error) };
          var u = r.data && r.data.user;
          // 이메일 확인이 켜진 프로젝트에서 이미 가입된 이메일로 재가입하면,
          // Supabase가 (계정 열거 방지를 위해) 에러 없이 identities 빈 배열을 돌려준다 → 중복으로 처리한다.
          if (u && Array.isArray(u.identities) && u.identities.length === 0) {
            return { ok: false, msg: '이미 가입된 이메일입니다. 로그인하거나 비밀번호 재설정을 이용해주세요.' };
          }
          if (!r.data.session) {
            // 이메일 인증이 켜져 있는 프로젝트 — 메일 확인 후 로그인해야 한다
            return { ok: true, needConfirm: true };
          }
          return loadProfile(r.data.user).then(function () { return { ok: true }; });
        });
    },

    login: function (email, pw, captchaToken) {
      var opts = {};
      if (captchaToken) opts.captchaToken = captchaToken;
      return client.auth.signInWithPassword({ email: String(email).trim().toLowerCase(), password: pw, options: opts })
        .then(function (r) {
          if (r.error) return { ok: false, msg: koAuthMsg(r.error) };
          return loadProfile(r.data.user).then(function () { return { ok: true }; });
        });
    },

    logout: function () {
      profile = null;
      return client.auth.signOut();
    },

    // 비밀번호 재설정 메일 발송 (captcha 필요 시 토큰 전달)
    resetRequest: function (email, captchaToken) {
      email = String(email).trim().toLowerCase();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return Promise.resolve({ ok: false, msg: '이메일 형식이 올바르지 않습니다.' });
      var opts = { redirectTo: window.location.origin + '/reset.html' };
      if (captchaToken) opts.captchaToken = captchaToken;
      return client.auth.resetPasswordForEmail(email, opts).then(function (r) {
        if (r.error) return { ok: false, msg: koAuthMsg(r.error) };
        return { ok: true };
      });
    },

    // 이메일(아이디) 찾기 — 이름+휴대폰이 모두 맞아야 마스킹된 이메일을 돌려준다
    findEmail: function (name, phone) {
      var digits = String(phone || '').replace(/[^0-9]/g, '');
      return client.rpc('find_email_masked', { p_name: String(name || '').trim(), p_phone: digits })
        .then(function (r) {
          if (r.error) return { ok: false, msg: '조회 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.' };
          if (!r.data) return { ok: true, found: false };
          return { ok: true, found: true, masked: r.data };
        });
    },

    // 복구 링크로 들어온 세션에서 새 비밀번호 설정 (로그인 여부와 무관)
    setNewPassword: function (pw) {
      var pErr = pwError(pw); if (pErr) return Promise.resolve({ ok: false, msg: pErr });
      return client.auth.updateUser({ password: pw }).then(function (r) {
        if (r.error) return { ok: false, msg: koAuthMsg(r.error) };
        return { ok: true };
      });
    },

    // 휴대폰 번호 변경 (user_metadata)
    updatePhone: function (phone) {
      if (!profile) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      var digits = String(phone).replace(/[^0-9]/g, '');
      if (!/^01[016789][0-9]{7,8}$/.test(digits)) return Promise.resolve({ ok: false, msg: '휴대폰 번호를 정확히 입력해주세요.' });
      var formatted = digits.replace(/(\d{3})(\d{3,4})(\d{4})/, '$1-$2-$3');
      return client.auth.updateUser({ data: { phone: formatted } }).then(function (r) {
        if (r.error) return { ok: false, msg: '변경에 실패했습니다: ' + r.error.message };
        if (profile) profile.phone = formatted;
        return { ok: true, phone: formatted };
      });
    },

    // 소셜 로그인 시작 — 구글/카카오. 인증 후 사이트로 돌아온다.
    oauthLogin: function (provider) {
      if (provider !== 'google' && provider !== 'kakao') {
        return Promise.resolve({ ok: false, msg: '지원하지 않는 로그인입니다.' });
      }
      var redirectTo = (typeof location !== 'undefined' ? location.origin : '') + '/auth?social=1';
      return client.auth.signInWithOAuth({
        provider: provider,
        options: { redirectTo: redirectTo }
      }).then(function (r) {
        // 성공 시 브라우저가 provider 로 이동하므로 이 프라미스는 보통 반환 전에 페이지가 바뀐다
        if (r.error) return { ok: false, msg: koAuthMsg(r.error) };
        return { ok: true };
      });
    },

    // 소셜 최초 로그인 후 프로필 완성 — 닉네임·전화·약관동의를 채운다
    completeSocialProfile: function (data) {
      if (!profile) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      data = data || {};
      var nickname = String(data.nickname || '').trim();
      if (nickname.length < 2) return Promise.resolve({ ok: false, msg: '닉네임은 2자 이상 입력해주세요.' });
      var digits = String(data.phone || '').replace(/[^0-9]/g, '');
      if (!/^01[016789][0-9]{7,8}$/.test(digits)) return Promise.resolve({ ok: false, msg: '휴대폰 번호를 정확히 입력해주세요.' });
      var formatted = digits.replace(/(\d{3})(\d{3,4})(\d{4})/, '$1-$2-$3');
      var meta = {
        nickname: nickname,
        phone: formatted,
        terms_agreed: true,
        privacy_agreed: true,
        marketing_agreed: !!data.marketing,
        agreed_at: new Date().toISOString()
      };
      return client.auth.updateUser({ data: meta }).then(function (r) {
        if (r.error) return { ok: false, msg: '저장에 실패했습니다: ' + r.error.message };
        return client.from('profiles').update({ nickname: nickname }).eq('id', profile.id).then(function (r2) {
          if (r2.error) return { ok: false, msg: '저장에 실패했습니다: ' + r2.error.message };
          profile.nickname = nickname;
          profile.phone = formatted;
          profile.needsProfile = false;
          return { ok: true };
        });
      });
    },

    // 회원 탈퇴 — RPC가 auth.users 를 지우면 모든 데이터가 cascade 파기됨
    deleteAccount: function () {
      if (!profile) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      return client.rpc('delete_own_account').then(function (r) {
        if (r.error) return { ok: false, msg: '탈퇴 처리에 실패했습니다: ' + r.error.message };
        profile = null;
        return client.auth.signOut().then(function () { return { ok: true }; });
      });
    },

    // 실명 변경 (본인·비공개) — profiles.name + 메타데이터 동시 갱신
    updateName: function (name) {
      if (!profile) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      name = String(name).trim();
      var nErr = nameError(name); if (nErr) return Promise.resolve({ ok: false, msg: nErr });
      return client.from('profiles').update({ name: name }).eq('id', profile.id)
        .then(function (r) {
          if (r.error) return { ok: false, msg: '변경에 실패했습니다: ' + r.error.message };
          return client.auth.updateUser({ data: { name: name } }).then(function () {
            profile.name = name; return { ok: true };
          });
        });
    },

    // 닉네임 변경 (공개 표시) — profiles.nickname + 메타데이터 동시 갱신
    updateNickname: function (nickname) {
      if (!profile) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      nickname = String(nickname).trim();
      if (nickname.length < 2) return Promise.resolve({ ok: false, msg: '닉네임은 2자 이상 입력해주세요.' });
      return client.from('profiles').update({ nickname: nickname }).eq('id', profile.id)
        .then(function (r) {
          if (r.error) return { ok: false, msg: '변경에 실패했습니다: ' + r.error.message };
          return client.auth.updateUser({ data: { nickname: nickname } }).then(function () {
            profile.nickname = nickname; return { ok: true };
          });
        });
    },

    updatePassword: function (pw) {
      if (!profile) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      var pErr = pwError(pw); if (pErr) return Promise.resolve({ ok: false, msg: pErr });
      return client.auth.updateUser({ password: pw }).then(function (r) {
        if (r.error) return { ok: false, msg: koAuthMsg(r.error) };
        return { ok: true };
      });
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
        .then(function (r) {
          if (r.error) {
            // RLS로 막히면(유료 강의 자가수강) 안내 메시지로 변환
            if (/row-level security|permission|policy/i.test(r.error.message || '')) {
              throw new Error('이 강의는 결제 또는 코치 승인 후 수강할 수 있습니다.');
            }
            throw r.error;
          }
        });
    },

    /* 코치용 — 회원별 수강 권한 부여/회수 */
    allEnrollments: function () {
      return client.from('enrollments').select('user_id,course_id')
        .then(function (r) {
          if (r.error) throw r.error;
          return r.data || [];
        });
    },
    grantEnrollment: function (userId, courseId) {
      return client.from('enrollments')
        .upsert({ user_id: userId, course_id: courseId }, { onConflict: 'user_id,course_id' })
        .then(function (r) { if (r.error) throw r.error; });
    },
    revokeEnrollment: function (userId, courseId) {
      return client.from('enrollments').delete()
        .eq('user_id', userId).eq('course_id', courseId)
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
        .select('id,text,created_at,author:profiles(nickname,role)')
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

    /* 수강평·별점 */
    // 특정 강의의 후기 목록 (최신순) — 누구나 조회 가능
    courseReviews: function (courseId) {
      return client.from('reviews')
        .select('id,rating,text,created_at,author_id,author:profiles(nickname,role)')
        .eq('course_id', courseId).order('created_at', { ascending: false })
        .then(function (r) {
          if (r.error) throw r.error;
          return (r.data || []).map(function (row) {
            var a = mapAuthor(row);
            return { id: row.id, name: a.name, coach: a.coach, authorId: row.author_id,
                     rating: row.rating, text: row.text, ts: Date.parse(row.created_at) };
          });
        });
    },

    // 전체 강의 평점 집계 { courseId: { avg, count } } — 카드용, 한 번의 쿼리
    reviewStats: function () {
      return client.from('reviews').select('course_id,rating')
        .then(function (r) {
          if (r.error) throw r.error;
          var m = {};
          (r.data || []).forEach(function (row) {
            var s = m[row.course_id] || (m[row.course_id] = { sum: 0, count: 0 });
            s.sum += row.rating; s.count += 1;
          });
          Object.keys(m).forEach(function (k) { m[k].avg = m[k].sum / m[k].count; });
          return m;
        });
    },

    // 내가 이 강의에 남긴 후기 (수정·삭제 판별용)
    myReview: function (courseId) {
      if (!profile) return Promise.resolve(null);
      return client.from('reviews').select('id,rating,text,created_at')
        .eq('course_id', courseId).eq('author_id', profile.id).maybeSingle()
        .then(function (r) {
          if (r.error) throw r.error;
          if (!r.data) return null;
          return { id: r.data.id, rating: r.data.rating, text: r.data.text, ts: Date.parse(r.data.created_at) };
        });
    },

    // 후기 작성/수정 (upsert) — RLS가 수강 이력 없는 작성을 거부한다
    addReview: function (courseId, rating, text) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      rating = Math.max(1, Math.min(5, parseInt(rating, 10) || 0));
      return client.from('reviews')
        .upsert({ course_id: courseId, author_id: profile.id, rating: rating, text: String(text || '').trim() },
                { onConflict: 'course_id,author_id' })
        .then(function (r) {
          if (r.error) {
            if (/row-level security|policy|permission/i.test(r.error.message || '')) {
              throw new Error('수강 후기는 해당 강의를 수강한 회원만 작성할 수 있습니다.');
            }
            throw r.error;
          }
        });
    },

    // 후기 삭제 — 본인 것(id 없이 강의 기준) 또는 코치가 특정 id 삭제
    deleteReview: function (courseId, reviewId) {
      if (!profile) return Promise.reject(new Error('로그인이 필요합니다'));
      var q = client.from('reviews').delete();
      q = reviewId ? q.eq('id', reviewId) : q.eq('course_id', courseId).eq('author_id', profile.id);
      return q.then(function (r) { if (r.error) throw r.error; });
    },

    /* 커뮤니티 */
    posts: function () {
      return client.from('posts')
        .select('id,cat,title,body,created_at,author_id,author:profiles(nickname,role),comments:post_comments(id,text,created_at,author:profiles(nickname,role))')
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
              name: a.name, authorId: row.author_id, coach: a.coach, ts: Date.parse(row.created_at),
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

    /* 관리자 — 이메일은 코치만 볼 수 있게 서버 함수(get_members)로 조회.
       함수가 아직 없으면(구버전 스키마) 이메일 없는 목록으로 폴백. */
    members: function () {
      return client.rpc('get_members').then(function (r) {
        if (!r.error && Array.isArray(r.data)) {
          return r.data.map(function (row) {
            return { id: row.id, name: row.name, nickname: row.nickname, email: row.email, role: row.role, joined: Date.parse(row.joined) };
          });
        }
        // 폴백 — 실명은 컬럼 제한으로 못 읽으니 닉네임만
        return client.from('profiles').select('id,nickname,role,joined').order('joined', { ascending: false })
          .then(function (r2) {
            if (r2.error) throw r2.error;
            return (r2.data || []).map(function (row) {
              return { id: row.id, name: row.nickname, nickname: row.nickname, email: '(코치 전용)', role: row.role, joined: Date.parse(row.joined) };
            });
          });
      });
    }
  };
}
