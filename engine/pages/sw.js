/* Daily Brief 앱: 온라인이면 항상 최신 페이지, 오프라인이면 마지막으로 받은 페이지를 보여준다. */
var CACHE = "daily-brief-v1";
var SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png"];
self.addEventListener("install", function (e) { e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); })); });
self.addEventListener("activate", function (e) { e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); })); });
self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(fetch(req, { cache: "no-store" }).then(function (res) {
    var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); return res;
  }).catch(function () { return caches.match(req).then(function (m) { return m || caches.match("./index.html"); }); }));
});
