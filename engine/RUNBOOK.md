# Daily Market Brief 실행 절차 (예약 작업용)

이 문서는 매 영업일 아침 예약 작업이 그대로 따라 하는 절차다. 모든 수치는 원자료에서 가져오고, 추정값은 넣지 않는다.

- PC 폴더: `C:\Users\Training-28\Documents\Daily_Brief`
  - `inbox\` 팀원이 한국자금중개 「일일 원화자금 현황」 PDF를 저장하는 곳
  - `output\` 고객 전달용 PDF 저장 (`YYYY-MM-DD_Daily_Market_Brief.pdf`)
  - `engine\` 이 문서, `make_brief.py`, `make_email.py`(팀 메일 본문), `build_pages.py`+`pages\`(앱용 GitHub Pages), `templates\`, `raw\`(원자료·누적 이력)
- 웹페이지(팀 내부용): https://claude.ai/artifact/A9xGuRin8tpMD7bPNiiG1i (매일 같은 주소로 갱신)

## 0. 시작
1. 오늘(Asia/Seoul) 날짜를 확인한다. 토·일이면 아무것도 하지 않고 종료.
2. `engine\raw\*.json`, `engine\templates\*`, `engine\scrapers\*.js`, `engine\make_brief.py`, `engine\make_email.py`, `engine\build_pages.py`, `engine\pages\*`, `engine\signals.py`, `engine\qa_static.json`, `engine\config.json`을 작업 공간으로 가져온다(device_stage_files). `inbox\`의 PDF 목록도 확인한다(device_list_dir).
3. `pip install --break-system-packages weasyprint jinja2 matplotlib` (없을 때만).

## 1. 국내 금리 — 한국은행 ECOS (raw/rates_kr.json)
- 통계 817Y002(시장금리 일별). WebFetch로 `https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/{시작}/{끝}/817Y002/D/{날짜}/{날짜}` 를 1~10, 11~20, 21~30 세 번 호출해 하루치 전 항목을 받는다. (샘플키는 1회 10건 제한. engine\config에 개인 인증키가 생기면 그것을 쓴다.)
- 날짜 4개: d0 = ECOS에 값이 있는 가장 최근 영업일, d1 = 그 직전 영업일, w1 = d0의 7일 전 이하 가장 가까운 영업일, m0 = 전월 마지막 영업일.
- 오늘 실행에서 d0가 직전 실행의 d0와 같으면 휴장일로 보고 종료한다(사용자에게 한 줄 알림).
- items의 각 항목에 {d0,d1,w1,m0} 값을 넣는다. KOFR·민평처럼 하루 늦게 나오는 항목은 d0를 null로 둔다.
- series: CD(91일)·CP(91일)·콜금리(1일)·KOFR를 m0~d0 구간으로 항목별 조회(`.../817Y002/D/{m0}/{d0}/{항목코드}`)해 채운다. 항목코드: 콜 010101000, CD 010502000, CP 010503000, KOFR 010901000, 국고3년 010200000.
- WebFetch 요약 모델이 값을 옮기므로, 날짜별 조회값과 항목별 시계열 값이 일치하는지 반드시 대조한다. 불일치하면 해당 항목을 다시 받는다.

## 2. 미 국채 — 미 재무부 (raw/rates_us.json)
- `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value_month=YYYYMM` (필요하면 전월 페이지도). 3M·2Y·10Y·30Y를 d0·d1·w1·m0에 맞춰 넣는다(미국 기준 같은 날짜 또는 그 이전 최근일).

## 3. MMF·펀드 자금흐름 — 금투협 FreeSIS (raw/freesis.json, raw/mmf_history.json)
내장 브라우저로 한다(사이트 승인 완료 상태).

### 3-1. MMF 설정원본 1년 일별 시계열 (raw/mmf_history.json, 단위 억원)
1. `https://freesis.kofia.or.kr/` 열기 → 상단 `펀드` → 메인 화면의 「펀드집계 통계 [투자신탁구분]」 링크(serviceId STATFND0100100010)로 「집합투자기구구분」 화면을 연다. 화면은 프레임(window.frames[0]) 안에 있다.
2. 프레임 컨텍스트에서 아래 요청을 직접 보낸다(화면의 「추이」 탭 조회와 같은 요청).
```js
const W=window.frames[0];
async function q(type, gb, from, to){ const body=JSON.stringify({dmSearch:{tmpV40:"100000000",tmpV41:"1",tmpV30:from,tmpV31:to,tmpV6:"1",tmpV10:"0",tmpV4:"",tmpV7:gb,tmpV3:type,tmpV11:"",OBJ_NM:"STATFND0100100011BO"}});
  const r=await W.fetch('../meta/getMetaDataList.do',{method:'POST',headers:{'Content-Type':'application/json; charset=UTF-8'},body}); return JSON.parse(await r.text()).ds1; }
// tmpV6 "1"=설정원본, tmpV7 ""=공모+사모 전체 / "1"=공모 / "2"=사모, tmpV3 "05"=단기금융(MMF) (채권형 01, 주식형 02, 부동산 07, 특별자산 11)
// 응답 ds1: TMPV1 날짜(YYYYMMDD), TMPV16 합계(억원), TMPV17 전일대비(억원)
```
3. raw/mmf_history.json의 마지막 날짜 다음날부터 오늘까지 전체·공모·사모 세 번 조회해 [YYYY-MM-DD, 합계, 공모, 사모] 행을 추가한다(이미 있는 날짜는 덮어쓴다).
4. 검증: 모든 새 행에서 |합계 − (공모+사모)| ≤ 1억, 그리고 TMPV17(전일대비)이 합계 차이와 같은지 확인.

