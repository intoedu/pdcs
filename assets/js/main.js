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
