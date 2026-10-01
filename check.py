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
# 900x800 — 데스크톱 메뉴가 나오는 861~1023px 구간. 이 폭에서 메뉴가 두 줄로 꺾였다
VIEWPORTS = [(2400, 1300), (1920, 1080), (1440, 900), (1366, 768), (1280, 800),
             (1180, 800), (1024, 800), (900, 800), (860, 900), (768, 1024), (390, 844), (360, 640)]
# 메인 히어로만 따로 재는 크기 — 낮은 노트북 창 · 울트라와이드 · 휴대폰 가로 · 기준점 경계(1010px).
# 다섯 페이지 전부 돌리기엔 느려서 index 히어로 구도 · 대비 · 슬라이더 조작만 본다
HERO_EXTRA = [(1010, 768), (1366, 657), (1280, 600), (1920, 700), (2560, 1000), (3440, 1300),
              (960, 540), (844, 390)]

# 학교가 쓰지 말라고 한 말 (CLAUDE.md 참조)
BANNED = ["School of Tomorrow", "IGNITIA", "ACSI", r"140여? ?개국", "S\\.O\\.T"]
# 제작용 흔적
LEFTOVER = [r"［[^］]*］", r"\bTODO\b", r"\bFIXME\b", "lorem ipsum", "여기에 내용"]

# 학교 대표번호 — 눌렀을 때 걸리는 번호는 이것뿐이어야 한다 (CLAUDE.md 참조)
# 사이트 주소 — 가비아 pdcs.kr, GitHub Pages 맞춤 도메인 www.pdcs.kr (2026-10-01 연결)
SITE = "https://www.pdcs.kr/"
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
    # 히어로 사진 위치 — 학교가 hero-tuner.html 에서 고른 값을 GitHub 웹에서 붙여 넣는 파일.
    # 사람이 붙여 넣으므로 형식이 깨질 수 있다. 하나라도 빠지면 그 사진은 style.css 의 기본값으로 떨어진다
    hp = os.path.join(ROOT, "assets/css/hero-position.css")
    if not os.path.exists(hp):
        fail("assets/css/hero-position.css 가 없다 — 히어로 사진 위치를 학교가 고칠 수 없다")
    else:
        got = dict(re.findall(r"(--hero[1-4]-(?:pc|tab|mob))\s*:\s*(\d{1,3}(?:\.\d+)?%\s+\d{1,3}(?:\.\d+)?%)\s*;",
                              open(hp, encoding="utf-8").read()))
        need = [f"--hero{i}-{b}" for i in range(1, 5) for b in ("pc", "tab", "mob")]
        miss = [k for k in need if k not in got]
        if miss:
            fail(f"hero-position.css: 형식이 깨졌거나 빠진 값이 있다 — {miss[:4]}")
        if 'hero-position.css' not in open(os.path.join(ROOT, "index.html"), encoding="utf-8").read():
            fail("index.html: hero-position.css 를 불러오지 않는다")
    tn = os.path.join(ROOT, "hero-tuner.html")
    if os.path.exists(tn):
        t = open(tn, encoding="utf-8").read()
        if 'content="noindex' not in t:
            fail("hero-tuner.html: noindex 가 없다 — 조정 도구가 검색에 뜬다")
        for n in PAGES:
            if "hero-tuner" in open(os.path.join(ROOT, n), encoding="utf-8").read():
                fail(f"{n}: 조정 도구(hero-tuner.html)로 가는 링크가 공개 화면에 있다")
    # 도메인 — CNAME 파일이 사라지면 www.pdcs.kr 연결이 통째로 끊긴다.
    # 옛 주소(intoedu.github.io/pdcs)가 남으면 공유 썸네일 · 검색 주소가 옛 곳을 가리킨다
    cn = os.path.join(ROOT, "CNAME")
    if not os.path.exists(cn) or open(cn, encoding="utf-8").read().strip() != "www.pdcs.kr":
        fail("CNAME: www.pdcs.kr 가 아니다 — 도메인 연결이 끊긴다")
    for n in PAGES + ["sitemap.xml", "robots.txt"]:
        t = open(os.path.join(ROOT, n), encoding="utf-8").read()
        if "intoedu.github.io" in t or "/pdcs/" in t:
            fail(f"{n}: 옛 주소(intoedu.github.io/pdcs)가 남아 있다")
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
        # h3 도 본다 — 입학 페이지 연락 카드가 "바로 연락하기 / 바로 연락하기" 였다
        for m in re.finditer(r'<p class="eyebrow[^"]*">([^<]+)</p>\s*<h[23][^>]*>([^<]*)', s):
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
        # 새 창으로 열리는 링크는 화면 낭독기에도 그렇다고 알린다 (대부분 알리지 않고 있었다)
        for m in re.finditer(r'(<a\b[^>]*target="_blank"[^>]*>)(.*?)</a>', s, re.S):
            if "(새 창)" not in m.group(0):
                fail(f"{name}: 새 창으로 열리는 링크가 그 사실을 알리지 않는다 — {re.sub(r'<[^>]+>', '', m.group(2)).strip()[:20] or m.group(1)[:60]}")
        # 브라우저 자동 다크가 엠블럼 색을 반전시켰다 — 밝은 화면 한 벌뿐이라고 선언한다
        if '<meta name="color-scheme" content="only light">' not in s:
            fail(f"{name}: <meta name=\"color-scheme\" content=\"only light\"> 가 없다 — 자동 다크가 로고를 반전시킨다")
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

    check_css()
    check_fonts()
    check_meta()
    check_copy()
    check_js_source()

    if not fails:
        ok("금지어 · 제작용 흔적 · 죽은 링크 · 캐시 해시 · 신청 경로 · CSS · 폰트 · 공유 정보 — 이상 없음")


# ── CSS — 쓰지 않는 규칙 · 조용히 덮이는 규칙 ────────────────────
# 지운 화면의 규칙(영상 · 탭 · 슬라이더 막대 …)이 13묶음 남아 있었고,
# 같은 선택자를 두 번 적어 앞의 값이 한 번도 적용되지 않는 곳이 여럿 있었다.
# 앞의 값을 고쳐 놓고 "고쳤는데 안 바뀐다"가 되는 원인이다
CSS_KEEP = {"sr-only"}   # 화면 낭독기 전용 글자 — 쓰는 곳이 없어도 두는 공용 도구


def _css_rules(text, ctx=""):
    """(@media 조건, 선택자, 선언) 을 차례로 내놓는다. @media 한 겹까지만 푼다."""
    i = 0
    while True:
        j = text.find("{", i)
        if j < 0:
            return
        head = text[i:j].strip()
        if head.startswith(("@media", "@supports")):
            depth, k = 1, j + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(text[k], 0)
                k += 1
            yield from _css_rules(text[j + 1:k - 1], head)
            i = k
            continue
        k = text.find("}", j)
        if not head.startswith("@"):
            yield ctx, head, text[j + 1:k]
        i = k + 1


