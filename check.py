#!/usr/bin/env python3
"""배포 전 자동 검사.

사람 눈으로 놓치는 것을 기계가 잡는다.
한 번이라도 눈으로 놓쳐 배포된 적이 있는 항목은 전부 여기에 들어온다.

  python3 check.py           # 전체 검사
  python3 check.py --shots   # 검사 + 화면 캡처 저장

통과하지 못하면 종료 코드 1. 배포하지 않는다.
"""

import http.server
import socketserver
import subprocess
import sys
import threading
import os
import re
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 0   # 0이면 비어 있는 포트를 운영체제가 준다
PAGES = ["index.html", "about.html", "admission.html", "privacy.html"]
VIEWPORTS = [(2400, 1300), (1920, 1080), (1440, 900), (1180, 800), (860, 900), (390, 844), (360, 640)]

# 학교가 쓰지 말라고 한 말 (CLAUDE.md 참조)
BANNED = ["School of Tomorrow", "IGNITIA", "ACSI", r"140여? ?개국", "S\\.O\\.T"]
# 제작용 흔적
LEFTOVER = [r"［[^］]*］", r"\bTODO\b", r"\bFIXME\b", "lorem ipsum", "여기에 내용"]

# 학교 대표번호 — 눌렀을 때 걸리는 번호는 이것뿐이어야 한다 (CLAUDE.md 참조)
TEL_MAIN = "041-425-0085"
# 화면에 적어도 되는 번호 (tel: 링크가 아닌 안내용 표기 포함)
TEL_OK = {"041-425-0085", "041-425-0096", "042-623-7067", "010-9665-7391", "010-6628-8290",
          "010-0000-0000"}   # 마지막은 입력칸 예시 (placeholder)

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

fails = []
warns = []


def fail(msg):
    fails.append(msg)
    print(f"  \033[31m✗\033[0m {msg}")


def warn(msg):
    warns.append(msg)
    print(f"  \033[33m!\033[0m {msg}")


def ok(msg):
    print(f"  \033[32m✓\033[0m {msg}")


# ── 파일만 보고 알 수 있는 것 ────────────────────────────────
def check_source():
    print("\n[소스]")
    for name in PAGES:
        s = open(os.path.join(ROOT, name), encoding="utf-8").read()
        for pat in BANNED:
            hit = re.findall(pat, s)
            if hit:
                fail(f"{name}: 쓰지 말라고 한 말이 남아 있다 — {set(hit)}")
        for pat in LEFTOVER:
            hit = re.findall(pat, s)
            if hit:
                fail(f"{name}: 제작용 흔적이 남아 있다 — {set(hit)}")
        if 'href="#"' in s:
            fail(f"{name}: 눌러도 아무 일이 없는 링크가 있다")
        if "assets/img/logo.png" in s:
            fail(f"{name}: 422KB 원본 로고를 화면에서 쓰고 있다 (logo-96.png를 쓸 것)")
        if "?v=" not in s:
            fail(f"{name}: 스타일·스크립트에 해시가 없다 — ./bump.sh 를 실행할 것")
        # 전화번호 — 학교가 대표번호를 바꾼 적이 있다. 한 페이지만 옛 번호로 남는 것을 막는다
        for t in set(re.findall(r'href="tel:([^"]+)"', s)):
            if t != TEL_MAIN:
                fail(f"{name}: 전화 링크가 대표번호가 아니다 — {t} (대표 {TEL_MAIN})")
        for t in set(re.findall(r"0\d{1,2}-\d{3,4}-\d{4}", s)):
            if t not in TEL_OK:
                fail(f"{name}: 학교 번호가 아닌 전화번호가 적혀 있다 — {t}")
    # 상담 신청은 메일 한 곳으로만 간다.
    # 예전엔 휴대폰이면 문자로 갈라져 신청을 놓치기 쉬웠다. 그 분기가 되살아나면 실패시킨다
    js = open(os.path.join(ROOT, "assets/js/main.js"), encoding="utf-8").read()
    if "sms:" in js:
        fail("main.js: 신청이 문자로 가는 경로가 남아 있다 — 메일로 통일할 것")
    if "mailto:" not in js:
        fail("main.js: 신청을 보낼 메일 주소가 없다")
    for name in PAGES:
        s = open(os.path.join(ROOT, name), encoding="utf-8").read()
        if re.search(r"내용이 담긴 <b>문자", s):
            fail(f"{name}: 신청이 문자로 간다고 안내하고 있다 — 지금은 메일로만 간다")

    if not fails:
        ok("금지어 · 제작용 흔적 · 죽은 링크 · 캐시 해시 · 신청 경로 — 이상 없음")


