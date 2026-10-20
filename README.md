# Wholesale Daily Brief

AI 에이전트(Claude)가 매 영업일 09:00에 공개 데이터를 모아 팀 공용 시황 자료를 만들고 배포하는 프로젝트입니다.

- **앱 주소:** https://minsoo2528-spec.github.io/daily-brief/
  - 안드로이드(Chrome): 주소를 열고 화면 아래 **앱 설치**
  - 아이폰(Safari): 공유 버튼 → **홈 화면에 추가**
- 이 저장소의 루트(`index.html` 등)는 매일 실행이 자동으로 덮어쓰는 **배포본**이고, 코드는 `engine/`에 있습니다.

## 코드 구조 (`engine/`)

| 파일 | 역할 |
|---|---|
| `RUNBOOK.md` | 예약 실행이 그대로 따르는 실행 절차서 (수집 → 생성 → 검수 → 배포) |
| `scrapers/kofia_bond.js`, `scrapers/dart_bonds.js` | 브라우저 안에서 실행하는 수집 스크립트 (금투협 채권정보센터, DART) |
| `make_brief.py` | 원자료를 하나의 데이터 묶음으로 합쳐 웹페이지(HTML)와 고객 PDF를 생성 |
| `signals.py` | 세일즈 시그널 28개 규칙 판정 (영업일 계산, 중복 생략) |
| `templates/web_template.html` | 웹페이지 화면 (탭, 차트, 질문하기 창, Claude 답변) |
| `templates/ask.js` | 질문하기 계산 엔진 (질문 해석 → 데이터 계산 → 답변) |
| `templates/pdf_template.html` | 고객 PDF 양식 |
| `make_email.py` | 팀 메일 본문(시그널 요약 + 링크) 생성 |
| `build_pages.py`, `pages/` | 설치형 앱(GitHub Pages)용 파일 생성 (아이콘, 오프라인 지원) |
| `qa_static.json` | 질문하기 용어 설명 12개 |
| `config.example.json` | 설정 예시 (휴일, 시그널 기준값, 메일 받는 사람) |

## 데이터 처리 원칙

- 인증키·비밀번호 없음 (공개 API·공개 화면만 사용)
- 메일 주소가 담긴 실제 설정 파일, 원자료, 생성물, 자금중개 PDF는 저장소에 올리지 않음 (`engine/.gitignore`)
- 숫자는 코드가 계산하고, AI(Claude)는 해설·요약·답변만 작성
- 확인되지 않은 값은 추정하지 않고 비워 둠

참고자료이며 특정 상품의 투자권유를 목적으로 하지 않습니다.
