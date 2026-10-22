# Fund Sales Daily Brief

한화투자증권 Wholesale 금융상품영업팀(펀드 브로커)을 위한 데일리 세일즈 도구입니다.
AI 에이전트(Claude)가 매 영업일 오전 9시에 공개 시장 데이터를 모아 **하나의 화면**으로 정리하고, 웹·앱·PDF·팀 메일로 배포합니다.

- **앱 주소:** https://minsoo2528-spec.github.io/daily-brief/
  - 휴대폰: 주소를 열고 **앱 설치**(안드로이드) 또는 공유 → **홈 화면에 추가**(아이폰)
  - PC: Edge·Chrome에서 주소를 열고 **앱 설치**
- 저장소 루트(`index.html` 등)는 매일 실행이 자동으로 덮어쓰는 **배포본**이고, 소스코드는 `engine/`에 있습니다.

## 주요 기능

| 구분 | 내용 |
|---|---|
| 시장 브리프 | 요약(장중 현재 시황 포함) · 매크로 · 수익증권 · 채권 · 단기자금 · 캘린더 6개 탭 |
| 영업 데스크 | 세일즈 시그널(28개 기준 자동 판정) · MMF 주문(BETA) · 펀드 관리(BETA, 운용사 공문 일정·금액) |
| Claude 챗봇 | 그날 브리프 데이터로 답변. 계산이 필요하면 페이지의 계산 엔진을 도구로 호출 |
| 메일함 확인(시연) | 메일에서 MMF 주문·운용사 공문을 Claude가 추출하고, 코드가 원문 문구와 날짜·금액·매수/환매를 대조한 뒤 반영 |
| 실시간 조회 | 보는 사람이 넣은 본인 인증키로 한국은행 ECOS 시장금리, OpenDART 발행공시 조회(채권 탭) |
| 배포 | claude.ai 팀 페이지 · 설치형 앱(GitHub Pages) · 고객 PDF(사람 검토 후 발송) · 팀 메일(PDF 첨부) |

## 코드 구조 (`engine/`)

| 파일 | 역할 |
|---|---|
| `RUNBOOK.md` | 매일 예약 실행이 그대로 따르는 실행 절차서 (수집 → 생성 → 검수 → 배포) |
| `scrapers/kofia_bond.js`, `scrapers/dart_bonds.js` | 브라우저 안에서 실행하는 수집 스크립트 (금투협 채권정보센터, DART) |
| `scrapers/market_now.js` | 장중 현재 시황(코스피·코스닥·미국 지수) 스냅샷 수집 |
| `make_brief.py` | 원자료를 하나의 데이터 묶음으로 합쳐 웹페이지(HTML)와 고객 PDF 생성 |
| `signals.py` | 세일즈 시그널 28개 기준 판정 (영업일 계산, 3영업일 중복 생략) |
| `mmf_orders.py` | MMF 주문 추출값을 메일 원문과 대조, 10영업일 바둑판·합계 계산 |
| `notices.py` | 운용사 공문 일정·금액을 원문과 대조, 공문 종류별 정리 |
| `templates/web_template.html` | 화면 전체 (탭, 차트, 질문하기, Claude 답변, 메일함 확인, API 설정) |
| `templates/ask.js` | 질문하기 계산 엔진 (질문 해석 → 데이터 계산 → 답변) |
| `templates/pdf_template.html` | 고객 PDF 양식 |
| `make_email.py` | 팀 메일 본문(현재 시황 + 시그널 요약 + 링크) 생성 |
| `build_pages.py`, `pages/` | 설치형 앱 파일 생성(아이콘, 오프라인 지원). 실제 메일 데이터가 섞이면 중단 |
| `server/apps_script_Code.gs`, `server/apps_script_appsscript.json` | 앱용 시연 서버(Google Apps Script): Claude API 중계, Gmail 읽기 전용(제목에 MMF·공문이 있는 메일만), ECOS·OpenDART 중계 |
| `server/cloudflare_worker.js` | 같은 기능의 Cloudflare Worker 대안 코드(현재 미사용) |
| `qa_static.json` | 질문하기 용어 설명 |
| `config.example.json` | 설정 예시 (휴일, 시그널 기준값, 메일 받는 사람, 시연 서버 주소) |

## 데이터 출처

한국은행 ECOS · 미 재무부 · 금융투자협회 FreeSIS·채권정보센터 · 한국예탁결제원 SEIBro · 금융감독원 DART · 다음 금융(장중 시세) · 한국자금중개 「일일 원화자금 현황」(활용 협의 완료) · 언론 기사(자체 요약 + 원문 링크)

## 데이터 처리 원칙

- 숫자는 코드가 원자료에서 계산하고, AI(Claude)는 해설·요약·답변·메일 추출만 담당. AI가 뽑은 값은 코드가 원문과 대조해 맞는 것만 반영
- 확인되지 않은 값은 추정으로 채우지 않고 비워 둠
- API 키·비밀번호는 저장소·페이지에 없음 (Claude API 키는 시연 서버의 스크립트 속성에만, ECOS·DART 키는 보는 사람의 브라우저에만 저장)
- 메일 주소가 담긴 실제 설정 파일, 원자료, 생성물, 자금중개 PDF, 회사 CI 이미지는 저장소에 올리지 않음 (`engine/.gitignore`)
- MMF 주문·펀드 관리의 기본 데이터는 가상 메일. 실제 회사 메일함 연결은 사내 승인 후 진행
- 고객에게는 자동 발송하지 않음. 모든 자료에 출처·기준일·투자권유 아님 문구 표시
