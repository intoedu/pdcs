/* 폴앤다니엘기독학교 — 공통 스크립트 */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = document.documentElement;

  /* 모바일 메뉴 */
  var toggle = document.querySelector('.nav-toggle');
  var gnb = document.getElementById('gnb');
  var top0 = document.querySelector('.site-top');
  var drawer = window.matchMedia('(max-width: 860px)');   /* style.css 의 서랍 메뉴 경계와 같은 값 */
  /* 메뉴가 열리면 상단 바탕이 흰색이 된다. 그 사실을 상단 전체에 알려
     글자색 규칙이 "내려간 상태"와 똑같이 걸리게 한다.
     예전에 이 처리가 없어 흰 바탕에 흰 글씨로 배포된 적이 있다.
     aria-hidden 은 붙이지 않는다 — 태블릿에서 열었다 닫고 가로로 돌리면 PC 메뉴가
     화면에는 보이는데 화면 낭독기에서 통째로 사라졌다. 닫힌 서랍은 CSS visibility 가 숨긴다 */
  var measureRoom = function () {
    if (!gnb || !toggle) return;
    var hd = toggle.closest('.header') || toggle;
    var bar = document.querySelector('.mobile-cta');   /* 아래 고정 바에 마지막 버튼이 겹치지 않게 */
    var low = bar && bar.getBoundingClientRect().height ? bar.getBoundingClientRect().top : window.innerHeight;
    gnb.style.setProperty('--gnb-room', Math.max(160, low - hd.getBoundingClientRect().bottom) + 'px');
  };
  var setOpen = function (on) {
    if (toggle) {
      toggle.setAttribute('aria-expanded', String(on));
      toggle.setAttribute('aria-label', on ? '메뉴 닫기' : '메뉴 열기');
    }
    if (gnb) {
      /* 가로로 눕힌 휴대폰은 화면이 낮아 아래 항목(오시는 길 · 상담 신청)이 잘렸다.
         남은 높이만큼만 펼치고 안에서 스크롤한다 */
      if (on) measureRoom();
      gnb.classList.toggle('is-open', on);
      gnb.removeAttribute('aria-hidden');
    }
    if (top0) { top0.classList.toggle('is-open', on); }
    /* 열린 동안 뒤 화면이 같이 스크롤되지 않게 */
    root.classList.toggle('is-menu-open', on && drawer.matches);
  };
  if (toggle && gnb) {
    var isOpen = function () { return toggle.getAttribute('aria-expanded') === 'true'; };
    toggle.addEventListener('click', function () { setOpen(!isOpen()); });
    gnb.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('a') && drawer.matches) setOpen(false);
    });
    /* Esc 로 닫고 버튼으로 돌아간다 */
    document.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.key === 'Esc') && isOpen()) { setOpen(false); toggle.focus(); }
    });
    /* 바깥을 누르면 닫는다. 그 누름은 뒤 화면으로 넘기지 않는다(메뉴에 가려 안 보이던 링크가 눌린다) */
    document.addEventListener('click', function (e) {
      if (!isOpen() || !drawer.matches) return;
      if (gnb.contains(e.target) || toggle.contains(e.target)) return;
      e.preventDefault(); e.stopPropagation();
      setOpen(false);
    }, true);
    /* Tab 으로 메뉴 밖에 나가면 닫는다. 열린 메뉴 뒤로 초점이 숨었다 */
    gnb.addEventListener('focusout', function (e) {
      if (!drawer.matches || !isOpen()) return;
      var to = e.relatedTarget;
      if (to && !gnb.contains(to) && to !== toggle) setOpen(false);
    });
    /* 서랍 폭을 벗어나면(회전 · 창 크기) 열림 상태를 걷는다 */
    var sync = function () { if (!drawer.matches) setOpen(false); };
    if (drawer.addEventListener) drawer.addEventListener('change', sync); else if (drawer.addListener) drawer.addListener(sync);
    /* 열린 채로 휴대폰을 돌리면 세로에서 잰 높이(659px)가 남아 가로 화면(390px)에서
       아래 두 항목(오시는 길 · 입학 상담 신청)에 닿을 수 없었다. 열려 있으면 다시 잰다 */
    window.addEventListener('resize', function () { if (isOpen() && drawer.matches) measureRoom(); });
  }

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

  /* 2~4번 사진은 HTML 에 data-src 로만 둔다. 첫 사진과 대역폭을 다퉈 첫 화면이 늦게 떴다(1.6MB).
     첫 사진이 뜬 뒤 받는다. 번호를 먼저 누르면 그 사진만 바로 받는다 */
  var fill = function (img) {
    if (img && img.getAttribute('data-src')) { img.src = img.getAttribute('data-src'); img.removeAttribute('data-src'); }
  };
  var fillAll = function () { Array.prototype.forEach.call(document.querySelectorAll('.hero__slide img[data-src]'), fill); };
  if (slides.length) {
    var first = slides[0].querySelector('img');
    if (!first || first.complete) fillAll();
    else { first.addEventListener('load', fillAll); first.addEventListener('error', fillAll); }
  }

  if (slides.length > 1) {
    var idx = 0, timer = null, HOLD = 7000;
    var playBtn = document.getElementById('hero-play');
    var pauseIcon = playBtn && playBtn.querySelector('[data-icon="pause"]');
    var playIcon = playBtn && playBtn.querySelector('[data-icon="play"]');

    var show = function (i) {
      var to = (i + slides.length) % slides.length;
      fill(slides[to].querySelector('img'));
      /* 켄번스 확대는 .is-active 에만 걸려 있어, 빠지는 순간 7% 확대가 1.0 으로 한 번에 튀었다.
         나가는 사진은 마지막 배율에 붙잡아 두고, 사라진 뒤(1.4초) 놓는다 */
      var out = slides[idx] && slides[idx].querySelector('img');
      if (out && to !== idx) {
        out.style.transform = getComputedStyle(out).transform;
        setTimeout(function () { out.style.transform = ''; }, 1400);
      }
      idx = to;
      for (var a = 0; a < slides.length; a++) slides[a].classList.toggle('is-active', a === idx);
      for (var c = 0; c < nums.length; c++) {
        if (c === idx) nums[c].setAttribute('aria-current', 'true');
        else nums[c].removeAttribute('aria-current');
      }
    };
    /* 동작 줄이기를 켠 사람에게는 저절로 돌리지 않는다. 다만 재생 버튼을 직접 누르면 돈다(force) —
       예전엔 눌러도 아무 일이 없었다 */
    var start = function (force) { if ((force || !reduced) && !timer) timer = setInterval(function () { show(idx + 1); }, HOLD); };
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
      if (playBtn) playBtn.setAttribute('aria-label', running ? '사진 자동 넘김 멈추기' : '사진 자동 넘김 다시 시작');
    };
    /* ← → 번호를 누르면 7초를 처음부터 다시 센다. 멈춰 둔 상태면 멈춘 채로 둔다 —
       예전엔 멈춘 뒤 →를 누르면 자동 넘김이 다시 켜졌다 */
    var restart = function () { if (timer) { stop(); start(true); } paint(); };

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
      if (timer) { stop(); } else { start(true); }
      paint();
    });

    /* 다른 탭에 가 있는 동안에는 돌리지 않는다 */
    var wasRunning = false;
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) { wasRunning = !!timer; stop(); }
      else if (wasRunning) { start(true); }
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

  /* 숫자 카운트업 — 화면에 들어올 때 한 번.
     HTML 에는 실제 숫자가 들어 있다(스크립트가 없으면 "하루 0번"으로 보였다).
     여기서 0 으로 되돌린 뒤 올라가게 하는 것은 장식일 뿐이다 */
  var counters = document.querySelectorAll('[data-count]');
  function runCount(el) {
    var end = parseInt(el.getAttribute('data-count'), 10);
    var suffix = el.getAttribute('data-suffix') || '';
    if (isNaN(end)) return;
    var t0 = null, dur = 1100;
    function frame(now) {
      if (t0 === null) t0 = now;
      var p = Math.min((now - t0) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(end * eased) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  if (counters.length && !reduced && 'IntersectionObserver' in window) {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { runCount(entry.target); co.unobserve(entry.target); }
      });
    }, { threshold: 0.4 });
    Array.prototype.forEach.call(counters, function (el) {
      el.textContent = '0' + (el.getAttribute('data-suffix') || '');
      co.observe(el);
    });
  }

  /* 학교소개 옆 메뉴 — 지금 보고 있는 구역을 표시한다.
     예전엔 HTML 에 「교장 인사말」이 고정으로 박혀 있어 어디를 보든 그것만 빨갛게 보였다.
     화면 위 40% 선을 지난 마지막 구역이 현재 위치다 */
  var sideLinks = document.querySelectorAll('.sidenav__box a[href^="#"]');
  if (sideLinks.length && 'IntersectionObserver' in window) {
    var blocks = [];
    Array.prototype.forEach.call(sideLinks, function (a) {
      var t = document.getElementById(a.getAttribute('href').slice(1));
      if (t) blocks.push([t, a]);
    });
    var markSide = function () {
      var line = window.innerHeight * 0.4, cur = blocks.length ? blocks[0][1] : null;   /* 맨 위에서는 첫 구역 */
      for (var i = 0; i < blocks.length; i++) {
        if (blocks[i][0].getBoundingClientRect().top <= line) cur = blocks[i][1];
      }
      /* 맨 아래까지 내렸으면 마지막 구역 */
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2 && blocks.length) cur = blocks[blocks.length - 1][1];
      Array.prototype.forEach.call(sideLinks, function (a) {
        if (a === cur) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
      });
    };
    var so = new IntersectionObserver(markSide, { rootMargin: '0px 0px -60% 0px' });
    blocks.forEach(function (b) { so.observe(b[0]); });
    window.addEventListener('scroll', function () { if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) markSide(); }, { passive: true });
    markSide();
  }

  /* 상담 신청 — 서버 없이, 메일 한 곳으로 모은다.
     예전에는 휴대폰이면 문자, 컴퓨터면 메일로 갈라졌다. 신청이 두 군데로
     흩어져 놓치기 쉬웠으므로 기기와 상관없이 메일로 통일한다.
     HTML 의 form 은 method="post" action="mailto:…" 다. 스크립트가 죽어도
     이름 · 연락처가 주소창(GET)에 실려 GitHub 서버로 가지 않는다 */
  var form = document.getElementById('inquiry-form');
  if (form) {
    var MAIL_TO = 'bcia_k@naver.com';
    /* 메일 주소(mailto) 가 이보다 길면 Windows 메일 프로그램이 열리지 않거나 본문이 잘린다.
       한글 1자가 9자로 늘어나 문의 내용 150자 남짓이면 넘는다 */
    var MAX_URL = 1900;
    /* 스크립트가 있으면 직접 검사한다. 없으면 브라우저가 required 로 막는다 */
    form.noValidate = true;
    var box = document.getElementById('form-message');

    var val = function (id) {
      var el = document.getElementById(id);
      return el ? el.value.trim() : '';
    };

    /* 메일 본문 줄바꿈은 CRLF(RFC 6068) */
    var compose = function (nl) {
      var want = form.querySelector('input[name="want"]:checked');
      var rows = [
        '[입학 상담 신청]',
        '학부모: ' + val('pname'),
        '연락처: ' + val('phone'),
        '자녀 학년: ' + val('grade'),
        '희망: ' + (want ? want.value : '')
      ];
      if (val('email')) rows.push('이메일: ' + val('email'));
      rows.push('개인정보 수집 · 이용: 동의함');
      /* 학부모가 쓴 여러 줄도 같은 줄바꿈으로 — 머리 줄만 CRLF 이고 본문은 LF 로 나갔다 */
      if (val('msg')) { rows.push(''); rows.push(val('msg').replace(/\r?\n/g, nl || '\r\n')); }
      return rows.join(nl || '\r\n');
    };

    /* 안내문 — 우리가 쓴 문장만 innerHTML 로 넣는다. 학부모가 쓴 글은 절대 여기로 보내지 않는다 */
    var say = function (html) {
      if (!box) return;
      box.innerHTML = html;
      box.hidden = false;
      box.focus();
    };
    /* 학부모가 쓴 글을 그대로 보여 줄 때 — textContent 로만 넣는다.
       innerHTML 로 넣었다가 '<' 뒤 글자가 사라지고 적어 넣은 태그가 실행됐다 */
    var showText = function (lead, text) {
      if (!box) return;
      box.textContent = '';
      var p = document.createElement('span');
      p.textContent = lead;
      var pre = document.createElement('pre');
      pre.style.cssText = 'white-space:pre-wrap;margin:8px 0 0;font-family:inherit';
      pre.textContent = text;
      box.appendChild(p); box.appendChild(pre);
      box.hidden = false;
      box.focus();
    };
    var copy = function (text, ok, no) {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, no);
      else no();
    };

    /* ── 검사 — 빠진 칸 옆에 빨간 테두리와 문구, 화면을 그 칸으로 옮기고 커서를 넣는다.
       예전엔 안내문이 버튼 아래(화면 밖)에 떴고, 안내문이 커서를 빼앗아 칸이 어디인지 몰랐다 */
    var RULES = [
      ['pname', function (v) { return v ? '' : '학부모 성함을 적어 주세요.'; }],
      ['phone', function (v) {
        if (!v) return '연락처를 적어 주세요.';
        var d = v.replace(/\D/g, '');
        return (d.length < 9 || d.length > 13 || /[^\d\s()+.-]/.test(v)) ? '연락처를 다시 확인해 주세요. (예: 010-1234-5678)' : '';
      }],
      ['grade', function (v) { return v ? '' : '자녀 학년을 골라 주세요.'; }],
      ['email', function (v, el) {
        return (v && (!el.checkValidity() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v))) ? '이메일 주소를 다시 확인해 주세요. 비워 두셔도 됩니다.' : '';
      }],
      ['agree', function (v, el) { return el.checked ? '' : '개인정보 수집 · 이용에 동의해 주셔야 보낼 수 있습니다. 동의하지 않으시면 전화로 상담하실 수 있습니다.'; }]
    ];
    var holder = function (el) { return el.closest('.field') || el.closest('.agree') || el.parentNode; };
    var clearError = function (el) {
      el.removeAttribute('aria-invalid');
      el.removeAttribute('aria-describedby');
      var e = document.getElementById(el.id + '-error');
      if (e) e.parentNode.removeChild(e);
    };
    var markError = function (el, msg) {
      el.setAttribute('aria-invalid', 'true');
      var e = document.createElement('p');
      e.className = 'field-error';
      e.id = el.id + '-error';
      e.textContent = msg;
      var h = holder(el);
      if (h.classList.contains('agree')) h.parentNode.insertBefore(e, h.nextSibling);
      else h.appendChild(e);
      el.setAttribute('aria-describedby', e.id);
    };
    var validate = function () {
      var firstBad = null;
      RULES.forEach(function (r) {
        var el = document.getElementById(r[0]);
        if (!el) return;
        clearError(el);
        var msg = r[1](val(r[0]), el);
        if (msg) { markError(el, msg); if (!firstBad) firstBad = el; }
      });
      if (firstBad) {
        if (box) box.hidden = true;
        holder(firstBad).scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
        try { firstBad.focus({ preventScroll: true }); } catch (err) { firstBad.focus(); }
        return false;
      }
      return true;
    };
    /* 고치면 바로 빨간 표시를 걷는다 */
    RULES.forEach(function (r) {
      var el = document.getElementById(r[0]);
      if (!el) return;
      var off = function () { if (el.getAttribute('aria-invalid') && !r[1](val(r[0]), el)) clearError(el); };
      el.addEventListener('input', off);
      el.addEventListener('change', off);
    });

    var mailLink = function (subject) {
      return 'mailto:' + MAIL_TO + '?subject=' + encodeURIComponent(subject);
    };

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!validate()) return;

      var subject = '[입학 상담 신청] ' + val('pname');
      var url = mailLink(subject) + '&body=' + encodeURIComponent(compose('\r\n'));
      if (url.length > MAX_URL) {
        /* 길면 메일 앱에 넘기지 않는다 — 잘린 신청이 가는 것보다 낫다. 복사해 두고 빈 메일만 연다 */
        var text = compose('\n');
        var after = function (copied) {
          var lead = '문의 내용이 길어 메일 앱에 한 번에 담기지 않을 수 있습니다. ';
          if (copied) {
            say(lead + '작성하신 내용을 <b>복사해 두었습니다.</b><br>아래 <b>메일 쓰기</b>를 눌러 본문에 붙여넣은 뒤 <b>' + MAIL_TO + '</b>으로 보내 주세요.');
          } else {
            showText(lead + '아래 내용을 길게 눌러 복사한 뒤, 메일 쓰기를 눌러 붙여넣어 보내 주세요.', text);
          }
          var a = document.createElement('a');
          a.href = mailLink(subject);
          a.className = 'btn btn--outline btn--sm';
          a.style.marginTop = '12px';
          a.textContent = '메일 쓰기';
          var wrap = document.createElement('span');
          wrap.style.display = 'block';
          wrap.appendChild(a);
          box.appendChild(wrap);
          /* say() 의 focus 는 버튼이 붙기 전에 화면을 옮긴다. 390x844 에서 버튼이 아래 고정 바에 가렸다.
             붙인 다음 다시 맞춘다 — html 의 scroll-padding-bottom 이 바 높이를 비켜 준다 */
          a.scrollIntoView({ block: 'nearest', behavior: 'auto' });
        };
        copy(text, function () { after(true); }, function () { after(false); });
        return;
      }

      location.href = url;
      // 메일 앱이 설정돼 있지 않으면 아무 일도 일어나지 않는다.
      // 그때 학부모가 막히지 않도록 복사 버튼과 받는 주소를 같이 알린다.
      say('메일 앱이 열립니다. 메일에서 <b>보내기</b>까지 눌러야 학교에 전달됩니다.'
        + '<br>열리지 않으면 위의 <b>작성 내용 복사</b>를 누르고 <b>' + MAIL_TO + '</b>으로 보내 주세요.'
        + '<br>메일이 어려우시면 <a href="tel:041-425-0085" style="color:inherit"><b>041-425-0085</b></a>로 전화 주셔도 됩니다.');
    });

    var copyBtn = document.getElementById('copy-form');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        /* 복사도 보내기와 같은 검사를 거친다 — 빈 양식 · 동의 없이도 "복사했습니다"라고 했다 */
        if (!validate()) return;
        var text = compose('\n');
        copy(text, function () {
          say('작성하신 내용을 복사했습니다. 메일에 붙여넣어 <b>' + MAIL_TO + '</b>으로 보내 주세요.');
        }, function () {
          showText('이 브라우저에서는 복사가 막혀 있습니다. 아래 내용을 길게 눌러 복사한 뒤 ' + MAIL_TO + '으로 보내 주세요.', text);
        });
      });
    }
  }
})();
