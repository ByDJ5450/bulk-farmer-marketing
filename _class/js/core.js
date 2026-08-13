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

/* ---------- 입력 검증 (가입·변경 공통) ---------- */
// 이름(실명): 한글 또는 영문만(공백 허용). 통과 시 '' 반환.
function nameError(name) {
  name = String(name == null ? '' : name).trim();
  if (name.length < 2) return '이름(실명)은 2자 이상 입력해주세요.';
  if (!/^[가-힣a-zA-Z\s]+$/.test(name)) return '이름은 한글 또는 영문만 입력할 수 있습니다.';
  return '';
}
// 비밀번호: 8자 이상 + 영문 대/소문자 + 특수문자 각 1개 이상, 한글 불가. 통과 시 '' 반환.
function pwError(pw) {
  pw = String(pw == null ? '' : pw);
  if (/[가-힣ㄱ-ㅎㅏ-ㅣ]/.test(pw)) return '비밀번호에 한글은 사용할 수 없습니다.';
  if (pw.length < 8) return '비밀번호는 8자 이상이어야 합니다.';
  if (!/[A-Z]/.test(pw)) return '비밀번호에 영문 대문자를 1자 이상 포함해주세요.';
  if (!/[a-z]/.test(pw)) return '비밀번호에 영문 소문자를 1자 이상 포함해주세요.';
  if (!/[^A-Za-z0-9]/.test(pw)) return '비밀번호에 특수문자를 1자 이상 포함해주세요.';
  return '';
}
// 비밀번호 각 조건의 충족 여부를 반환 (실시간 체크리스트용)
function pwReqs(pw) {
  pw = String(pw == null ? '' : pw);
  return {
    len: pw.length >= 8,
    upper: /[A-Z]/.test(pw),
    lower: /[a-z]/.test(pw),
    special: /[^A-Za-z0-9]/.test(pw)
  };
}
// 비밀번호 입력창 ↔ 조건 체크리스트(li[data-req]) 실시간 연결
function bindPwReqs(input, listEl) {
  if (!input || !listEl) return;
  var items = listEl.querySelectorAll('li[data-req]');
  function update() {
    var r = pwReqs(input.value);
    for (var i = 0; i < items.length; i++) {
      var li = items[i];
      li.classList.toggle('ok', !!r[li.getAttribute('data-req')]);
    }
  }
  input.addEventListener('input', update);
  update();
}
// 입력창에서 한글을 실시간 제거 (비밀번호 필드용)
function blockHangul(input) {
  if (!input || input.dataset.noHangul) return;
  input.dataset.noHangul = '1';
  var composing = false;
  input.addEventListener('compositionstart', function () { composing = true; });
  input.addEventListener('compositionend', function () { composing = false; scrub(); });
  input.addEventListener('input', function (e) { if (!composing && !(e && e.isComposing)) scrub(); });
  function scrub() {
    var cleaned = input.value.replace(/[가-힣ㄱ-ㅎㅏ-ㅣ]/g, '');
    if (cleaned !== input.value) input.value = cleaned;
  }
}
// 이름 입력창 — 한글·영문·공백만 남기고 실시간 제거 (IME 조합 중에는 건드리지 않음)
function nameFilter(input) {
  if (!input || input.dataset.nameFilter) return;
  input.dataset.nameFilter = '1';
  var composing = false;
  input.addEventListener('compositionstart', function () { composing = true; });
  input.addEventListener('compositionend', function () { composing = false; scrub(); });
  input.addEventListener('input', function (e) { if (!composing && !(e && e.isComposing)) scrub(); });
  function scrub() {
    // 완성 한글·영문·공백만 허용. 미완성 자모(ㄱ-ㅎㅏ-ㅣ)는 조합 중에만 잠시 존재하므로 여기서만 제거.
    var cleaned = input.value.replace(/[^가-힣a-zA-Z\s]/g, '');
    if (cleaned !== input.value) input.value = cleaned;
  }
}

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

