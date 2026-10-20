"""Daily Market Brief 생성기 (날짜 무관).

사용: python3 make_brief.py [엔진폴더]
입력 (엔진폴더/raw):
  rates_kr.json   한국은행 ECOS 시장금리. dates{d0,d1,w1,m0}, items{항목:{d0,d1,w1,m0}}, series{dates,CD(91일),CP(91일),...}
  rates_us.json   미 재무부 수익률. 같은 구조(3M,2Y,10Y,30Y)
  freesis.json    금투협 FreeSIS 펀드 기준 설정원본·자금유출입(백만원), MMF 고객유형(억원)
  mmf_history.json  [[YYYY-MM-DD, 백만원], ...]  MMF 설정원본 계
  repo_history.json [[YYYY-MM-DD, 행수, 매도합계, 매수합계, 업종별...], ...] 원
  content.json    그날의 텍스트(요약, 뉴스, 코멘트, 자금중개, 캘린더, 출처)
  (선택) bond_deals.json 공모 회사채 수요예측·발행조건(DART) / kofia_investor.json 투자자별 순매수(금투협)
         cp_daily.json CP 일자별(금투협) / stb_daily.json 전단채 발행사별(금투협)
         corp_liquidity.json 대기업 현금성자산(DART 정기보고서) / corp_events.json 회사채 만기·납입 일정
출력 (엔진폴더/out):
  brief_data.json, web.html(웹 게시용), YYYY-MM-DD_Daily_Market_Brief.pdf(고객 전달용)
"""
import json, os, re, sys, datetime as dt

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
RAW, OUT, TPL = (os.path.join(ROOT, p) for p in ("raw", "out", "templates"))
os.makedirs(OUT, exist_ok=True)
L = lambda f: json.load(open(os.path.join(RAW, f), encoding="utf-8"))
KR, US, FS, MH, RH, CT = (L(f) for f in ("rates_kr.json", "rates_us.json", "freesis.json", "mmf_history.json", "repo_history.json", "content.json"))
WD = "월화수목금토일"

def md(iso):  # 2026-10-16 -> 10/16
    d = dt.date.fromisoformat(iso); return f"{d.month:02d}/{d.day:02d}"
def mdw(iso):
    d = dt.date.fromisoformat(iso); return f"{d.month}/{d.day}({WD[d.weekday()]})"

# ---------- 숫자 포맷 ----------
def bp(a, b):
    return None if a is None or b is None else round((a - b) * 100, 1)
def fbp(x):
    if x is None: return "-"
    return "0.0" if x == 0 else f"{'+' if x > 0 else '−'}{abs(x):.1f}"
def sgn(x, nd=0):
    if x is None: return "-"
    if round(x, nd) == 0: return "0"
    return f"{'+' if x > 0 else '−'}{abs(x):,.{nd}f}"

KD = KR["dates"]
HEAD = [md(KD["d0"]), "전일", f"1주({md(KD['w1'])})", f"전월말({md(KD['m0'])})"]

def rrow(src, key, label=None, nd=3):
    v = src["items"][key]
    if v.get("d0") is None and v.get("d1") is not None:  # 공표 지연 항목(예: KOFR)
        return [f"{label or key} ({md(KD['d1'])})", f"{v['d1']:.{nd}f}", "-", "-", fbp(bp(v["d1"], v["m0"]))]
    return [label or key, f"{v['d0']:.{nd}f}", fbp(bp(v["d0"], v["d1"])), fbp(bp(v["d0"], v["w1"])), fbp(bp(v["d0"], v["m0"]))]

def sprow(label, a, b):
    I = KR["items"]; s = {k: round((I[a][k] - I[b][k]) * 100, 1) for k in ("d0", "d1", "w1", "m0")}
    return [label, f"{s['d0']:.1f}", fbp(round(s["d0"] - s["d1"], 1)), fbp(round(s["d0"] - s["w1"], 1)), fbp(round(s["d0"] - s["m0"], 1))]

bond_rates = [rrow(KR, k) for k in ["국고채(1년)", "국고채(2년)", "국고채(3년)", "국고채(5년)", "국고채(10년)", "국고채(30년)",
                                     "통안증권(1년)", "통안증권(2년)", "산금채(1년)", "회사채(3년, AA-)", "회사채(3년, BBB-)"]]