# ── 브라우저로 띄워봐야 아는 것 ──────────────────────────────
PROBE = r"""
(async () => {
  const out = { overflow: false, errs: [], contrast: [] };
  out.overflow = document.documentElement.scrollWidth > window.innerWidth + 1;

  // 배경 대비 — 요소 뒤에 실제로 깔린 색을 거슬러 올라가 찾는다
  const lum = (c) => {
    const m = c.match(/[\d.]+/g);
    if (!m) return null;
    if (m.length > 3 && parseFloat(m[3]) < 0.5) return null;   // 거의 투명하면 건너뛴다
    const v = m.slice(0, 3).map((x) => {
      x = x / 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const bgOf = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const L = lum(getComputedStyle(n).backgroundColor);
      if (L !== null) return L;
    }
    return 1;
  };
  const ratio = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

  for (const el of document.querySelectorAll('a, button, p, h1, h2, h3, h4, li, dd, span, label')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (!el.textContent.trim()) continue;
    if (el.querySelector('a, button, p, h1, h2, h3, h4, li')) continue;   // 자식이 글을 가진 껍데기
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    // 사진 위 글자는 배경색을 계산할 수 없으므로 제외한다 (눈으로 본다)
    if (el.closest('.hero, .subhero')) continue;
    // 투명 헤더도 같은 이유 — 단 메뉴가 펼쳐지면 흰 바탕이므로 그때는 검사한다
    const top = el.closest('.site-top');
    if (top && !top.classList.contains('is-stuck') && !el.closest('.gnb.is-open')) continue;
    const fg = lum(cs.color);
    if (fg === null) continue;
    const bg = bgOf(el);
    const px = parseFloat(cs.fontSize);
    const big = px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700);
    const need = big ? 3.0 : 4.5;
    const got = ratio(fg, bg);
    if (got < need) {
      out.contrast.push({
        text: el.textContent.trim().slice(0, 28),
        sel: el.tagName.toLowerCase() + '.' + (el.className || '').toString().split(' ')[0],
        got: Math.round(got * 10) / 10, need
      });
    }
  }
  return out;
})()
"""


