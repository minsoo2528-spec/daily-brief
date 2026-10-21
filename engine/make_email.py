"""팀 메일 본문 생성 — make_brief.py 실행 후 돌린다.

python3 make_email.py <엔진폴더>
  입력: out/brief_data.json, config.json("email")
  출력: out/email.json {to, subject, html, text}
보내기는 실행 세션이 Gmail 연결(send_message)로 한다(RUNBOOK 8단계).
"""
import html
import json
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
D = json.load(open(os.path.join(OUT, "brief_data.json"), encoding="utf-8"))
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8")).get("email", {})
E = html.escape

to = CFG.get("team_to") or []
url = CFG.get("web_url", "")
app = CFG.get("app_url", "")
meta = D["meta"]
m = re.match(r"\d{4}\.\s*(\d+)\.\s*(\d+)\s*\((.)\)", meta["label"])
short = f"{int(m.group(1))}/{int(m.group(2))}({m.group(3)})" if m else meta["date"]

sig = D.get("signals") or {"list": [], "count": {"red": 0, "orange": 0}}
fired = [s for s in sig["list"] if s.get("status") == "fired"]
fired.sort(key=lambda s: s["level"] != "red")
cnt = sig.get("count", {})
nr, no = cnt.get("red", 0), cnt.get("orange", 0)
LV = {"red": ("행동", "#c0392b", "#fdeeec"), "orange": ("주목", "#c76a00", "#fff4e5")}

rows = []
for s in fired:
    t, c, bg = LV[s["level"]]
    items = "".join(f'<li style="margin:2px 0">{E(i)}</li>' for i in s.get("items", []))
    links = "".join(f' <a href="{E(u)}" style="color:#d35f12">원문</a>' for u in s.get("links", []))
    rows.append(
        f'<tr><td style="padding:12px 14px;border-bottom:1px solid #e0e4ea;vertical-align:top">'
        f'<span style="display:inline-block;font-size:12px;font-weight:700;color:{c};background:{bg};border-radius:4px;padding:1px 7px">{t}</span>'
        f'<span style="font-size:12px;color:#858d99;margin-left:6px">{E(s["sec"])}</span>'
        f'<div style="font-size:15px;font-weight:700;color:#142031;margin:6px 0 2px">{E(s["name"])}</div>'
        f'<div style="font-size:14px;color:#142031">{E(s["value"])}</div>'
        + (f'<ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:#4c5666">{items}</ul>' if items else "")
        + f'<div style="font-size:13px;background:#f3f4f6;border-radius:6px;padding:7px 10px;margin-top:8px"><b>영업 포인트</b> {E(s["action"])}{links}</div>'
        f'<div style="font-size:11px;color:#858d99;margin-top:5px">기준: {E(s["rule"])} · 출처: {E(s["src"])}</div></td></tr>'
    )

