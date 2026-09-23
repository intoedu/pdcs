/* 폴앤다니엘기독학교 — 공통 스크립트 */
(function () {
  'use strict';

  /* 모바일 메뉴 */
  var toggle = document.querySelector('.nav-toggle');
  var gnb = document.getElementById('gnb');
  var top0 = document.querySelector('.site-top');
  /* 메뉴가 열리면 상단 바탕이 흰색이 된다. 그 사실을 상단 전체에 알려
     글자색 규칙이 "내려간 상태"와 똑같이 걸리게 한다.
     예전에 이 처리가 없어 흰 바탕에 흰 글씨로 배포된 적이 있다. */
  var setOpen = function (on) {
    if (toggle) { toggle.setAttribute('aria-expanded', String(on)); }
    if (gnb) { gnb.classList.toggle('is-open', on); gnb.setAttribute('aria-hidden', String(!on)); }
    if (top0) { top0.classList.toggle('is-open', on); }
  };
  if (toggle && gnb) {
    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    gnb.addEventListener('click', function (e) {
      if (e.target.tagName === 'A' && window.matchMedia('(max-width: 860px)').matches) setOpen(false);
    });
  }

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* 상단 바 — 내리면 흰 바탕으로 */
  var siteTop = document.querySelector('.site-top');
  if (siteTop) {
    var stuck = null;
    var syncTop = function () {
      var next = window.scrollY > 40;
      if (next !== stuck) { stuck = next; siteTop.classList.toggle('is-stuck', next); }
    };
    syncTop();
    window.addEventListener('scroll', syncTop, { passive: true });
  }

  /* 히어로 배경 — 스크롤보다 느리게 따라온다 */
  var heroMedia = document.querySelector('.hero__media');
  if (heroMedia && !reduced) {
    var pending = false;
    var moveHero = function () {
      var limit = window.innerHeight;
      var y = Math.min(window.scrollY, limit);
      heroMedia.style.transform = 'translate3d(0,' + (y * 0.26).toFixed(1) + 'px,0)';
      pending = false;
    };
    window.addEventListener('scroll', function () {
      if (!pending) { pending = true; requestAnimationFrame(moveHero); }
    }, { passive: true });
  }

  /* 히어로 사진 — 자동으로 넘어가고, 직접 넘길 수도 있다 */
  var slides = document.querySelectorAll('.hero__slide');
  var nums = document.querySelectorAll('.hero__num');
  if (slides.length > 1) {
    var idx = 0, timer = null, HOLD = 7000;
    var playBtn = document.getElementById('hero-play');
    var pauseIcon = playBtn && playBtn.querySelector('[data-icon="pause"]');
    var playIcon = playBtn && playBtn.querySelector('[data-icon="play"]');

    var show = function (i) {
      idx = (i + slides.length) % slides.length;
      for (var a = 0; a < slides.length; a++) slides[a].classList.toggle('is-active', a === idx);
      for (var c = 0; c < nums.length; c++) {
        if (c === idx) nums[c].setAttribute('aria-current', 'true');
        else nums[c].removeAttribute('aria-current');
      }
    };
    var start = function () { if (!reduced && !timer) timer = setInterval(function () { show(idx + 1); }, HOLD); };
    var stop = function () { if (timer) { clearInterval(timer); timer = null; } };

    /* 버튼 모양은 HTML 의 hidden 에 기대지 않고 항상 여기서 맞춘다.
       예전에 멈춤과 재생 아이콘이 동시에 보인 적이 있다 */
    /* SVG 요소에는 hidden 프로퍼티가 없다(HTMLElement 에만 있다).
       el.hidden = true 로는 화면이 바뀌지 않아 멈춤·재생 아이콘이 둘 다 보였다.
       속성을 직접 붙였다 뗀다. */
    var setHidden = function (el, on) {
      if (!el) return;
      if (on) el.setAttribute('hidden', ''); else el.removeAttribute('hidden');
    };
    var paint = function () {
      var running = !!timer;
      setHidden(pauseIcon, !running);
      setHidden(playIcon, running);
      if (playBtn) playBtn.setAttribute('aria-label', running ? '사진 자동 넘김 멈추기' : '사진 자동 넘김 다시 하기');
    };
    var restart = function () { stop(); start(); paint(); };

    start(); paint();

    Array.prototype.forEach.call(nums, function (n) {
      n.addEventListener('click', function () {
        show(parseInt(n.getAttribute('data-go'), 10) || 0);
        restart();
      });
    });
    var prev = document.getElementById('hero-prev');
    var next = document.getElementById('hero-next');
    if (prev) prev.addEventListener('click', function () { show(idx - 1); restart(); });
    if (next) next.addEventListener('click', function () { show(idx + 1); restart(); });
    if (playBtn) playBtn.addEventListener('click', function () {
      if (timer) { stop(); } else { start(); }
      paint();
    });

    /* 다른 탭에 가 있는 동안에는 돌리지 않는다 */
    var wasRunning = true;
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { wasRunning = !!timer; stop(); }
      else if (wasRunning) { start(); }
      paint();
    });
  }

  /* 스크롤 등장 */
  var targets = document.querySelectorAll('.reveal');
  var showAll = function () {
    Array.prototype.forEach.call(targets, function (el) { el.classList.add('is-in'); });
  };
  try {
    if (reduced || !('IntersectionObserver' in window)) {
      showAll();
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in');
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
      Array.prototype.forEach.call(targets, function (el) { io.observe(el); });
    }
  } catch (e) {
    showAll();
  }

  /* 숫자 카운트업 — 화면에 들어올 때 한 번 */
  var counters = document.querySelectorAll('[data-count]');
  function runCount(el) {
    var end = parseInt(el.getAttribute('data-count'), 10);
    var suffix = el.getAttribute('data-suffix') || '';
    if (isNaN(end)) return;
    if (reduced) { el.textContent = end + suffix; return; }
    var start = null, dur = 1100;
    function frame(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(end * eased) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  if (counters.length) {
    if (!('IntersectionObserver' in window)) {
      Array.prototype.forEach.call(counters, runCount);
    } else {
      var co = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { runCount(entry.target); co.unobserve(entry.target); }
        });
      }, { threshold: 0.4 });
      Array.prototype.forEach.call(counters, function (el) { co.observe(el); });
    }
  }

  /* 상담 신청 — 서버 없이, 메일 한 곳으로 모은다.
     예전에는 휴대폰이면 문자, 컴퓨터면 메일로 갈라졌다. 신청이 두 군데로
     흩어져 놓치기 쉬웠으므로 기기와 상관없이 메일로 통일한다. */
  var form = document.getElementById('inquiry-form');
  if (form) {
    var MAIL_TO = 'bcia_k@naver.com';

    var val = function (id) {
      var el = document.getElementById(id);
      return el ? el.value.trim() : '';
    };

    var compose = function () {
      var want = form.querySelector('input[name="want"]:checked');
      var rows = [
        '[입학 상담 신청]',
        '학부모: ' + val('pname'),
        '연락처: ' + val('phone'),
        '자녀 학년: ' + val('grade'),
        '희망: ' + (want ? want.value : '')
      ];
      if (val('email')) rows.push('이메일: ' + val('email'));
      if (val('msg')) { rows.push(''); rows.push(val('msg')); }
      return rows.join('\n');
    };

    var say = function (html) {
      var box = document.getElementById('form-message');
      if (!box) return;
      box.innerHTML = html;
      box.hidden = false;
      box.focus();
    };

    var missing = function () {
      var need = [['pname', '학부모 성함'], ['phone', '연락처'], ['grade', '자녀 학년']];
      for (var i = 0; i < need.length; i++) {
        if (!val(need[i][0])) {
          var el = document.getElementById(need[i][0]);
          if (el) el.focus();
          return need[i][1];
        }
      }
      var agree = document.getElementById('agree');
      if (agree && !agree.checked) { agree.focus(); return '개인정보 수집 · 이용 동의'; }
      return null;
    };

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var lack = missing();
      if (lack) { say('<b>' + lack + '</b>을(를) 입력해 주세요.'); return; }

      var body = compose();
      location.href = 'mailto:' + MAIL_TO
        + '?subject=' + encodeURIComponent('[입학 상담 신청] ' + (val('pname') || ''))
        + '&body=' + encodeURIComponent(body);
      // 메일 앱이 설정돼 있지 않으면 아무 일도 일어나지 않는다.
      // 그때 학부모가 막히지 않도록 복사 버튼과 받는 주소를 같이 알린다.
      say('메일 앱이 열립니다. <b>보내기</b>를 눌러 주세요.'
        + '<br>열리지 않으면 아래 <b>작성 내용 복사</b>를 누르고 <b>' + MAIL_TO + '</b> 로 보내 주십시오.'
        + '<br>메일이 어려우시면 <a href="tel:041-425-0085" style="color:inherit"><b>041-425-0085</b></a> 로 전화 주셔도 됩니다.');
    });

    var copyBtn = document.getElementById('copy-form');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var text = compose();
        var done = function () { say('작성하신 내용을 복사했습니다. 메일에 붙여넣어 <b>' + MAIL_TO + '</b> 로 보내 주십시오.'); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { say('<pre style="white-space:pre-wrap;margin:0;font-family:inherit">' + text + '</pre>'); });
        } else {
          say('<pre style="white-space:pre-wrap;margin:0;font-family:inherit">' + text + '</pre>');
        }
      });
    }
  }
})();
