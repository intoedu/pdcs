# 폴앤다니엘기독학교 홈페이지

충청남도 아산의 기숙형 기독 대안교육기관 **폴앤다니엘기독학교(PDCS)**의 새 홈페이지입니다.
빌드 도구 없이 동작하는 정적 사이트라, 파일을 열면 바로 보입니다.

## 페이지

| 파일 | 내용 |
|---|---|
| `index.html` | 메인 — 히어로, 세 기둥, 하루 일과, 교육과정, 갤러리, 상담 안내, 오시는 길 |
| `about.html` | 학교소개 — 인사말, 신앙고백, 교육철학, 섬기는 분들 |
| `admission.html` | 입학 · 문의 — 입학 절차, 상담 신청 양식, FAQ |
| `privacy.html` | 개인정보처리방침 |
| `404.html` | 잘못된 주소 안내 |

## 구조

```
index.html / about.html / admission.html / privacy.html / 404.html
robots.txt / sitemap.xml
assets/
  css/style.css              모든 스타일 (CSS 변수로 색상 관리)
  js/main.js                 모바일 메뉴, 히어로 슬라이더, 스크롤 등장, 숫자 카운트업, 옆 메뉴 현재 위치,
                             상담 양식 검사 · 메일 작성 (CLAUDE.md 「스크립트 동작」)
  fonts/woff2-dynamic-subset/ Pretendard 조각 92개 (쓰인 글자가 든 조각만 받는다)
  fonts/LICENSE.txt          SIL OFL 1.1 원문
  img/                       학교 사진, 엠블럼
bump.sh / check.py           배포 전 실행 (CLAUDE.md 참조)
```

## 미리 보기

```bash
python3 -m http.server 8000
# http://localhost:8000
```

`file://` 로 열어도 대부분 동작하지만, 웹폰트는 로컬 서버에서 봐야 제대로 적용됩니다.
`404.html` 은 도메인 맨 위(`/assets/...`) 기준 절대경로입니다. 저장소 폴더를 웹 서버 맨 위로 띄우면 그대로 보입니다. 배포 주소는 https://www.pdcs.kr/ 입니다.

## 만들어진 방식

- **반응형** — 1280 / 1080 / 860 / 520px 기준으로 레이아웃이 바뀝니다. 모바일에서는 하단에 전화·상담 버튼이 고정됩니다
- **접근성** — 본문 바로가기, 키보드 포커스 표시, 아이콘 버튼 `aria-label`, 터치 영역 최소 46px
- **동작 줄이기 존중** — 기기 설정에서 '동작 줄이기'를 켠 분에게는 모든 애니메이션이 꺼집니다
- **웹폰트 자체 호스팅** — 외부 CDN에 의존하지 않습니다

## 서버 없이 동작하는 방식

이 사이트는 **GitHub 저장소와 GitHub Pages만으로** 돌아갑니다. 서버도, 데이터베이스도, 빌드 도구도 없습니다.

- **상담 신청** — 입력한 내용을 담은 메일을 자동 작성해 열어 줍니다(휴대전화·컴퓨터 모두 메일).
  학부모가 보내기를 눌러야 학교(bcia_k@naver.com)에 도착합니다
- **지도** — 구글지도 iframe. API 키가 필요 없습니다. 카카오맵 길찾기 링크도 함께 둡니다
- **안내 카드(상담 안내)** — `index.html` #news 의 카드를 직접 고칩니다. 고쳐서 push 하면 몇 분 안에 반영됩니다

## 아직 비어 있는 것

학교에 받아야 할 자료는 [필요한자료.md](필요한자료.md)에 정리되어 있습니다.

## 색상과 폰트

브랜드 기준, 폰트 라이선스 정책, 확인이 필요한 사항은 [`CLAUDE.md`](CLAUDE.md)에 정리되어 있습니다.

폰트는 **Pretendard Variable 1.3.9**(SIL Open Font License 1.1)를 씁니다. 상업적 사용과 웹폰트 임베딩이 허용됩니다.
공식 npm 패키지 `pretendard@1.3.9` 의 조각 나눔(dynamic subset) 배포본을 그대로 자체 호스팅합니다.

## 디자인 시안

시안 캔버스: https://claude.ai/artifact/TF2sG65xHQLue1zA9yyosX (비공개)
