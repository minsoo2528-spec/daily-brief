"""공문 일정(BETA) — 메일 본문에서 뽑은 일정·금액을 원문과 대조하고 화면용 데이터로 만든다.

build(raw_dir, today_iso) -> dict | None
  입력: raw/notice_extract.json(추출 결과), 그 안의 "source" 파일(받은편지함 원문)
  규칙: 모든 date·won은 src 문구에서 다시 읽어 같은지 확인하고, src는 메일 본문에 그대로 있어야 한다.
        하나라도 어긋나면 그 항목을 '확인 필요'로 표시하고 화면 일정에서 뺀다(추정으로 채우지 않는다).
"""
import datetime as dt
import json
import os
import re

TYPES = ["설정", "캐피탈콜", "배당", "만기·청산", "수익자총회", "기타"]


def parse_krw(s):
    """'18억 4,500만원' / '600억원' / '4,500,000,000원' → 원(int). 금액이 없으면 None."""
    m = re.search(r"(?:(\d[\d,]*)\s*조)?\s*(?:(\d[\d,]*)\s*억)?\s*(?:(\d[\d,]*)\s*만)?\s*원", s)
    if not m or not any(m.groups()):
        m2 = re.search(r"(\d[\d,]{3,})\s*원", s)
        return int(m2.group(1).replace(",", "")) if m2 else None
    jo, eok, man = (int(g.replace(",", "")) if g else 0 for g in m.groups())
    return jo * 10**12 + eok * 10**8 + man * 10**4


def parse_date(s):
    m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", s) or re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", s)
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat() if m else None


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def build(raw_dir, today_iso):
    ext_p = os.path.join(raw_dir, "notice_extract.json")
    if not os.path.exists(ext_p):
        return None
    EX = json.load(open(ext_p, encoding="utf-8"))
    src_p = os.path.join(raw_dir, EX.get("source", "notice_inbox_sample.json"))
    IB = json.load(open(src_p, encoding="utf-8"))
    mails = {m["id"]: m for m in IB["messages"]}
    today = dt.date.fromisoformat(today_iso)
    notices, events, issues = [], [], []
    for n in EX["notices"]:
        m = mails.get(n["id"])
        prob = []
        if not m:
            prob.append("원문 메일 없음")
            body = ""
        else:
            body = _norm(m["body"])
        evs = []
        for e in n.get("events", []):
            ok = _norm(e["src"]) in body and parse_date(e["src"]) == e["date"]
            if not ok:
                prob.append(f"일정 불일치: {e['label']}")
                continue
            evs.append(e)
        ams = []
        for a in n.get("amounts", []):
            ok = _norm(a["src"]) in body and parse_krw(a["src"]) == a["won"]
            if not ok:
                prob.append(f"금액 불일치: {a.get('investor') or a['label']}")
                continue
            ams.append(a)
        typ = n["type"] if n["type"] in TYPES else "기타"
        total = next((a["won"] for a in ams if a["label"] in ("합계", "분배금 총액", "최초 설정금액")), None)
        rec = {"id": n["id"], "type": typ, "manager": n["manager"], "fund": n["fund"], "summary": n.get("summary", ""),
               "received": m["received"] if m else "", "subject": m["subject"] if m else "", "body": m["body"] if m else "",
               "events": evs, "amounts": ams, "total": total, "status": "확인 필요" if prob else "ok", "issues": prob}
        notices.append(rec)
        if prob:
            issues.append({"id": n["id"], "fund": n["fund"], "issues": prob})
        for e in evs:
            d = dt.date.fromisoformat(e["date"])
            events.append({"date": e["date"], "dday": (d - today).days, "label": e["label"], "type": typ, "fund": n["fund"],
                           "manager": n["manager"], "id": n["id"],
                           "total": total if re.search("지급|납입|설정일|상환", e["label"]) else None,
                           "investors": [[a["investor"], a["won"]] for a in ams if a.get("investor")]})
    events.sort(key=lambda x: (x["date"], x["fund"]))
    notices.sort(key=lambda x: x["received"], reverse=True)
    up = [e for e in events if e["dday"] >= 0]
    wk_end = today + dt.timedelta(days=6 - today.weekday() + 7)  # 다음 주 일요일까지
    return {
        "beta": True, "sample": "가상" in IB.get("mailbox", "") or "_note" in IB, "mailbox": IB.get("mailbox", ""),
        "asof": today_iso, "notices": notices, "events": events, "issues": issues,
        "kpi": {
            "new_today": sum(1 for n in notices if n["received"][:10] == today_iso),
            "next2w": sum(1 for e in up if dt.date.fromisoformat(e["date"]) <= wk_end),
            "call_due": sum(e["total"] or 0 for e in up if e["type"] == "캐피탈콜"),
            "dist_due": sum(e["total"] or 0 for e in up if e["type"] == "배당" and "지급" in e["label"]),
        },
    }


if __name__ == "__main__":
    import sys
    r = build(sys.argv[1] if len(sys.argv) > 1 else "raw", sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat())
    print(json.dumps({"n": len(r["notices"]), "events": len(r["events"]), "issues": r["issues"], "kpi": r["kpi"]}, ensure_ascii=False))
