#!/bin/sh
# 스타일·스크립트가 바뀌면 파일 내용 해시를 주소에 붙인다.
# 브라우저가 옛 파일을 계속 쓰는 것을 막는다. 배포 전 항상 실행.
set -e
cd "$(dirname "$0")"
python3 - <<'PY'
import pathlib, hashlib, re
v = {p: hashlib.sha1(pathlib.Path(p).read_bytes()).hexdigest()[:8]
     for p in ("assets/css/style.css", "assets/js/main.js")}
# 404.html 은 어느 주소에서 떠도 자원을 찾도록 절대경로(/pdcs/...)를 쓴다.
# 빠뜨리면 404 화면만 옛 스타일로 남는다
for name in ("index.html", "about.html", "admission.html", "privacy.html", "404.html"):
    p = pathlib.Path(name); s = p.read_text(encoding="utf-8")
    s = re.sub(r'href="(/pdcs/)?assets/css/style\.css(\?v=[0-9a-f]+)?"',
               lambda m: f'href="{m.group(1) or ""}assets/css/style.css?v={v["assets/css/style.css"]}"', s)
    s = re.sub(r'src="(/pdcs/)?assets/js/main\.js(\?v=[0-9a-f]+)?"',
               lambda m: f'src="{m.group(1) or ""}assets/js/main.js?v={v["assets/js/main.js"]}"', s)
    p.write_text(s, encoding="utf-8")
print("css", v["assets/css/style.css"], "· js", v["assets/js/main.js"])
PY
