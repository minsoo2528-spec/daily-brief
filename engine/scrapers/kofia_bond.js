// 금투협 채권정보센터 (https://www.kofiabond.or.kr) — 내장 브라우저에서 아무 페이지나 연 뒤 javascript_tool로 실행
// 모든 조회는 POST /proframeWeb/XMLSERVICES/ (XML). 프레임 안이 아니어도 같은 출처면 동작.
async function kofia(svc, fn, vals){const body=`<?xml version="1.0" encoding="utf-8"?>\n<message>\n  <proframeHeader>\n    <pfmAppName>BIS-KOFIABOND</pfmAppName>\n    <pfmSvcName>${svc}</pfmSvcName>\n    <pfmFnName>${fn}</pfmFnName>\n  </proframeHeader>\n  <systemHeader></systemHeader>\n    <BISComDspDatDTO>\n${vals.map((v,i)=>`    <val${i+1}>${v}</val${i+1}>`).join('\n')}\n</BISComDspDatDTO>\n</message>\n`;
 const t=await (await fetch('/proframeWeb/XMLSERVICES/',{method:'POST',headers:{'Content-Type':'application/xml; charset=UTF-8'},body})).text(); const x=new DOMParser().parseFromString(t,'text/xml');
 return [...x.getElementsByTagName('BISComDspDatDTO')].map(n=>{const o=[]; for(let i=1;i<=16;i++){const e=n.getElementsByTagName('val'+i)[0]; o.push(e?e.textContent:'')} return o;});}
// ① 투자자별 거래현황(억원, 거래대금): 행 = [매매유형(총거래/매도/매수/순매수), 채권종류, val3..val15]
//    열 매핑(화면 확인): val3 전체, val4 증권사간, val5 은행, val6 자산운용(공모), val7 자산운용(사모), val8 보험, val9 종금상호, val10 기금공제, val11 외국인, val12 국가지자체, val13 기타법인, val14 개인, val15 선물
const investor=(d)=>kofia('BISIvtrTrdSrchSO','list',[d,d,'','','8','C']);
// ② CP 일자별: 행 = [할인/매출/중개, 항목(가중평균금리/당일거래대금/거래량/금일잔액), 59일이하, 60~90일, 91~180일, 181~270일, 271일~1년, 합계] 단위 백만원·%
const cpDay=(d)=>kofia('BISCPRepSrchSO','listDay',[d]);
// ③ 전자단기사채 거래 건별: [거래일, AB구분, 회사명, 기초자산, 거래구분, 통화, 발행일, 만기일, 금리, 거래금액, 등급, 잔존일, 거래량(액면, 백만원)]
const stb=(d)=>kofia('BISITShortPMnyInfoSrchSO','list',[d,d,'6','','','','','','']);
// ④ 종목별 발행정보(회사채=val3 '7', 잔존 전체=''): [종목명, 표준코드, 발행일, 만기일, 잔존, 발행액(억), 이자유형, 주기, 표면금리]
const corpBonds=()=>kofia('BISItmIssInfoSrchSO','list',['NM','','7','','']);
