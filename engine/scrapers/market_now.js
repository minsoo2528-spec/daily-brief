// 개장 시황 수집 — 내장 브라우저에서 https://finance.daum.net/domestic 을 연 뒤 javascript_tool로 이 파일 내용을 그대로 실행한다.
// 원/달러는 다음 금융 값이 은행 고시 매매기준율이라(서울 외환시장 시세 아님) 넣지 않는다.
// 미 국채 10년은 기준 시각이 안 나와 넣지 않는다(채권 탭의 재무부 값 사용).
// 결과(JSON)를 raw/market_now.json 으로 저장한다. 값은 다음 금융 시세 API 원값 그대로 두고 가공은 make_brief.py에서 한다.
await (async () => {
  const j = async (u) => { const r = await fetch(u, { headers: { Accept: "application/json" } }); if (!r.ok) throw new Error(u + " " + r.status); return r.json(); };
  const dom = await j("/api/domestic/quotes?summary=true&changeStatistics=true");
  const glob = await j("/api/global/quotes");
  const arr = (x) => (Array.isArray(x) ? x : x.data || []);
  const kr = arr(dom).filter((o) => ["코스피", "코스닥"].includes(o.name)).map((o) => ({
    name: o.name, open: o.openingPrice, high: o.highPrice, low: o.lowPrice, price: o.tradePrice, prev: o.prevClosingPrice,
    chg: o.change === "FALL" ? -Math.abs(o.changePrice) : Math.abs(o.changePrice), rate: o.change === "FALL" ? -Math.abs(o.changeRate) : Math.abs(o.changeRate),
    time: o.exchangeDate, status: o.marketStatus,
    inv: o.investorSummary ? { indiv: o.investorSummary.individualStraightPurchasePrice, inst: o.investorSummary.institutionStraightPurchasePrice, frgn: o.investorSummary.foreignStraightPurchasePrice } : null,
    breadth: o.changeStatistics ? { up: o.changeStatistics.riseCount, flat: o.changeStatistics.evenCount, down: o.changeStatistics.fallCount } : null,
  }));
  const US = { "US.DJI": "다우", "US.SP500": "S&P 500", "US.COMP": "나스닥", "US.SOX": "필라델피아 반도체" };
  const us = arr(glob.north_america).filter((o) => US[o.symbolCode]).map((o) => ({
    sym: o.symbolCode, name: US[o.symbolCode], price: o.tradePrice, prev: o.prevClosingPrice, time: o.date, closed: o.isClosing,
  }));
  const now = new Date(); const pad = (n) => String(n).padStart(2, "0");
  const captured = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  return { captured_at: captured, src: "다음 금융(finance.daum.net) 시세", kr, us };
})()
