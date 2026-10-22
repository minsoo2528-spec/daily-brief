/**
 * Fund Sales Daily Brief — 중계 서버 (Cloudflare Worker, 1단계 시제품)
 *
 * 앱(GitHub Pages)에서 Claude 챗봇과 '메일함 확인'(MMF 주문·펀드 관리)을 쓰기 위한 서버.
 * API 키·메일 권한은 이 서버의 비밀값(Secrets)에만 있고 앱에는 없다.
 *
 * 엔드포인트 (모두 POST, 헤더 X-Team-Code 필요)
 *   /ask   {messages:[{role,content}], tools?:[{name,description,input_schema}]}  → Claude 응답 그대로 {content, stop_reason}
 *   /mail  {kind:"mmf"|"notice"}  → 고정 검색어로 Gmail(읽기 전용)에서 최근 14일 메일만 {mails:[...]}
 *
 * 비밀값(Settings → Variables and Secrets, 종류 Secret)
 *   ANTHROPIC_API_KEY      Claude API 키
 *   TEAM_CODE              (선택) 팀 접속 코드. 비워 두면 접속 코드 없이 누구나 사용
 *   GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN   Gmail 읽기 전용(gmail.readonly)
 * 일반 변수(Text)
 *   ALLOWED_ORIGIN         https://minsoo2528-spec.github.io,null  (null = PC에서 직접 연 HTML 파일)
 *   CLAUDE_MODEL           (선택) 기본 claude-sonnet-5-5
 */

const QUERIES = {
  mmf: { q: 'MMF -subject:"Daily Brief" -subject:"앱 push 시험" newer_than:14d', re: /MMF/i },
  notice: { q: '공문 -subject:"Daily Brief" -subject:"앱 push 시험" newer_than:14d', re: /공문/ },
};
const MAX_BODY = 400 * 1024;     // 요청 본문 상한
const MAX_TOKENS = 2000;         // 답변 길이 상한
const MAX_THREADS = 10;

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = (env.ALLOWED_ORIGIN || "").split(",").map((s) => s.trim()).filter(Boolean);
    const okOrigin = allowed.includes(origin);
    const cors = {
      "Access-Control-Allow-Origin": okOrigin ? origin : (allowed[0] || ""),
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Team-Code",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    };
    const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { ...cors, "Content-Type": "application/json; charset=utf-8" } });

    if (request.method === "OPTIONS") return new Response(null, { status: okOrigin ? 204 : 403, headers: cors });
    if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
    if (!okOrigin) return json({ error: "origin_not_allowed" }, 403);
    // TEAM_CODE를 설정하면 접속 코드가 필요하고, 비워 두면 앱·HTML을 가진 누구나 쓸 수 있다(사용자 결정 2026-10-22, 발표 시연용).
    const raw = await request.text();
    if (raw.length > MAX_BODY) return json({ error: "too_large" }, 413);
    let body;
    try { body = JSON.parse(raw || "{}"); } catch { return json({ error: "bad_json" }, 400); }
    const code = request.headers.get("X-Team-Code") || String(body.code || "");
    if (env.TEAM_CODE && !safeEqual(code, env.TEAM_CODE)) return json({ error: "bad_team_code" }, 401);

    const path = String(body.path || new URL(request.url).pathname).replace(/\/+$/, "");
    try {
      if (path === "/ask") return json(await ask(body, env));
      if (path === "/mail") return json(await mail(body, env));
      return json({ error: "not_found" }, 404);
    } catch (e) {
      return json({ error: e.code || "upstream_error", message: String(e.message || e).slice(0, 300) }, e.status || 502);
    }
  },
};

function safeEqual(a, b) {
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let d = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) d |= (x[i] || 0) ^ (y[i] || 0);
  return d === 0;
}

function fail(code, message, status = 502) { const e = new Error(message); e.code = code; e.status = status; return e; }