MN = D.get("market_now")
def _c(v): return "#d9363e" if v > 0 else "#2f6fd6" if v < 0 else "#555555"
def _s(v, nd): return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):,.{nd}f}"
mkt_html, mkt_text = "", ""
if MN and (MN.get("kr") or MN.get("us")):
    cells = [(o["name"] + f" ({o['time']})", f"{o['price']:,.2f}", f"{_s(o['chg'], 2)} ({_s(o['pct'], 2)}%)", o["chg"]) for o in MN.get("kr", [])]
    if MN.get("fx"):
        cells.append((f"원/달러 ({MN['fx']['time']})", f"{MN['fx']['price']:,.1f}", f"전일 대비 {_s(MN['fx']['chg'], 1)}", MN["fx"]["chg"]))
    cells += [(f"{o['name']} ({o['date']} 마감)", f"{o['price']:,.2f}", f"{_s(o['pct'], 2)}%", o["chg"]) for o in MN.get("us", [])]
    n_kr = len(cells) - len(MN.get("us", []))
    def _td(a, b, c, v):
        return (f'<td style="padding:8px 10px;border:1px solid #e0e4ea;vertical-align:top">'
                f'<div style="font-size:11px;color:#858d99">{E(a)}</div><div style="font-size:16px;font-weight:700;color:#142031">{E(b)}</div>'
                f'<div style="font-size:12px;color:{_c(v)}">{E(c)}</div></td>')
    rows_ = [cells[:n_kr], cells[n_kr:]]
    tds = "".join(f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;margin-bottom:-1px"><tr>{"".join(_td(*x) for x in r)}</tr></table>' for r in rows_ if r)
    kp = next((o for o in MN.get("kr", []) if o["name"] == "코스피" and o.get("inv")), None)
    inv = (f'<div style="font-size:12px;color:#4c5666;margin-top:6px">코스피 수급(억원, 장중 잠정): 외국인 {_s(kp["inv"]["frgn"], 0)} · 기관 {_s(kp["inv"]["inst"], 0)} · 개인 {_s(kp["inv"]["indiv"], 0)}</div>' if kp else "")
    cm = (f'<div style="font-size:13px;background:#f3f4f6;border-radius:6px;padding:8px 10px;margin-top:8px"><b>시황 코멘트</b> {E(MN["comment"])}</div>' if MN.get("comment") else "")
    mkt_html = (f'<div style="font-size:16px;font-weight:700;margin-bottom:8px">현재 시황 <span style="font-size:12px;font-weight:400;color:#858d99">{E(MN["asof"])} 기준 · 장중 스냅샷</span></div>'
                f'{tds}{inv}{cm}'
                f'<div style="font-size:11px;color:#858d99;margin:4px 0 18px">출처: {E(MN.get("src", ""))} · 실시간 아님</div>')
    mkt_text = (f"현재 시황 ({MN['asof']} 기준)\n" + "\n".join(f"- {a} {b} {c}" for a, b, c, _ in cells)
                + (f"\n시황 코멘트: {MN['comment']}" if MN.get("comment") else "") + "\n\n")

summ = [x["text"] if isinstance(x, dict) else x for x in D.get("summary", [])]
pts = "".join(f'<li style="margin:4px 0">{E(x)}</li>' for x in summ)

if fired:
    sig_html = (f'<div style="font-size:16px;font-weight:700;margin-bottom:8px">오늘의 시그널 '
                f'<span style="color:#c0392b">행동 {nr}</span> · <span style="color:#c76a00">주목 {no}</span></div>'
                f'<table style="width:100%;border-collapse:collapse;border-top:1px solid #e0e4ea">{"".join(rows)}</table>')
    subject = f"[Daily Brief] {short} 시그널 행동 {nr} · 주목 {no}"
else:
    sig_html = '<div style="font-size:15px;font-weight:700;margin-bottom:8px">오늘 발생한 시그널 없음</div>'
    subject = f"[Daily Brief] {short} 시그널 없음"

APP_NOTE = "자세한 사항은 어플리케이션에서 확인 바랍니다."
def _b(href, label, bg):
    return (f'<a href="{E(href)}" style="display:inline-block;background:{bg};color:#fff;text-decoration:none;padding:10px 16px;'
            f'border-radius:8px;font-weight:600;font-size:14px;margin:0 6px 6px 0">{label}</a>')
note_top = (f'<div style="font-size:13px;color:#142031;background:#fef0e7;border-radius:6px;padding:8px 10px;margin-bottom:14px">'
            f'{APP_NOTE}' + (f' <a href="{E(app)}" style="color:#d35f12;font-weight:600">앱 열기 →</a>' if app else "") + '</div>')
btn = ('<div style="margin:18px 0 4px">' + (f'<div style="font-size:13px;margin-bottom:8px">{APP_NOTE}</div>')
       + (_b(app, "앱에서 보기", "#f47321") if app else "") + (_b(url, "웹페이지(Claude 챗봇 포함)", "#555555") if url else "") + "</div>")

body = (f'<div style="font-family:\'Malgun Gothic\',\'Apple SD Gothic Neo\',sans-serif;max-width:680px;color:#142031">'
        f'<div style="background:#2d2d2d;color:#fff;padding:16px 18px;border-radius:10px 10px 0 0;border-bottom:3px solid #f47321">'
        f'<div style="font-size:18px;font-weight:700">Fund Sales Daily Brief</div>'
        f'<div style="font-size:13px;opacity:.8">{E(meta["label"])} · {E(meta["asof"])} · 팀 내부용</div></div>'
        f'<div style="border:1px solid #e0e4ea;border-top:0;border-radius:0 0 10px 10px;padding:16px 18px">'
        f'{note_top}{mkt_html}{sig_html}'
        f'<div style="font-size:16px;font-weight:700;margin:18px 0 6px">핵심 포인트</div>'
        f'<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.6">{pts}</ul>'
        f'{btn}'
        f'<div style="font-size:11px;color:#858d99;margin-top:14px">참고자료이며 특정 상품의 투자권유를 목적으로 하지 않습니다. 수치는 각 출처의 기준일 값입니다.</div>'
        f'</div></div>')

text = (f"Fund Sales Daily Brief {meta['label']}\n{APP_NOTE}" + (f" {app}" if app else "") + "\n\n" + mkt_text
        + (f"오늘의 시그널: 행동 {nr} · 주목 {no}\n" + "\n".join(
            f"- [{LV[s['level']][0]}] {s['name']}: {s['value']} / 영업 포인트: {s['action']}" for s in fired)
           if fired else "오늘 발생한 시그널 없음")
        + "\n\n핵심 포인트\n" + "\n".join("- " + x for x in summ)
        + (f"\n\n{APP_NOTE}" + (f"\n앱: {app}" if app else "") + (f"\n웹페이지(Claude 챗봇 포함): {url}" if url else ""))
        + "\n\n참고자료이며 특정 상품의 투자권유를 목적으로 하지 않습니다.")

out = {"to": to, "subject": subject, "html": body, "text": text, "fired": len(fired)}
json.dump(out, open(os.path.join(OUT, "email.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"to": to, "subject": subject, "fired": len(fired), "html_len": len(body)}, ensure_ascii=False))
