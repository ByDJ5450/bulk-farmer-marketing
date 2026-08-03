// 벌크농부 클래스 — 공통 헬퍼 + 헤더/푸터 (데이터 로직은 adapter-*.js)
'use strict';

function $(sel, root) { return (root || document).querySelector(sel); }
function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

function qsParam(name) { return new URLSearchParams(location.search).get(name); }

function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }

function fmtPrice(n) { return n > 0 ? Number(n).toLocaleString('ko-KR') + '원' : '무료'; }

function timeAgo(ts) {
  var diff = Date.now() - ts;
  var m = Math.floor(diff / 60000);
  if (m < 1) return '방금 전';
  if (m < 60) return m + '분 전';
  var h = Math.floor(m / 60);
  if (h < 24) return h + '시간 전';
  var d = Math.floor(h / 24);
  if (d < 30) return d + '일 전';
  return new Date(ts).toLocaleDateString('ko-KR');
}

// 유튜브 링크 → embed URL (watch / youtu.be / shorts / embed / live 지원)
function ytEmbed(url) {
  if (!url) return null;
  var m = String(url).match(/(?:youtu\.be\/|[?&]v=|shorts\/|embed\/|live\/)([A-Za-z0-9_-]{11})/);
  return m ? 'https://www.youtube.com/embed/' + m[1] + '?rel=0' : null;
}

function toast(msg) {
  var old = $('.toast');
  if (old) old.remove();
  var el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function () { el.remove(); }, 2600);
}

function herePath() { return location.pathname.split('/').pop() + location.search; }

function gotoLogin() {
  location.href = 'auth.html?next=' + encodeURIComponent(herePath());
}

/* ---------- 강의 구조 헬퍼 ---------- */
function allLectures(course) {
  return course.sections.reduce(function (acc, s) { return acc.concat(s.lectures); }, []);
}
function lectureCount(course) { return allLectures(course).length; }
function sectionOf(course, lecId) {
  for (var i = 0; i < course.sections.length; i++) {
    for (var j = 0; j < course.sections[i].lectures.length; j++) {
      if (course.sections[i].lectures[j].id === lecId) return course.sections[i];
    }
  }
  return null;
}

var CAT_LABEL = { notice: '공지', qna: '질문', free: '자유' };

/* ---------- 공통 UI 조각 ---------- */
function commentHTML(c) {
  return '<div class="comment">' +
    '<div class="c-head"><strong>' + esc(c.name) + '</strong>' +
    (c.coach ? '<span class="coach">코치</span>' : '') +
    '<span class="time">' + timeAgo(c.ts) + '</span></div>' +
    '<p>' + esc(c.text) + '</p></div>';
}

// st: { enrolled: bool, pct: number } | null
function courseCardHTML(c, st) {
  var thumbTitle = esc(c.thumbTitle || c.title).replace(/\n/g, '<br>');
  var priceLabel = (st && st.enrolled) ? '수강 중 ' + st.pct + '%' : fmtPrice(c.price);
  return '<a class="course-card" href="course.html?id=' + esc(c.id) + '">' +
    '<div class="thumb thumb-' + esc(c.color) + '">' +
    '<span class="thumb-badge">' + esc(c.badge) + '</span>' +
    '<strong>' + thumbTitle + '</strong></div>' +
    '<div class="card-body"><h3>' + esc(c.title) + '</h3>' +
    '<p>' + esc(c.tagline) + '</p>' +
    '<div class="card-meta"><span>' + lectureCount(c) + '강 · ' + esc(c.level) + '</span>' +
    '<span class="price">' + priceLabel + '</span>' +
    '</div></div></a>';
}

function updateUserChip() {
  var area = $('#userArea');
  if (!area) return;
  var u = API.me();
  if (u) {
    area.innerHTML =
      '<span class="user-name">👤 ' + esc(u.name) +
      (u.role === 'coach' ? ' <b class="coach-tag">코치</b>' : '') + '</span>' +
      '<button class="user-chip" id="logoutBtn" type="button">로그아웃</button>';
    $('#logoutBtn').addEventListener('click', function () {
      API.logout().then(function () {
        toast('로그아웃 되었습니다.');
        setTimeout(function () { location.href = 'index.html'; }, 500);
      });
    });
  } else {
    area.innerHTML =
      '<button class="user-chip" id="loginBtn" type="button">로그인</button>' +
      '<button class="user-chip chip-primary" id="signupBtn" type="button">회원가입</button>';
    $('#loginBtn').addEventListener('click', gotoLogin);
    $('#signupBtn').addEventListener('click', function () {
      location.href = 'auth.html?mode=signup&next=' + encodeURIComponent(herePath());
    });
  }
}

// API.init() 이후에 호출할 것 (로그인 상태 표시 때문)
function renderHeader(active) {
  var el = $('#siteHeader');
  if (!el) return;
  var links = [
    ['index.html', 'home', '홈'],
    ['index.html#courses', 'courses', '강의'],
    ['community.html', 'community', '커뮤니티'],
    ['admin.html', 'admin', '관리자']
  ];
  var nav = links.map(function (l) {
    return '<a href="' + l[0] + '"' + (active === l[1] ? ' class="active"' : '') + '>' + l[2] + '</a>';
  }).join('');
  el.innerHTML = '<div class="header-inner">' +
    '<a class="logo" href="index.html">벌크농부<span>클래스</span></a>' +
    '<nav>' + nav + '</nav>' +
    '<div class="user-area" id="userArea"></div></div>';
  updateUserChip();
}

function renderFooter() {
  var el = $('#siteFooter');
  if (!el) return;
  el.innerHTML = '<div class="footer-inner">' +
    '<div class="logo">벌크농부<span>클래스</span></div>' +
    '<p>55kg 멸치에서 88kg까지 — 경험으로 가르치는 벌크업 클래스</p>' +
    '<p class="dim">1:1 코칭 문의 · 인스타그램 @bulk_farmer · K-Classic 클래식 보디빌딩 3위</p></div>';
}