spreads = [sprow("AA- 3년 − 국고 3년", "회사채(3년, AA-)", "국고채(3년)"), sprow("국고 10년 − 3년", "국고채(10년)", "국고채(3년)")]
us_rows = [rrow(US, t, f"미 국채 {t}", 2) for t in ["3M", "2Y", "10Y", "30Y"]]
money_rates = [rrow(KR, "콜금리(1일, 전체거래)", "콜금리(1일)"), rrow(KR, "KOFR"), rrow(KR, "CD(91일)", "CD 91일"),
               rrow(KR, "CP(91일)", "CP 91일"), rrow(KR, "통안증권(91일)", "통안 91일"), rrow(KR, "MMF(7일)", "MMF 7일 수익률"),
               sprow("CP 91일 − CD 91일 (bp)", "CP(91일)", "CD(91일)")]
tenor_keys = [("1년", "국고채(1년)"), ("2년", "국고채(2년)"), ("3년", "국고채(3년)"), ("5년", "국고채(5년)"),
              ("10년", "국고채(10년)"), ("20년", "국고채(20년)"), ("30년", "국고채(30년)")]
curve = {"x": [t for t, _ in tenor_keys], "series": [
    {"name": md(KD["m0"]), "values": [KR["items"][k]["m0"] for _, k in tenor_keys], "muted": True},
    {"name": md(KD["d0"]), "values": [KR["items"][k]["d0"] for _, k in tenor_keys]}]}
ks = KR["series"]
cpcd = {"x": [md(d) for d in ks["dates"]], "series": [{"name": "CD 91일", "values": ks["CD(91일)"]}, {"name": "CP 91일", "values": ks["CP(91일)"]}]}

# ---------- 수급 (최근 1년 일별) ----------
cols = RH["cols"]
allrows = sorted(RH["rows"], key=lambda r: r[0])
for r in allrows:
    assert r[2] == r[3], f"Repo 매도≠매수 {r[0]}"            # 수집 누락 검출
end_d = max(allrows[-1][0], max(r[0] for r in MH["rows"]))
start_d = (dt.date.fromisoformat(end_d) - dt.timedelta(days=365)).isoformat()
rows = [r for r in allrows if r[0] >= start_d]
rd = {r[0]: r for r in rows}
r_last, r_prev = rows[-1], rows[-2]
m0 = KD["m0"]
r_m0 = rd.get(m0) or max((r for r in rows if r[0] <= m0), key=lambda r: r[0], default=rows[0])
mh = {r[0]: r[1] for r in MH["rows"] if r[0] >= start_d}          # 억원
dates = sorted(set(rd) | set(mh))
yl = lambda iso: f"{iso[2:4]}.{iso[5:7]}.{iso[8:10]}"
month_ticks, prev_m = [], None
for i, d in enumerate(dates):
    if d[:7] != prev_m:
        month_ticks.append(i); prev_m = d[:7]
month_ticks = [i for i in month_ticks if i > 3][::2]               # 두 달 간격 라벨
tick_labels = [f"{dates[i][2:4]}.{dates[i][5:7]}" for i in month_ticks]
qmarks = []
for q in ("03", "06", "09", "12"):
    for y in sorted({d[:4] for d in dates}):
        inq = [i for i, d in enumerate(dates) if d[:7] == f"{y}-{q}"]
        if inq and dates[inq[-1]][8:] >= "28": qmarks.append(inq[-1])