### 3-2. 기준일 설정원본·자금유출입 (raw/freesis.json, 단위 백만원)
1. 상단 `펀드` → 펀드 요약 화면에서 라디오 `펀드`(AUM 아님) 선택.
2. 네트워크 응답 `fundSubMain/STATFNDSUBMAIN01BO.do`(설정원본)와, `자금유출입` 탭 클릭 후 `STATFNDSUBMAIN03BO.do`(자금유출입)의 본문을 읽는다(read_network_requests의 requestId).
3. 01BO(설정원본): dmTab3Title로 열 의미를 확인한다. TMPV2 공모·TMPV3 사모·TMPV4 계(기준일), TMPV5~7 공모·사모·계 전일대비, TMPV8~10 전월말대비. → setup의 단기금융·부동산·채권·특별자산.
4. 03BO(자금유출입): TMPV4 공모 증감, TMPV7 사모 증감, TMPV10 계 증감 → flows의 단기금융·채권·주식·부동산·특별자산·합계.
5. 검증: 01BO 단기금융 계(백만원)/100 이 3-1의 같은 날짜 합계(억원)와 1억 이내로 같은지 확인.
6. 고객유형별(월별)은 매월 초에만 갱신: 펀드 > 펀드산업 > 판매통계 > 고객유형별규모, 응답 ds1의 단기금융 행(개인 TMPV2, 일반법인 TMPV4, 금융기관 TMPV6, 합계 TMPV9, 억원)과 화면의 기준일.

