// Cache-first service worker: the app is one self-contained page, so one cache entry makes it work offline.
// Bump VERSION whenever index.html changes so phones pick up the new build.
const VERSION = "bj-v6";
const FILES = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png", "./icon-180.png",
  "./fonts/archivo-latin.woff2", "./fonts/ibm-plex-mono-400-latin.woff2", "./fonts/ibm-plex-mono-600-latin.woff2"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(VERSION).then((c) => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", (e) => {
  // The sync API must always hit the server, never this cache.
  if (e.request.method !== "GET" || new URL(e.request.url).pathname.includes("/api/")) return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => {
    const net = fetch(e.request).then((res) => { if (res.ok && new URL(e.request.url).origin === location.origin) caches.open(VERSION).then((c) => c.put(e.request, res.clone())); return res; }).catch(() => hit);
    return hit || net;
  }));
});
