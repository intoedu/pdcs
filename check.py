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
PAGES = ["index.html", "about.html", "admission.html", "privacy.html", "404.html"]
# 1366x768 · 1280x800 은 한국에서 가장 흔한 노트북 해상도다.
# 히어로 표어가 건물 위에 얹히던 문제가 바로 이 폭에서 가장 심했다
VIEWPORTS = [(2400, 1300), (1920, 1080), (1440, 900), (1366, 768), (1280, 800),
             (1180, 800), (1024, 800), (860, 900), (768, 1024), (390, 844), (360, 640)]

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
        # 작은 라벨과 큰 제목이 같은 말을 반복하면 아마추어처럼 읽힌다
        for m in re.finditer(r'<p class="eyebrow[^"]*">([^<]+)</p>\s*<h2[^>]*>([^<]*)', s):
            lab = m.group(1).strip()
            head = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if lab and head and (lab == head or lab in head or head in lab):
                fail(f"{name}: 라벨과 제목이 같은 말이다 — \"{lab}\" / \"{head}\"")
        # 크기 없는 사진은 불러오는 동안 화면을 밀어 올린다
        for tag in re.findall(r"<img [^>]*>", s):
            if "width=" not in tag:
                src = re.search(r'src="([^"]+)"', tag)
                fail(f"{name}: 사진에 크기가 없다 — {src.group(1) if src else tag[:40]}")
        # 404 는 예외다. 없는 주소를 정식 주소로 가리키면 안 되고, noindex 라야 한다
        if name == "404.html":
            if "noindex" not in s:
                fail("404.html: noindex 가 없다 — 검색에 잡히면 안 된다")
            if 'rel="canonical"' in s:
                fail("404.html: canonical 이 있다 — 404 에는 넣지 않는다")
        elif 'rel="canonical"' not in s:
            fail(f"{name}: canonical 주소가 없다")
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



# ── 사진 위 글자가 읽히는지 픽셀로 재는 검사 ──────────────────
# 글자만 잠깐 숨기고 그 자리의 사진을 찍어, 가장 밝은 부분과 흰 글자의 대비를 본다.
# 장막(.hero__veil, .hero__inner::before)은 그대로 둔다 — 실제로 깔리는 것이기 때문이다.
HERO_TEXT = [
    (".hero__title-en", 3.0, "표어"),      # 큰 글자 3:1
    (".hero__title-ko", 3.0, "학교 이름"),
    (".hero__lead", 4.5, "리드 문장"),     # 작은 글자 4.5:1
    (".hero .eyebrow", 4.5, "라벨"),
]


