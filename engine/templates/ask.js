/* 질문 도우미: (A) 데이터 질의 엔진 — 페이지에 들어 있는 원자료로 직접 계산
                (B) 답변 은행 — 그날 Claude가 미리 쓴 해설형 답변 중 가장 비슷한 질문을 찾음
   외부 호출 없음. B.ask 데이터만 사용. */
(function () {
  var A = B.ask; if (!A) return;
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var nf = function (n, d) { return n == null || isNaN(n) ? "-" : Number(n).toLocaleString("ko-KR", { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); };
  var sg = function (n, d) { if (n == null || isNaN(n)) return "-"; var r = Number(n.toFixed(d || 0)); return (r > 0 ? "+" : r < 0 ? "−" : "") + nf(Math.abs(r), d); };
  var md = function (iso) { return +iso.slice(5, 7) + "/" + +iso.slice(8, 10); };
  var D0 = A.d0, Y = +D0.slice(0, 4), M0 = +D0.slice(5, 7);
  var iso = function (y, m, d) { return y + "-" + String(m).padStart(2, "0") + "-" + String(d).padStart(2, "0"); };
  var addDays = function (s, n) { var d = new Date(s + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
  var mondayOf = function (s) { var d = new Date(s + "T12:00:00"), w = (d.getDay() + 6) % 7; return addDays(s, -w); };
  var tbl = function (head, rows, right) {
    return '<div class="atbl"><table><thead><tr>' + head.map(function (h, i) { return "<th" + (right && i ? ' class="r"' : "") + ">" + esc(h) + "</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function (r) { return "<tr>" + r.map(function (c, i) { return "<td" + (right && i ? ' class="r"' : "") + ">" + esc(c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>";
  };
  var ans = function (html, src, kind) { return { html: html, src: src, kind: kind || "data" }; };

  /* ---------- 기간 해석 ---------- */
  function period(q, dates, futureOK) {
    var m, today = D0;
    if ((m = q.match(/(\d{1,2})\s*[\/.월]\s*(\d{1,2})\s*일?\s*(?:~|-|부터|에서)\s*(\d{1,2})\s*[\/.월]\s*(\d{1,2})/))) {
      var a = iso(+m[1] > M0 && !futureOK ? Y - 1 : Y, +m[1], +m[2]), b = iso(+m[3] > M0 && !futureOK ? Y - 1 : Y, +m[3], +m[4]);
      return { from: a, to: b, label: md(a) + "~" + md(b) };
    }
    if ((m = q.match(/(\d{1,2})\s*[\/.]\s*(\d{1,2})|(\d{1,2})\s*월\s*(\d{1,2})\s*일/))) {
      var mm = +(m[1] || m[3]), dd = +(m[2] || m[4]); var y = mm > M0 + (futureOK ? 2 : 0) ? Y - 1 : Y;
      var s = iso(y, mm, dd); return { from: s, to: s, label: md(s), single: true };
    }
    if ((m = q.match(/최근\s*(\d+)\s*(영업일|일|주|개월|달)/))) {
      var n = +m[1], unit = m[2];
      if (unit === "주") return { from: addDays(today, -7 * n + 1), to: today, label: "최근 " + n + "주" };
      if (unit === "개월" || unit === "달") return { from: addDays(today, -30 * n + 1), to: today, label: "최근 " + n + "개월" };
      if (dates) { var idx = dates.filter(function (d) { return d <= today; }); return { from: idx[Math.max(0, idx.length - n)], to: today, label: "최근 " + n + "영업일" }; }
    }
    if (/1\s*년|연간|올해/.test(q)) return { from: addDays(today, -365), to: today, label: "최근 1년" };
    if (/(\d{1,2})\s*월/.test(q)) { var mo = +q.match(/(\d{1,2})\s*월/)[1]; var yy = mo > M0 ? Y - 1 : Y; return { from: iso(yy, mo, 1), to: iso(yy, mo, 31), label: mo + "월" }; }
    if (/이번\s*달|이달|당월|월초/.test(q)) return { from: iso(Y, M0, 1), to: today, label: M0 + "/1~" + md(today) };
    if (/지난\s*달|전월|저번\s*달/.test(q)) { var pm = M0 === 1 ? 12 : M0 - 1, py = M0 === 1 ? Y - 1 : Y; return { from: iso(py, pm, 1), to: iso(py, pm, 31), label: pm + "월" }; }
    if (/다음\s*주|차주/.test(q)) { var nm = addDays(mondayOf(B.meta.date), 7); return { from: nm, to: addDays(nm, 6), label: md(nm) + " 주" }; }
    if (/이번\s*주|금주/.test(q)) { var tm = mondayOf(B.meta.date); return { from: tm, to: addDays(tm, 6), label: "이번 주(" + md(tm) + "~)" }; }
    if (/지난\s*주|전주|저번\s*주/.test(q)) { var lm = addDays(mondayOf(D0), -7); return { from: lm, to: addDays(lm, 6), label: md(lm) + " 주" }; }
    if (/어제|전일|전날/.test(q)) return { from: A.d1, to: A.d1, label: md(A.d1), single: true };
    if (/오늘|당일|최근|현재|지금/.test(q)) return { from: today, to: today, label: md(today), single: true, latest: true };
    return null;
  }
  function inRange(d, p) { return d >= p.from && d <= p.to; }

  /* ---------- 사전 ---------- */
  var INV = [["자산운용(공모)", /자산운용\s*\(?공모|공모\s*펀드|공모펀드|운용사\s*공모|mmf\s*포함|자산운용(?!.*사모)/], ["자산운용(사모)", /사모/], ["은행", /은행(?!채)/], ["보험", /보험/], ["기금공제", /기금|공제|연기금/], ["외국인", /외국인|외인/], ["기타법인", /기타\s*법인|법인/], ["개인", /개인/], ["국가지자체", /국가|지자체/], ["종금상호", /종금|상호/]];
  var BT = [["국채", /국채|국고/], ["통안증권", /통안/], ["은행채", /은행채/], ["기타금융채", /여전|카드채|캐피탈채|기타금융/], ["특수채", /특수채|공사채/], ["회사채", /회사채/], ["지방채", /지방채/], ["ABS", /abs|유동화/]];
  var RATES = [
    [/국고\D*30|30년/, "국고채(30년)"], [/국고\D*20|20년/, "국고채(20년)"], [/국고\D*10|10년(?!.*미)/, "국고채(10년)"], [/국고\D*5|5년/, "국고채(5년)"], [/국고\D*3|3년\s*국고|국고3/, "국고채(3년)"],
    [/국고\D*2|국고채\s*2/, "국고채(2년)"], [/국고\D*1년|국고채\s*1/, "국고채(1년)"], [/통안\D*91|통안\s*3개월/, "통안증권(91일)"], [/통안\D*2년/, "통안증권(2년)"], [/통안\D*1년|통안/, "통안증권(1년)"],
    [/bbb/, "회사채(3년, BBB-)"], [/aa-|aa−|회사채/, "회사채(3년, AA-)"], [/cd/, "CD(91일)"], [/cp(?!.*잔액)/, "CP(91일)"], [/콜/, "콜금리(1일, 전체거래)"], [/kofr/, "KOFR"], [/산금채/, "산금채(1년)"], [/mmf\s*(7일|수익률)/, "MMF(7일)"]];
  var US = [[/미\D*30|미국\D*30/, "30Y"], [/미\D*10|미국\D*10|us\s*10/, "10Y"], [/미\D*2년|미국\D*2년|us\s*2/, "2Y"], [/미\D*3개월|미국\D*3개월|3m/, "3M"]];
  var mmfDates = A.mmf.map(function (r) { return r[0]; });
  var repoDates = A.repo.map(function (r) { return r[0]; });
  var invDates = Object.keys(A.inv).sort().map(function (d) { return d.slice(0, 4) + "-" + d.slice(4, 6) + "-" + d.slice(6); });

  /* ---------- 시계열 공통 ---------- */
  function seriesAnswer(name, unit, dates, vals, p, q, src, dec) {
    var idx = dates.map(function (d, i) { return i; }), last = dates.length - 1;
    if (/분기말/.test(q)) {
      var rows = [];
      dates.forEach(function (d, i) {
        var nx = dates[i + 1];
        if (nx && /^\d{4}-(03|06|09|12)/.test(d) && nx.slice(5, 7) !== d.slice(5, 7) && i >= 10) {
          rows.push([d.slice(2).replace(/-/g, "."), nf(vals[i], dec), sg(vals[i] - vals[i - 10], dec), i + 5 <= last ? sg(vals[i + 5] - vals[i], dec) : "-"]);
        }
      });
      return ans("<p><b>" + esc(name) + "</b> 분기말 패턴 (" + unit + ")</p>" + tbl(["분기말", "잔액", "직전 10영업일 대비", "이후 5영업일"], rows, true) + '<p class="an">분기말 영업일 기준. 직전 10영업일 전 값과 비교.</p>', src);
    }
    p = p || { from: dates[last], to: dates[last], label: md(dates[last]), latest: true, single: true };
    var sel = idx.filter(function (i) { return inRange(dates[i], p); });
    if (!sel.length) return ans("<p>" + esc(p.label) + " 기간의 " + esc(name) + " 데이터가 없습니다. 보유 기간: " + md(dates[0]) + "(" + dates[0].slice(0, 4) + ")~" + md(dates[last]) + "</p>", src);
    var a = sel[0], b = sel[sel.length - 1];
    if (/가장|최대|최고|최저|최소|제일/.test(q) && /증가|감소|늘|줄|빠|유입|유출|변동|변화/.test(q)) {
      var ch = sel.filter(function (i) { return i > 0; }).map(function (i) { return [i, vals[i] - vals[i - 1]]; });
      ch.sort(function (x, y) { return /감소|줄|빠|유출/.test(q) ? x[1] - y[1] : y[1] - x[1]; });
      return ans("<p><b>" + esc(name) + "</b> " + esc(p.label) + " 중 하루 " + (/감소|줄|빠|유출/.test(q) ? "감소" : "증가") + " 상위</p>" +
        tbl(["날짜", "전일 대비", "잔액"], ch.slice(0, 5).map(function (x) { return [dates[x[0]].slice(2).replace(/-/g, "."), sg(x[1], dec), nf(vals[x[0]], dec)]; }), true), src);
    }
    if (/최대|최고|가장\s*(많|높|컸)|피크/.test(q) || /최저|최소|가장\s*(적|낮)/.test(q)) {
      var hi = /최대|최고|많|높|컸|피크/.test(q), k = sel.reduce(function (x, i) { return (hi ? vals[i] > vals[x] : vals[i] < vals[x]) ? i : x; }, sel[0]);
      return ans("<p><b>" + esc(name) + "</b> " + esc(p.label) + " " + (hi ? "최고" : "최저") + ": <b>" + nf(vals[k], dec) + unit + "</b> (" + dates[k].slice(2).replace(/-/g, ".") + ")</p>", src);
    }
    if (/평균/.test(q)) {
      var s = sel.reduce(function (x, i) { return x + vals[i]; }, 0) / sel.length;
      return ans("<p><b>" + esc(name) + "</b> " + esc(p.label) + " 평균 <b>" + nf(s, dec) + unit + "</b> (" + sel.length + "영업일)</p>", src);
    }
    if (p.single) {
      var i0 = b, prev = i0 - 1, m0i = idx.filter(function (i) { return dates[i] <= A.m0; }).pop(), y1 = idx.filter(function (i) { return dates[i] <= addDays(dates[i0], -365); }).pop();
      var rows2 = [["잔액", nf(vals[i0], dec)], ["전일 대비", prev >= 0 ? sg(vals[i0] - vals[prev], dec) : "-"], ["전월말(" + md(A.m0) + ") 대비", m0i != null ? sg(vals[i0] - vals[m0i], dec) : "-"]];
      if (y1 != null) rows2.push(["1년 전(" + dates[y1].slice(2).replace(/-/g, ".") + ") 대비", sg(vals[i0] - vals[y1], dec)]);
      else rows2.push(["보유 첫날(" + dates[0].slice(2).replace(/-/g, ".") + ") 대비", sg(vals[i0] - vals[0], dec)]);
      return ans("<p><b>" + esc(name) + "</b> " + dates[i0].slice(2).replace(/-/g, ".") + " (" + unit + ")</p>" + tbl(["항목", "값"], rows2, true), src);
    }
    var prevA = a > 0 ? a - 1 : a;
    return ans("<p><b>" + esc(name) + "</b> " + esc(p.label) + " (" + unit + ")</p>" + tbl(["항목", "값"], [
      ["시작 (" + dates[prevA].slice(2).replace(/-/g, ".") + " 말)", nf(vals[prevA], dec)], ["끝 (" + dates[b].slice(2).replace(/-/g, ".") + ")", nf(vals[b], dec)], ["기간 증감", sg(vals[b] - vals[prevA], dec)],
      ["기간 최고", nf(Math.max.apply(null, sel.map(function (i) { return vals[i]; })), dec)], ["기간 최저", nf(Math.min.apply(null, sel.map(function (i) { return vals[i]; })), dec)]], true), src);
  }

  /* ---------- 의도별 처리 ---------- */
  var H = [];
  // 1) 시그널
  H.push(function (q) {
    if (!/시그널|신호|특이사항|알림/.test(q) || !B.signals) return null;
    var L = B.signals.list.filter(function (x) { return x.status === "fired"; });
    if (/행동|빨간|레드|긴급/.test(q)) L = L.filter(function (x) { return x.level === "red"; });
    if (/주목|주황/.test(q)) L = L.filter(function (x) { return x.level === "orange"; });
    ["매크로", "수익증권", "채권", "단기자금"].forEach(function (s) { if (q.indexOf(s) >= 0) L = L.filter(function (x) { return x.sec === s; }); });
    if (!L.length) return ans("<p>조건에 맞는 오늘 발생 시그널이 없습니다. (전체 " + B.signals.list.length + "개 기준 점검)</p>", "시그널 탭");
    return ans("<p>오늘 발생 시그널 " + L.length + "건</p><ul>" + L.map(function (x) { return "<li><b>" + (x.level === "red" ? "🔴" : "🟠") + " " + esc(x.name) + "</b> (" + esc(x.sec) + ") — " + esc(x.value) + "<br><span class=\"an\">영업 포인트: " + esc(x.action) + "</span></li>"; }).join("") + "</ul>", "시그널 탭 · " + B.signals.asof);
  });
  // 2) 공모채 딜(회사명·수요예측)
  H.push(function (q, raw) {
    var I = B.bond.issue; if (!I) return null;
    var hit = I.rows.filter(function (r) { return raw.replace(/\s/g, "").indexOf(r.corp.replace(/\s/g, "")) >= 0; });
    var up = I.upcoming.filter(function (u) { return raw.replace(/\s/g, "").indexOf(u.corp.replace(/\s/g, "")) >= 0; });
    var dealQ = /수요예측|공모채|회사채\s*발행|발행\s*시장|경쟁률|신종자본|후순위/.test(q);
    if (/만기|상환|납입/.test(q) && !/수요예측|경쟁률/.test(q)) return null;
    if (!hit.length && !up.length && !dealQ) return null;
    if (!hit.length && !up.length) {
      if (/예정|이번\s*주|다음|일정/.test(q) && I.upcoming.length) hit = [], up = I.upcoming;
      else hit = I.rows;
      if (/신종자본|후순위/.test(q)) { hit = hit.filter(function (r) { return /신종|후순위/.test(r.kind); }); up = I.upcoming.filter(function (u) { return /신종|후순위/.test(u.kind); }); }
    }
    var out = "";
    if (hit.length) {
      if (hit.length > 1 && /누가|참여|비중|주체/.test(q)) out += "<p>최근 " + I.n + "건 합계 참여 비중: " + I.share.map(function (x) { return esc(x[0]) + " " + x[2] + "%"; }).join(" · ") + " (총 수요 " + nf(I.demand) + "억, 발행 " + nf(I.amt) + "억)</p>";
      out += tbl(["발행사", "수요예측", "발행액(억)", "수요(억)", "운용사/증권사/연기금·은행·보험 %", "확정 가산금리", "확정 금리"], hit.map(function (r) { return [r.corp + " " + r.kind + " " + r.grade, r.dfd, nf(r.amt), r.demand == null ? "-" : nf(r.demand) + " (" + r.ratio + "배)", r.share ? r.share.join(" / ") : "-", r.spread + (r.band ? " · 밴드 " + r.band : ""), r.rate]; }));
    }
    if (up.length) out += "<p><b>예정</b></p><ul>" + up.map(function (u) { return "<li>" + esc(u.dfd) + " 수요예측 · " + esc(u.corp) + " " + esc(u.kind) + " " + esc(u.grade) + " · " + nf(u.amt) + "억 · " + esc(u.band) + " · 납입 " + esc(u.pay) + "</li>"; }).join("") + "</ul>";
    return ans(out, "DART 증권신고서 · " + I.window);
  });
  // 3) 회사채 만기·납입
  H.push(function (q, raw) {
    var named = A.mats.filter(function (m) { return raw.replace(/\s/g, "").indexOf(m.issuer.replace(/\s/g, "")) >= 0; });
    if ((!/만기|상환|납입/.test(q) && !(named.length && /만기|상환/.test(q))) || /cp|기업어음|전단채/.test(q)) return null;
    if (/납입/.test(q) && !/만기/.test(q)) {
      var P = A.payins.filter(function (p) { return p.date > A.d0; });
      return ans("<p>공모채 납입 예정 (자금 유입)</p>" + tbl(["납입일", "발행사", "구분", "금액(억)"], P.map(function (p) { return [md(p.date), p.issuer, p.kind, nf(p.amt)]; })), "DART");
    }
    var p = period(q, null, true) || { from: addDays(A.d0, 1), to: "2099-12-31", label: "향후 전체(보유 범위)" };
    var L = (named.length ? named : A.mats).filter(function (m) { return inRange(m.date, p) || (named.length && !period(q, null, true)); });
    var mth = (q.match(/(\d[\d,]*)\s*억\s*이상/) || [])[1]; if (mth) L = L.filter(function (m) { return m.amt >= +mth.replace(/,/g, ""); });
    var thr = (q.match(/(\d+(?:\.\d+)?)\s*조\s*이상/) || [])[1]; if (thr) L = L.filter(function (m) { return m.amt >= +thr * 1e4; });
    ["금융", "공기업", "일반기업", "리츠"].forEach(function (s) { if (q.indexOf(s) >= 0) L = L.filter(function (m) { return m.sector === s; }); });
    L.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : b.amt - a.amt; });
    if (!L.length) return ans("<p>" + esc(p.label) + " 조건에 맞는 공모 회사채 만기가 없습니다.</p>", "금투협 채권정보센터");
    var sum = L.reduce(function (s, m) { return s + m.amt; }, 0);
    return ans("<p>" + esc(named.length ? L[0].issuer : p.label) + " 공모 회사채 만기 <b>" + L.length + "건 · " + nf(sum) + "억</b></p>" +
      tbl(["만기일", "발행사", "종목", "금액(억)", "표면금리"], L.slice(0, 40).map(function (m) { return [md(m.date), m.issuer, m.nm, nf(m.amt), (typeof cpf === "function" ? cpf(m.cpn) : nf(m.cpn, 2)) + "%"]; })) + (L.length > 40 ? '<p class="an">상위 40건만 표시</p>' : "") +
      '<p class="an">발행 조건상 만기 · 조기상환 미반영 · 100억 이상 공모채(주식연계채 제외)</p>', "금투협 채권정보센터 「종목별 발행정보」");
  });
  // 4) 대기업 현금성자산
  H.push(function (q, raw) {
    var named = A.liq.filter(function (r) { return raw.replace(/\s/g, "").indexOf(r.nm.replace(/\s/g, "")) >= 0; });
    if (!/현금|유동성|단기금융상품|여유\s*자금|곳간/.test(q)) return null;
    var L = named.length ? named : A.liq.slice();
    if (/증가|늘/.test(q)) L.sort(function (a, b) { return b.chg - a.chg; }); else if (/감소|줄/.test(q)) L.sort(function (a, b) { return a.chg - b.chg; });
    var n = +((q.match(/(\d+)\s*(개|곳|위)/) || [])[1] || (named.length ? named.length : 10));
    return ans("<p>대기업 단기 운용자산 (" + esc(A.liq_asof) + ", 연결, 조원)</p>" + tbl(["기업", "현금성자산", "단기금융상품", "합계", "2025년말 대비"], L.slice(0, n).map(function (r) { return [r.nm, nf(r.cash / 1e4, 1), r.stfi == null ? "-" : nf(r.stfi / 1e4, 1), nf(r.liq / 1e4, 1), sg(r.chg / 1e4, 1)]; }), true) +
      '<p class="an">단기금융상품은 재무상태표에 따로 표시된 경우만 포함 · 팀 내부용</p>', "DART 반기보고서");
  });
  // 5) 투자자별 순매수
  H.push(function (q) {
    if (!/순매수|순매도|매수|매도|사들|샀|팔/.test(q) || /repo|레포|rp|수요예측/.test(q) || !invDates.length) return null;
    var inv = INV.filter(function (x) { return x[1].test(q); }).map(function (x) { return x[0]; });
    var bt = BT.filter(function (x) { return x[1].test(q); }).map(function (x) { return x[0]; }); if (!bt.length) bt = ["합계"];
    var p = period(q, invDates) || { from: invDates[invDates.length - 1], to: invDates[invDates.length - 1], label: md(invDates[invDates.length - 1]) };
    var ds = invDates.filter(function (d) { return inRange(d, p); });
    if (!ds.length) return ans("<p>" + esc(p.label) + " 투자자별 데이터가 없습니다. 보유 기간: " + md(invDates[0]) + "~" + md(invDates[invDates.length - 1]) + "</p>", "금투협 채권정보센터");
    var sum = function (ivi, b) { return ds.reduce(function (s, d) { return s + A.inv[d.replace(/-/g, "")][b][ivi]; }, 0); };
    var label = esc(p.label) + (ds.length > 1 ? " (" + ds.length + "영업일)" : "");
    if (!inv.length || /누가|순위|가장/.test(q)) {
      var rows = A.inv_names.map(function (nm, i) { return [nm, bt.reduce(function (s, b) { return s + sum(i, b); }, 0)]; }).sort(function (a, b) { return /순매도|팔/.test(q) ? a[1] - b[1] : b[1] - a[1]; });
      return ans("<p>" + label + " " + bt.join("·") + " 투자자별 순매수 (억원)</p>" + tbl(["투자자", "순매수"], rows.map(function (r) { return [r[0], sg(r[1])]; }), true), "금투협 채권정보센터 · 장외 거래대금");
    }
    var rows2 = inv.map(function (nm) { var i = A.inv_names.indexOf(nm); return [nm].concat(bt.map(function (b) { return sg(sum(i, b)); })); });
    return ans("<p>" + label + " 순매수 (억원)</p>" + tbl(["투자자"].concat(bt), rows2, true) + (inv.indexOf("자산운용(공모)") >= 0 ? '<p class="an">자산운용(공모)에는 MMF 등 공모펀드 포함</p>' : ""), "금투협 채권정보센터 · 장외 거래대금");
  });
  // 6) Repo
  H.push(function (q) {
    if (!/repo|레포|rp|환매조건/.test(q)) return null;
    var col = 0;
    if (/집합투자|펀드/.test(q)) col = /매도/.test(q) ? 8 : 1; else if (/국내\s*은행|은행\s*직접/.test(q)) col = 2; else if (/신탁/.test(q) && /증권/.test(q)) col = 4; else if (/신탁/.test(q)) col = 3; else if (/여신|캐피탈|카드/.test(q)) col = 5; else if (/증권/.test(q)) col = /매도/.test(q) ? 7 : 6;
    var vals = A.repo.map(function (r) { return r[col + 1]; });
    return seriesAnswer("Repo " + A.repo_cols[col] + " 잔액", "조원", repoDates, vals, period(q, repoDates), q, "예탁원 SEIBro 매매잔액(원화)", 1);
  });
  // 7) MMF 잔고
  H.push(function (q) {
    if (!/mmf|머니마켓|단기금융펀드/.test(q) || /수익률|7일/.test(q)) return null;
    var c = /공모/.test(q) ? 2 : /사모/.test(q) ? 3 : 1;
    var vals = A.mmf.map(function (r) { return r[c] / 1e4; });
    return seriesAnswer("MMF 설정원본" + (c === 2 ? "(공모)" : c === 3 ? "(사모)" : ""), "조원", mmfDates, vals, period(q, mmfDates), q, "금투협 FreeSIS(펀드 기준)", 1);
  });
  // 8) CP 잔액·전단채
  H.push(function (q) {
    if (!/cp|기업어음|전단채|단기사채/.test(q) || /스프레드|금리\s*차|격차|차이/.test(q) || (/금리|수익률/.test(q) && !/만기별|구간/.test(q) && !/전단채/.test(q))) return null;
    if (/전단채|단기사채/.test(q) && B.bond.cp && B.bond.cp.stb) {
      var st = B.bond.cp.stb;
      return ans("<p>전단채 신규 인수(일반물) " + esc(st.asof) + "</p>" + tbl(["발행사 구분", "금액(억)", "금리(%)", "평균 만기(일)"], st.byCls.map(function (c) { return [c.cls, nf(c.amt / 100), c.rate == null ? "-" : nf(c.rate, 2), nf(c.days, 1)]; }), true) +
        tbl(["발행사", "금액(억)", "금리(%)", "만기", "등급"], st.top_corp.concat(st.top_sec).map(function (t) { return [t.nm, nf(t.amt / 100), t.rate == null ? "-" : nf(t.rate, 2), t.dmin === t.dmax ? t.dmin + "일" : t.dmin + "~" + t.dmax + "일", t.gr]; }), true), "금투협 전자단기사채정보");
    }
    var cd = Object.keys(A.cp).sort(), dates = cd.map(function (d) { return d.slice(0, 4) + "-" + d.slice(4, 6) + "-" + d.slice(6); }).filter(function (d) { return d <= A.d0; });
    if (/만기별|구간/.test(q)) { var x = A.cp[dates[dates.length - 1].replace(/-/g, "")]; return ans("<p>CP 만기별 할인 금리·잔액 " + md(dates[dates.length - 1]) + "</p>" + tbl(["구간", "할인 금리(%)", "잔액(조)"], A.cp_buckets.map(function (b, i) { return [b, x.dr[i] == null ? "-" : nf(x.dr[i], 2), nf(x.bal[i], 1)]; }), true), "금투협 CP정보"); }
    return seriesAnswer("CP 잔액", "조원", dates, dates.map(function (d) { return A.cp[d.replace(/-/g, "")].bal[5]; }), period(q, dates), q, "금투협 CP정보(할인 기준 잔액)", 1);
  });
  // 9) 금리·스프레드
  H.push(function (q) {
    var spread = /스프레드|금리\s*차|격차|차이/.test(q);
    if (spread) {
      var rows = B.bond.spreads.slice();
      var k = A.kr, cpcd = function (t) { return k["CP(91일)"][t] != null && k["CD(91일)"][t] != null ? (k["CP(91일)"][t] - k["CD(91일)"][t]) * 100 : null; };
      rows.push(["CP 91일 − CD 91일", nf(cpcd("d0"), 1), sg(cpcd("d0") - cpcd("d1"), 1), sg(cpcd("d0") - cpcd("w1"), 1), sg(cpcd("d0") - cpcd("m0"), 1)]);
      return ans("<p>스프레드 (bp)</p>" + tbl(B.bond.head.map(function (h, i) { return i ? h : h + " 값"; }), rows, true), "한국은행 ECOS");
    }
    var hits = [];
    US.forEach(function (x) { if (x[0].test(q)) hits.push(["미 국채 " + x[1], A.us[x[1]], "미 재무부"]); });
    if (!hits.length) RATES.forEach(function (x) { if (x[0].test(q) && !hits.some(function (h) { return h[0] === x[1]; })) hits.push([x[1], A.kr[x[1]], "한국은행 ECOS"]); });
    if (!hits.length || !/금리|수익률|얼마|몇|bp|%|변동|올랐|내렸|상승|하락|국고|통안|cd|cp|콜|kofr|aa|bbb|산금채|미\s*국채|미국채/.test(q)) return null;
    hits = hits.slice(0, 4);
    var r = function (v) { return v == null ? "-" : nf(v, 3); }, b = function (a, c) { return a == null || c == null ? "-" : sg((a - c) * 100, 1); };
    return ans("<p>금리 (%, 변동 bp)</p>" + tbl(["금리", md(A.d0), "전일", "1주(" + md(A.w1) + ")", "전월말(" + md(A.m0) + ")"], hits.map(function (h) { var v = h[1]; return [h[0], r(v.d0), b(v.d0, v.d1), b(v.d0, v.w1), b(v.d0, v.m0)]; }), true) +
      (hits.some(function (h) { return h[1].d0 == null; }) ? '<p class="an">"-"는 해당일 미공시</p>' : ""), hits[0][2]);
  });
  // 10) 펀드 자금흐름
  H.push(function (q) {
    if (!/펀드|자금\s*흐름|유입|유출|설정|해지/.test(q) || /mmf\s*잔고|설정원본/.test(q)) return null;
    var f = B.realestate.flows, rows = f.rows;
    var pick = rows.filter(function (r) { return q.indexOf(r[0].replace(/\(.*\)/, "")) >= 0 || (r[0].indexOf("MMF") >= 0 && /mmf/.test(q)); });
    if (!pick.length) pick = rows;
    return ans("<p>펀드 유형별 자금흐름 · 일간 " + esc(f.asof) + " 하루 (억원)</p>" + tbl(["유형", "설정원본(조)", "공모", "사모", "순유입 계"], pick.map(function (r) { return [r[0], r[1] == null ? "-" : nf(r[1], 1), sg(r[2]), sg(r[3]), sg(r[4])]; }), true) + '<p class="an">순유입 = 설정 − 해지, 해당일 하루 기준</p>', "금투협 FreeSIS");
  });
  // 11) 일정
  H.push(function (q) {
    if (!/일정|언제|캘린더|금통위|fomc|지준|마감|발행\s*일정|이벤트/.test(q)) return null;
    var L = B.calendar.slice(), p = period(q, null, true);
    if (/금통위|fomc/.test(q)) L = L.filter(function (c) { return /금통위|FOMC/.test(c.text); });
    else if (/지준/.test(q)) L = L.filter(function (c) { return /지준/.test(c.text); });
    else if (p) L = L.filter(function (c) { return inRange(c.date, p); });
    else L = L.filter(function (c) { return c.date >= B.meta.date; }).slice(0, 15);
    if (!L.length) return ans("<p>조건에 맞는 일정이 없습니다.</p>", "캘린더");
    return ans("<ul>" + L.map(function (c) { return "<li><b>" + esc(c.d) + "(" + esc(c.w) + ")</b> " + esc(c.text) + (c.check ? ' <span class="an">[' + esc(c.check) + "]</span>" : "") + "</li>"; }).join("") + "</ul>", "캘린더 탭");
  });

  /* ---------- 답변 은행(B) ---------- */
  function grams(s) { s = s.toLowerCase().replace(/[^0-9a-z가-힣]/g, ""); var g = {}; for (var i = 0; i < s.length - 1; i++) { var k = s.substr(i, 2); g[k] = (g[k] || 0) + 1; } return g; }
  var QA = (A.qa || []).map(function (x) { var t = [x.q].concat(x.alts || []).join(" ") + " " + (x.tags || []).join(" "); return { x: x, g: grams(t) }; });
  var DF = {}; QA.forEach(function (e) { Object.keys(e.g).forEach(function (k) { DF[k] = (DF[k] || 0) + 1; }); });
  function vec(g) { var v = {}, n = 0; Object.keys(g).forEach(function (k) { var w = g[k] * Math.log(1 + QA.length / (1 + (DF[k] || 0))); v[k] = w; n += w * w; }); return { v: v, n: Math.sqrt(n) || 1 }; }
  QA.forEach(function (e) { e.vv = vec(e.g); });
  function bank(q) {
    var qv = vec(grams(q)), res = QA.map(function (e) { var s = 0; Object.keys(qv.v).forEach(function (k) { if (e.vv.v[k]) s += qv.v[k] * e.vv.v[k]; }); return [s / (qv.n * e.vv.n), e.x]; });
    return res.sort(function (a, b) { return b[0] - a[0]; });
  }
  function bankAns(x) { return ans("<p><b>" + esc(x.q) + "</b></p>" + x.a.split(/\n+/).map(function (p) { return "<p>" + esc(p) + "</p>"; }).join(""), (x.src || "사전 작성 해설") + (x.static ? "" : " · " + md(B.meta.date) + " 작성"), "bank"); }

  window.ASK = function (raw) {
    var q = raw.toLowerCase().replace(/[?？!.]/g, " ").replace(/\s+/g, " ").trim();
    var interp = /왜|이유|의미|어떻게|설명|전망|영향|포인트|문구|조언|해석|뭐야|무엇|정의|차이|시사점|고객|관계|연관|상관/.test(q);
    var br = bank(q), top = br[0];
    if (interp && top && top[0] >= 0.24) return [bankAns(top[1])];
    for (var i = 0; i < H.length; i++) { try { var r = H[i](q, raw); if (r) { var outA = [r]; if (top && top[0] >= 0.45) outA.push(bankAns(top[1])); return outA; } } catch (e) { console.log("ask error", e); } }
    if (top && top[0] >= 0.22) return [bankAns(top[1])];
    var sug = br.slice(0, 3).map(function (x) { return x[1].q; });
    return [ans("<p>오늘 자료로는 답을 찾지 못했습니다. 지표명·기간·회사명을 넣어 다시 물어보세요.</p><p class=\"an\">예: \"10월 자산운용 공모 은행채 순매수\", \"다음 주 1,000억 이상 회사채 만기\", \"MMF 분기말 패턴\", \"GS 수요예측 누가 샀어\"</p>", "", "none")].concat(sug.length ? [{ html: "", src: "", kind: "sug", sug: sug }] : []);
  };
  window.ASK_SUGGEST = (A.qa || []).filter(function (x) { return x.pin; }).map(function (x) { return x.q; });
})();
