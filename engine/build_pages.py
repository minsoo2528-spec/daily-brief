"""GitHub Pages(앱)용 파일 만들기 — make_brief.py 다음에 실행.

python3 build_pages.py <엔진폴더> <출력폴더>
  out/web.html + pages/(manifest·아이콘·sw.js·robots.txt) → <출력폴더>/index.html 등
웹페이지 본문은 claude.ai 판과 같고, 앱 설치용 head·설치 안내만 더한다.
claude.ai 밖이라 'Claude 답변'은 자동으로 숨고 '빠른 계산'만 작동한다.
"""
import os, shutil, sys
ROOT = sys.argv[1]; DST = sys.argv[2]
os.makedirs(DST, exist_ok=True)
body = open(os.path.join(ROOT, "out", "web.html"), encoding="utf-8").read()
HEAD = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#1b2a44">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Daily Brief">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>body{margin:0}.instbar{position:fixed;left:12px;bottom:12px;z-index:39;display:flex;gap:8px;align-items:center;background:#fff;color:#142031;border:1px solid #e0e4ea;border-radius:12px;padding:8px 10px;box-shadow:0 4px 16px rgba(0,0,0,.15);font:500 13px system-ui,sans-serif;max-width:calc(100vw - 150px)}.instbar[hidden]{display:none}.instbar button{border:0;border-radius:8px;padding:6px 10px;font:600 13px system-ui,sans-serif;cursor:pointer}.instbar .go{background:#1b2a44;color:#fff}.instbar .x{background:transparent;color:#858d99}@media print{.instbar{display:none}}</style>
</head><body>
"""
TAIL = """
<div class="instbar" id="instbar" hidden><span id="insttxt">앱으로 설치하면 홈 화면에서 바로 열 수 있습니다</span><button type="button" class="go" id="instgo">앱 설치</button><button type="button" class="x" id="instx" aria-label="닫기">✕</button></div>
<script>
(function () {
  if ("serviceWorker" in navigator) { window.addEventListener("load", function () { navigator.serviceWorker.register("sw.js").catch(function () {}); }); }
  var bar = document.getElementById("instbar"), go = document.getElementById("instgo"), txt = document.getElementById("insttxt"), evt = null;
  var standalone = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone;
  var dismissed = false; try { dismissed = localStorage.getItem("inst-x") === "1"; } catch (e) {}
  if (standalone || dismissed) return;
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); evt = e; bar.hidden = false; });
  go.addEventListener("click", function () { if (!evt) return; evt.prompt(); evt.userChoice.finally(function () { evt = null; bar.hidden = true; }); });
  document.getElementById("instx").addEventListener("click", function () { bar.hidden = true; try { localStorage.setItem("inst-x", "1"); } catch (e) {} });
  if (/iphone|ipad|ipod/i.test(navigator.userAgent)) { txt.textContent = "공유 버튼 → '홈 화면에 추가'로 앱처럼 설치할 수 있습니다"; go.hidden = true; bar.hidden = false; }
  window.addEventListener("appinstalled", function () { bar.hidden = true; });
})();
</script>
</body></html>
"""
open(os.path.join(DST, "index.html"), "w", encoding="utf-8").write(HEAD + body + TAIL)
src = os.path.join(ROOT, "pages")
for f in os.listdir(src):
    shutil.copy(os.path.join(src, f), os.path.join(DST, f))
open(os.path.join(DST, ".nojekyll"), "w").close()
print("ok", sorted(os.listdir(DST)))