// 중앙 안내 모달. opts: {title, body, btnText, onClose, dismissible}
function showModal(opts) {
  opts = opts || {};
  var old = $('.modal-ov');
  if (old && old.parentNode) old.parentNode.removeChild(old);
  var ov = document.createElement('div');
  ov.className = 'modal-ov';
  var card = document.createElement('div');
  card.className = 'modal-card';
  if (opts.icon) { var ic = document.createElement('div'); ic.className = 'modal-icon'; ic.textContent = opts.icon; card.appendChild(ic); }
  var h = document.createElement('h3'); h.textContent = opts.title || '';
  var p = document.createElement('p'); p.textContent = opts.body || '';
  var btn = document.createElement('button'); btn.className = 'btn btn-green'; btn.textContent = opts.btnText || '확인';
  function close() { if (ov.parentNode) ov.parentNode.removeChild(ov); document.removeEventListener('keydown', onKey); if (opts.onClose) opts.onClose(); }
  function onKey(e) { if (e.key === 'Escape' && opts.dismissible !== false) close(); }
  btn.addEventListener('click', close);
  ov.addEventListener('click', function (e) { if (e.target === ov && opts.dismissible !== false) close(); });
  document.addEventListener('keydown', onKey);
  card.appendChild(h); card.appendChild(p); card.appendChild(btn);
  ov.appendChild(card);
  document.body.appendChild(ov);
  btn.focus();
  return close;
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

/* ---------- 별점 ---------- */
// 정수 별점(1~5)을 채운/빈 별로. 평균 표시는 반올림해 별을 그린다.
function starsHTML(rating) {
  var full = Math.round(Number(rating) || 0);
  var out = '';
  for (var i = 1; i <= 5; i++) {
    out += '<span class="star' + (i <= full ? ' on' : '') + '">★</span>';
  }
  return '<span class="stars" aria-label="별점 ' + full + '점">' + out + '</span>';
}
// 카드용 요약 — 평균 별 + 숫자 + (개수). 후기가 없으면 빈 문자열.
function ratingSummaryHTML(stat) {
  if (!stat || !stat.count) return '';
  return '<span class="rating-sum">' + starsHTML(stat.avg) +
    '<b>' + stat.avg.toFixed(1) + '</b><span class="cnt">(' + stat.count + ')</span></span>';
}

/* ---------- 공통 UI 조각 ---------- */
function commentHTML(c) {
  return '<div class="comment">' +
    '<div class="c-head"><strong>' + esc(c.name) + '</strong>' +
    (c.coach ? '<span class="coach">코치</span>' : '') +
    '<span class="time">' + timeAgo(c.ts) + '</span></div>' +
    '<p>' + esc(c.text) + '</p></div>';
}

// st: { enrolled: bool, pct: number, rating: {avg,count} } | null
function courseCardHTML(c, st) {
  var thumbTitle = esc(c.thumbTitle || c.title).replace(/\n/g, '<br>');
  var priceLabel = (st && st.enrolled) ? '수강 중 ' + st.pct + '%' : fmtPrice(c.price);
  var rating = st && st.rating ? ratingSummaryHTML(st.rating) : '';
  return '<a class="course-card" href="course.html?id=' + esc(c.id) + '">' +
    '<div class="thumb thumb-' + esc(c.color) + '">' +
    '<span class="thumb-badge">' + esc(c.badge) + '</span>' +
    '<strong>' + thumbTitle + '</strong></div>' +
    '<div class="card-body"><h3>' + esc(c.title) + '</h3>' +
    '<p>' + esc(c.tagline) + '</p>' +
    (rating ? '<div class="card-rating">' + rating + '</div>' : '') +
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
      '<a class="user-name" href="mypage.html" title="마이페이지">👤 ' + esc(u.nickname || u.name) +
      (u.role === 'coach' ? ' <b class="coach-tag">코치</b>' : '') + '</a>' +
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
    ['about.html', 'about', '코치 소개'],
    ['index.html#courses', 'courses', '강의'],
    ['community.html', 'community', '커뮤니티']
  ];
  // 관리자 메뉴는 코치 계정으로 로그인했을 때만 보인다
  var meNow = API.me();
  if (meNow && meNow.role === 'coach') {
    links.push(['admin.html', 'admin', '관리자']);
  }
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
    '<p>55kg에서 88kg까지, 경험으로 가르치는 벌크업 클래스</p>' +
    '<p class="dim">1:1 코칭 문의 · 인스타그램 @bulk_farmer · K-Classic 클래식 보디빌딩 3위</p>' +
    '<p class="footer-legal"><a href="terms.html">이용약관</a><a href="privacy.html">개인정보 처리방침</a><a href="refund.html">환불정책</a></p></div>';
}