def _lum(px):
    def f(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(px[0]) + 0.7152 * f(px[1]) + 0.0722 * f(px[2])


def check_hero_text(pg, page, w):
    import io
    try:
        from PIL import Image
    except ImportError:
        return
    boxes = []
    for sel, need, 이름 in HERO_TEXT:
        el = pg.query_selector(sel)
        if not el:
            continue
        b = el.bounding_box()
        if not b or b["width"] < 4 or b["height"] < 4:
            continue
        if b["y"] + b["height"] <= 0 or b["y"] >= pg.viewport_size["height"]:
            continue
        boxes.append((sel, need, 이름, b))
    if not boxes:
        return
    # 글자만 숨긴다. 장막과 사진은 그대로다
    pg.add_style_tag(content=(
        ".hero .eyebrow, .hero__title, .hero__lead, .hero__actions "
        "{ visibility: hidden !important; } "
        ".hero__slide.is-active img { animation: none !important; }"))
    pg.wait_for_timeout(250)
    shot = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    for sel, need, 이름, b in boxes:
        x0 = max(0, int(b["x"])); y0 = max(0, int(b["y"]))
        x1 = min(shot.width, int(b["x"] + b["width"]))
        y1 = min(shot.height, int(b["y"] + b["height"]))
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        crop = shot.crop((x0, y0, x1, y1))
        crop.thumbnail((160, 160))
        raw = crop.tobytes()
        vals = sorted(_lum(raw[i:i + 3]) for i in range(0, len(raw) - 2, 3))
        # 가장 밝은 10% 를 본다. 한 점만 밝은 것은 글자가 묻히는 원인이 되지 않는다
        bright = vals[int(len(vals) * 0.90)]
        ratio = (1.0 + 0.05) / (bright + 0.05)      # 흰 글자 기준
        if ratio < need:
            fail(f"{page} {w}px: 히어로 {이름}이 사진의 밝은 부분에 얹혀 묻힌다 "
                 f"— {ratio:.2f}:1 (필요 {need}:1)")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(300)



# ── 히어로 구도 — 표어가 건물 위에 얹히지 않는지 ────────────────
# 항공샷 hero-aerial.jpg 안에서 건물은 가로 44~70% 자리에 있다(사진에 격자를 얹어 실측).
# object-fit: cover 는 화면 비율에 따라 사진을 잘라 옮기므로,
# 같은 object-position 이라도 폭마다 건물이 화면의 다른 자리에 온다.
# object-position 70% 일 때 1280px 에서 건물이 x=362 로 와서 표어(x=537까지)가 건물 벽에 얹혔다.
# 값을 바꿀 때는 사진에 격자를 얹어 건물 구간을 다시 재고 이 상수를 고친다.
BUILDING_X = (0.47, 0.74)     # 원본 사진 안에서 건물이 차지하는 가로 구간 (격자를 얹어 실측)
BUILDING_Y = (0.00, 0.48)     # 세로 구간 — 건물은 사진 위쪽에 있다 (위는 지붕까지 여유를 둔다)
GAP = 16                      # 글자 끝과 건물 사이에 최소한 남겨야 하는 여백(px)


def check_hero_frame(pg, page, w):
    """표어 오른쪽 끝이 건물 왼쪽 모서리보다 왼쪽에 있어야 한다."""
    geo = pg.evaluate("""({bx, by}) => {
      const img = document.querySelector('.hero__slide.is-active img');
      const t = document.querySelector('.hero__title-en');
      if (!img || !t) return null;
      if (!/hero-aerial\\.jpg/.test(img.currentSrc)) return null;   // 휴대폰 세로 컷은 기준이 다르다
      const r = img.getBoundingClientRect();
      const nw = img.naturalWidth, nh = img.naturalHeight;
      if (!nw || !nh) return null;
      const scale = Math.max(r.width / nw, r.height / nh);
      const posX = parseFloat(getComputedStyle(img).objectPosition) / 100;
      const offX = (r.width - nw * scale) * posX;
      const at = f => r.left + offX + f * nw * scale;
      // 글자 상자가 아니라 글자 자체의 오른쪽 끝을 잰다.
      // span 은 블록이라 상자는 단 전체 폭이다 — 그걸 쓰면 실제보다 훨씬 넓게 나온다
      const rg = document.createRange();
      rg.selectNodeContents(t);
      let right = 0;
      for (const q of rg.getClientRects()) if (q.width > 0) right = Math.max(right, q.right);
      if (!right) right = t.getBoundingClientRect().right;
      const atY = f => r.top + (r.height - nh * scale) * (parseFloat(getComputedStyle(img).objectPosition.split(' ')[1]) / 100) + f * nh * scale;
      const tr = t.getBoundingClientRect();
      return { 건물왼쪽: at(bx[0]), 건물오른쪽: at(bx[1]),
               건물위: atY(by[0]), 건물아래: atY(by[1]),
               글자위: tr.top, 글자아래: tr.bottom,
               글자오른쪽: right, 화면폭: innerWidth };
    }""", {"bx": list(BUILDING_X), "by": list(BUILDING_Y)})
    if not geo:
        return
    # 글자가 건물보다 아래에 있으면 가로로 겹쳐도 상관없다.
    # 701~1000px 에서는 아예 글자를 건물 아래로 내려 두었다
    세로겹침 = geo["글자위"] < geo["건물아래"] and geo["글자아래"] > geo["건물위"]
    if 세로겹침 and geo["글자오른쪽"] + GAP > geo["건물왼쪽"]:
        fail(f"{page} {w}px: 히어로 표어가 건물 위에 얹힌다 — "
             f"글자 끝 {geo['글자오른쪽']:.0f}px, 건물 시작 {geo['건물왼쪽']:.0f}px")
    if geo["건물오른쪽"] > geo["화면폭"] + 2:
        fail(f"{page} {w}px: 히어로에서 건물 오른쪽이 화면 밖으로 잘린다 — "
             f"건물 끝 {geo['건물오른쪽']:.0f}px, 화면 {geo['화면폭']}px")


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
                pg.goto(f"http://localhost:{PORT}/pdcs/{page}", wait_until="networkidle")
                pg.wait_for_timeout(500)

                r = pg.evaluate(PROBE)
                if r["overflow"]:
                    fail(f"{page} {w}px: 가로로 삐져나온다")
                for c in r["contrast"]:
                    fail(f"{page} {w}px: 글자가 배경에 묻힌다 — \"{c['text']}\" {c['sel']} {c['got']}:1 (필요 {c['need']}:1)")
                for e in errs:
                    fail(f"{page} {w}px: {e}")

                # 목록의 표시(점 · Q)가 첫 글자를 덮지 않는지.
                # 질문 목록 스타일을 빌려 쓰면서 여백만 줄여 "스마트폰"이
                # "☗마트폰"으로 보인 적이 있다
                bump_ = pg.evaluate("""() => {
                  const out = [];
                  for (const li of document.querySelectorAll('li')) {
                    const bf = getComputedStyle(li, '::before');
                    if (bf.content === 'none' || bf.position !== 'absolute') continue;
                    const padL = parseFloat(getComputedStyle(li).paddingLeft) || 0;
                    const left = parseFloat(bf.left) || 0;
                    const w = bf.content && bf.content !== '""'
                      ? parseFloat(bf.fontSize) * 0.7
                      : (parseFloat(bf.width) || 0);
                    if (padL < left + w + 3) {
                      out.push(li.textContent.trim().slice(0, 16) + ' (여백 ' + Math.round(padL)
                               + ' < 표시 ' + Math.round(left + w) + ')');
                    }
                  }
                  return out;
                }""")
                for t in bump_:
                    fail(f"{page} {w}px: 목록 표시가 첫 글자를 덮는다 — {t}")

                # 글자가 제 상자 밖으로 삐져나오지 않는지 —
                # 라디오 버튼이 글자 입력칸 규칙(width:100%)을 물려받아
                # 선택지 글자가 테두리 밖으로 나간 적이 있다
                spill = pg.evaluate("""() => {
                  const out = [];
                  for (const el of document.querySelectorAll('.choice, .btn, .staff__item, .faq > summary')) {
                    const r = el.getBoundingClientRect();
                    if (!r.width) continue;
                    if (el.scrollWidth > Math.ceil(r.width) + 2) {
                      out.push(el.textContent.trim().slice(0, 20) + ' (' + el.scrollWidth + ' > ' + Math.round(r.width) + ')');
                    }
                  }
                  return out;
                }""")
                for t in spill:
                    fail(f"{page} {w}px: 글자가 상자 밖으로 나간다 — {t}")

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
                  const 보이나 = e => {
                    if (!e) return false;
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
                  };
                  const pick = () => {
                    const a = t.querySelector('.gnb a:not(.btn)');
                    const k = t.querySelector('.brand__ko');
                    const b = t.querySelector('.nav-toggle span');
                    return {
                      // 화면에 실제로 보이는 것만 검사한다. 닫혀 있는 서랍 메뉴는 색이 무엇이든 상관없다
                      메뉴: 보이나(a) ? getComputedStyle(a).color : null,
                      교명: 보이나(k) ? getComputedStyle(k).color : null,
                      '메뉴 버튼': 보이나(t.querySelector('.nav-toggle')) && b
                                 ? getComputedStyle(b).backgroundColor : null,
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
                    # 헤더가 히어로 사진 위에 얹히지 않는 폭(sticky)에서는
                    # 맨 위에서도 바탕이 크림색 본문이다. 흰 글자면 통째로 묻힌다.
                    # 860px 에서 교명과 메뉴 버튼이 실제로 그렇게 묻혀 있었다
                    겹침 = pg.evaluate("""() => {
                      const t = document.querySelector('.site-top');
                      const h = document.querySelector('.hero, .subhero');
                      if (!t || !h) return null;
                      return t.getBoundingClientRect().bottom > h.getBoundingClientRect().top + 1;
                    }""")
                    상태들 = ["내림", "열림"] if 겹침 else ["투명", "내림", "열림"]
                    for 상태 in 상태들:
                        for 무엇 in ("메뉴", "교명", "메뉴 버튼"):
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

                # 히어로 — 사진 위에 얹힌 글자가 실제로 읽히는지 픽셀로 잰다.
                # CSS 로 배경색을 따라가는 대비 검사는 사진 위에서는 통하지 않는다.
                # 표어가 건물 흰 벽·밝은 지붕 위에 얹혀 배포된 적이 있다(노트북 폭에서 가장 심했다).
                if page == "index.html" and pg.query_selector(".hero__title-en"):
                    # 켄번스 확대가 돌고 있으면 잴 때마다 값이 달라진다. 멈추고 잰다
                    pg.add_style_tag(content=".hero__slide img { animation: none !important; }")
                    pg.wait_for_timeout(150)
                    check_hero_frame(pg, page, w)
                    check_hero_text(pg, page, w)

                if save_shots and w in (1440, 390):
                    pg.screenshot(path=f"{shots}/{page}-{w}.png", full_page=False)
                pg.close()
        b.close()
    if not fails:
        ok(f"{len(PAGES)}페이지 × {len(VIEWPORTS)}뷰포트 — 넘침 · 대비 · 오류 · 404 없음")
        ok("모바일 메뉴를 열어 글자가 보이는지 확인함")


class Quiet(http.server.SimpleHTTPRequestHandler):
    """배포본은 /pdcs/ 아래에 놓인다. 404.html 이 절대경로를 쓰므로
    검사도 같은 주소 구조로 해야 의미가 있다."""

    def translate_path(self, path):
        if path.startswith("/pdcs/"):
            path = path[len("/pdcs"):]
        elif path == "/pdcs":
            path = "/"
        return super().translate_path(path)

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
