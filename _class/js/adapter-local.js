// 벌크농부 클래스 — 로컬 어댑터
// 서버 설정이 없을 때 사용. 모든 데이터를 이 브라우저의 localStorage에 저장한다.
// (API 모양은 adapter-supabase.js 와 동일 — 전부 Promise 반환)
'use strict';

var LocalAPI = (function () {
  var DB_KEY = 'bulkclass_db_v1';
  var USERS_KEY = 'bulkclass_users_v1';
  var SESSION_KEY = 'bulkclass_session_v1';
  var COACH_CODE = 'bulk88'; // 가입 시 이 코드를 입력하면 코치(관리자) 계정

  /* ----- 데이터 저장소 ----- */
  var db = null;

  function load() {
    try {
      var raw = localStorage.getItem(DB_KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.courses)) {
          db = parsed;
          db.comments = db.comments || {};
          db.posts = db.posts || [];
          // 계정 도입 전 구버전 데이터 이관 (수강·진도를 회원 단위 구조로)
          if (!db.enrollments || Array.isArray(db.enrollments)) db.enrollments = {};
          var oldShape = false;
          if (db.progress && typeof db.progress === 'object') {
            for (var k in db.progress) { if (Array.isArray(db.progress[k])) { oldShape = true; break; } }
          }
          if (!db.progress || oldShape) db.progress = {};
          return;
        }
      }
    } catch (e) {
      console.error('저장 데이터 손상 — 시드로 복구합니다', e);
    }
    db = JSON.parse(JSON.stringify(window.SEED));
    save();
  }

  function save() {
    try { localStorage.setItem(DB_KEY, JSON.stringify(db)); }
    catch (e) { console.error('저장 실패', e); }
  }

  load();

  /* ----- 계정 ----- */
  // 비밀번호는 원문 대신 SHA-256 해시(계정별 salt)로 저장한다.
  function hashPw(pw, salt) {
    var text = salt + '::' + pw;
    if (window.crypto && crypto.subtle && crypto.subtle.digest) {
      var data = new TextEncoder().encode(text);
      return crypto.subtle.digest('SHA-256', data).then(function (buf) {
        return Array.prototype.map.call(new Uint8Array(buf), function (b) {
          return ('0' + b.toString(16)).slice(-2);
        }).join('');
      });
    }
    // 보안 컨텍스트가 아닐 때의 폴백 (프로토타입용 단순 해시)
    var h = 5381;
    for (var i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) >>> 0;
    return Promise.resolve('fb-' + h.toString(16));
  }

  function users() {
    try {
      var arr = JSON.parse(localStorage.getItem(USERS_KEY) || '[]');
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function saveUsers(arr) { localStorage.setItem(USERS_KEY, JSON.stringify(arr)); }
  function findUser(email) {
    email = String(email).trim().toLowerCase();
    var list = users();
    for (var i = 0; i < list.length; i++) {
      if (list[i].email === email) return list[i];
    }
    return null;
  }
  function sessionUser() {
    var email = localStorage.getItem(SESSION_KEY);
    return email ? findUser(email) : null;
  }
  function pub(u) {
    return u ? { id: u.id, name: u.name, email: u.email, role: u.role, joined: u.joined } : null;
  }

  /* ----- 공개 API ----- */
  return {
    mode: 'local',

    init: function () { return Promise.resolve(); },

    me: function () { return pub(sessionUser()); },

    signup: function (name, email, pw, coachCode) {
      name = String(name).trim();
      email = String(email).trim().toLowerCase();
      coachCode = String(coachCode || '').trim();
      if (name.length < 2) return Promise.resolve({ ok: false, msg: '이름(닉네임)은 2자 이상 입력해주세요.' });
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return Promise.resolve({ ok: false, msg: '이메일 형식이 올바르지 않습니다.' });
      if (String(pw).length < 6) return Promise.resolve({ ok: false, msg: '비밀번호는 6자 이상이어야 합니다.' });
      if (findUser(email)) return Promise.resolve({ ok: false, msg: '이미 가입된 이메일입니다. 로그인해주세요.' });
      var dupName = users().some(function (u) { return u.name === name; });
      if (dupName) return Promise.resolve({ ok: false, msg: '이미 사용 중인 이름입니다. 다른 이름을 골라주세요.' });
      if (coachCode && coachCode !== COACH_CODE) return Promise.resolve({ ok: false, msg: '코치 코드가 올바르지 않습니다. 일반 가입은 비워두세요.' });

      var salt = uid();
      return hashPw(pw, salt).then(function (hash) {
        var list = users();
        list.push({
          id: uid(),
          name: name,
          email: email,
          salt: salt,
          hash: hash,
          role: coachCode === COACH_CODE ? 'coach' : 'member',
          joined: Date.now()
        });
        saveUsers(list);
        localStorage.setItem(SESSION_KEY, email);
        return { ok: true };
      });
    },

    login: function (email, pw) {
      var user = findUser(email);
      if (!user) return Promise.resolve({ ok: false, msg: '가입되지 않은 이메일입니다.' });
      return hashPw(pw, user.salt).then(function (hash) {
        if (hash !== user.hash) return { ok: false, msg: '비밀번호가 일치하지 않습니다.' };
        localStorage.setItem(SESSION_KEY, user.email);
        return { ok: true };
      });
    },

    logout: function () {
      localStorage.removeItem(SESSION_KEY);
      return Promise.resolve();
    },

    updateName: function (name) {
      var u = sessionUser();
      if (!u) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      name = String(name).trim();
      if (name.length < 2) return Promise.resolve({ ok: false, msg: '이름(닉네임)은 2자 이상 입력해주세요.' });
      var dup = users().some(function (x) { return x.name === name && x.email !== u.email; });
      if (dup) return Promise.resolve({ ok: false, msg: '이미 사용 중인 이름입니다.' });
      var list = users();
      for (var i = 0; i < list.length; i++) {
        if (list[i].email === u.email) { list[i].name = name; break; }
      }
      saveUsers(list);
      return Promise.resolve({ ok: true });
    },

    updatePassword: function (pw) {
      var u = sessionUser();
      if (!u) return Promise.resolve({ ok: false, msg: '로그인이 필요합니다.' });
      if (String(pw).length < 6) return Promise.resolve({ ok: false, msg: '비밀번호는 6자 이상이어야 합니다.' });
      var salt = uid();
      return hashPw(pw, salt).then(function (hash) {
        var list = users();
        for (var i = 0; i < list.length; i++) {
          if (list[i].email === u.email) { list[i].salt = salt; list[i].hash = hash; break; }
        }
        saveUsers(list);
        return { ok: true };
      });
    },

    /* 강의 */
    courses: function () { return Promise.resolve(db.courses); },

    saveCourse: function (course) {
      for (var i = 0; i < db.courses.length; i++) {
        if (db.courses[i].id === course.id) { db.courses[i] = course; save(); return Promise.resolve(); }
      }
      db.courses.push(course);
      save();
      return Promise.resolve();
    },

    deleteCourse: function (id) {
      db.courses = db.courses.filter(function (c) { return c.id !== id; });
      save();
      return Promise.resolve();
    },

    /* 수강·진도 (회원별) */
    myEnrollments: function () {
      var u = sessionUser();
      if (!u) return Promise.resolve([]);
      return Promise.resolve(db.enrollments[u.email] || []);
    },

    enroll: function (courseId) {
      var u = sessionUser();
      if (!u) return Promise.reject(new Error('로그인이 필요합니다'));
      // 유료 강의는 스스로 수강 불가 (코치는 예외 — 미리보기용)
      var c = null;
      for (var i = 0; i < db.courses.length; i++) { if (db.courses[i].id === courseId) { c = db.courses[i]; break; } }
      var paid = c && Number(c.price) > 0;
      if (paid && u.role !== 'coach') {
        return Promise.reject(new Error('이 강의는 결제 또는 코치 승인 후 수강할 수 있습니다.'));
      }
      if (!db.enrollments[u.email]) db.enrollments[u.email] = [];
      if (db.enrollments[u.email].indexOf(courseId) < 0) {
        db.enrollments[u.email].push(courseId);
        save();
      }
      return Promise.resolve();
    },

    /* 코치용 — 회원별 수강 권한 부여/회수 */
    allEnrollments: function () {
      var out = [];
      var byEmail = {};
      users().forEach(function (x) { byEmail[x.email] = x.id; });
      Object.keys(db.enrollments).forEach(function (email) {
        (db.enrollments[email] || []).forEach(function (cid) {
          out.push({ user_id: byEmail[email] || email, course_id: cid });
        });
      });
      return Promise.resolve(out);
    },
    grantEnrollment: function (userId, courseId) {
      var user = users().filter(function (x) { return x.id === userId; })[0];
      if (!user) return Promise.reject(new Error('회원을 찾을 수 없습니다'));
      if (!db.enrollments[user.email]) db.enrollments[user.email] = [];
      if (db.enrollments[user.email].indexOf(courseId) < 0) {
        db.enrollments[user.email].push(courseId);
        save();
      }
      return Promise.resolve();
    },
    revokeEnrollment: function (userId, courseId) {
      var user = users().filter(function (x) { return x.id === userId; })[0];
      if (!user) return Promise.resolve();
      var arr = db.enrollments[user.email] || [];
      var i = arr.indexOf(courseId);
      if (i >= 0) { arr.splice(i, 1); save(); }
      return Promise.resolve();
    },

    myProgress: function (courseId) {
      var u = sessionUser();
      if (!u) return Promise.resolve([]);
      var mine = db.progress[u.email] || {};
      return Promise.resolve(mine[courseId] || []);
    },

    setDone: function (courseId, lecId, done) {
      var u = sessionUser();
      if (!u) return Promise.reject(new Error('로그인이 필요합니다'));
      if (!db.progress[u.email]) db.progress[u.email] = {};
      if (!db.progress[u.email][courseId]) db.progress[u.email][courseId] = [];
      var list = db.progress[u.email][courseId];
      var i = list.indexOf(lecId);
      if (done && i < 0) list.push(lecId);
      if (!done && i >= 0) list.splice(i, 1);
      save();
      return Promise.resolve();
    },

    /* 강의실 댓글 */
    lectureComments: function (courseId, lecId) {
      return Promise.resolve(db.comments[courseId + '/' + lecId] || []);
    },

    addLectureComment: function (courseId, lecId, text) {
      var u = sessionUser();
      if (!u) return Promise.reject(new Error('로그인이 필요합니다'));
      var key = courseId + '/' + lecId;
      if (!db.comments[key]) db.comments[key] = [];
      db.comments[key].push({
        id: uid(),
        name: u.name,
        coach: u.role === 'coach',
        text: text,
        ts: Date.now()
      });
      save();
      return Promise.resolve();
    },

    /* 커뮤니티 */
    posts: function () { return Promise.resolve(db.posts); },

    addPost: function (cat, title, body) {
      var u = sessionUser();
      if (!u) return Promise.reject(new Error('로그인이 필요합니다'));
      if (cat === 'notice' && u.role !== 'coach') return Promise.reject(new Error('공지는 코치만 쓸 수 있습니다'));
      db.posts.unshift({
        id: uid(),
        cat: cat,
        title: title,
        body: body,
        name: u.name,
        authorId: u.id,
        coach: u.role === 'coach',
        ts: Date.now(),
        comments: []
      });
      save();
      return Promise.resolve();
    },

    addPostComment: function (postId, text) {
      var u = sessionUser();
      if (!u) return Promise.reject(new Error('로그인이 필요합니다'));
      for (var i = 0; i < db.posts.length; i++) {
        if (db.posts[i].id === postId) {
          db.posts[i].comments.push({
            id: uid(),
            name: u.name,
            coach: u.role === 'coach',
            text: text,
            ts: Date.now()
          });
          save();
          break;
        }
      }
      return Promise.resolve();
    },

    /* 관리자 */
    members: function () {
      return Promise.resolve(users().map(function (u) {
        return { id: u.id, name: u.name, email: u.email, role: u.role, joined: u.joined };
      }));
    },

    /* 로컬 모드 전용 — 백업/복원/초기화 */
    exportData: function () {
      return { db: db, users: users() };
    },
    importData: function (obj) {
      if (!obj || !obj.db || !Array.isArray(obj.db.courses)) throw new Error('형식 오류');
      db = obj.db;
      save();
      if (Array.isArray(obj.users)) saveUsers(obj.users);
      load();
    },
    resetData: function () {
      localStorage.removeItem(DB_KEY);
      load();
    }
  };
})();