def _css_text():
    s = open(os.path.join(ROOT, "assets/css/style.css"), encoding="utf-8").read()
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def check_css():
    css = _css_text()
    src = "".join(open(os.path.join(ROOT, n), encoding="utf-8").read() for n in PAGES)
    src += open(os.path.join(ROOT, "assets/js/main.js"), encoding="utf-8").read()
    names, seen, dup = set(), {}, []
    for n, (ctx, sel, body) in enumerate(_css_rules(css)):
        names |= set(re.findall(r"\.([a-zA-Z_][\w-]*)", re.sub(r"\[[^\]]*\]", "", sel)))
        props = [d.split(":", 1)[0].strip() for d in body.split(";") if ":" in d]
        for one in (re.sub(r"\s+", " ", x.strip()) for x in sel.split(",")):
            for p in props:
                key = (ctx, one, p)
                if key in seen and seen[key] != n and key not in dup:
                    dup.append(key)
                seen[key] = n
    for c in sorted(names - CSS_KEEP):
        if not re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", src):
            fail(f"style.css: 어느 페이지에도 없는 규칙이 남아 있다 — .{c}")
    for ctx, sel, p in dup:
        fail(f"style.css: 같은 선택자에 같은 속성을 두 번 적었다(앞의 값은 무시된다) — "
             f"{sel} {{ {p} }}{' @ ' + ctx if ctx else ''}")


# ── 폰트 — 허락된 한 벌만, 화면에 쓰인 글자는 전부 그 안에서 ──────────
# Pretendard 를 92조각(unicode-range)으로 나눠 받는다. 조각에 없는 글자를 새로 쓰면
# 그 글자만 방문자 컴퓨터의 시스템 글꼴로 그려진다. 눈으로는 거의 안 보인다
FONT_OK = {"pretendard", "inherit", "-apple-system", "blinkmacsystemfont", "system-ui", "sans-serif"}


def _page_text(name):
    import html as _h
    s = open(os.path.join(ROOT, name), encoding="utf-8").read()
    s = re.sub(r"<(script|style)\b.*?</\1>", "", s, flags=re.S)
    attrs = " ".join(re.findall(r'(?:alt|placeholder|aria-label|title|value|content)="([^"]*)"', s))
    return _h.unescape(re.sub(r"<[^>]+>", " ", s) + " " + attrs)


def check_fonts():
    css = _css_text()
    # 다른 서체 선언 금지 (CLAUDE.md 폰트 정책)
    every = css + "".join(open(os.path.join(ROOT, n), encoding="utf-8").read() for n in PAGES)
    every += open(os.path.join(ROOT, "assets/js/main.js"), encoding="utf-8").read()
    for v in re.findall(r"font-family\s*:\s*([^;}\"]+)", every):
        for fam in (x.strip().strip("'\"").lower() for x in v.split(",")):
            if fam and fam not in FONT_OK:
                fail(f"허락되지 않은 서체 선언 — {fam} (CLAUDE.md 폰트 정책: Pretendard 한 벌뿐)")
    faces = []
    for body in re.findall(r"@font-face\s*\{([^}]*)\}", css):
        m = re.search(r"url\('?\.\./fonts/([^')]+)'?\)", body)
        if not m:
            fail("style.css: @font-face 가 assets/fonts 밖의 파일을 가리킨다 — 자체 호스팅만 쓴다")
            continue
        path = os.path.join(ROOT, "assets/fonts", m.group(1))
        if not os.path.exists(path):
            fail(f"style.css: 폰트 파일이 없다 — assets/fonts/{m.group(1)}")
            continue
        rs = []
        ur = re.search(r"unicode-range\s*:\s*([^;]+)", body)
        for part in (ur.group(1).split(",") if ur else ["U+0-10FFFF"]):
            a, _, b = part.strip()[2:].partition("-")
            rs.append((int(a, 16), int(b or a, 16)))
        faces.append((path, rs))
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        warn("fontTools 가 없어 글자 포함 여부를 재지 못했다 — pip install fonttools brotli")
        return
    cmaps = {p: set(TTFont(p).getBestCmap()) for p, _ in faces}
    text = "".join(_page_text(n) for n in PAGES)
    js = open(os.path.join(ROOT, "assets/js/main.js"), encoding="utf-8").read()
    text += "".join(re.findall(r"'((?:[^'\\\n]|\\.)*)'", js))
    text += "".join(re.findall(r'content:\s*"([^"]*)"', css))
    missing = []
    for ch in sorted(set(text)):
        cp = ord(ch)
        if ch.isspace() or cp < 0x20:
            continue
        if not any(cp in cmaps[p] for p, rs in faces if any(a <= cp <= b for a, b in rs)):
            missing.append(ch)
    if missing:
        fail(f"폰트에 없는 글자를 쓰고 있다(시스템 글꼴로 그려진다) — {' '.join(missing[:30])}")


# ── 문구 — 학교가 확인하지 않은 말 · 이름이 제각각인 메뉴 · 어긋난 동의 문구 ──────
# 전부 한 번씩 공개 화면에 나갔던 것이다 (CLAUDE.md 「화면에 내보내면 안 되는 것」)
UNCONFIRMED = [
    (r"전원 기숙(?!인가요)", "「전원 기숙」 — 학교가 확인하지 않았다. 「기숙형」으로 쓴다"),
    (r"한 해도 쉬지", "「한 해도 쉬지 않은」 — 확인된 것은 2010년 설립뿐이다"),
    (r"세 번의 예배", "「세 번의 예배」 — 실제 일과는 성경 연구 · 정오 기도 · 저녁 예배다"),
    (r"바로 전달되", "신청이 「바로 전달」된다고 약속한다 — 메일에서 보내기를 눌러야 전달된다"),
    (r"\d+\s*[~–-]\s*\d+일 안에", "응답 기한을 약속한다 — 학교가 정해 준 적이 없다"),
    (r"동의 여부를 확인한", "학부모 동의를 확인했다고 단정한다 — 확인 기록이 없다"),
    (r"학교 요람", "「학교 요람」 — 보낼 실물 파일이 없다"),
    (r"선생님 <span data-count", "「선생님 16명」 — 16명에 행정 · 자문이 들어 있다. 「섬기는 분」으로 쓴다"),
]
# 같은 장면을 다른 크기로 자른 사진들. 한 페이지에 둘이 같이 나오면 같은 사진을 두 번 보여 주는 것이다
# (hero-aerial.jpg 와 hero-aerial-m.jpg 는 한 <picture> 안의 폭별 사본이라 같이 있어도 된다)
SAME_SHOT = [{"hero-aerial.jpg", "aerial.webp"}, {"hero-aerial-m.jpg", "aerial.webp"}, {"hero-main.jpg", "front.jpg"},
             {"hero-nature.jpg", "court.jpg"}, {"hero-dorm.jpg", "dorm.jpg"}]