/* 자주 묻는 질문 — 홈·강의 상세에서 공용으로 쓰는 아코디언 HTML */
function faqHTML() {
  var qa = [
    ['운동을 한 번도 안 해봤는데 괜찮을까요?', '괜찮습니다. 왜 지금까지 벌크업이 안 됐는지 원리부터 시작해, 마른 체형에게 맞는 첫 루틴 구성까지 단계별로 알려드립니다.'],
    ['마른 체형인데 정말 몸이 커지나요?', '코치 본인이 55kg에서 88kg까지 늘린 방법입니다. 살이 안 찌는 체질은 없습니다. 칼로리 잉여와 훈련 원리를 지키면 몸은 바뀝니다.'],
    ['강의만 들어도 되나요? 1:1 코칭은 언제 필요한가요?', '스스로 설계하고 싶다면 강의로 충분합니다. 내 몸 상태에 맞게 직접 봐주길 원하면 1:1 코칭이 맞습니다. 코칭 문의는 인스타그램 @bulk_farmer DM으로 받습니다.'],
    ['입이 짧아서 많이 못 먹어요.', '그 고민을 다루는 강의가 따로 있습니다. 한 끼 칼로리를 올리는 공식과, 간식으로 하루 총량을 채우는 법을 알려드립니다.'],
    ['헬스장이 꼭 있어야 하나요?', '기구 운동이 효율적이라 헬스장을 권합니다. 다만 원리를 알면 환경에 맞게 응용할 수 있습니다.'],
    ['결제와 수강은 어떻게 하나요?', '무료 강의는 회원가입 후 바로 볼 수 있습니다. 유료 강의와 1:1 코칭은 인스타그램 @bulk_farmer DM으로 문의해주세요.']
  ];
  return '<div class="faq-list">' + qa.map(function (x) {
    return '<details class="faq-item"><summary>' + esc(x[0]) + '</summary><div class="faq-a">' + esc(x[1]) + '</div></details>';
  }).join('') + '</div>';
}

/* 비밀번호 입력에 보기/숨기기 토글(눈 아이콘)을 붙인다. 여러 번 호출해도 안전. */
function initPwToggles(root) {
  var scope = root || document;
  var inputs = scope.querySelectorAll('input[type="password"]');
  for (var i = 0; i < inputs.length; i++) {
    (function (inp) {
      if (inp.dataset.pwToggle) return;
      inp.dataset.pwToggle = '1';
      var wrap = document.createElement('div');
      wrap.className = 'pw-wrap';
      inp.parentNode.insertBefore(wrap, inp);
      wrap.appendChild(inp);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'pw-eye';
      btn.setAttribute('aria-label', '비밀번호 표시');
      btn.textContent = '👁';
      btn.addEventListener('click', function () {
        var show = inp.type === 'password';
        inp.type = show ? 'text' : 'password';
        btn.classList.toggle('on', show);
        btn.setAttribute('aria-label', show ? '비밀번호 숨기기' : '비밀번호 표시');
      });
      wrap.appendChild(btn);
    })(inputs[i]);
  }
}