// ── Claude ──
async function ask(body, env) {
  if (!env.ANTHROPIC_API_KEY) throw fail("not_configured", "ANTHROPIC_API_KEY 없음", 500);
  const msgs = Array.isArray(body.messages) ? body.messages : null;
  if (!msgs || !msgs.length) throw fail("bad_request", "messages 없음", 400);
  for (const m of msgs) {
    if (!m || (m.role !== "user" && m.role !== "assistant")) throw fail("bad_request", "role은 user/assistant만", 400);
  }
  const req = { model: env.CLAUDE_MODEL || "claude-sonnet-5-5", max_tokens: MAX_TOKENS, messages: msgs };
  if (Array.isArray(body.tools) && body.tools.length) {
    req.tools = body.tools.slice(0, 8).map((t) => ({ name: String(t.name), description: String(t.description || ""), input_schema: t.input_schema || { type: "object", properties: {} } }));
  }
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  const out = await r.json().catch(() => ({}));
  if (!r.ok) {
    const code = r.status === 429 ? "rate_limited" : r.status === 401 ? "bad_api_key" : "upstream_error";
    throw fail(code, (out.error && out.error.message) || "Claude API " + r.status, r.status === 429 ? 429 : 502);
  }
  return { content: out.content || [], stop_reason: out.stop_reason || "" };
}

// ── Gmail (읽기 전용, 고정 검색어만) ──
async function gmailToken(env) {
  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET || !env.GOOGLE_REFRESH_TOKEN) throw fail("not_configured", "Gmail 비밀값 없음", 500);
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, refresh_token: env.GOOGLE_REFRESH_TOKEN, grant_type: "refresh_token" }),
  });
  const t = await r.json().catch(() => ({}));
  if (!r.ok || !t.access_token) throw fail("needs_reauth", "Gmail 인증 만료: " + (t.error || r.status), 502);
  return t.access_token;
}

async function mail(body, env) {
  const Q = QUERIES[body.kind];
  if (!Q) throw fail("bad_request", "kind는 mmf 또는 notice", 400);
  const tok = await gmailToken(env);
  const g = async (u) => {
    const r = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/" + u, { headers: { authorization: "Bearer " + tok } });
    if (!r.ok) throw fail(r.status === 401 ? "needs_reauth" : "upstream_error", "Gmail " + r.status);
    return r.json();
  };
  const list = await g("threads?maxResults=" + MAX_THREADS + "&q=" + encodeURIComponent(Q.q));
  const threads = (list.threads || []).slice(0, MAX_THREADS);
  const mails = [];
  for (const t of threads) {
    const th = await g("threads/" + encodeURIComponent(t.id) + "?format=full");
    for (const m of th.messages || []) {
      if ((m.labelIds || []).includes("DRAFT")) continue;
      const h = Object.fromEntries((m.payload && m.payload.headers || []).map((x) => [x.name.toLowerCase(), x.value]));
      const text = bodyText(m.payload);
      const subject = h.subject || "";
      if (!Q.re.test(subject + " " + text)) continue;
      mails.push({ id: m.id, date: new Date(Number(m.internalDate)).toISOString(), sender: h.from || "", subject, plaintextBody: text.slice(0, 20000), labelIds: m.labelIds || [] });
    }
  }
  return { mails };
}

function b64url(s) {
  const bin = atob(String(s || "").replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder("utf-8").decode(bytes);
}
function bodyText(p) {
  if (!p) return "";
  let plain = "", html = "";
  (function walk(x) {
    if (!x) return;
    if (x.mimeType === "text/plain" && x.body && x.body.data && !plain) plain = b64url(x.body.data);
    else if (x.mimeType === "text/html" && x.body && x.body.data && !html) html = b64url(x.body.data);
    (x.parts || []).forEach(walk);
  })(p);
  if (plain) return plain;
  return html.replace(/<style[\s\S]*?<\/style>/gi, "").replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|li|tr)>/gi, "\n").replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/\n{3,}/g, "\n\n").trim();
}