def check_copy():
    import html as _h
    txt = lambda x: re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", "", x))).strip()
    src = {n: open(os.path.join(ROOT, n), encoding="utf-8").read() for n in PAGES}
    js = open(os.path.join(ROOT, "assets/js/main.js"), encoding="utf-8").read()
    for name, s in list(src.items()) + [("main.js", js)]:
        for pat, why in UNCONFIRMED:
            if re.search(pat, s):
                fail(f"{name}: {why}")
        # 말투 — 권유는 「-주세요」 하나로. 「-십시오」 가 섞여 있었다
        if "십시오" in s:
            fail(f"{name}: 「-십시오」 가 남아 있다 — 「-주세요」 로 맞춘다")
        # 「</b> 으로」 처럼 조사 앞에 빈칸
        for m in re.findall(r"</b>\s+(?:으로|로|을|를|이|가)[\s.,]", s):
            fail(f"{name}: 조사 앞에 빈칸이 있다 — \"{m.strip()}\"")
    # 교장 서명이 붙은 메인 발췌는 학교소개 인사말 원문을 그대로 잘라 쓴 것이어야 한다.
    # 한때 뜻만 옮겨 고쳐 쓴 문장에 「교장 김남주」 서명이 붙어 나갔다
    about_g = re.search(r'<section[^>]*\bid="greeting"[^>]*>(.*?)</section>', src["about.html"], re.S)
    excerpt = re.search(r'class="greeting greeting--text".*?<div class="reveal"[^>]*data-delay[^>]*>(.*?)<div class="sign"',
                        src["index.html"], re.S)
    if not about_g or not excerpt:
        fail("교장 인사말 발췌 또는 학교소개 #greeting 을 찾지 못했다 — 검사 구조를 고칠 것")
    else:
        whole = txt(about_g.group(1))
        for p_ in re.findall(r"<p[^>]*>(.*?)</p>", excerpt.group(1), re.S):
            if txt(p_) and txt(p_) not in whole:
                fail(f"index.html: 교장 서명이 붙은 발췌가 원문과 다르다 — 「{txt(p_)[:30]}…」")
    for name, s in src.items():
        # 자기 섹션으로만 가는 버튼 — 「신앙고백 10항 전문 보기」 가 제자리로 올라가기만 했다
        for sid, body in re.findall(r'<section[^>]*\bid="([^"]+)"[^>]*>(.*?)</section>', s, re.S):
            if re.search(r'href="#' + re.escape(sid) + '"', body):
                fail(f"{name}: #{sid} 안의 링크가 #{sid} 로 간다 — 눌러도 제자리다")
        # 공유 제목은 그 페이지 제목이거나 학교 이름이어야 한다 (404 가 개인정보처리방침 것을 쓰고 있었다)
        t = re.search(r"<title>([^<]+)</title>", s)
        og = re.search(r'<meta property="og:title" content="([^"]*)"', s)
        if t and og and og.group(1) not in (t.group(1), "폴앤다니엘기독학교"):
            fail(f"{name}: og:title 이 이 페이지 것이 아니다 — \"{og.group(1)}\"")
        # 한 페이지에 같은 장면 두 번
        used = set(re.findall(r'assets/img/([\w.-]+\.(?:jpg|webp|png))', s))
        for group in SAME_SHOT:
            if len(used & group) > 1:
                fail(f"{name}: 같은 장면의 사진을 두 번 쓴다 — {sorted(used & group)}")
    # 학교가 강조해 달라고 한 「대안교육기관」 — 검색 결과에 뜨는 제목 · 설명에 있어야 한다
    s = src["index.html"]
    for what, pat in (("검색 제목", r"<title>([^<]+)"), ("검색 설명", r'<meta name="description" content="([^"]*)"'),
                      ("공유 설명", r'<meta property="og:description" content="([^"]*)"')):
        m = re.search(pat, s)
        if not m or "대안교육기관" not in m.group(1):
            fail(f"index.html: {what}에 「대안교육기관」 이 없다")
    # 주 메뉴는 다섯 페이지에서 같은 이름이어야 하고, #news 로 가는 링크는 그 섹션 제목을 써야 한다.
    # 공지가 하나도 없는 섹션을 「공지 · 소식」「공지사항」 으로 불렀다
    menus = {}
    for name, s in src.items():
        nav = re.search(r'<nav class="gnb"[^>]*>(.*?)</nav>', s, re.S)
        if nav:
            menus[name] = [txt(a) for a in re.findall(r"<a [^>]*>(.*?)</a>", nav.group(1), re.S)]
    if len({tuple(v) for v in menus.values()}) > 1:
        fail("주 메뉴 이름이 페이지마다 다르다 — " + " / ".join(f"{k}: {v}" for k, v in menus.items()))
    h2 = re.search(r'<section[^>]*id="news".*?<h2[^>]*>(.*?)</h2>', src["index.html"], re.S)
    news = txt(h2.group(1)) if h2 else None
    for name, s in src.items():
        for label in re.findall(r'<a href="(?:index\.html)?#news"[^>]*>(.*?)</a>', s, re.S):
            if txt(label) != news:
                fail(f"{name}: #news 링크 이름이 섹션 제목과 다르다 — \"{txt(label)}\" (제목 \"{news}\")")
    # 동의 문구 — 양식이 실제로 받는 칸이 동의란과 개인정보처리방침에 모두 적혀 있어야 한다
    s = src["admission.html"]
    fields = [txt(x) for x in re.findall(r'<label for="(?!agree)[^"]+">([^<]+)', s)]
    fields += [txt(x) for x in re.findall(r"<legend[^>]*>([^<]+)</legend>", s)]
    agree = re.search(r'<div class="agree">.*?<small>(.*?)</small>', s, re.S)
    agree = txt(agree.group(1)) if agree else ""
    policy = txt(src["privacy.html"])
    for f in fields:
        if f not in agree:
            fail(f"admission.html: 동의란 수집 항목에 「{f}」 이 없다 — 양식은 받고 있다")
        if f not in policy:
            fail(f"privacy.html: 수집 항목에 「{f}」 이 없다 — 양식은 받고 있다")
    for need in ("동의하지 않", "안전성 확보", "시행합니다", "bcia_k@naver.com", TEL_MAIN):
        if need not in policy:
            fail(f"privacy.html: 개인정보처리방침에 「{need}」 항목이 없다")


