"""영업 시그널 판정 (매크로·수익증권·채권·단기자금).

make_brief.py가 import해서 evaluate(ctx)를 호출한다. ctx에는 raw 데이터와 브리프 기준일이 들어 있다.
기준값은 config.json의 "signals" 블록에서 바꿀 수 있다(없으면 아래 DEFAULT).
결과: 규칙마다 {id, sec, name, level, status, value, rule, action, src, items?, links?}
  status: fired(발생) / ok(기준 미달) / nodata(데이터 준비 중) / cooldown(최근 3영업일 내 같은 시그널, 생략)
  level : red(행동) / orange(주목)
"""
import datetime as dt
import re

DEFAULT = {
    "cooldown_bd": 3,
    "policy_days_bd": 3,
    "us10y_d_bp": 10, "us10y_w_bp": 20,
    "kospi_pct": 3.0, "fx_pct": 1.0, "cpi_surprise_pp": 0.2,
    "re_fund_eok": 1000, "bond_mmf_public_eok": 5000,
    "news_lookback_bd": 2,
    "risk_keywords": ["연체", "만기연장", "브릿지론", "유상증자 미달", "청약 미달", "부실", "손실", "디폴트", "EOD", "기한이익"],
    "reit_rate_bp": 30,
    "ktb3_d_bp": 5, "ktb3_w_bp": 15, "credit_w_bp": 5,
    "deal_new_bd": 3, "deal_hot_ratio": 8.0, "deal_hot_bp": -10,
    "fund_buy_jo": 2.0, "foreign_ktb_sell_jo": 1.0,
    "mmf_drop_jo": -5.0, "mmf_jump_jo": 6.0, "mmf_5d_jo": 14.0,
    "repo_jo": 5.0, "fund_repo_drop_jo": -6.0,
    "call_gap_bp": 10, "kofr_d_bp": 5,
    "reserve_end_bd": 2,
    "period_end_bd": 5,
    "mat_week_jo": 1.5, "mat_single_eok": 1000, "mat_lead_bd": 5, "payin_eok": 1000,
    "cp_bal_w_jo": 5.0, "cp_cd_w_bp": 10,
    "cash_up_jo": 1.0, "cash_new_bd": 3,
}


def _cpn(x):
    """표면금리: 셋째 자리가 있으면 그대로(2.065), 없으면 둘째 자리까지(2.66)."""
    t = f"{x:.3f}"
    return t[:-1] if t.endswith("0") else t


class BD:
    """영업일 계산(주말 + config 휴일)."""
    def __init__(self, holidays):
        self.h = {dt.date.fromisoformat(x) for x in holidays}

    def is_bd(self, d):
        return d.weekday() < 5 and d not in self.h

    def between(self, a, b):
        """a에서 b까지 영업일 수(a 다음날 ~ b 포함). b가 a보다 앞이면 음수."""
        if b == a:
            return 0
        lo, hi, sg = (a, b, 1) if b > a else (b, a, -1)
        return sg * sum(1 for i in range(1, (hi - lo).days + 1) if self.is_bd(lo + dt.timedelta(days=i)))

    def back(self, d, n):
        x = d
        while n > 0:
            x -= dt.timedelta(days=1)
            if self.is_bd(x):
                n -= 1
        return x

    def last_bd_of_month(self, d):
        x = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        while not self.is_bd(x):
            x -= dt.timedelta(days=1)
        return x


