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
    links = "".join(f' <a href="{E(u)}" style="color:#2a78d6">원문</a>' for u in s.get("links", []))
    rows.append(
        f'<tr><td style="padding:12px 14px;border-bottom:1px solid #e0e4ea;vertical-align:top">'
        f'<span style="display:inline-block;font-size:12px;font-weight:700;color:{c};background:{bg};border-radius:4px;padding:1px 7px">{t}</span>'
        f'<span style="font-size:12px;color:#858d99;margin-left:6px">{E(s["sec"])}</span>'
        f'<div style="font-size:15px;font-weight:700;color:#142031;margin:6px 0 2px">{E(s["name"])}</div>'
        f'<div style="font-size:14px;color:#142031">{E(s["value"])}</div>'
        + (f'<ul style="margin:6px 0 0;padding-left:18px;font-size:13px;color:#4c5666">{items}</ul>' if items else "")
        + f'<div style="font-size:13px;background:#eef1f5;border-radius:6px;padding:7px 10px;margin-top:8px"><b>영업 포인트</b> {E(s["action"])}{links}</div>'
        f'<div style="font-size:11px;color:#858d99;margin-top:5px">기준: {E(s["rule"])} · 출처: {E(s["src"])}</div></td></tr>'
    )

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

btn = (f'<div style="margin:18px 0 4px"><a href="{E(url)}" style="display:inline-block;background:#1b2a44;color:#fff;'
       f'text-decoration:none;padding:10px 16px;border-radius:8px;font-weight:600;font-size:14px">웹페이지 전체 보기</a></div>') if url else ""

body = (f'<div style="font-family:\'Malgun Gothic\',\'Apple SD Gothic Neo\',sans-serif;max-width:680px;color:#142031">'
        f'<div style="background:#1b2a44;color:#fff;padding:16px 18px;border-radius:10px 10px 0 0">'
        f'<div style="font-size:18px;font-weight:700">Wholesale Daily Brief</div>'
        f'<div style="font-size:13px;opacity:.8">{E(meta["label"])} · {E(meta["asof"])} · 팀 내부용</div></div>'
        f'<div style="border:1px solid #e0e4ea;border-top:0;border-radius:0 0 10px 10px;padding:16px 18px">'
        f'{sig_html}'
        f'<div style="font-size:16px;font-weight:700;margin:18px 0 6px">핵심 포인트</div>'
        f'<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.6">{pts}</ul>'
        f'{btn}'
        f'<div style="font-size:11px;color:#858d99;margin-top:14px">참고자료이며 특정 상품의 투자권유를 목적으로 하지 않습니다. 수치는 각 출처의 기준일 값입니다.</div>'
        f'</div></div>')

text = (f"Wholesale Daily Brief {meta['label']}\n\n"
        + (f"오늘의 시그널: 행동 {nr} · 주목 {no}\n" + "\n".join(
            f"- [{LV[s['level']][0]}] {s['name']}: {s['value']} / 영업 포인트: {s['action']}" for s in fired)
           if fired else "오늘 발생한 시그널 없음")
        + "\n\n핵심 포인트\n" + "\n".join("- " + x for x in summ)
        + (f"\n\n웹페이지: {url}" if url else "")
        + "\n\n참고자료이며 특정 상품의 투자권유를 목적으로 하지 않습니다.")

out = {"to": to, "subject": subject, "html": body, "text": text, "fired": len(fired)}
json.dump(out, open(os.path.join(OUT, "email.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"to": to, "subject": subject, "fired": len(fired), "html_len": len(body)}, ensure_ascii=False))