# ── 스크립트 동작 — 파일만 보고 알 수 있는 것 ────────────────────
# 전부 한 번씩 배포됐던 것이다 (CLAUDE.md 「스크립트 동작」)
def check_js_source():
    import html as _h
    src = {n: open(os.path.join(ROOT, n), encoding="utf-8").read() for n in PAGES}
    js = open(os.path.join(ROOT, "assets/js/main.js"), encoding="utf-8").read()
    css = _css_text()
    s = src["index.html"]
    # 미리 받는 사진은 첫 슬라이드여야 한다. 슬라이드 순서를 바꾼 뒤 3번 사진을 최우선으로 받고 있었다
    slides = re.findall(r'<div class="hero__slide[^"]*">(.*?)</div>', s, re.S)
    first = re.search(r'<img [^>]*\bsrc="([^"]+)"', slides[0]) if slides else None
    for href in re.findall(r'<link rel="preload" as="image" href="([^"]+)"', s):
        if not first or href != first.group(1):
            fail(f"index.html: 첫 슬라이드가 아닌 사진을 미리 받는다 — {href}")
    # 2번째 슬라이드부터는 data-src 로만 둔다. src 면 첫 사진과 대역폭을 다툰다(1.6MB)
    for i, sl in enumerate(slides[1:], 2):
        if re.search(r'<img [^>]*(?<![\w-])src=', sl):
            fail(f"index.html: 히어로 {i}번 사진이 처음부터 내려온다 — src 대신 data-src 로 둘 것")
    # 숫자는 HTML 에 실제 값으로. 스크립트가 없으면 "하루 0번"으로 보였다
    for n in PAGES:
        for v, t in re.findall(r'data-count="(\d+)"[^>]*>([^<]*)<', src[n]):
            if t.strip() != v:
                fail(f"{n}: 지표 숫자가 HTML 에 「{t.strip()}」 로 들어 있다 — 실제 값 {v} 을 적을 것")
    # 학교소개 옆 메뉴의 현재 위치는 스크립트가 정한다. HTML 에 고정하면 어디서든 「교장 인사말」이다
    side = re.search(r'<nav class="sidenav__box".*?</nav>', src["about.html"], re.S)
    if side and "aria-current" in side.group(0):
        fail("about.html: 옆 메뉴에 aria-current 가 고정으로 박혀 있다")
    # 상담 양식 — 스크립트가 죽어도 개인정보가 주소창(GET)으로 GitHub 에 가지 않게
    f = re.search(r'<form id="inquiry-form"([^>]*)>', src["admission.html"])
    if f:
        a = f.group(1)
        if 'method="post"' not in a or 'action="mailto:' not in a:
            fail("admission.html: 상담 양식이 method=\"post\" action=\"mailto:…\" 가 아니다 — 스크립트가 죽으면 이름 · 연락처가 주소창에 실린다")
        if "novalidate" in a:
            fail("admission.html: 상담 양식에 novalidate 가 박혀 있다 — 스크립트 없이도 required 가 막아야 한다(main.js 가 끈다)")
        if not re.search(r'<textarea id="msg"[^>]*maxlength="\d+"', src["admission.html"]):
            fail("admission.html: 문의 내용에 maxlength 가 없다 — 메일 주소 길이가 끝없이 늘어난다")
    # 학부모가 쓴 글을 innerHTML 로 넣으면 '<' 뒤가 사라지고 적어 넣은 태그가 실행된다
    if re.search(r"say\([^;]*\btext\b", js) or re.search(r"innerHTML\s*=[^;]*compose\(", js):
        fail("main.js: 학부모가 쓴 글을 innerHTML 로 넣는다 — textContent 로 보여 줄 것")
    if "\\r\\n" not in js:
        fail("main.js: 메일 본문 줄바꿈이 CRLF 가 아니다 (RFC 6068)")
    if "동의함" not in js:
        fail("main.js: 메일 본문에 개인정보 수집 · 이용 동의가 적히지 않는다")
    # 동작 줄이기 — 켄번스 확대를 끈다
    rm = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", css, re.S)
    if not rm or not re.search(r"\.hero__slide\.is-active img\s*\{\s*animation:\s*none", rm.group(1)):
        fail("style.css: 동작 줄이기에서도 히어로 켄번스 확대가 돈다")


