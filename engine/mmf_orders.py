"""MMF 주문(BETA) — 고객 주문 메일에서 뽑은 실행일·금액·매수/환매를 원문과 대조하고 화면용 데이터로 만든다.

build(raw_dir, today_iso, holidays) -> dict | None
  입력: raw/mmf_extract.json(추출 결과), 그 안의 "source" 파일(받은편지함 원문)
  규칙: src는 메일 본문에 그대로 있어야 하고, src에서 다시 읽은 날짜·금액·구분(매수/환매)이 추출값과 같아야 한다.
        어긋나면 '확인 필요'로 빼고 합계에 넣지 않는다.
"""
import datetime as dt
import json
import os
import re

from notices import parse_krw, _norm


def parse_md(s, year):
    """'10월 23일' → ISO. 연도가 있으면 그 연도."""
    m = re.search(r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일", s)
    if not m:
        return None
    return dt.date(int(m.group(1) or year), int(m.group(2)), int(m.group(3))).isoformat()


def side_of(s):
    b, r = "매수" in s or "설정" in s, "환매" in s or "해지" in s
    return "매수" if b and not r else "환매" if r and not b else None


def build(raw_dir, today_iso, holidays=()):
    ext_p = os.path.join(raw_dir, "mmf_extract.json")
    if not os.path.exists(ext_p):
        return None
    EX = json.load(open(ext_p, encoding="utf-8"))
    IB = json.load(open(os.path.join(raw_dir, EX.get("source", "mmf_inbox_sample.json")), encoding="utf-8"))
    mails = {m["id"]: m for m in IB["messages"]}
    today = dt.date.fromisoformat(today_iso)
    seg = EX.get("clients", {})
    orders, issues = [], []
    for o in EX["orders"]:
        m = mails.get(o["id"])
        prob = []
        if not m:
            prob.append("원문 메일 없음")
        else:
            body = _norm(m["body"])
            yr = int(m["received"][:4])
            if _norm(o["src"]) not in body:
                prob.append("원문에 없는 문구")
            if parse_md(o["src"], yr) != o["date"]:
                prob.append("실행일 불일치")
            if parse_krw(o["src"]) != o["won"]:
                prob.append("금액 불일치")
            if side_of(o["src"]) != o["side"]:
                prob.append("매수/환매 불일치")
        d = dt.date.fromisoformat(o["date"])
        rec = {"id": o["id"], "client": o["client"], "seg": seg.get(o["client"], "기타"), "side": o["side"], "date": o["date"],
               "dday": (d - today).days, "won": o["won"], "note": o.get("note", ""),
               "received": m["received"] if m else "", "from": m["from"] if m else "", "body": m["body"] if m else "",
               "status": "확인 필요" if prob else "ok", "issues": prob}
        if prob:
            issues.append({"id": o["id"], "client": o["client"], "issues": prob})
        orders.append(rec)
    ok = [o for o in orders if o["status"] == "ok"]
    # 오늘부터 10영업일 바둑판
    hol = set(holidays)
    days, d = [], today
    while len(days) < 10:
        if d.weekday() < 5 and d.isoformat() not in hol:
            days.append(d.isoformat())
        d += dt.timedelta(days=1)
    grid = []
    for iso in days:
        lst = sorted([o for o in ok if o["date"] == iso], key=lambda x: (x["side"] != "매수", -x["won"]))
        buy = sum(o["won"] for o in lst if o["side"] == "매수")
        red = sum(o["won"] for o in lst if o["side"] == "환매")
        grid.append({"date": iso, "dday": (dt.date.fromisoformat(iso) - today).days, "buy": buy, "red": red, "net": buy - red,
                     "orders": [[o["client"], o["side"], o["won"], o["note"]] for o in lst]})
    wk_end = (today + dt.timedelta(days=6 - today.weekday())).isoformat()
    tdy = [o for o in ok if o["date"] == today_iso]
    wk = [o for o in ok if today_iso <= o["date"] <= wk_end]
    orders.sort(key=lambda x: (x["date"], x["side"] != "매수", -x["won"]))
    return {
        "beta": True, "sample": "가상" in IB.get("mailbox", ""), "asof": today_iso, "orders": orders, "grid": grid, "issues": issues,
        "kpi": {"today_n": len(tdy), "today_buy": sum(o["won"] for o in tdy if o["side"] == "매수"),
                "today_red": sum(o["won"] for o in tdy if o["side"] == "환매"),
                "week_n": len(wk), "week_buy": sum(o["won"] for o in wk if o["side"] == "매수"),
                "week_red": sum(o["won"] for o in wk if o["side"] == "환매"),
                "new_today": sum(1 for o in orders if o["received"][:10] == today_iso), "wk_end": wk_end},
    }


if __name__ == "__main__":
    import sys
    r = build(sys.argv[1] if len(sys.argv) > 1 else "raw", sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat())
    print(json.dumps({"n": len(r["orders"]), "issues": r["issues"], "kpi": r["kpi"],
                      "grid": [(g["date"], g["buy"] // 10**8, g["red"] // 10**8, len(g["orders"])) for g in r["grid"]]}, ensure_ascii=False))