## 4. Repo 잔액 — 예탁원 SEIBro (raw/repo_history.json, 단위 원)
1. 내장 브라우저로 `https://seibro.or.kr/websquare/control.jsp?w2xPath=/IPORTAL/user/moneyMarke/BIP_CNTS04028V.xml&menuNo=937` 를 연다.
2. 같은 페이지에서 화면이 쓰는 조회 요청을 날짜별로 직접 보낸다(한 번에 전 행, 요청 사이 0.25초 간격):
```js
const body = d8 => `<reqParam action="repoTradingBalanceDayObjList" task="ksd.safe.bip.cnts.MoneyMarke.process.ShortmFncegdStatPTask"><MENU_NO value="937"/><CMM_BTN_ABBR_NM value="total_search,openall,print,hwp,word,pdf,seach,xls,xls,"/><W2XPATH value="/IPORTAL/user/moneyMarke/BIP_CNTS04028V.xml"/><STD_DT value="${d8}"/><TD_TPCD value=""/><SHORTM_FNCE_INDTP_TPCD value=""/><PURAMT_APLI_CUR_KACD value=""/><START_PAGE value="1"/><END_PAGE value="200"/></reqParam>`;
async function day(d8){ const r=await fetch('/websquare/engine/proworks/callServletService.jsp',{method:'POST',headers:{'Content-Type':'application/xml; charset=UTF-8'},body:body(d8)});
  const x=new DOMParser().parseFromString(await r.text(),'text/xml');
  return [...x.getElementsByTagName('result')].filter(e=>e.getElementsByTagName('TD_TPCD_NM').length).map(e=>{const g=n=>{const el=e.getElementsByTagName(n)[0];return el?el.getAttribute('value'):null;};
    return {side:g('TD_TPCD_NM'), ind:g('SHORTM_FNCE_INDTP_TPCD_NM'), cur:g('PURAMT_APLI_CUR_KACD'), sum:+g('DAYOBJ_SUM')};}); }
```
3. raw/repo_history.json 마지막 날짜 다음날부터 오늘까지 평일마다 조회. 행이 0개면 휴장일이니 건너뛴다. cur==='KRW' 행만 써서 [YYYY-MM-DD, KRW행수, 매도합계, 매수합계, 매수|은행(신탁), 매수|집합투자, 매수|국내은행, 매수|증권사(신탁), 매수|여신 금융업, 매수|증권사, 매도|증권사, 매도|집합투자] (원)을 추가.
4. 검증: 매도합계 = 매수합계가 아니면 그 날짜를 다시 조회한다. make_brief.py도 이를 확인한다.
5. 차트는 make_brief.py가 최근 1년(365일) 구간을 자동으로 잘라 그린다. 이력 파일은 지우지 않고 계속 쌓는다.

## 4-2. 회사채 발행·투자자·CP — DART·금투협 채권정보센터 (매일)
내장 브라우저에서 두 사이트가 승인돼 있어야 한다(dart.fss.or.kr, www.kofiabond.or.kr). 승인이 안 돼 있으면 이 단계 결과 파일은 전날 것을 그대로 두고 알림에 "사이트 승인 필요"를 적는다.
- 공모채 수요예측(raw/bond_deals.json): dart.fss.or.kr 탭에서 engine/scrapers/dart_bonds.js 내용을 실행한 뒤 `await dartBonds(최근 3주 시작일, 오늘)`. 결과 {deals, upcoming}에 source·asof·window·unit·cols를 붙여 저장. 검사: 각 수요예측 표에서 6개 투자자 합 = 합계(어긋나면 그 건 제외), 발행액(amts)이 비면 [발행조건확정] 문서의 「3. 모집 또는 매출금액」을 직접 확인해 채운다. 비어 있는 확정금리는 청약 전날 공시가 나오면 채워진다(그 전에는 "-").
- 투자자별 순매수(raw/kofia_investor.json): www.kofiabond.or.kr 탭에서 engine/scrapers/kofia_bond.js 실행 후 d0(전 영업일) `investor('YYYYMMDD')`를 호출해 「순매수」 행만 daily[YYYYMMDD]에 추가(투자자명 매핑은 스크립트 주석대로). 검사: 채권종류 합 = 합계(±12억), 이번 달 일별 합 = 기간 조회(`kofia('BISIvtrTrdSrchSO','list',[월초,d0,'','','8','C'])`) 값(±5억). 최근 25영업일만 남긴다.
- CP(raw/cp_daily.json): `cpDay('YYYYMMDD')` 결과에서 할인 금리·거래량·잔액, 매출 금리·거래량을 daily[d0]에 추가(만기 구간 합 = 합계 검사). 최근 30영업일 유지.
- 전단채(raw/stb_daily.json): `stb(d0)` 전체 건을 받아 AB구분='일반'·거래구분='직접매입(할인)'만 발행사별로 합산(금액=거래량 액면, 백만원). 금리는 같은 발행사·만기의 '매출' 건 금리를 금액 가중평균. 발행사 구분: 이름에 증권→증권사, 캐피탈·카드·파이낸셜·저축은행·리스→캐피탈·카드, 공사·공단·한국전력→공기업, 은행·생명·화재·보험→은행·보험, 그 외 일반기업. byCls 합 = top 합 검사.
- 코멘트(content.json bond_flow_comment): 수요예측 건수·발행액·총수요·참여 비중, 눈에 띄는 딜(높은 경쟁률, 미달, 밴드 상단 발행), 이번 달 자산운용(공모)·은행·기금공제 순매수, CP 잔액 변화를 raw에서 계산한 숫자로 쓴다.