# ── 공유 · 검색 정보 ─────────────────────────────────────────
def check_meta():
    try:
        from PIL import Image
    except ImportError:
        Image = None
    sitemap = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
    for name in PAGES:
        s = open(os.path.join(ROOT, name), encoding="utf-8").read()
        meta = dict(re.findall(r'<meta property="(og:[\w:]+)" content="([^"]*)"', s))
        for k in ("og:title", "og:description", "og:image", "og:image:width", "og:image:height",
                  "og:site_name", "og:locale"):
            if k not in meta:
                fail(f"{name}: 공유 정보 {k} 가 없다 — 카톡·페북 미리보기가 불완전해진다")
        img = meta.get("og:image", "")
        if Image and "og:image:width" in meta and img.startswith(SITE):
            p = os.path.join(ROOT, img[len(SITE):])
            if not os.path.exists(p):
                fail(f"{name}: og:image 파일이 없다 — {img}")
            else:
                w, h = Image.open(p).size
                if (meta.get("og:image:width"), meta.get("og:image:height")) != (str(w), str(h)):
                    fail(f"{name}: og:image 크기 표기가 실제와 다르다 — 실제 {w}x{h}, 표기 "
                         f"{meta.get('og:image:width')}x{meta.get('og:image:height')}")
        # 검색 제외는 noindex 가 맡는다. robots.txt 로 막으면 검색엔진이 noindex 를 못 읽는다
        noindex = re.search(r'<meta name="robots" content="[^"]*noindex', s)
        if name in ("privacy.html", "404.html") and not noindex:
            fail(f"{name}: noindex 가 없다 — robots.txt 로는 검색에서 빠지지 않는다")
        loc = SITE + ("" if name == "index.html" else name)
        if noindex and loc in sitemap:
            fail(f"sitemap.xml: 검색에서 뺀 페이지가 사이트맵에 있다 — {name}")
        if not noindex and f"<loc>{loc}</loc>" not in sitemap:
            fail(f"sitemap.xml: {name} 이 사이트맵에 없다")


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

  // small 도 본다 — 동의란 안내(<small>, 4.1:1)가 여기서 빠져 있어 놓쳤다
  for (const el of document.querySelectorAll('a, button, p, h1, h2, h3, h4, li, dd, span, label, small')) {
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
# 글자만 잠깐 숨기고 그 자리의 사진을 찍어, 가장 밝은 부분과 **실제 글자색**의 대비를 본다.
# 장막(.hero__veil, .hero__inner::before)은 그대로 둔다 — 실제로 깔리는 것이기 때문이다.
# 사진 네 장을 하나씩 켜서 모두 잰다. 예전엔 1번 사진 · 흰 글자만 가정해서
# 골드 라벨이 2~4번 사진 위에서 2.0:1 로 묻힌 것을 놓쳤다.
# 투명 헤더(메뉴 · 교명 · 유틸바)도 사진 위에 얹히는 폭에서는 같이 잰다 — 옥상 위 메뉴가 1.8:1 이었다.
HERO_TEXT = [
    (".hero__title-en", 3.0, "표어"),      # 큰 글자 3:1
    (".hero__title-ko", 3.0, "학교 이름"),
    (".hero__lead", 4.5, "리드 문장"),     # 작은 글자 4.5:1
    (".hero .eyebrow", 4.5, "라벨"),
    (".hero__num", 4.5, "사진 번호"),
]
HEADER_TEXT = [
    (".site-top .gnb > a:not(.btn)", 4.5, "투명 헤더 메뉴"),
    (".site-top .brand__ko", 4.5, "투명 헤더 교명"),
    (".site-top .brand__kind", 4.5, "투명 헤더 「대안교육기관」"),
    (".site-top .utility a:not(.kakao-link)", 4.5, "유틸바 링크"),
    (".site-top .utility__tel", 4.5, "유틸바 번호"),
    (".site-top .utility__badge", 4.5, "유틸바 등록 표시"),
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
    over = pg.evaluate("""() => {
      const t = document.querySelector('.site-top'), h = document.querySelector('.hero');
      return !!(t && h && !t.classList.contains('is-stuck')
                && t.getBoundingClientRect().bottom > h.getBoundingClientRect().top + 1); }""")
    targets = HERO_TEXT + (HEADER_TEXT if over else [])
    boxes = pg.evaluate("""(targets) => {
      const out = [];
      for (const [sel, need, name] of targets) for (const e of document.querySelectorAll(sel)) {
        // 상자가 아니라 글자가 실제로 놓인 자리를 잰다. 라벨 · 표어는 블록이라 상자가 단 전체 폭이다
        const rg = document.createRange(); rg.selectNodeContents(e);
        const qs = [...rg.getClientRects()].filter(q => q.width > 0);
        const cs = getComputedStyle(e);
        const r = qs.length ? { left: Math.min(...qs.map(q => q.left)), top: Math.min(...qs.map(q => q.top)),
                                right: Math.max(...qs.map(q => q.right)), bottom: Math.max(...qs.map(q => q.bottom)) }
                            : e.getBoundingClientRect();
        r.width = r.right - r.left; r.height = r.bottom - r.top;
        if (r.width < 4 || r.height < 4 || r.bottom <= 0 || r.top >= innerHeight) continue;
        if (cs.visibility === 'hidden' || cs.display === 'none') continue;
        const c = cs.color.match(/[\d.]+/g).map(Number);
        out.push({ sel, need, name, txt: e.textContent.trim().slice(0, 12), c,
                   b: [r.left, r.top, r.right, r.bottom] });
      }
      return out; }""", [list(t) for t in targets])
    if not boxes:
        return
    # 글자만 숨긴다. 장막과 사진은 그대로다
    hide = ", ".join(sel for sel, _, _ in targets)
    pg.add_style_tag(content=(
        ".hero .eyebrow, .hero__title, .hero__lead, .hero__actions, " + hide +
        " { visibility: hidden !important; } "
        ".hero__slide img { animation: none !important; } .hero__slide { transition: none !important; }"))
    n = pg.evaluate("document.querySelectorAll('.hero__slide').length") or 1
    worst = {}
    for s in range(n):
        pg.evaluate("(s) => document.querySelectorAll('.hero__slide')"
                    ".forEach((el, i) => el.classList.toggle('is-active', i === s))", s)
        pg.wait_for_timeout(200)
        shot = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
        for bx in boxes:
            x0, y0, x1, y1 = (int(v) for v in bx["b"])
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(shot.width, x1), min(shot.height, y1)
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue
            crop = shot.crop((x0, y0, x1, y1))
            crop.thumbnail((160, 160))
            raw = crop.tobytes()
            vals = sorted(_lum(raw[i:i + 3]) for i in range(0, len(raw) - 2, 3))
            # 가장 밝은 10% 를 본다. 한 점만 밝은 것은 글자가 묻히는 원인이 되지 않는다
            bright = vals[int(len(vals) * 0.90)]
            fg = _lum(bx["c"][:3])
            ratio = (max(fg, bright) + 0.05) / (min(fg, bright) + 0.05)
            key = (bx["name"], bx["txt"])
            if ratio < bx["need"] and (key not in worst or ratio < worst[key][0]):
                worst[key] = (ratio, s + 1, bx["need"])
    for (이름, txt), (ratio, s, need) in worst.items():
        fail(f"{page} {w}px: 히어로 {s}번 사진 위 {이름} 「{txt}」 이 묻힌다 — {ratio:.2f}:1 (필요 {need}:1)")
    pg.reload(wait_until="load")
    pg.wait_for_timeout(300)



# ── 히어로 구도 — 표어가 건물 위에 얹히지 않는지 ────────────────
# 항공샷 hero-aerial.jpg 안에서 건물은 가로 47~74%, 세로 0~48% 자리에 있다(합성본 2000x872 에 격자를 얹어 실측).
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
      const brand = document.querySelector('.site-top .brand');
      return { 표어왼쪽: tr.left, 로고왼쪽: brand ? brand.getBoundingClientRect().left : tr.left,
               건물왼쪽: at(bx[0]), 건물오른쪽: at(bx[1]),
               건물위: atY(by[0]), 건물아래: atY(by[1]),
               글자위: tr.top, 글자아래: tr.bottom,
               글자오른쪽: right, 화면폭: innerWidth };
    }""", {"bx": list(BUILDING_X), "by": list(BUILDING_Y)})
    if not geo:
        return
    # 글자가 건물보다 아래에 있으면 가로로 겹쳐도 상관없다.
    # (701~1000px 는 표어를 세 줄로 접어 건물 왼쪽에 둔다 — 글자를 건물 아래로 내리는 방법은 버렸다)
    세로겹침 = geo["글자위"] < geo["건물아래"] and geo["글자아래"] > geo["건물위"]
    if 세로겹침 and geo["글자오른쪽"] + GAP > geo["건물왼쪽"]:
        warn(f"{page} {w}px: 히어로 표어가 건물 위에 얹힌다(학교가 고른 위치라면 그대로 둔다) — "
             f"글자 끝 {geo['글자오른쪽']:.0f}px, 건물 시작 {geo['건물왼쪽']:.0f}px")
    # 2401px 이상에서 표어만 왼쪽 6vw 로 빼서 로고 · 지표 띠와 왼쪽 선이 어긋난 적이 있다
    if abs(geo["표어왼쪽"] - geo["로고왼쪽"]) > 2:
        fail(f"{page} {w}px: 히어로 표어 왼쪽({geo['표어왼쪽']:.0f}px)이 헤더 로고 왼쪽({geo['로고왼쪽']:.0f}px)과 어긋난다")
    if geo["건물오른쪽"] > geo["화면폭"] + 2:
        warn(f"{page} {w}px: 히어로에서 건물 오른쪽이 화면 밖으로 잘린다(학교가 고른 위치라면 그대로 둔다) — "
             f"건물 끝 {geo['건물오른쪽']:.0f}px, 화면 {geo['화면폭']}px")


# ── 배치 — 한 번씩 무너졌던 것들 ──────────────────────────────
# 클래스 규칙이 `.block p` 같은 본문 규칙(명시도 0,1,1)에 덮여 단계 번호 · 신앙고백 번호 · 라벨이
# 본문 크기 회색으로 나간 적이 있다. 대표 요소의 크기가 제 규칙대로 나오는지 본다
STYLE_EXPECT = [(".step__no", "30px"), (".creed__no", "20px"), (".greeting__cap", "12.5px"),
                ("main .eyebrow:not(.eyebrow--light)", "13px")]


def check_layout(pg, page, w, h):
    r = pg.evaluate("""(expect) => {
      const out = [];
      const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      for (const [sel, px] of expect) for (const e of document.querySelectorAll(sel)) {
        const fs = getComputedStyle(e).fontSize;
        if (vis(e) && fs !== px) out.push(`${sel} 글자 크기 ${fs} (규칙은 ${px}) — 다른 규칙에 덮였다`);
      }
      // 데스크톱 메뉴는 한 줄 — 861~919px 에서 「상담 / 안내」 가 두 줄로 꺾였다
      if (innerWidth > 860) for (const a of document.querySelectorAll('.gnb > a'))
        if (vis(a) && a.getBoundingClientRect().height > 50) out.push(`메뉴 「${a.textContent.trim()}」 가 두 줄로 꺾인다`);
      const hw = document.querySelector('.header .wrap');
      if (hw && hw.scrollWidth > hw.clientWidth + 1) out.push(`헤더 메뉴가 한 줄에 들어가지 않고 넘친다 (${hw.scrollWidth} > ${hw.clientWidth})`);
      // 갤러리 빈 칸 — 두 칸 격자에서 묶음마다 한 칸이 비었다
      const g = document.querySelector('.gallery');
      if (g) {
        const gr = g.getBoundingClientRect(), cells = [...g.querySelectorAll('.gallery__cell')].map(c => c.getBoundingClientRect());
        let holes = 0;
        for (let y = gr.top + 30; y < gr.bottom - 30; y += 30) for (let x = gr.left + 30; x < gr.right - 30; x += 30)
          if (!cells.some(c => x >= c.left - 17 && x <= c.right + 17 && y >= c.top - 17 && y <= c.bottom + 17)) holes++;
        if (holes) out.push(`갤러리에 빈 칸이 있다 (${holes}점)`);
      }
      // 전화번호·번지가 하이픈에서 두 줄로 꺾이지 않는지 — 개인정보처리방침 「1833- / 6972」 가 390px 에서 갈렸다
      const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const NUM = /\\d{2,4}(?:-\\d{2,4}){1,2}/g;
      for (let n; (n = tw.nextNode()); ) {
        if (!n.parentElement || !vis(n.parentElement)) continue;
        for (const m of n.data.matchAll(NUM)) {
          const rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length);
          const tops = new Set([...rg.getClientRects()].filter(q => q.width > 0).map(q => Math.round(q.top)));
          if (tops.size > 1) out.push(`「${m[0]}」 가 두 줄로 갈린다 — .nowrap 으로 감쌀 것`);
        }
      }
      // 입력칸 글자가 16px 미만이면 아이폰이 칸을 누를 때마다 화면을 확대한다
      for (const f of document.querySelectorAll('input:not([type=radio]):not([type=checkbox]), select, textarea'))
        if (vis(f) && parseFloat(getComputedStyle(f).fontSize) < 16) out.push(`입력칸 #${f.id} 글자가 ${getComputedStyle(f).fontSize} — 아이폰이 확대한다`);
      // 히어로 슬라이더 조작이 첫 화면 안에 있는지 (높이 낮은 노트북 창에서 잘렸다)
      const c = document.querySelector('.hero__ctrl');
      if (c && innerHeight > 500 && scrollY === 0 && c.getBoundingClientRect().bottom > innerHeight)
        out.push(`히어로 슬라이더 조작이 화면 아래로 잘린다 (${Math.round(c.getBoundingClientRect().bottom)} > ${innerHeight})`);
      return out; }""", [list(x) for x in STYLE_EXPECT])
    for m in r:
        fail(f"{page} {w}x{h}: {m}")
    # 맨 끝까지 내렸을 때 마지막 줄(개인정보처리방침)이 하단 고정 바에 덮이지 않는지,
    # 바가 없는 페이지에 빈 띠가 남지 않는지
    if w <= 860:
        end = pg.evaluate("""() => {
          const html = document.documentElement, old = html.style.scrollBehavior;
          html.style.scrollBehavior = 'auto'; scrollTo(0, html.scrollHeight);
          const last = document.querySelector('.footer__bottom a'), bar = document.querySelector('.mobile-cta');
          const foot = document.querySelector('.footer');
          let r = null;
          if (last) { const b = last.getBoundingClientRect(), hit = document.elementFromPoint(b.left + 4, b.top + b.height / 2);
                      r = { 덮임: !!(hit && hit.closest('.mobile-cta')),
                            띠: (!bar || getComputedStyle(bar).display === 'none') && foot ? Math.round(innerHeight - foot.getBoundingClientRect().bottom) : 0 }; }
          scrollTo(0, 0); html.style.scrollBehavior = old;
          return r; }""")
        if end and end["덮임"]:
            fail(f"{page} {w}x{h}: 맨 아래 「개인정보처리방침」 이 하단 고정 바에 덮여 누를 수 없다")
        if end and end["띠"] > 2:
            fail(f"{page} {w}x{h}: 하단 바가 없는데 푸터 아래 {end['띠']}px 빈 띠가 있다")


def check_rendered_font(pg, page):
    pg.evaluate("document.fonts.ready")
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("DOM.enable"); cdp.send("CSS.enable")
    root = cdp.send("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
    other = {}
    for nid in cdp.send("DOM.querySelectorAll", {"nodeId": root, "selector": "body *"})["nodeIds"]:
        try:
            fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": nid})["fonts"]
        except Exception:
            continue
        for f in fonts:
            if f["familyName"] != "Pretendard Variable":
                html = cdp.send("DOM.getOuterHTML", {"nodeId": nid})["outerHTML"]
                other.setdefault(f["familyName"], re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()[:30])
    cdp.detach()
    for fam, where in other.items():
        fail(f"{page}: 글자가 Pretendard 가 아니라 {fam} 로 그려진다 — \"{where}\"")
    # 같은 이유로 <button> 은 브라우저 기본 회색 바탕(buttonface)을 갖는다.
    # 「작성 내용 복사」만 회색 상자로 보였다
    grey = pg.evaluate("""() => [...document.querySelectorAll('button')]
      .filter(b => b.getBoundingClientRect().width && getComputedStyle(b).backgroundColor === 'rgb(239, 239, 239)')
      .map(b => (b.textContent.trim() || b.getAttribute('aria-label') || '').slice(0, 20))""")
    for t in grey:
        fail(f"{page}: 버튼이 브라우저 기본 회색 바탕이다 — \"{t}\"")


# ── 히어로 2번(본관 정면) — 건물이 화면 밖으로 잘리지 않는지 ──────────
# hero-main.jpg 안에서 본관은 가로 23~70% 에 있다(격자 실측).
# object-position 78% 이던 때 왼쪽 날개가 잘리고 현관이 표어 밑에 깔렸다.
# 14% 로 고쳤을 때는 1021~1180px 에서 오른쪽 끝이 또 잘렸다 — 그래서 폭마다 잰다.
SLIDE2_X = (0.23, 0.70)


def check_hero_slide2(pg, page, w):
    if w <= 720:     # 700px 근처는 본관이 화면보다 넓어 들어갈 수 없다(계산으로 확인)
        return
    g = pg.evaluate("""(bx) => new Promise(done => {
      const s = [...document.querySelectorAll('.hero__slide')];
      if (s.length < 2) return done(null);
      const img = s[1].querySelector('img');
      if (img.dataset.src && !img.src.includes(img.dataset.src)) img.src = img.dataset.src;
      s.forEach((e, i) => e.classList.toggle('is-active', i === 1));
      const go = () => {
        const r = img.getBoundingClientRect(), nw = img.naturalWidth, nh = img.naturalHeight;
        const sc = Math.max(r.width / nw, r.height / nh);
        const off = (r.width - nw * sc) * parseFloat(getComputedStyle(img).objectPosition) / 100;
        const at = f => r.left + off + f * nw * sc;
        s.forEach((e, i) => e.classList.toggle('is-active', i === 0));
        done({ 왼쪽: at(bx[0]), 오른쪽: at(bx[1]), 폭: innerWidth });
      };
      (img.complete && img.naturalWidth) ? go() : (img.onload = go);
    })""", list(SLIDE2_X))
    if g and (g["왼쪽"] < -2 or g["오른쪽"] > g["폭"] + 2):
        warn(f"{page} {w}px: 히어로 2번(본관) 건물이 화면 밖으로 잘린다(학교가 고른 위치라면 그대로 둔다) — "
             f"{g['왼쪽']:.0f}~{g['오른쪽']:.0f}px, 화면 {g['폭']}px")


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
                    check_hero_slide2(pg, page, w)
                    check_hero_text(pg, page, w)

                check_layout(pg, page, w, h)

                # 화면의 글자가 실제로 Pretendard 로 그려지는지 — 브라우저에게 직접 묻는다.
                # <button> 은 글꼴을 물려받지 않아 신청 버튼만 시스템 글꼴로 그려진 적이 있다
                if w == 1366:
                    check_rendered_font(pg, page)

                if save_shots and w in (1440, 390):
                    pg.screenshot(path=f"{shots}/{page}-{w}.png", full_page=False)
                pg.close()
        for w, h in HERO_EXTRA:
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto(f"http://localhost:{PORT}/index.html", wait_until="networkidle")
            pg.add_style_tag(content=".hero__slide img { animation: none !important; }")
            pg.wait_for_timeout(300)
            if pg.evaluate("document.documentElement.scrollWidth > innerWidth + 1"):
                fail(f"index.html {w}x{h}: 가로로 삐져나온다")
            check_layout(pg, "index.html", w, h)
            check_hero_frame(pg, "index.html", f"{w}x{h}")
            check_hero_text(pg, "index.html", f"{w}x{h}")
            pg.close()
        check_behaviour(b)
        b.close()
    if not fails:
        ok(f"{len(PAGES)}페이지 × {len(VIEWPORTS)}뷰포트 — 넘침 · 대비 · 오류 · 404 없음")
        ok("모바일 메뉴를 열어 글자가 보이는지 확인함")


# ── 스크립트 동작 — 실제로 눌러 본다 ──────────────────────────
# 상담 양식 · 모바일 메뉴 · 슬라이더 · 옆 메뉴. 전부 "보기엔 멀쩡한데 눌러 보면 틀린" 것이었다
def check_behaviour(b):
    base = f"http://localhost:{PORT}/"
    def new(w, h, **kw):
        ctx = b.new_context(viewport={"width": w, "height": h}, **kw)
        pg = ctx.new_page()
        return ctx, pg

    # 상담 양식 (휴대폰) — 빈 칸으로 보내면 커서가 그 칸에 가고, 칸 옆 문구가 화면 안에 보여야 한다.
    # 예전엔 안내문이 버튼 아래(화면 밖)에 떠서 커서를 빼앗았다
    ctx, pg = new(390, 844, permissions=["clipboard-read", "clipboard-write"])
    mails = []
    pg.on("request", lambda r: mails.append(r.url) if r.url.startswith("mailto:") else None)
    pg.goto(base + "admission.html", wait_until="networkidle")
    pg.click("#inquiry-form button[type=submit]"); pg.wait_for_timeout(900)
    r = pg.evaluate("""() => { const a = document.activeElement, e = document.getElementById(a.id + '-error');
      const q = e && e.getBoundingClientRect();
      return { id: a.id, inv: a.getAttribute('aria-invalid'), 보임: !!q && q.top >= 0 && q.bottom <= innerHeight }; }""")
    if r["id"] != "pname" or r["inv"] != "true" or not r["보임"]:
        fail(f"admission.html 390px: 빈 양식을 보내면 빈 칸으로 가지 않는다 — 초점 {r['id']}, aria-invalid {r['inv']}, 문구 화면 안 {r['보임']}")
    pg.click("#copy-form"); pg.wait_for_timeout(400)
    if "복사했습니다" in (pg.text_content("#form-message") or ""):
        fail("admission.html: 빈 양식 · 동의 없이도 「복사했습니다」 라고 한다")
    pg.fill("#pname", "홍길동"); pg.fill("#phone", "010"); pg.select_option("#grade", index=3)
    pg.fill("#email", "not-an-email"); pg.check("#agree")
    pg.click("#inquiry-form button[type=submit]"); pg.wait_for_timeout(500)
    if pg.evaluate("document.activeElement.id") != "phone" or mails:
        fail("admission.html: 연락처 「010」 · 이메일 「not-an-email」 도 그대로 신청된다")
    pg.uncheck("#agree"); pg.fill("#phone", "010-1234-5678"); pg.fill("#email", "")
    pg.click("#inquiry-form button[type=submit]"); pg.wait_for_timeout(500)
    if pg.evaluate("document.activeElement.id") != "agree" or mails:
        fail("admission.html: 동의하지 않아도 보낸다, 또는 동의란으로 가지 않는다")
    pg.check("#agree")
    pg.fill("#msg", "첫 줄\n둘째 줄")
    pg.click("#inquiry-form button[type=submit]"); pg.wait_for_timeout(500)
    body = mails[0] if mails else ""
    if "%0D%0A" not in body or "%EB%8F%99%EC%9D%98%ED%95%A8" not in body:   # 동의함
        fail("admission.html: 메일 본문 줄바꿈이 CRLF 가 아니거나 동의 여부가 빠졌다")
    # 머리 줄만 CRLF 이고 학부모가 쓴 여러 줄 문의 내용은 LF 그대로 나간 적이 있다
    if re.search(r"(?<!%0D)%0A", body):
        fail("admission.html: 문의 내용 안의 줄바꿈이 CRLF 가 아니다 — 메일 본문 줄바꿈이 섞인다")
    # 복사가 막힌 브라우저 — 쓴 글을 글자 그대로 보여 줘야 한다(태그로 실행하지 말고)
    pg.fill("#msg", '1<2 <img src=x onerror="window.__x=1"> 끝')
    pg.evaluate("Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })")
    pg.click("#copy-form"); pg.wait_for_timeout(400)
    if pg.evaluate("window.__x === 1 || !!document.querySelector('#form-message img')"):
        fail("admission.html: 복사 실패 안내가 학부모가 쓴 글을 HTML 로 실행한다")
    # 길면 메일 앱에 넘기지 않는다 — 잘린 신청이 가는 것보다 낫다
    n = len(mails)
    pg.fill("#msg", "가" * 400)
    pg.click("#inquiry-form button[type=submit]"); pg.wait_for_timeout(500)
    if len(mails) > n and len(mails[-1]) > 2000:
        fail(f"admission.html: {len(mails[-1])}자짜리 mailto 주소를 연다 — 메일 앱이 자르거나 열지 못한다")
    # 그때 새로 붙는 「메일 쓰기」 버튼이 아래 고정 바에 가려졌다(390x844)
    hit = pg.evaluate("""() => { const a = [...document.querySelectorAll('#form-message a')].find(x => x.textContent.trim() === '메일 쓰기');
      if (!a) return '버튼 없음'; const q = a.getBoundingClientRect(); const e = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
      return (e && (e === a || a.contains(e))) ? '' : (e ? e.className || e.tagName : '화면 밖'); }""")
    if hit:
        fail(f"admission.html 390px: 긴 문의 뒤 「메일 쓰기」 버튼을 누를 수 없다 — {hit}")
    ctx.close()

    # 모바일 메뉴 — Esc 로 닫히고, 버튼 이름이 상태를 따라가야 한다
    ctx, pg = new(390, 844)
    pg.goto(base + "index.html", wait_until="networkidle")
    pg.click(".nav-toggle"); pg.wait_for_timeout(300)
    lab = pg.get_attribute(".nav-toggle", "aria-label")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    r = pg.evaluate("""() => ({ open: document.getElementById('gnb').classList.contains('is-open'),
      focus: document.activeElement.classList.contains('nav-toggle') })""")
    if lab != "메뉴 닫기" or r["open"] or not r["focus"]:
        fail(f"index.html 390px: 모바일 메뉴 — 열린 뒤 버튼 이름 「{lab}」, Esc 뒤 열림 {r['open']}, 초점 복귀 {r['focus']}")
    ctx.close()

    # 가로로 눕힌 휴대폰 — 메뉴 마지막 항목(입학 상담 신청)까지 손이 닿아야 한다
    # 세로로 연 채 돌린 경우도 본다 — 세로에서 잰 높이가 남아 아래 두 항목에 닿지 못했다
    for w, h, rot in [(844, 390, False), (667, 375, False), (844, 390, True)]:
        ctx, pg = new(h if rot else w, w if rot else h)
        pg.goto(base + "index.html", wait_until="networkidle")
        pg.click(".nav-toggle"); pg.wait_for_timeout(500)
        if rot:
            pg.set_viewport_size({"width": w, "height": h}); pg.wait_for_timeout(500)
        # 사람처럼 메뉴 위에서 굴린다(scrollTop 을 직접 바꾸면 overflow:hidden 이어도 움직여 검사가 속는다)
        g = pg.locator("#gnb").bounding_box()
        pg.mouse.move(g["x"] + g["width"] / 2, g["y"] + min(g["height"], 120) / 2)
        for _ in range(4):
            pg.mouse.wheel(0, 300); pg.wait_for_timeout(150)
        hit = pg.evaluate("""() => { const a = [...document.querySelectorAll('#gnb a')].pop(), r = a.getBoundingClientRect();
          return r.bottom <= innerHeight && a.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)); }""")
        if not hit:
            fail(f"index.html {w}x{h}{' (세로로 열고 돌림)' if rot else ''}: 열린 메뉴의 마지막 항목에 닿을 수 없다")
        ctx.close()

    # 태블릿을 가로로 돌리면(768 → 1024) PC 메뉴가 화면 낭독기에서 사라지면 안 된다
    ctx, pg = new(768, 1024)
    pg.goto(base + "index.html", wait_until="networkidle")
    pg.click(".nav-toggle"); pg.wait_for_timeout(300); pg.click(".nav-toggle"); pg.wait_for_timeout(400)
    pg.set_viewport_size({"width": 1024, "height": 768}); pg.wait_for_timeout(400)
    if pg.get_attribute("#gnb", "aria-hidden") == "true":
        fail("index.html 768→1024: 메뉴를 열었다 닫고 돌리면 PC 메뉴에 aria-hidden=true 가 남는다")
    ctx.close()

    # 슬라이더 — 멈춰 둔 뒤 → 를 눌러도 멈춘 채여야 한다
    ctx, pg = new(1366, 768)
    pg.goto(base + "index.html", wait_until="networkidle")
    pg.click("#hero-play"); pg.click("#hero-next"); pg.wait_for_timeout(200)
    if pg.get_attribute("#hero-play", "aria-label") != "사진 자동 넘김 다시 시작":
        fail("index.html: 자동 넘김을 멈춘 뒤 → 를 누르면 다시 돌기 시작한다")
    blank = pg.evaluate("[...document.querySelectorAll('.hero__slide img')].filter(i => !i.currentSrc).length")
    if blank:
        fail(f"index.html: 첫 화면이 뜬 뒤에도 히어로 사진 {blank}장이 비어 있다 — 번호를 누르면 빈 칸이 뜬다")
    ctx.close()

    # 동작 줄이기 — 켄번스가 멈추고, 재생 버튼은 눌렀을 때 실제로 돌아야 한다
    ctx, pg = new(1440, 900, reduced_motion="reduce")
    pg.goto(base + "index.html", wait_until="networkidle")
    anim = pg.evaluate("document.querySelector('.hero__slide.is-active img').getAnimations().length")
    pg.click("#hero-play"); pg.wait_for_timeout(200)
    lab = pg.get_attribute("#hero-play", "aria-label")
    if anim or lab != "사진 자동 넘김 멈추기":
        fail(f"index.html 동작 줄이기: 켄번스 {anim}개 도는 중, 재생을 눌러도 「{lab}」")
    ctx.close()

    # 학교소개 옆 메뉴 — 보고 있는 구역을 가리켜야 한다
    ctx, pg = new(1440, 900)
    # 주소의 #staff 로 부드럽게 굴러 내려가는 데 1초 남짓 걸린다
    pg.goto(base + "about.html#staff", wait_until="networkidle"); pg.wait_for_timeout(1800)
    cur = pg.evaluate("[...document.querySelectorAll('.sidenav__box a[aria-current]')].map(a => a.getAttribute('href'))")
    if cur != ["#staff"]:
        fail(f"about.html: 「섬기는 분들」 을 보는데 옆 메뉴는 {cur} 을 가리킨다")
    ctx.close()

    # 스크립트가 없을 때 — 지표가 0 으로 보이지 않고, 상담 양식이 주소창으로 개인정보를 보내지 않는다
    ctx, pg = new(390, 844, java_script_enabled=False)
    pg.goto(base + "index.html", wait_until="load")
    bad = pg.evaluate("[...document.querySelectorAll('[data-count]')].filter(e => e.textContent.trim() !== e.dataset.count).length")
    if bad:
        fail(f"index.html 스크립트 없음: 지표 숫자 {bad}개가 실제 값이 아니다")
    pg.goto(base + "admission.html", wait_until="load")
    if pg.is_visible("#inquiry-form") and pg.get_attribute("#inquiry-form", "method") != "post":
        fail("admission.html 스크립트 없음: 상담 양식이 GET 으로 개인정보를 주소창에 싣는다")
    ctx.close()

    if not fails:
        ok("상담 양식 검사 · 모바일 메뉴 · 슬라이더 · 옆 메뉴 · 스크립트 없음 — 눌러 보고 확인함")


class Quiet(http.server.SimpleHTTPRequestHandler):
    """배포본은 도메인 맨 위(https://www.pdcs.kr/)에 놓인다. 검사도 같은 주소 구조로 띄운다.
    (2026-10 까지는 intoedu.github.io/pdcs/ 아래였다)"""

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