def check_browser(save_shots=False):
    from playwright.sync_api import sync_playwright

    print("\n[브라우저]")
    shots = os.path.join(ROOT, ".shots")
    if save_shots:
        os.makedirs(shots, exist_ok=True)

    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        for page in PAGES:
            for w, h in VIEWPORTS:
                pg = b.new_page(viewport={"width": w, "height": h})
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("response", lambda r: errs.append(f"{r.status} {r.url.split('/')[-1]}") if r.status >= 400 else None)
                pg.goto(f"http://localhost:{PORT}/{page}", wait_until="networkidle")
                pg.wait_for_timeout(500)

                r = pg.evaluate(PROBE)
                if r["overflow"]:
                    fail(f"{page} {w}px: 가로로 삐져나온다")
                for c in r["contrast"]:
                    fail(f"{page} {w}px: 글자가 배경에 묻힌다 — \"{c['text']}\" {c['sel']} {c['got']}:1 (필요 {c['need']}:1)")
                for e in errs:
                    fail(f"{page} {w}px: {e}")

                # 히어로 슬라이더를 실제로 눌러본다 —
                # SVG 에는 hidden 프로퍼티가 없어서 멈춤·재생 아이콘이 둘 다 보인 적이 있다
                if page == "index.html":
                    shown = pg.evaluate("""() => {
                      const v = s => { const e = document.querySelector(s);
                        return e ? e.getBoundingClientRect().width > 0 : null; };
                      return { 멈춤: v('[data-icon="pause"]'), 재생: v('[data-icon="play"]') };
                    }""")
                    if shown["멈춤"] is not None:
                        if shown["멈춤"] and shown["재생"]:
                            fail(f"{page} {w}px: 멈춤과 재생 아이콘이 동시에 보인다")
                        if not shown["멈춤"] and not shown["재생"]:
                            fail(f"{page} {w}px: 멈춤·재생 아이콘이 둘 다 안 보인다")
                        btn = pg.query_selector("#hero-play")
                        if btn:
                            btn.click(); pg.wait_for_timeout(250)
                            after = pg.evaluate("""() => {
                              const v = s => document.querySelector(s).getBoundingClientRect().width > 0;
                              return { 멈춤: v('[data-icon="pause"]'), 재생: v('[data-icon="play"]') };
                            }""")
                            if after == shown:
                                fail(f"{page} {w}px: 멈춤 버튼을 눌러도 아이콘이 바뀌지 않는다")
                            btn.click(); pg.wait_for_timeout(150)

                # 상단 바가 세 상태에서 모두 읽히는지 — 투명 / 내린 뒤 / 메뉴 열림.
                # 투명할 때만 흰 글자로 바꾸는 구조라, 한 상태만 빠뜨리면 글자가 사라진다
                head = pg.evaluate("""() => {
                  const t = document.querySelector('.site-top'); if (!t) return null;
                  // 색에 transition 이 걸려 있어 클래스를 바꾼 직후에 읽으면
                  // 바뀌는 도중의 값(거의 원래 색)이 나온다. 먼저 전환을 끈다
                  const off = document.createElement('style');
                  off.textContent = '*{transition:none !important}';
                  document.head.appendChild(off);
                  const pick = () => {
                    const a = t.querySelector('.gnb a:not(.btn)');
                    const k = t.querySelector('.brand__ko');
                    return { 메뉴: a && getComputedStyle(a).color, 교명: k && getComputedStyle(k).color,
                             바탕: getComputedStyle(t).backgroundColor };
                  };
                  const before = t.className;
                  t.classList.remove('is-stuck', 'is-open');
                  const 투명 = pick();
                  t.classList.add('is-stuck');
                  const 내림 = pick();
                  t.classList.remove('is-stuck'); t.classList.add('is-open');
                  const 열림 = pick();
                  t.className = before;
                  off.remove();
                  return { 투명, 내림, 열림 };
                }""")
                if head:
                    # 밝은 바탕이 되는 두 상태에서 글자가 흰색이면 안 보인다
                    for 상태 in ("내림", "열림"):
                        for 무엇 in ("메뉴", "교명"):
                            c = head[상태][무엇]
                            if c and re.match(r"rgba?\(\s*2[45]\d,\s*2[45]\d,\s*2[45]\d", c):
                                fail(f"{page} {w}px: 상단이 흰 바탕인데({상태}) {무엇} 글자가 흰색이다 — {c}")

                # 모바일 메뉴를 실제로 열어본다 — 한 번 놓쳐서 배포된 적이 있다
                if w <= 860:
                    tog = pg.query_selector(".nav-toggle")
                    if tog:
                        tog.click()
                        pg.wait_for_timeout(500)
                        mr = pg.evaluate(PROBE)
                        for c in mr["contrast"]:
                            fail(f"{page} {w}px 메뉴 열림: 글자가 묻힌다 — \"{c['text']}\" {c['got']}:1")
                        vis = pg.evaluate("""() => {
                          const a = document.querySelector('.gnb a:not(.btn)');
                          if (!a) return null;
                          const r = a.getBoundingClientRect();
                          return { 보임: r.width > 0 && r.height > 0, 색: getComputedStyle(a).color };
                        }""")
                        if vis and not vis["보임"]:
                            fail(f"{page} {w}px: 메뉴를 열었는데 항목이 보이지 않는다")
                        if save_shots:
                            pg.screenshot(path=f"{shots}/{page}-{w}-menu.png")
                        tog.click()
                        pg.wait_for_timeout(300)

                if save_shots and w in (1440, 390):
                    pg.screenshot(path=f"{shots}/{page}-{w}.png", full_page=False)
                pg.close()
        b.close()
    if not fails:
        ok(f"{len(PAGES)}페이지 × {len(VIEWPORTS)}뷰포트 — 넘침 · 대비 · 오류 · 404 없음")
        ok("모바일 메뉴를 열어 글자가 보이는지 확인함")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    global PORT
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Quiet)
    PORT = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


if __name__ == "__main__":
    save = "--shots" in sys.argv
    print("배포 전 검사")
    check_source()
    srv = serve()
    try:
        check_browser(save)
    finally:
        srv.shutdown()

    print()
    if fails:
        print(f"\033[31m{len(fails)}건 — 배포하지 말 것\033[0m")
        sys.exit(1)
    if warns:
        print(f"\033[33m경고 {len(warns)}건\033[0m")
    print("\033[32m전부 통과\033[0m")
