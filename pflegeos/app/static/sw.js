/**
 * PflegeOS Service Worker — Offline-Unterstützung für mobile Pflegekräfte.
 *
 * Strategie:
 *  - Shell (CSS, JS, Fonts): Cache-First
 *  - API / dynamische Seiten: Network-First mit Offline-Fallback
 *  - Fotos / Uploads: Network-Only (zu groß für Cache)
 */

const CACHE_NAME = 'pflegeos-v1';
const OFFLINE_URL = '/offline';

// Statische Assets, die immer gecacht werden sollen
const STATIC_ASSETS = [
  '/offline',
  '/static/manifest.json',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
];

// ── Install ───────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.warn('[SW] Cache-Vorladung teilweise fehlgeschlagen:', err);
      });
    })
  );
  self.skipWaiting();
});

// ── Activate ──────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME)
          .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Nicht abfangen: andere Origins, POST/PUT/DELETE, Uploads
  if (
    url.origin !== location.origin ||
    request.method !== 'GET' ||
    url.pathname.startsWith('/uploads/') ||
    url.pathname.startsWith('/static/icons/')
  ) {
    return;
  }

  // CDN-Assets: Cache-First
  if (url.hostname.includes('cdn.jsdelivr.net') || url.hostname.includes('unpkg.com')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Statische App-Assets: Cache-First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Alle anderen GET-Anfragen: Network-First mit Offline-Fallback
  event.respondWith(networkFirst(request));
});

// ── Strategien ────────────────────────────────────────────────────────────────

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Nicht verfügbar', { status: 503 });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // Offline-Fallback nur für navigations-Anfragen
    if (request.mode === 'navigate') {
      const offline = await caches.match(OFFLINE_URL);
      if (offline) return offline;
    }
    return new Response('Offline', { status: 503 });
  }
}

// ── Background Sync (zukünftig für Offline-Formulare) ─────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'sync-reports') {
    event.waitUntil(syncPendingReports());
  }
});

async function syncPendingReports() {
  // Placeholder — wird in einem späteren Release implementiert
  console.log('[SW] Background Sync: Berichte werden synchronisiert...');
}