## 4-3. 대기업 단기자금 — 회사채 만기·납입(매일), 현금성자산(분기)
- 회사채 만기·납입(raw/corp_events.json): kofiabond 탭에서 `corpBonds()`로 회사채 전 종목을 받아 만기일이 오늘~6주 뒤인 것 중 종목명에 '사모'·CB·BW·EB가 없는 100억 이상만 남긴다(발행사명은 종목명 끝 회차 숫자 제거). 구분: 증권·금융지주·에프앤아이·자산관리→금융, 발전·수력원자력→공기업, 위탁관리부동산→리츠, 그 외 일반기업. payins는 bond_deals.json의 납입일(오늘 이후)과 upcoming 예정 납입. 조기상환은 반영되지 않는다는 문구 유지.
- 대기업 현금성자산(raw/corp_liquidity.json): 분기·반기·사업보고서 제출 시즌(5월 중순, 8월 중순, 11월 중순, 3월 말) 다음 영업일에만 갱신. DART 상세검색(publicType A003 분기/A002 반기/A001 사업, corporationType P)으로 보고서 목록을 받고, rows의 기업명과 같은 회사의 최신 보고서에 `bsCash(rcpNo)`를 실행. 단위(원·천원·백만원)를 억원으로 환산, 단기 운용자산 = 현금및현금성자산 + '단기금융상품/단기금융자산/단기투자자산'으로 표시된 금액. 비교 시점은 직전 사업연도 말. 이 표는 팀 웹페이지 전용(고객 PDF 미포함).
- 캘린더: make_brief.py가 1,000억 이상 만기와 공모채 납입을 자동으로 캘린더에 추가한다(초록색 '기업' 표시).
- 코멘트(content.json corp_comment): 현금성자산 상위·증감, 6주 만기 합계와 가장 많은 주, 큰 납입 건.

## 4-4. 영업 시그널 입력값 (signals.py가 자동 판정)
- 시그널은 make_brief.py 실행 때 engine/signals.py가 raw 데이터로 자동 판정한다(29개 기준). 기준값은 config.json의 "signals"에 키를 넣어 바꿀 수 있다(키 이름·기본값은 signals.py의 DEFAULT). 휴장일은 config.json "holidays"에 추가(연초에 1년치 갱신).
- content.json에 매일 채울 값(뉴스·공식 자료에서 확인한 수치만):
  - market.kospi {date, close, chg_pct, src}, market.usdkrw {date, close, chg(원), src} — 지표 기준일 종가.
  - cpi: 이번 주 발표된 한국·미국 CPI [{name, actual, consensus, date}] (예상치가 기사에 없으면 consensus 생략 → 판정 안 함). 지난 발표는 지운다.
  - base_rate: 현재 한국은행 기준금리(%). 금통위에서 바뀌면 갱신.
  - policy_surprise: 금통위·FOMC 결과가 시장 예상과 달랐던 날만 {"text": "..."} 입력, 다음 날 삭제.