def _qe_text(rows):
    """최근 분기말들의 MMF 패턴: 분기말 직전 10영업일 대비 감소, 이후 5영업일 재유입(조원)."""
    d = [r[0] for r in rows]; v = {r[0]: r[1] / 1e4 for r in rows}
    drops, rebs = [], []
    for i, x in enumerate(d):
        nxt = d[i + 1] if i + 1 < len(d) else None
        if nxt and x[5:7] in ("03", "06", "09", "12") and nxt[5:7] != x[5:7] and i >= 10 and i + 5 < len(d):
            drops.append(v[x] - v[d[i - 10]]); rebs.append(v[d[i + 5]] - v[x])
    if not drops:
        return "MMF 이탈 후 재유입 패턴 안내"
    return (f"MMF 이탈 후 재유입 패턴 안내 — 최근 {len(drops)}개 분기말 직전 10영업일 대비 {max(drops):+.0f}~{min(drops):+.0f}조, "
            f"이후 5영업일 {min(rebs):+.0f}~{max(rebs):+.0f}조 재유입")


def _f(x, d=1):
    return f"{x:+,.{d}f}"


def evaluate(ctx):
    C = dict(DEFAULT, **(ctx.get("cfg") or {}))
    bd = BD(ctx.get("holidays", []))
    today = dt.date.fromisoformat(ctx["date"])          # 브리프 날짜
    d0 = dt.date.fromisoformat(ctx["d0"])               # 지표 기준일
    KR, US, CT = ctx["KR"], ctx["US"], ctx["CT"]
    out = []

    def add(id_, sec, name, level, fired, value, rule, action, src, items=None, links=None, nodata=False, key=None, mag=None):
        out.append({"id": id_, "sec": sec, "name": name, "level": level,
                    "status": "nodata" if nodata else ("fired" if fired else "ok"),
                    "value": value, "rule": rule, "action": action, "src": src,
                    "items": items or [], "links": links or [], "key": key or id_, "mag": mag})

    it = KR["items"]
    def r(n, k): return (it.get(n) or {}).get(k)
    def bp(a, b): return None if a is None or b is None else round((a - b) * 100, 1)

    # ---------------- 매크로 ----------------
    ev = []
    for c in CT.get("calendar", []):
        if re.search(r"금통위|FOMC", c["text"]):
            dd = dt.date.fromisoformat(c["date"])
            n = bd.between(today, dd)
            if 0 <= n <= C["policy_days_bd"]:
                ev.append(f"{dd.month}/{dd.day} {c['text']} (D-{n})" if n else f"오늘 {c['text']}")
    surprise = CT.get("policy_surprise")  # {"text": ...} 결과가 예상과 다를 때 수기 입력
    add("M1", "매크로", "통화정책 이벤트", "red" if surprise else "orange", bool(ev or surprise),
        surprise["text"] if surprise else (" · ".join(ev) if ev else "3영업일 내 금통위·FOMC 없음"),
        f"금통위·FOMC {C['policy_days_bd']}영업일 전부터 / 결과가 예상과 다르면 행동",
        "금리 방향이 바뀌면 MMF·단기채 듀레이션 제안 준비", "캘린더", key="M1|" + "|".join(ev))

    u = US["items"]["10Y"]
    dd_, ww_ = bp(u["d0"], u["d1"]), bp(u["d0"], u["w1"])
    add("M2", "매크로", "미 국채 10년 급변", "orange",
        dd_ is not None and (abs(dd_) >= C["us10y_d_bp"] or abs(ww_) >= C["us10y_w_bp"]),
        f"{u['d0']:.2f}% · 전일 {_f(dd_)}bp · 1주 {_f(ww_)}bp",
        f"하루 ±{C['us10y_d_bp']}bp 또는 1주 ±{C['us10y_w_bp']}bp", "국내 장기물 동조화, 채권형 수요 변화 점검", "미 재무부", mag=ww_)

    mk = CT.get("market", {})
    k = mk.get("kospi")
    add("M3", "매크로", "국내 증시 급변", "red", bool(k) and abs(k["chg_pct"]) >= C["kospi_pct"],
        f"코스피 {k['close']:,.2f} ({_f(k['chg_pct'], 2)}%, {k['date'][5:].replace('-', '/')})" if k else "데이터 없음",
        f"코스피 하루 ±{C['kospi_pct']:.0f}%", "위험회피 자금의 MMF·파킹형 이동 — 법인 대기자금 제안", k.get("src", "") if k else "", nodata=not k, mag=k and k["chg_pct"])
    fx = mk.get("usdkrw")
    if fx:
        pct = fx["chg"] / (fx["close"] - fx["chg"]) * 100
    add("M4", "매크로", "환율 급변", "orange", bool(fx) and abs(pct) >= C["fx_pct"],
        f"원/달러 {fx['close']:,.1f}원 ({_f(fx['chg'])}원, {_f(pct, 2)}%)" if fx else "데이터 없음",
        f"원/달러 하루 ±{C['fx_pct']:.0f}%", "외화 유동성·외국인 채권 매매 변화 점검", fx.get("src", "") if fx else "", nodata=not fx)
    cpis = CT.get("cpi", [])
    hit = [c for c in cpis if c.get("consensus") is not None and abs(c["actual"] - c["consensus"]) >= C["cpi_surprise_pp"] - 1e-9]
    add("M5", "매크로", "물가 서프라이즈", "orange", bool(hit),
        " · ".join(f"{c['name']} {c['actual']}% (예상 {c['consensus']}%, {_f(c['actual'] - c['consensus'], 1)}%p)" for c in (hit or cpis)) or "이번 주 발표 없음",
        f"CPI 실제치가 예상 대비 ±{C['cpi_surprise_pp']}%p", "금리 인하 기대 조정 — 단기채 금리 전망 업데이트", "뉴스핌 등", nodata=not cpis)

    # ---------------- 수익증권 ----------------
    FS = ctx["FS"]
    fl = FS["flows"]
    re_ = fl["부동산"]["계_증감"] / 100
    add("F1", "수익증권", "부동산펀드 자금 급변", "orange", abs(re_) >= C["re_fund_eok"],
        f"{FS['asof'][5:].replace('-', '/')} 순{'유입' if re_ >= 0 else '유출'} {abs(re_):,.0f}억 (공모 {fl['부동산']['공모_증감'] / 100:+,.0f} · 사모 {fl['부동산']['사모_증감'] / 100:+,.0f})",
        f"일간 순유출입 ±{C['re_fund_eok']:,}억 (잠정)", "사모 부동산펀드 설정·청산 동향 확인, 운용사 컨택", "금투협 FreeSIS", mag=re_)
    big = [(n, fl[k]["공모_증감"] / 100) for n, k in [("채권형", "채권"), ("MMF", "단기금융")] if abs(fl[k]["공모_증감"] / 100) >= C["bond_mmf_public_eok"]]
    add("F2", "수익증권", "채권형·MMF 공모 대량 이동", "orange", bool(big),
        " · ".join(f"{n} 공모 {v:+,.0f}억" for n, v in big) or f"채권형 공모 {fl['채권']['공모_증감'] / 100:+,.0f}억 · MMF 공모 {fl['단기금융']['공모_증감'] / 100:+,.0f}억",
        f"공모 일간 ±{C['bond_mmf_public_eok']:,}억 (잠정)", "리테일·법인 자금 방향 확인", "금투협 FreeSIS")
    lb = bd.back(today, C["news_lookback_bd"])
    risky = []
    for n in CT.get("fund_news", []):
        if dt.date.fromisoformat(n["date"]) < lb:
            continue
        txt = n["title"] + " " + n.get("summary", "")
        kw = [w for w in C["risk_keywords"] if w in txt]
        if kw:
            risky.append({"t": f"{n['title']} — {n['outlet']} {n['date'][5:].replace('-', '/')} ({', '.join(kw)})", "url": n.get("url")})
    add("F3", "수익증권", "PF·리츠 부실 이슈", "red", bool(risky), f"{len(risky)}건" if risky else f"최근 {C['news_lookback_bd']}영업일 기사 중 해당 없음",
        "연체·만기연장·브릿지론·유증 미달 등 키워드 + 수치·회사 특정 기사", "보유 고객 사전 설명, 대체 상품 안내", "부동산·펀드 기사",
        items=[x["t"] for x in risky], links=[x["url"] for x in risky if x["url"]], key="F3|" + "|".join(x["t"][:20] for x in risky))
    RO = ctx.get("RO")
    ro = (RO or {}).get("items", [])
    add("F4", "수익증권", "리츠·부동산 공모 일정", "orange", bool(ro),
        " · ".join(f"{x['date'][5:].replace('-', '/')} {x['corp']} {x['title']}" for x in ro) if ro else (f"{RO['window']} 신규 증권신고서 없음" if RO else "데이터 없음"),
        "DART 신규 증권신고서(리츠 유상증자·부동산 집합투자증권)", "신규 상품 공급 — 청약 일정 안내", "DART", nodata=RO is None,
        links=[x["url"] for x in ro], key="F4|" + "|".join(x["rcp"] for x in ro))
    BDL = ctx.get("BD")
    reit_rows = []
    if BDL:
        for d in BDL["deals"]:
            if re.search("리츠|위탁관리부동산", d["corp"] + d["kind"]) and d["rates"] and d.get("prev_rate") is not None:
                gap = round((d["rates"][0]["rate"] - d["prev_rate"]) * 100)
                if abs(gap) >= C["reit_rate_bp"]:
                    reit_rows.append(f"{d['corp']} {d['rates'][0]['rate']:.2f}% (직전 {d['prev_rate']:.2f}%, {gap:+d}bp)")
    add("F5", "수익증권", "리츠 조달금리 변화", "orange", bool(reit_rows), " · ".join(reit_rows) or "직전 발행 금리 이력 준비 중",
        f"리츠 공모채 확정금리가 직전 발행 대비 ±{C['reit_rate_bp']}bp", "리츠 배당 여력 판단 자료로 활용", "DART", nodata=not reit_rows)

    # ---------------- 채권 ----------------
    a, b_, c_ = r("국고채(3년)", "d0"), r("국고채(3년)", "d1"), r("국고채(3년)", "w1")
    dd3, ww3 = bp(a, b_), bp(a, c_)
    add("B1", "채권", "국고 3년 급변", "orange", abs(dd3) >= C["ktb3_d_bp"] or abs(ww3) >= C["ktb3_w_bp"],
        f"{a:.3f}% · 전일 {_f(dd3)}bp · 1주 {_f(ww3)}bp", f"하루 ±{C['ktb3_d_bp']}bp 또는 1주 ±{C['ktb3_w_bp']}bp (잠정)",
        "신탁·MMF 편입 금리 변화 안내", "한국은행 ECOS", mag=ww3)
    s0 = bp(r("회사채(3년, AA-)", "d0"), a); s1 = bp(r("회사채(3년, AA-)", "w1"), c_)
    add("B2", "채권", "크레딧 스프레드 확대", "red", s0 - s1 >= C["credit_w_bp"],
        f"AA− 3년 − 국고 3년 {s0:.1f}bp (1주 {_f(s0 - s1)}bp)", f"1주 +{C['credit_w_bp']}bp 이상 확대 (잠정)",
        "크레딧 경계 — 우량물 위주 제안", "한국은행 ECOS", mag=s0 - s1)
    weak, hot = [], []
    if BDL:
        for d in BDL["deals"]:
            conf_dates = [x.split()[0].replace(".", "-") for x in d["docs"] if "발행조건확정" in x]
            if not conf_dates:
                continue
            first_conf = dt.date.fromisoformat(min(conf_dates))
            if bd.between(first_conf, today) > C["deal_new_bd"]:
                continue
            ks = []
            for x in d["dem"]:
                m = re.match(r"\s*([\d.]+)\s*:", x["k"] or "")
                ks.append(float(m.group(1)) if m else None)
            sps = [float(s.split("|")[1]) * 100 for s in d["sp"]]
            band_top = d.get("band") and d["rates"] and abs(d["rates"][0]["rate"] - float(re.findall(r"[\d.]+", d["band"])[-1])) < 1e-9
            label = f"{d['corp']}({d['grade']})"
            if any(k is not None and k < 1 for k in ks) or band_top:
                weak.append(f"{label} 경쟁률 {'/'.join(f'{k:.2f}' for k in ks if k is not None)}배" + (f", 희망밴드 상단 {d['rates'][0]['rate']:.2f}% 확정" if band_top else ""))
            if ks and max(k or 0 for k in ks) >= C["deal_hot_ratio"] and sps and min(sps) <= C["deal_hot_bp"]:
                hot.append(f"{label} 최고 {max(k or 0 for k in ks):.1f}배, 민평 대비 {min(sps):+.0f}bp")
    add("B3", "채권", "수요예측 미달·밴드 상단", "red", bool(weak), " · ".join(weak) or f"최근 {C['deal_new_bd']}영업일 확정 건 중 해당 없음",
        "경쟁률 1배 미만, 또는 희망금리 상단 확정", "해당 업종 크레딧 점검, 보유 고객 안내", "DART", nodata=not BDL, key="B3|" + "|".join(weak))
    add("B4", "채권", "수요예측 과열", "orange", bool(hot), " · ".join(hot) or "해당 없음",
        f"{C['deal_hot_ratio']:.0f}배 이상이면서 민평 대비 {C['deal_hot_bp']}bp 이하 확정", "크레딧 강세 — 발행 증가 전망 공유", "DART", nodata=not BDL, key="B4|" + "|".join(hot))
    up = [u_ for u_ in (BDL or {}).get("upcoming", []) if re.search("신종|후순위|조건부", u_["kind"]) and dt.date.fromisoformat(u_["dfd"]) >= today]
    add("B5", "채권", "신종자본·후순위 공모 예정", "red", bool(up),
        " · ".join(f"{u_['dfd'][5:].replace('-', '/')} 수요예측 {u_['corp']} {sum(t['amt'] for t in u_['tr']):,.0f}억 ({u_['grade']}, {u_['band']})" for u_ in up) or "예정 없음",
        "금융지주·보험사 신종자본·후순위 증권신고서 제출", "기관 투자자 사전 안내", "DART", nodata=not BDL,
        links=["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + u_["rcp"] for u_ in up], key="B5|" + "|".join(u_["rcp"] for u_ in up))
    KI = ctx.get("KI")
    if KI:
        days = sorted(KI["daily"]); k0 = days[-1]
        fb = KI["daily"][k0]["합계"]["자산운용(공모)"] / 1e4
        c5 = sum(KI["daily"][d]["합계"]["자산운용(공모)"] for d in days[-5:]) / 1e4
        c5p = sum(KI["daily"][d]["합계"]["자산운용(공모)"] for d in days[-6:-1]) / 1e4
        turned = c5 < 0 <= c5p
        add("B6", "채권", "펀드 매수세 급변", "orange", fb >= C["fund_buy_jo"] or turned,
            f"자산운용(공모) {k0[4:6]}/{k0[6:]} {fb:+.2f}조 · 5일 누적 {c5:+.1f}조", f"하루 순매수 {C['fund_buy_jo']:.0f}조 이상, 또는 5일 누적 순매도 전환",
            "MMF 자금 흐름의 선행 신호 — 단기물 수급 점검", "금투협 채권정보센터")
        fk = KI["daily"][k0]["국채"]["외국인"] / 1e4
        add("B7", "채권", "외국인 국채 매도", "orange", fk <= -C["foreign_ktb_sell_jo"],
            f"외국인 국채 {k0[4:6]}/{k0[6:]} {fk:+.2f}조", f"하루 순매도 {C['foreign_ktb_sell_jo']:.0f}조 이상", "장기물 약세 가능성 공유", "금투협 채권정보센터")
    else:
        add("B6", "채권", "펀드 매수세 급변", "orange", False, "데이터 없음", "", "", "금투협", nodata=True)
        add("B7", "채권", "외국인 국채 매도", "orange", False, "데이터 없음", "", "", "금투협", nodata=True)
    RT = ctx.get("RT")
    downs = (RT or {}).get("downgrades", [])
    add("B8", "채권", "신용등급 하향", "red", bool(downs), " · ".join(downs) or "데이터 준비 중",
        "등급 하향 또는 하향 검토 대상 지정", "보유 여부 점검, 고객 안내", "신용평가사 공시", nodata=RT is None)

    # ---------------- 단기자금 ----------------
    MH = ctx["MH"]["rows"]
    dm = (MH[-1][1] - MH[-2][1]) / 1e4
    d5 = (MH[-1][1] - MH[-6][1]) / 1e4
    add("S1", "단기자금", "MMF 급감·급증", "red",
        dm <= C["mmf_drop_jo"] or dm >= C["mmf_jump_jo"] or abs(d5) >= C["mmf_5d_jo"],
        f"{MH[-1][0][5:].replace('-', '/')} 설정원본 {MH[-1][1] / 1e4:,.1f}조 · 전일 {dm:+.2f}조 · 5일 {d5:+.1f}조",
        f"하루 {C['mmf_drop_jo']:.0f}조 이하 / +{C['mmf_jump_jo']:.0f}조 이상 (1년 상하위 5%), 5일 ±{C['mmf_5d_jo']:.0f}조",
        "법인 자금 이탈·재유입 시점 — 회수 고객 재유치 컨택", "금투협 FreeSIS", mag=dm)
    RH = ctx["RH"]; cols = RH["cols"]; R0, R1 = RH["rows"][-1], RH["rows"][-2]
    i_t, i_f = cols.index("매도합계"), cols.index("매수|집합투자")
    dr = (R0[i_t] - R1[i_t]) / 1e12; df = (R0[i_f] - R1[i_f]) / 1e12
    add("S2", "단기자금", "Repo 잔액 급변", "orange", abs(dr) >= C["repo_jo"],
        f"{R0[0][5:].replace('-', '/')} {R0[i_t] / 1e12:,.1f}조 · 전일 {dr:+.2f}조", f"하루 ±{C['repo_jo']:.0f}조 (1년 상하위 5%)", "단기자금 수급 변화 공유", "예탁원 SEIBro", mag=dr)
    add("S3", "단기자금", "펀드(집합투자) Repo 매수 급감", "orange", df <= C["fund_repo_drop_jo"],
        f"집합투자 매수 {R0[i_f] / 1e12:,.1f}조 · 전일 {df:+.2f}조", f"하루 {C['fund_repo_drop_jo']:.0f}조 이하 (1년 하위 5%)", "Repo 자금 공급 주체 변화 — 은행·증권 RP 수요 점검", "예탁원 SEIBro", mag=df)
    base = CT.get("base_rate")
    call, call_lb = r("콜금리(1일, 전체거래)", "d0"), ""
    if call is None:  # ECOS 당일분 미공표면 전일 값을 날짜를 붙여 쓴다
        call = r("콜금리(1일, 전체거래)", "d1"); call_lb = f"({ctx['KR']['dates']['d1'][5:].replace('-', '/')}) "
    kd = bp(r("KOFR", "d0"), r("KOFR", "d1"))
    gap = bp(call, base) if base is not None and call is not None else None
    add("S4", "단기자금", "콜·KOFR 이탈", "red", (gap is not None and abs(gap) >= C["call_gap_bp"]) or (kd is not None and abs(kd) >= C["kofr_d_bp"]),
        (f"콜 {call_lb}{call:.3f}% (기준금리 {base:.2f}% 대비 {_f(gap)}bp)" if call is not None and base is not None else "콜 미공시") + " · KOFR 전일 " + ("미공시" if kd is None else f"{_f(kd)}bp"),
        f"콜이 기준금리 대비 ±{C['call_gap_bp']}bp, KOFR 하루 ±{C['kofr_d_bp']}bp", "은행권 자금 부족 — RP 금리 제안 기회", "한국은행 ECOS", nodata=base is None or call is None)
    km = CT.get("kmb")
    rend = None
    if km:
        for x in km.get("kpis", []):
            if x[0] == "지준 마감일":
                mm = re.match(r"(\d+)/(\d+)", x[1])
                if mm:
                    rend = dt.date(today.year, int(mm.group(1)), int(mm.group(2)))
        cum = next((x for x in km["kpis"] if x[0].startswith("지준 적수")), None)
    n_end = bd.between(today, rend) if rend else None
    short = km and cum and cum[1].startswith(("−", "-"))
    add("S5", "단기자금", "지준 마감 임박", "red", bool(rend) and 0 <= n_end <= C["reserve_end_bd"] and bool(short),
        f"지준 마감 {rend.month}/{rend.day} (D-{n_end}) · 적수 {cum[1] if cum else '-'}" if rend else "자금중개 자료 없음",
        f"마감 {C['reserve_end_bd']}영업일 전 + 적수 부족", "은행 콜·RP 수요 — 은행 자금부 컨택", "한국자금중개", nodata=not rend)
    mend = bd.last_bd_of_month(today)
    n_m = bd.between(today, mend)
    qend = mend.month in (3, 6, 9, 12)
    add("S6", "단기자금", ("분기말" if qend else "월말") + " 계절성", "orange", 0 <= n_m <= C["period_end_bd"],
        f"{mend.month}/{mend.day} {'분기말' if qend else '월말'} 영업일 (D-{n_m})",
        f"D-{C['period_end_bd']}부터 (계절성)", _qe_text(ctx["MH"]["rows"]), "FreeSIS 1년 이력")
    CE = ctx.get("CE")
    if CE:
        mats = [m for m in CE["maturities"] if dt.date.fromisoformat(m["date"]) > today]
        soon = [m for m in mats if m["amt"] >= C["mat_single_eok"] and bd.between(today, dt.date.fromisoformat(m["date"])) <= C["mat_lead_bd"]]
        wk = {}
        for m in mats:
            d_ = dt.date.fromisoformat(m["date"]); mon = d_ - dt.timedelta(days=d_.weekday())
            wk[mon] = wk.get(mon, 0) + m["amt"]
        this_mon = today - dt.timedelta(days=today.weekday())
        heavy = [(w, v) for w, v in sorted(wk.items()) if v / 1e4 >= C["mat_week_jo"] and (w - this_mon).days <= 7]
        items = [f"{dt.date.fromisoformat(m['date']).month}/{dt.date.fromisoformat(m['date']).day} {m['issuer']} {m['amt']:,.0f}억 ({_cpn(m['cpn'])}%)" for m in sorted(soon, key=lambda m: m["date"])]
        items += [f"{w.month}/{w.day} 주 만기 합계 {v / 1e4:.2f}조" for w, v in heavy]
        add("S7", "단기자금", "대기업 회사채 만기", "red", bool(soon or heavy),
            f"{C['mat_lead_bd']}영업일 내 1,000억 이상 {len(soon)}건 {sum(m['amt'] for m in soon):,.0f}억" + (f" · 만기 집중 주 {len(heavy)}개" if heavy else ""),
            f"1,000억 이상 만기 {C['mat_lead_bd']}영업일 전, 또는 한 주 합계 {C['mat_week_jo']}조 이상(이번·다음 주)", "상환 자금 준비 단계 — MMF·RP 단기 운용 제안", "금투협 채권정보센터",
            items=items, key="S7|" + "|".join(m["nm"] for m in soon) + "|" + "|".join(str(w) for w, _ in heavy))
        pin = [p for p in CE["payins"] if p["date"] == today.isoformat() and p["amt"] >= C["payin_eok"]]
        add("S8", "단기자금", "공모채 납입", "red", bool(pin),
            " · ".join(f"{p['issuer']} {p['amt']:,}억" for p in pin) or "오늘 1,000억 이상 납입 없음",
            f"{C['payin_eok']:,}억 이상 납입 당일", "조달 자금 일시 운용 제안 (MMF·RP)", "DART", key="S8|" + "|".join(p["issuer"] for p in pin))
    CP = ctx.get("CP")
    cpcd_now = bp(r("CP(91일)", "d0"), r("CD(91일)", "d0")); cpcd_w = bp(r("CP(91일)", "w1"), r("CD(91일)", "w1"))
    chg_cpcd = round(cpcd_now - cpcd_w, 1)
    cbw = None
    if CP:
        dd_ = sorted(CP["daily"]); c0 = [d for d in dd_ if d <= ctx["d0"].replace("-", "")][-1]
        wk_ = [d for d in dd_ if d <= (dt.date(int(c0[:4]), int(c0[4:6]), int(c0[6:])) - dt.timedelta(days=7)).strftime("%Y%m%d")]
        if wk_:
            cbw = (CP["daily"][c0]["bal"][5] - CP["daily"][wk_[-1]]["bal"][5]) / 1e6
    add("S9", "단기자금", "CP 시장 경색", "orange", chg_cpcd >= C["cp_cd_w_bp"] or (cbw is not None and abs(cbw) >= C["cp_bal_w_jo"]),
        f"CP91−CD91 {cpcd_now:.0f}bp (1주 {_f(chg_cpcd, 0)}bp)" + (f" · CP 잔액 1주 {cbw:+.1f}조" if cbw is not None else ""),
        f"CP91−CD91 1주 +{C['cp_cd_w_bp']}bp, 또는 CP 잔액 1주 ±{C['cp_bal_w_jo']:.0f}조", "단기 크레딧 경계 — CP 편입 펀드 점검", "ECOS·금투협", mag=chg_cpcd)
    CL = ctx.get("CL")
    if CL:
        upd = dt.date.fromisoformat(CL.get("updated", "1900-01-01"))
        fresh = bd.between(upd, today) <= C["cash_new_bd"]
        ups = [x for x in CL["rows"] if x["chg"] / 1e4 >= C["cash_up_jo"]]
        add("S10", "단기자금", "대기업 현금 증가", "orange", fresh and bool(ups),
            (f"{len(ups)}개사 +{C['cash_up_jo']:.0f}조 이상 증가 ({CL['asof'][:10]})" if ups else "해당 없음") + ("" if fresh else " · 분기 보고서 갱신 시에만 발생"),
            f"분기 보고서에서 현금성자산 +{C['cash_up_jo']:.0f}조 이상 (분기 1회)", "신규 운용 제안 대상 리스트업", "DART",
            items=[f"{x['nm']} {x['chg'] / 1e4:+.1f}조" for x in ups[:8]] if fresh else [])

    # 쿨다운: 같은 key가 최근 N영업일 내 발생했으면 생략(수치가 더 커지면 다시 표시)
    hist = ctx.get("history", [])
    for s in out:
        if s["status"] != "fired":
            continue
        prev = [h for h in hist if h["key"] == s["key"] and h["date"] < today.isoformat()
                and bd.between(dt.date.fromisoformat(h["date"]), today) <= C["cooldown_bd"]]
        if prev and not (s["mag"] is not None and prev[-1].get("mag") is not None and abs(s["mag"]) > abs(prev[-1]["mag"])):
            s["status"] = "cooldown"
    new_hist = [h for h in hist if h["date"] != today.isoformat()] + [
        {"date": today.isoformat(), "id": s["id"], "key": s["key"], "mag": s["mag"]} for s in out if s["status"] == "fired"]
    cutoff = (today - dt.timedelta(days=60)).isoformat()
    return out, [h for h in new_hist if h["date"] >= cutoff]
