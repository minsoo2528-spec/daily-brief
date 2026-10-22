/**
 * Fund Sales Daily Brief — 발표 시연용 중계 서버 (Google Apps Script 웹앱)
 * 앱·HTML에서 Claude 챗봇과 '메일함 확인'(MMF 주문·펀드 관리)을 쓰게 한다.
 *  - Claude API 키는 스크립트 속성 ANTHROPIC_API_KEY 에만 둔다(코드·앱에 넣지 않음).
 *  - Gmail은 읽기 전용(gmail.readonly)으로, 정해진 검색어('MMF', '공문')의 최근 14일 메일만 읽는다.
 *  - 스크립트 속성 TEAM_CODE를 넣으면 접속 코드가 필요하고, 비워 두면 누구나 사용(사용자 결정 2026-10-22).
 * 요청: POST(text/plain) 본문 JSON {path:"/ask"|"/mail", ...}. 응답 JSON, 실패 시 {error, message}.
 */
var QUERIES = {
  mmf: { q: 'MMF -subject:"Daily Brief" -subject:"앱 push 시험" newer_than:14d', re: /MMF/i },
  notice: { q: '공문 -subject:"Daily Brief" -subject:"앱 push 시험" newer_than:14d', re: /공문/ }
};
var MAX_BODY = 400 * 1024, MAX_TOKENS = 2000, MAX_THREADS = 10;

function doGet() { return out_({ ok: true, service: "daily-brief-demo" }); }

function doPost(e) {
  try {
    var raw = (e && e.postData && e.postData.contents) || "{}";
    if (raw.length > MAX_BODY) return out_({ error: "too_large" });
    var body = JSON.parse(raw);
    var P = PropertiesService.getScriptProperties();
    var team = P.getProperty("TEAM_CODE");
    if (team && String(body.code || "") !== team) return out_({ error: "bad_team_code" });
    if (body.path === "/ask") return out_(ask_(body, P));
    if (body.path === "/mail") return out_(mail_(body));
    return out_({ error: "not_found" });
  } catch (err) {
    return out_({ error: err.code || "upstream_error", message: String(err.message || err).slice(0, 300) });
  }
}

function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function fail_(code, msg) { var e = new Error(msg); e.code = code; return e; }

function ask_(body, P) {
  var key = P.getProperty("ANTHROPIC_API_KEY");
  if (!key) throw fail_("not_configured", "ANTHROPIC_API_KEY 없음");
  var msgs = body.messages;
  if (!msgs || !msgs.length) throw fail_("bad_request", "messages 없음");
  for (var i = 0; i < msgs.length; i++) if (msgs[i].role !== "user" && msgs[i].role !== "assistant") throw fail_("bad_request", "role은 user/assistant만");
  var req = { model: P.getProperty("CLAUDE_MODEL") || "claude-sonnet-5-5", max_tokens: MAX_TOKENS, messages: msgs };
  if (body.tools && body.tools.length) req.tools = body.tools.slice(0, 8).map(function (t) {
    return { name: String(t.name), description: String(t.description || ""), input_schema: t.input_schema || { type: "object", properties: {} } };
  });
  var r = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {
    method: "post", contentType: "application/json", muteHttpExceptions: true,
    headers: { "x-api-key": key, "anthropic-version": "2023-06-01" }, payload: JSON.stringify(req)
  });
  var st = r.getResponseCode(), j = {};
  try { j = JSON.parse(r.getContentText()); } catch (x) {}
  if (st !== 200) throw fail_(st === 429 ? "rate_limited" : st === 401 ? "bad_api_key" : "upstream_error", (j.error && j.error.message) || ("Claude API " + st));
  return { content: j.content || [], stop_reason: j.stop_reason || "" };
}

function mail_(body) {
  var Q = QUERIES[body.kind];
  if (!Q) throw fail_("bad_request", "kind는 mmf 또는 notice");
  var list = Gmail.Users.Threads.list("me", { q: Q.q, maxResults: MAX_THREADS });
  var threads = (list.threads || []).slice(0, MAX_THREADS), mails = [];
  threads.forEach(function (t) {
    var th = Gmail.Users.Threads.get("me", t.id, { format: "full" });
    (th.messages || []).forEach(function (m) {
      if ((m.labelIds || []).indexOf("DRAFT") >= 0) return;
      var h = {}; ((m.payload && m.payload.headers) || []).forEach(function (x) { h[x.name.toLowerCase()] = x.value; });
      var text = bodyText_(m.payload), subject = h.subject || "";
      if (!Q.re.test(subject + " " + text)) return;
      mails.push({ id: m.id, date: new Date(Number(m.internalDate)).toISOString(), sender: h.from || "", subject: subject,
        plaintextBody: text.slice(0, 20000), labelIds: m.labelIds || [] });
    });
  });
  return { mails: mails };
}

function dec_(d) {
  if (!d) return "";
  var bytes = (typeof d === "string") ? Utilities.base64DecodeWebSafe(d) : d;
  return Utilities.newBlob(bytes).getDataAsString("UTF-8");
}
function bodyText_(p) {
  var plain = "", html = "";
  (function walk(x) {
    if (!x) return;
    if (x.mimeType === "text/plain" && x.body && x.body.data && !plain) plain = dec_(x.body.data);
    else if (x.mimeType === "text/html" && x.body && x.body.data && !html) html = dec_(x.body.data);
    (x.parts || []).forEach(walk);
  })(p);
  if (plain) return plain;
  return html.replace(/<style[\s\S]*?<\/style>/gi, "").replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|li|tr)>/gi, "\n").replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/\n{3,}/g, "\n\n").trim();
}