qmarks.sort()
eok = lambda m: round(m / 100)
st, fl, cl = FS["setup"]["단기금융"], FS["flows"]["단기금융"], FS["mmf_by_client"]
mh_last = max(mh)
supply = {
    "mmf": {"asof": md(FS["asof"]), "total": round(st["계"] / 1e6, 1), "dod_eok": eok(st["전일_계"]), "mtd_jo": round(st["전월말_계"] / 1e6, 1),
            "public": round(st["공모"] / 1e6, 1), "private": round(st["사모"] / 1e6, 1),
            "flow_public_eok": eok(fl["공모_증감"]), "flow_private_eok": eok(fl["사모_증감"]),
            "latest": {"asof": md(mh_last), "total": round(mh[mh_last] / 1e4, 1)}},
    "repo": {"asof": md(r_last[0]), "total": round(r_last[2] / 1e12, 1), "dod_eok": round((r_last[2] - r_prev[2]) / 1e8),
             "mtd_jo": round((r_last[2] - r_m0[2]) / 1e12, 1), "m0": md(r_m0[0])},
    "clients": {"asof": md(cl["asof"]), "rows": [[k, round(cl[k] / 1e4, 1), round(cl[k] / cl["합계"] * 100, 1)] for k in ["금융기관", "일반법인", "개인"]],
                "total": round(cl["합계"] / 1e4, 1)},
    "trend": {"x": [yl(d) for d in dates], "ticks": month_ticks, "tick_labels": tick_labels, "marks": qmarks, "series": [
        {"name": "MMF 설정원본", "values": [round(mh[d] / 1e4, 1) if d in mh else None for d in dates]},
        {"name": "Repo 잔액(원화)", "values": [round(rd[d][2] / 1e12, 1) if d in rd else None for d in dates]}]},
    "buyers": {"x": [yl(d) for d in dates], "ticks": month_ticks, "tick_labels": tick_labels, "marks": qmarks, "series": [
        {"name": lab, "values": [round(rd[d][cols.index(c)] / 1e12, 1) if d in rd else None for d in dates]}
        for c, lab in [("매수|은행(신탁)", "은행 신탁"), ("매수|집합투자", "집합투자"), ("매수|국내은행", "국내은행")]]},
    "period": f"{yl(dates[0])}~{yl(dates[-1])}",
    "comment": CT["supply_comment"],
}
flows = []
for k, lab in [("부동산", "부동산"), ("특별자산", "특별자산"), ("채권", "채권"), ("주식", "주식"), ("단기금융", "MMF(단기금융)")]:
    f = FS["flows"][k]; lv = FS["setup"].get(k)
    flows.append([lab, round(lv["계"] / 1e6, 1) if lv else None, eok(f["공모_증감"]), eok(f["사모_증감"]), eok(f["계_증감"])])

# 캘린더: ISO 날짜 → 표시용 필드
def dlabel(iso):
    d = dt.date.fromisoformat(iso); return {"d": f"{d.month}/{d.day}", "w": WD[d.weekday()]}
cal_items = [dict(c, **dlabel(c["date"])) for c in sorted(CT["calendar"], key=lambda c: c["date"])]
reserve_week = None
if CT.get("reserve_week"):
    rw = CT["reserve_week"]
    days = [dict(x, **dlabel(x["date"])) for x in rw["days"]]
    # 검산: 지준 당일(t) = 당일(t-1) + 공급 − 환수, 적수(t) = 적수(t-1) + 당일(t-1)×(휴일수) + 당일(t)
    for a_, b_ in zip(days, days[1:]):
        net = sum(v for _, v in b_["supply"]) - sum(v for _, v in b_["withdraw"])
        gap = (dt.date.fromisoformat(b_["date"]) - dt.date.fromisoformat(a_["date"])).days
        b_["check_daily"] = (a_["daily"] + net == b_["daily"])
        b_["check_cum"] = (a_["cum"] + a_["daily"] * (gap - 1) + b_["daily"] == b_["cum"])
    reserve_week = dict(rw, days=days)
for x in CT["macro"] + CT["fund_news"]:
    x.update({"date_label": f"{dt.date.fromisoformat(x['date']).month}/{dt.date.fromisoformat(x['date']).day}"})
bd = dt.date.fromisoformat(CT["date"])

