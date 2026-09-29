/* SETU Roadside Mode service worker.
 *
 * Scope: /roadside only (registered by src/components/roadside/roadside-mode.tsx).
 * It keeps a copy of the Roadside page and the static assets it needs, so the
 * page reloads without a network at a checkpoint. It never touches /api or any
 * other origin, and it stores no personal data: only the public page and the
 * build's static files.
 */
const CACHE_PREFIX = "setu-roadside-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;
const PAGE_URL = "/roadside";
const ASSET_PATTERN = /(?:src|href)="(\/(?:_next\/static\/[^"]+|icon\.svg[^"]*|favicon\.ico[^"]*))"/g;

function isStaticAsset(url) {
  return url.pathname.startsWith("/_next/static/") || url.pathname === "/icon.svg" || url.pathname === "/favicon.ico";
}

async function precache() {
  const cache = await caches.open(CACHE_NAME);
  const response = await fetch(PAGE_URL, { cache: "reload", credentials: "same-origin" });
  if (!response.ok) return;
  await cache.put(PAGE_URL, response.clone());
  const html = await response.text();
  const assets = new Set();
  for (const match of html.matchAll(ASSET_PATTERN)) assets.add(match[1].replace(/&amp;/g, "&"));
  await Promise.all(
    [...assets].map(async (asset) => {
      try {
        const assetResponse = await fetch(asset, { credentials: "same-origin" });
        if (assetResponse.ok) await cache.put(asset, assetResponse);
      } catch {
        // A missing asset is fetched again on the next online visit.
      }
    }),
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function pageNetworkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(PAGE_URL, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(PAGE_URL);
    if (cached) return cached;
    throw error;
  }
}

async function assetCacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request, { ignoreSearch: false });
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api")) return;

  if (request.mode === "navigate" && url.pathname === PAGE_URL) {
    event.respondWith(pageNetworkFirst(request));
    return;
  }
  if (isStaticAsset(url)) {
    event.respondWith(assetCacheFirst(request));
  }
});
