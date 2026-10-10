const CACHE_NAME = "cradleecho-v1";
const PRECACHE_URLS = ["/offline", "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png"];

function shouldCacheRequest(request) {
  const url = new URL(request.url);

  // Never cache cross-origin requests (daemon is different port/origin)
  if (url.origin !== location.origin) return false;

  // Never cache video feed, WebSocket, API routes, or POST requests
  const pathname = url.pathname;
  if (pathname.startsWith("/video_feed")) return false;
  if (pathname.startsWith("/ws/")) return false;
  if (pathname.startsWith("/api/")) return false;
  if (request.method !== "GET") return false;

  return true;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  if (!shouldCacheRequest(request)) {
    return;
  }

  // Navigation requests: network-first with offline fallback
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/offline")),
    );
    return;
  }

  // Immutable build assets and icons only: cache-first. Everything else (RSC payloads, data) goes to the network.
  const { pathname } = new URL(request.url);
  if (!pathname.startsWith("/_next/static/") && !PRECACHE_URLS.includes(pathname)) return;
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      });
    }),
  );
});