# ---------- 채권: 발행시장(공모채 수요예측) · 투자자별 순매수 · CP/전단채 ----------
def ld(name):
    p = os.path.join(RAW, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
BD, KI, CPD, STB, CL, CE = (ld(n) for n in ["bond_deals.json", "kofia_investor.json", "cp_daily.json", "stb_daily.json", "corp_liquidity.json", "corp_events.json"])
INV3 = ["운용사(집합)", "증권사", "연기금·은행·보험"]
issue = None
if BD:
    rows, tot = [], [0] * 7
    for d in sorted(BD["deals"], key=lambda x: x["dfd"] or x["pay"], reverse=True):
        amt = sum(a["amt"] for a in d["amts"])
        q = [sum(x["q"][i] for x in d["dem"]) for i in range(7)] if d["dem"] else None
        if q:
            assert sum(q[:6]) == q[6], d["corp"]
            tot = [a + b for a, b in zip(tot, q)]
        k = d["kind"]
        kind = "신종자본" if re.search("신종자본|조건부자본", k) else "담보부" if "담보부" in k else "후순위" if "후순위" in k else "무보증"
        sp = " · ".join(f"{s.split('|')[0]} {float(s.split('|')[1]) * 100:+.0f}bp" for s in d["sp"])
        rt = "/".join(f"{r['rate']:.2f}" for r in d["rates"]) + ("%" if d["rates"] else "")
        rows.append({"corp": d["corp"], "kind": kind, "grade": d["grade"], "dfd": md(d["dfd"]) if d["dfd"] else "-", "pay": md(d["pay"]) if d["pay"] else "-",
                     "amt": amt, "demand": q[6] if q else None, "ratio": round(q[6] / amt, 1) if q else None,
                     "share": [round(v / q[6] * 100) for v in q[:3]] if q else None, "spread": sp or "-", "rate": rt or "-",
                     "band": d.get("band"), "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + d["docs"][-1].split()[-1]})
    up = [{"corp": u["corp"], "kind": "신종자본" if "신종" in u["kind"] else "무보증", "grade": u["grade"], "dfd": mdw(u["dfd"]), "pay": md(u["pay"]),
           "amt": sum(t["amt"] for t in u["tr"]), "band": u["band"], "tenor": " · ".join(t["mat"] if t["mat"] in ("영구",) else f"{t['tr']}회" for t in u["tr"]),
           "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + u["rcp"]} for u in sorted(BD["upcoming"], key=lambda x: x["dfd"])]
    n_dem = sum(1 for r in rows if r["demand"])
    issue = {"asof": BD["asof"], "window": BD["window"], "rows": rows, "upcoming": up, "n": n_dem,
             "amt": sum(r["amt"] for r in rows if r["demand"]), "demand": tot[6],
             "share": [[INV3[i], tot[i], round(tot[i] / tot[6] * 100, 1)] for i in range(3)],
             "note": "수요예측 참여 기준(억원). 운용사(집합)=펀드·투자일임 계정, 증권사=투자매매·중개업자, 연기금·은행·보험에는 운용사 고유계정 포함. 가산금리는 민평 수익률 대비 확정치"}
investors = None
if KI:
    days = sorted(KI["daily"]); d0k = days[-1]; m0k = d0k[:6] + "01"
    BT = [(("국채",), "국채"), (("통안증권",), "통안"), (("은행채",), "은행채"), (("기타금융채",), "여전채 등"), (("특수채",), "특수채"), (("회사채",), "회사채"), (("지방채", "ABS"), "기타"), (("합계",), "합계")]
    INV = ["자산운용(공모)", "은행", "보험", "기금공제", "외국인", "기타법인", "개인", "국가지자체", "종금상호", "자산운용(사모)"]
    def tbl(ds):
        return [[iv] + [sum(KI["daily"][d][b][iv] for d in ds for b in bs) for bs, _ in BT] for iv in INV]
    mtd_days = [d for d in days if d >= m0k]
    t0, tm = tbl([d0k]), tbl(mtd_days)
    for r in t0 + tm:  # 채권종류 합 = 합계(반올림 오차 ±12억 허용)
        assert abs(sum(r[1:-1]) - r[-1]) <= 12, r
    run = {iv: [] for iv in ["자산운용(공모)", "은행", "외국인"]}
    for iv in run:
        c = 0
        for d in days:
            c += KI["daily"][d]["합계"][iv]; run[iv].append(round(c / 1e4, 2))
    investors = {"d0": f"{int(d0k[4:6])}/{int(d0k[6:])}", "mtd": f"{int(m0k[4:6])}/1~{int(d0k[4:6])}/{int(d0k[6:])}", "head": [b[1] for b in BT],
                 "t0": t0, "tm": tm,
                 "cum": {"x": [f"{d[4:6]}/{d[6:]}" for d in days], "series": [{"name": k, "values": v} for k, v in run.items()]},
                 "note": "장외 거래대금 기준 순매수(매수−매도), 억원. 자산운용(공모)에 MMF 등 공모펀드 포함 · 금투협 채권정보센터"}
cpst = None
if CPD:
    dd = sorted(CPD["daily"]); c0 = dd[-1] if dd[-1] <= KD["d0"].replace("-", "") else [d for d in dd if d <= KD["d0"].replace("-", "")][-1]
    qe = [d for d in dd if d[4:] in ("0331", "0630", "0930", "1231") and d <= c0]
    wk = [d for d in dd if d <= (dt.date(int(c0[:4]), int(c0[4:6]), int(c0[6:])) - dt.timedelta(days=7)).strftime("%Y%m%d")]
    def bal(d): return CPD["daily"][d]["bal"][5] / 1e6
    x = CPD["daily"][c0]
    cpst = {"asof": f"{int(c0[4:6])}/{int(c0[6:])}", "buckets": CPD["buckets"][:5],
            "disc_rate": x["dr"][:5], "disc_vol": [None if v is None else round(v / 100) for v in x["dv"][:5]], "sale_rate": x["sr"][:5],
            "bal": [round(v / 1e6, 1) for v in x["bal"][:5]], "bal_total": round(bal(c0), 1),
            "chg_w": round(bal(c0) - bal(wk[-1]), 1) if wk else None, "chg_q": round(bal(c0) - bal(qe[-1]), 1) if qe else None,
            "q_label": f"{int(qe[-1][4:6])}/{int(qe[-1][6:])}" if qe else None,
            "trend": {"x": [f"{d[4:6]}/{d[6:]}" for d in dd if d <= c0], "series": [{"name": "CP 잔액", "values": [round(bal(d), 1) for d in dd if d <= c0]}]},
            "note": "금투협 CP정보(일자별) · 증권사 보고 잠정치. 할인=증권사의 CP 매입(발행 인수), 매출=고객 판매. 잔액은 할인 기준"}
    if STB:
        cpst["stb"] = {"asof": md(STB["date"]), "byCls": STB["byCls"], "total": sum(c["amt"] for c in STB["byCls"]) / 1e6,
                       "top_corp": [t for t in STB["top"] if t["cls"] != "증권사"][:8], "top_sec": [t for t in STB["top"] if t["cls"] == "증권사"][:5],
                       "note": STB["note"]}
corp = None
if CL or CE:
    corp = {}
    if CL:
        corp["liq"] = {"asof": CL["asof"], "note": CL["note"], "next": CL["next_update"],
                       "rows": [[r["nm"], round(r["cash"][0] / 1e4, 1), None if not r["stfi"] else round(r["stfi"][0] / 1e4, 1), round(r["liq"][0] / 1e4, 1),
                                 round(r["chg"] / 1e4, 1)] for r in CL["rows"][:15]]}
    if CE:
        start = KD["d0"]
        mats = [m for m in CE["maturities"] if m["date"] > start]
        wk = {}
        for m in mats:
            d = dt.date.fromisoformat(m["date"]); mon = d - dt.timedelta(days=d.weekday())
            w = wk.setdefault(mon.isoformat(), {"amt": 0, "n": 0}); w["amt"] += m["amt"]; w["n"] += 1
        corp["events"] = {"window": CE["window"], "src": CE["src"],
                          "weeks": [[f"{dt.date.fromisoformat(k).month}/{dt.date.fromisoformat(k).day} 주", round(v["amt"]), v["n"]] for k, v in sorted(wk.items())],
                          "mat_total": round(sum(m["amt"] for m in mats)),
                          "big": [dict(m, d=md(m["date"])) for m in sorted(mats, key=lambda m: (m["date"], -m["amt"])) if m["amt"] >= 1000],
                          "payins": [dict(p, d=md(p["date"])) for p in CE["payins"] if p["date"] > start]}
        # 캘린더에 기업 자금 이벤트 추가(1,000억 이상 만기 · 공모채 납입)
        for m in corp["events"]["big"]:
            CT["calendar"].append({"date": m["date"], "text": f"{m['issuer']} 회사채 만기 {m['amt']:,.0f}억", "tag": "corp"})
        for p in corp["events"]["payins"]:
            CT["calendar"].append({"date": p["date"], "text": f"{p['issuer']} {p['kind']} {p['amt']:,}억", "tag": "corp"})
cal_items = [dict(c, **dlabel(c["date"])) for c in sorted(CT["calendar"], key=lambda c: c["date"])]

# ---------- 영업 시그널 ----------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signals as SIG
_cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "config.json")) else {}
_hist_p = os.path.join(RAW, "signal_history.json")
_hist = json.load(open(_hist_p, encoding="utf-8")) if os.path.exists(_hist_p) else []
sig_list, sig_hist = SIG.evaluate({"date": CT["date"], "d0": KD["d0"], "KR": KR, "US": US, "CT": CT, "FS": FS, "MH": MH, "RH": RH,
                                   "BD": BD, "KI": KI, "CP": CPD, "CL": CL, "CE": CE, "RO": ld("reit_offerings.json"), "RT": ld("ratings.json"),
                                   "cfg": _cfg.get("signals"), "holidays": _cfg.get("holidays", []), "history": _hist})
json.dump(sig_hist, open(_hist_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for s_ in sig_list:
    s_.pop("mag", None)
sig_fired = [s_ for s_ in sig_list if s_["status"] == "fired"]
signals = {"asof": CT["date"], "list": sig_list,
           "count": {"red": sum(1 for s_ in sig_fired if s_["level"] == "red"), "orange": sum(1 for s_ in sig_fired if s_["level"] == "orange"),
                     "checked": sum(1 for s_ in sig_list if s_["status"] != "nodata"), "nodata": sum(1 for s_ in sig_list if s_["status"] == "nodata"),
                     "cooldown": sum(1 for s_ in sig_list if s_["status"] == "cooldown")}}

# ---------- 질문 도우미용 원자료(브라우저에서 직접 계산) ----------
_mcols = MH["cols"]
ask = {
    "d0": KD["d0"], "d1": KD["d1"], "w1": KD["w1"], "m0": KD["m0"],
    "mmf": [[r[0], r[1], r[2], r[3]] for r in MH["rows"]],                      # 억원: 합계·공모·사모
    "repo_cols": ["총잔액", "집합투자 매수", "국내은행 매수", "은행(신탁) 매수", "증권사(신탁) 매수", "여신금융업 매수", "증권사 매수", "증권사 매도", "집합투자 매도"],
    "repo": [[r[0]] + [round(r[RH["cols"].index(c)] / 1e12, 2) for c in ["매도합계", "매수|집합투자", "매수|국내은행", "매수|은행(신탁)", "매수|증권사(신탁)", "매수|여신 금융업", "매수|증권사", "매도|증권사", "매도|집합투자"]] for r in RH["rows"]],
    "kr": KR["items"], "us": US["items"], "series": KR.get("series"),
    "inv_names": ["자산운용(공모)", "은행", "보험", "기금공제", "외국인", "기타법인", "개인", "국가지자체", "종금상호", "자산운용(사모)"],
    "inv": ({d: {b: [KI["daily"][d][b][iv] for iv in ["자산운용(공모)", "은행", "보험", "기금공제", "외국인", "기타법인", "개인", "국가지자체", "종금상호", "자산운용(사모)"]] for b in KI["daily"][d]} for d in KI["daily"]} if KI else {}),
    "cp": ({d: {"dr": v["dr"][:5], "bal": [round(x / 1e6, 1) for x in v["bal"]]} for d, v in CPD["daily"].items()} if CPD else {}),
    "cp_buckets": CPD["buckets"][:5] if CPD else [],
    "mats": (CE["maturities"] if CE else []), "payins": (CE["payins"] if CE else []),
    "liq": ([{"nm": r["nm"], "cash": r["cash"][0], "stfi": r["stfi"][0] if r["stfi"] else None, "liq": r["liq"][0], "chg": r["chg"]} for r in CL["rows"]] if CL else []),
    "liq_asof": CL["asof"] if CL else None,
    "qa": CT.get("qa", []) + (json.load(open(os.path.join(ROOT, "qa_static.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "qa_static.json")) else []),
}

data = {
    "meta": {"date": CT["date"], "label": f"{bd.year}. {bd.month}. {bd.day} ({WD[bd.weekday()]})",
             "asof": f"지표 기준일 {mdw(KD['d0'])} 마감", "team": "Wholesale 금융상품영업팀", "status": CT.get("status", "팀 내부용")},
    "summary": CT["summary"], "macro": CT["macro"],
    "realestate": {"news": CT["fund_news"], "flows_comment": CT["flows_comment"],
                   "flows": {"asof": md(FS["asof"]), "rows": flows,
                             "note": "순유입 = 설정(입금) − 해지(출금), 억원 · 설정원본 조원 · 금투협 FreeSIS 펀드 기준(투자일임 제외)"}},
    "bond": {"head": HEAD, "rates": bond_rates, "spreads": spreads, "us": us_rows, "curve": curve, "comment": CT["bond_comment"],
             "issue": issue, "investors": investors, "cp": cpst, "flow_comment": CT.get("bond_flow_comment")},
    "money": {"rates": money_rates, "cpcd": cpcd, "rates_comment": CT["money_comment"], "supply": supply, "kmb": CT.get("kmb"),
              "corp": corp, "corp_comment": CT.get("corp_comment")},
    "calendar": cal_items, "reserve_week": reserve_week, "sources": CT["sources"], "signals": signals, "ask": ask,
}
json.dump(data, open(os.path.join(OUT, "brief_data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 웹 ----------
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
web = open(os.path.join(TPL, "web_template.html"), encoding="utf-8").read().replace("/*__ASK_JS__*/", open(os.path.join(TPL, "ask.js"), encoding="utf-8").read()).replace("/*__BRIEF_DATA__*/null", payload)
open(os.path.join(OUT, "web.html"), "w", encoding="utf-8").write(web)

# ---------- PDF (고객 전달용) ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
for fp in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(fp): font_manager.fontManager.addfont(fp)
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "svg.fonttype": "path", "axes.unicode_minus": False})
INK, INK2, MUTED, GRID = "#1d1d1b", "#52514e", "#8a8984", "#e4e3df"
COL = ["#2a78d6", "#eb6834", "#1baf7a"]

def line_svg(name, spec, ylabel, dec, ticks=None, h=1.75, w=3.55, marks=None, tick_labels=None):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    n = len(spec["x"]); k = 0; ends = []
    for i in (marks or []):
        ax.axvline(i, color=GRID, linewidth=0.9, linestyle=(0, (2, 2)), zorder=0)
    for s in spec["series"]:
        xs = [i for i, v in enumerate(s["values"]) if v is not None]; ys = [s["values"][i] for i in xs]
        if s.get("muted"):
            ax.plot(xs, ys, color=MUTED, linewidth=1.4, linestyle=(0, (3, 2)), marker="o", markersize=2.5, label=s["name"])
        else:
            ax.plot(xs, ys, color=COL[k % 3], linewidth=2 if n <= 60 else 1.5, marker="o" if n <= 8 else None, markersize=3, label=s["name"])
            if xs: ends.append((xs[-1], ys[-1]))
            k += 1
    for sp in ["top", "right", "left"]: ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=INK2, labelsize=7, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    t = ticks if ticks is not None else [0, n // 2, n - 1]
    ax.set_xticks(t); ax.set_xticklabels(tick_labels or [spec["x"][i] for i in t])
    ax.set_xlim(-0.5, n - 1 + max(1.6, n * 0.06) if n > 8 else n - 0.4)
    lab = [s["name"] for s in spec["series"]]
    ax.legend(frameon=False, fontsize=7, loc="lower left", bbox_to_anchor=(0, 0.98), ncol=4, labelcolor=INK2, borderaxespad=0)
    if marks: ax.annotate("점선: 분기말", xy=(1, 1.0), xycoords="axes fraction", ha="right", va="bottom", fontsize=6.5, color=INK2)
    ax.set_ylabel(ylabel, fontsize=7, color=INK2, rotation=0, labelpad=10)
    fig.tight_layout(pad=0.3)
    # 끝점 라벨: 화면 좌표에서 최소 간격(8pt)을 두고 위에서부터 배치
    to_pt = lambda yv: ax.transData.transform((0, yv))[1] * 72 / fig.dpi
    placed = []
    for xe, ye in sorted(ends, key=lambda e: -e[1]):
        yp = to_pt(ye)
        if placed and placed[-1] - yp < 8: yp = placed[-1] - 8
        placed.append(yp)
        ax.annotate(f"{ye:.{dec}f}", (xe, ye), textcoords="offset points", xytext=(4, yp - to_pt(ye) - 2.5), ha="left", fontsize=7, color=INK)
    p = os.path.join(OUT, f"_{name}.svg"); fig.savefig(p); plt.close(fig); return p

T, Bu = supply["trend"], supply["buyers"]
charts = {
    "curve": line_svg("curve", curve, "%", 3, ticks=list(range(7)), h=1.85),
    "cpcd": line_svg("cpcd", cpcd, "%", 2, ticks=[0, len(cpcd["x"]) // 2, len(cpcd["x"]) - 1]),
    "trend": line_svg("trend", T, "조원", 1, ticks=T["ticks"], tick_labels=T["tick_labels"], marks=T["marks"], w=7.3, h=2.05),
    "buyers": line_svg("buyers", Bu, "조원", 1, ticks=Bu["ticks"], tick_labels=Bu["tick_labels"], marks=Bu["marks"], w=7.3, h=2.05),
}
# 월간 달력 격자 (브리프 기준 월, 월~일)
import calendar as _cal
def month_grid_for(items):
    ev = {}
    for c in items: ev.setdefault(c["date"], []).append(c)
    g = {"title": f"{bd.year}년 {bd.month}월", "weeks": [],
         "outside": [c for c in items if c["date"][:7] != f"{bd.year}-{bd.month:02d}" and c.get("tag") != "corp"]}
    for wk in _cal.Calendar(firstweekday=0).monthdatescalendar(bd.year, bd.month):
        g["weeks"].append([{"day": d.day, "in": d.month == bd.month, "today": d == bd, "wkend": d.weekday() >= 5,
                            "events": ev.get(d.isoformat(), [])} for d in wk])
    return g
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
env = Environment(loader=FileSystemLoader(TPL), autoescape=True)
# 고객용 PDF 설정: 한국자금중개 자료는 저작권 정책상 협의 전까지 고객용에서 제외(기본값)
CFG_P = os.path.join(ROOT, "config.json")
CFG = json.load(open(CFG_P, encoding="utf-8")) if os.path.exists(CFG_P) else {}
include_kmb = bool(CFG.get("client_pdf_include_kmb", False))
pdf_srcs = [x for x in data["sources"] if "대조 전" not in x and (include_kmb or "지준·콜·레포" not in x)]
pdf_cal = [c for c in data["calendar"] if not c.get("check") and (include_kmb or not c.get("kmb"))]
month_grid = month_grid_for(pdf_cal)
pdf_summary = [x["text"] if isinstance(x, dict) else x for x in data["summary"] if include_kmb or not (isinstance(x, dict) and x.get("kmb"))]
pdf_html = env.get_template("pdf_template.html").render(B=data, C=charts, sgn=sgn, include_kmb=include_kmb, summary=pdf_summary, month=month_grid,
                                                         cal=pdf_cal,
                                                         srcs=pdf_srcs)
open(os.path.join(OUT, "_pdf.html"), "w", encoding="utf-8").write(pdf_html)
pdf_path = os.path.join(OUT, f"{CT['date']}_Daily_Market_Brief.pdf")
HTML(string=pdf_html, base_url=OUT).write_pdf(pdf_path)
print(json.dumps({"web": os.path.join(OUT, "web.html"), "pdf": pdf_path}, ensure_ascii=False))