- raw/reit_offerings.json: dart 탭에서 `await reitOfferings(2주 전, 오늘)` 결과를 items로, window·checked 갱신.
- raw/signal_history.json: 시그널 발생 이력(3영업일 중복 방지용). make_brief.py가 갱신하므로 실행 후 반드시 PC의 engine\raw\에 되돌려 저장.
- raw/ratings.json(신용등급 하향), F5 리츠 직전 발행금리는 아직 수집 경로 준비 중 → 시그널 탭에 "준비 중"으로 표시됨.
- 알림 메시지(8단계)에 🔴 행동 시그널 제목을 1줄씩 넣는다.

## 5. 한국자금중개 PDF — inbox (content.json의 kmb, calendar)
- `inbox\`에서 수정시각이 가장 최근인 PDF를 가져와 텍스트를 추출하고(pdfplumber), 페이지를 이미지로도 확인한다. 리포트 날짜가 d0와 같은지 확인한다. 같은 날짜가 없으면 kmb를 null로 두고(웹·PDF에서 섹션 자동 생략) 사용자에게 "자금중개 PDF 미수신"을 알린다.
- kmb.kpis: 콜(O/N)·전일비, 레포(일반채·회사채), 지준 당일·적수(억원과 조원 병기), 지준 마감일, 한은 RP매각, 통안계정 금리.
- kmb.bullets: 지준·레포·증권·외은·전망을 각 2문장 이내로 다시 써서(원문 문장 복사 금지) 요약.
- reserve_week (주간 지준 요인표, 한국자금중개 캘린더와 같은 형식): 리포트의 「지준 주요 요인」 표를 날짜 열 그대로 옮긴다. 구조 `{"source","asof","note","days":[{"date":"YYYY-MM-DD","supply":[["항목",억원],...],"withdraw":[["항목",억원],...],"events":["금통위",...],"daily":억원,"cum":억원}]}`. 검산 필수: 지준 당일(t) = 지준 당일(t-1) + Σ공급 − Σ환수, 적수(t) = 적수(t-1) + 지준 당일(t). make_brief가 다시 검산하며 어긋나면 중단한다. 리포트가 없으면 reserve_week를 null로 둔다.
- calendar (월간 달력·일정 목록): 항목 `{"date":"YYYY-MM-DD","text","key":true(굵게, 선택),"kmb":true(자금중개 출처),"check":true(미확인)}`. 국고채·통안채 발행, 한은 RP 매입/매각·만기, 금통위, 공모주 환불, 지준 마감일, 주요 미국 지표를 넣는다. 공식 출처로 확인 못 한 일정은 "check"를 붙인다(고객 PDF에서 자동 제외). 날짜는 반드시 ISO 형식.
- 예상 적수 추이처럼 계산 가능한 값은 리포트 수치로 재계산해 맞는지 확인한다.
- 저작권: 한국자금중개 자료는 저작권 정책상 사전 협의 없이 고객 배포물에 쓰지 않는다. 그래서 자금중개에서 나온 요약 문장은 summary에 {"text": ..., "kmb": true}로, 캘린더 항목은 "kmb": true로 표시한다. 한국자금중개 자료 활용은 2026-10-19 협의 완료되어 engine\config.json의 client_pdf_include_kmb가 true다(고객 PDF에도 포함). 이 값은 사용자가 지시할 때만 바꾼다. false로 바꾸면 고객용 PDF에서 kmb 섹션·문장·일정이 빠지고 웹에는 그대로 남는다. 금통위처럼 공개된 일정은 kmb 표시 없이 따로 넣는다.

## 6. 뉴스·코멘트 (content.json)
- WebSearch extended 모드로: 국내 증시 마감, 원/달러 마감, 채권시장 마감(국고 3년 수치가 ECOS와 같은지 대조), 미국 지표·연준, 한은·금통위, 부동산 PF·오피스·리츠, 부동산펀드 관련 소식. 기사 본문은 WebFetch로 읽는다.
- 작성 규칙: 사실 중심 중립 문체, 특정 상품 매수·가입 권유 표현 금지, 기사 문장 복사 금지(직접 인용은 1건 15단어 미만), 항목마다 출처 표기.
- 채운다: date(오늘), summary 4줄, macro 4건, fund_news 6~8건, flows_comment, bond_comment, money_comment, supply_comment, sources.
- macro 항목: `{"title","outlet","date":"YYYY-MM-DD","url"(원문 기사 주소, WebFetch로 열어 확인한 것만),"key"(핵심 숫자, 예 "5,668.05"),"key_label"(그 숫자 설명),"body"(2~3문장 재작성),"points":[상세 화면용 2~4줄]}`.
- fund_news 항목(수익증권 탭, 부동산 중심): `{"cat"("부동산 PF"/"리츠"/"부동산펀드"/"펀드 자금"/"채권형" 등),"title","outlet","date","url","key","key_label","summary"(2~3문장),"points":[2~4줄]}`. 부동산 관련을 절반 이상, 최근 7일 이내 기사 우선.
- 사진: 언론사 사진은 저작권 문제로, 아티팩트는 보안 정책상 외부 이미지가 막혀 있어 넣지 않는다. 대신 카드에 핵심 숫자를 크게 보여주고, 누르면 상세(세컨) 화면 → "원문 기사 보기"로 기사에 연결한다. PDF는 기사 제목이 하이퍼링크다.
- 펀드 유형별 자금흐름은 FreeSIS 기준일 하루의 설정−해지(일간)이다. 화면 라벨 "일간 · 기준일 하루"를 유지한다.
- 오피스 시장 분기 자료 섹션은 2026-10-19 사용자 요청으로 삭제했다. 다시 넣지 않는다.
- 코멘트의 모든 숫자는 raw 데이터에서 계산해 넣는다.

## 6-2. 질문 도우미 답변 은행 (content.json "qa")
- 웹페이지 오른쪽 아래 '질문하기'는 외부 호출 없이 동작한다. 숫자 질문은 templates/ask.js가 페이지 안 원자료로 직접 계산하고, 해설형 질문은 content.json "qa"(그날 작성)와 qa_static.json(용어 설명, 고정)에서 가장 비슷한 질문을 찾아 답한다.
- 매일 content.json "qa"를 새로 쓴다(전날 것은 지운다). 15~25개, 형식 {q, alts:[비슷한 질문 2~4개], tags:[], src, a, pin?}.
  - 반드시 포함: "오늘 핵심 3줄"(pin), "이번 주 고객 연락 리스트"(pin), 발생한 시그널마다 "○○ 시그널은 왜 떴어?", 오늘 눈에 띄는 딜·이슈의 고객 안내 문구 초안 1~2개(pin 1개), MMF·금리·CP·지준 해설.
  - 답변의 모든 숫자는 raw·brief_data에서 확인한 값만 쓰고, 기준일과 출처(src)를 적는다. 추정·전망은 기사 출처가 있을 때만 "~라는 보도" 형태로 쓴다.
  - 투자권유 표현 금지. 고객 안내 문구는 "[안내 초안] … 발송 전 컴플라이언스 확인 필요"를 붙인다.
- 생성 후 검증: out/web.html을 브라우저(Playwright)로 열어 `window.ASK('오늘 핵심 3줄')`, `window.ASK('10월 자산운용 공모 은행채 순매수')`, `window.ASK('다음 주 1,000억 이상 회사채 만기')`, `window.ASK('MMF 분기말 패턴')`가 오류 없이 답하는지 확인한다.

## 7. 생성·검증
1. `python3 make_brief.py <엔진폴더>` → out/brief_data.json, out/web.html, out/YYYY-MM-DD_Daily_Market_Brief.pdf.
2. 검증: PDF 텍스트(pdfplumber)에 핵심 수치(국고3년, CP91, MMF 설정원본, Repo 잔액, 자금유출입 합계)가 raw 계산값과 같은지 코드로 대조. PDF 페이지를 이미지로 한 번 확인(겹침·넘침).
3. 실패 항목이 있으면 그 섹션만 비우고 이유를 알림에 적는다. 추정값으로 채우지 않는다.

## 8. 전달
1. PDF를 `C:\Users\Training-28\Documents\Daily_Brief\output\`에 저장(device_commit_files).
2. 갱신한 raw\*.json을 `engine\raw\`에 되돌려 저장(누적 이력 유지).
3. 웹: Artifact 도구로 위 URL을 read한 뒤, out/web.html을 같은 url로 publish. `capabilities` 인자는 넘기지 않는다(저장된 `sample` 선언이 그대로 유지되어 'Claude 답변'이 계속 작동한다. `{}`를 넘기면 꺼진다).
3-2. 앱(GitHub Pages) 갱신 — 사용자가 2026-10-20 지시. 주소 https://minsoo2528-spec.github.io/daily-brief/
   - add_repo(owner "minsoo2528-spec", repo "daily-brief", access "push")로 저장소를 붙이고 안내대로 `/home/claude/daily-brief`에 clone(이미 있으면 `git fetch origin main && git reset --hard FETCH_HEAD`).
   - `python3 build_pages.py <엔진폴더> /home/claude/daily-brief` (out/web.html + engine\pages\ → index.html·manifest·아이콘·sw.js).
   - `git add -A && git -c user.name=minsoo2528-spec -c user.email=minsoo2528-spec@users.noreply.github.com commit -m "Daily Brief YYYY-MM-DD"` 후 `git push origin main`. 공개 저장소이므로 커밋 작성자에 실제 메일 주소를 쓰지 않는다. 커밋 메시지 끝에는 세션 안내의 attribution 줄을 붙인다.
   - 저장소의 `engine/`은 코드 사본이다. 그날 PC의 코드(*.py, templates, scrapers, pages, RUNBOOK.md)가 바뀌었으면 같이 덮어쓴다. config.json·raw·out·PDF는 절대 올리지 않는다(메일 주소·자금중개 자료).
   - push가 거부되면(권한 만료 등) 앱 갱신만 건너뛰고 알림에 "앱 미갱신(이유)"을 적는다. 다른 저장소에 올리지 않는다.
   - 메일 본문 링크는 claude.ai 페이지(Claude 답변 포함) 그대로 둔다.
4. 팀 메일 자동 발송(사용자가 2026-10-20 지시: 매 실행 끝에 config.json "email"."team_to" 주소로 발송).
   - `python3 make_email.py <엔진폴더>` → out/email.json {to, subject, html, text}. 웹 게시(3번)가 끝난 뒤 실행한다.
   - Gmail 연결의 send_message로 보낸다: to=email.json "to", subject, htmlBody=html, body=text. 첨부는 넣지 않는다(웹페이지는 본문의 링크로 연다).
   - "to"가 비어 있거나 Gmail 연결이 없으면 보내지 않고 알림에 "팀 메일 미발송(이유)"을 적는다. 다른 주소로 바꾸거나 추가하지 않는다.
   - 같은 날 두 번 보내지 않는다: Gmail에서 같은 제목이 오늘 이미 보낸편지함에 있으면 건너뛴다.
5. 사용자에게 SendUserMessage로 3~5줄 알림(기준일, 핵심 3가지, 빠진 항목, 팀 메일 발송 여부)과 PDF(SendUserFile).
6. 고객 메일 발송은 하지 않는다. 팀원이 검토 후 직접 발송한다.
