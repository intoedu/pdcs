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

  /* 히어로 슬라이드 — 멈추고, 넘기고, 어디쯤인지 보인다 */
  var slides = document.querySelectorAll('.hero__slide');
  var dots = document.querySelectorAll('.hero__dot');
  var bar = document.querySelector('.hero__progress i');
  var playBtn = document.getElementById('hero-toggle');
  var HOLD = 5500;

  if (slides.length) {
    var idx = 0, playing = !reduced, started = 0, raf = null;

    var show = function (i) {
      idx = (i + slides.length) % slides.length;
      for (var s = 0; s < slides.length; s++) {
        slides[s].classList.toggle('is-active', s === idx);
      }
      for (var d = 0; d < dots.length; d++) {
        if (d === idx) { dots[d].setAttribute('aria-current', 'true'); }
        else { dots[d].removeAttribute('aria-current'); }
      }
      started = performance.now();
      if (bar) bar.style.width = '0%';
    };

    var frame = function (now) {
      if (!playing) return;
      var p = (now - started) / HOLD;
      if (bar) bar.style.width = Math.min(p, 1) * 100 + '%';
      if (p >= 1) show(idx + 1);
      raf = requestAnimationFrame(frame);
    };

    var setPlaying = function (on) {
      playing = on;
      if (playBtn) {
        playBtn.setAttribute('aria-label', on ? '슬라이드 멈춤' : '슬라이드 재생');
        var pause = playBtn.querySelector('.ico-pause');
        var play = playBtn.querySelector('.ico-play');
        if (pause) pause.hidden = !on;
        if (play) play.hidden = on;
      }
      if (on) { started = performance.now(); raf = requestAnimationFrame(frame); }
      else if (raf) { cancelAnimationFrame(raf); raf = null; }
    };

    /* 아이콘과 타이머 상태를 JS가 한 번에 확정한다 */
    show(0);
    var want = playing;
    playing = false;
    setPlaying(want);

    if (playBtn) playBtn.addEventListener('click', function () { setPlaying(!playing); });

    Array.prototype.forEach.call(dots, function (dot) {
      dot.addEventListener('click', function () {
        show(parseInt(dot.getAttribute('data-go'), 10) || 0);
        if (playing) { started = performance.now(); }
      });
    });

    /* 다른 탭으로 가 있는 동안은 돌리지 않는다 */
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { if (raf) { cancelAnimationFrame(raf); raf = null; } }
      else if (playing) { started = performance.now(); raf = requestAnimationFrame(frame); }
    });
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

  /* 문의 양식 — 백엔드 연결 전 안내 */
  var form = document.getElementById('inquiry-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var msg = document.getElementById('form-message');
      if (msg) {
        msg.hidden = false;
        msg.focus();
      }
    });
  }
})();
