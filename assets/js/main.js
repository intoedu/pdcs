/* 폴앤다니엘기독학교 — 공통 스크립트 */
(function () {
  'use strict';

  /* 모바일 메뉴 */
  var toggle = document.querySelector('.nav-toggle');
  var gnb = document.getElementById('gnb');
  if (toggle && gnb) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      gnb.classList.toggle('is-open', !open);
    });
    gnb.addEventListener('click', function (e) {
      if (e.target.tagName === 'A' && window.matchMedia('(max-width: 860px)').matches) {
        toggle.setAttribute('aria-expanded', 'false');
        gnb.classList.remove('is-open');
      }
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

  /* 스크롤 등장 */
  var targets = document.querySelectorAll('.reveal');
  if (reduced || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(targets, function (el) { el.classList.add('is-in'); });
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

  /* 상담 신청 — 서버 없이, 문자나 메일로 바로 보낸다 */
  var form = document.getElementById('inquiry-form');
  if (form) {
    var SMS_TO = '010-9665-7391';
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
      var phone = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
      if (phone) {
        location.href = 'sms:' + SMS_TO + '?body=' + encodeURIComponent(body);
        say('문자 앱이 열립니다. <b>보내기</b>를 눌러 주세요.<br>열리지 않으면 아래 <b>작성 내용 복사</b>를 눌러 ' + SMS_TO + ' 로 보내 주십시오.');
      } else {
        location.href = 'mailto:' + MAIL_TO
          + '?subject=' + encodeURIComponent('[입학 상담 신청] ' + (val('pname') || ''))
          + '&body=' + encodeURIComponent(body);
        say('메일 프로그램이 열립니다. <b>보내기</b>를 눌러 주세요.<br>열리지 않으면 아래 <b>작성 내용 복사</b>를 눌러 ' + MAIL_TO + ' 로 보내 주십시오.');
      }
    });

    var copyBtn = document.getElementById('copy-form');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var text = compose();
        var done = function () { say('작성하신 내용을 복사했습니다. 문자나 메일에 붙여넣어 보내 주십시오.<br>문자 ' + SMS_TO + ' · 메일 ' + MAIL_TO); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { say('<pre style="white-space:pre-wrap;margin:0;font-family:inherit">' + text + '</pre>'); });
        } else {
          say('<pre style="white-space:pre-wrap;margin:0;font-family:inherit">' + text + '</pre>');
        }
      });
    }
  }
})();
