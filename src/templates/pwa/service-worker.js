/*
 * Hoza Investment — PWA Service Worker
 *
 * Served from "/service-worker.js" (root scope) instead of "/static/pwa/..."
 * so it can control navigation to every page on the site — a service worker
 * served under /static/ could only ever control /static/ requests, since a
 * service worker's default max scope is the directory it's served from.
 *
 * SECURITY: this file intentionally caches almost nothing. Only the assets
 * listed in PRECACHE_URLS (icons, manifest, the offline fallback page) and
 * same-origin GET requests under /static/ are ever written to the cache.
 * Every other request — every finance, payment, client, vehicle, expense,
 * report, admin, and API page — is always served from the network and is
 * never read from or written to any cache. See isSafeToCache() below.
 */

const CACHE_VERSION = 'v1';
const CACHE_NAME = 'hoza-pwa-' + CACHE_VERSION;

const OFFLINE_URL = '/static/pwa/offline.html';

const PRECACHE_URLS = [
    OFFLINE_URL,
    '/static/pwa/manifest.json',
    '/static/pwa/icons/icon-72x72.png',
    '/static/pwa/icons/icon-96x96.png',
    '/static/pwa/icons/icon-128x128.png',
    '/static/pwa/icons/icon-144x144.png',
    '/static/pwa/icons/icon-152x152.png',
    '/static/pwa/icons/icon-192x192.png',
    '/static/pwa/icons/icon-384x384.png',
    '/static/pwa/icons/icon-512x512.png',
    '/static/pwa/icons/apple-touch-icon.png',
];

// Explicit deny-list of sensitive/authenticated path prefixes. Kept as a
// second, human-readable line of defense even though isSafeToCache() below
// already defaults to "deny" for everything outside /static/ — if either
// check disagrees, the fetch handler treats the request as unsafe.
const SENSITIVE_PATH_PREFIXES = [
    '/admin/',
    '/finance/',
    '/payments/',
    '/clients/',
    '/vehicles/',
    '/expenses/',
    '/reports/',
    '/ledger/',
    '/accounts/',
    '/api/',
    '/payroll/',
    '/repossessions/',
    '/auctions/',
    '/insurance/',
    '/documents/',
    '/audit/',
    '/permissions/',
    '/notifications/',
    '/auth/',
    '/media/',
];

function isSensitivePath(pathname) {
    return SENSITIVE_PATH_PREFIXES.some(function (prefix) {
        return pathname.startsWith(prefix);
    });
}

/**
 * Whitelist, not a blacklist: only these exact kinds of requests are ever
 * eligible for caching. Everything else — including paths nobody thought to
 * add to SENSITIVE_PATH_PREFIXES — is denied by default.
 */
function isSafeToCache(url) {
    const path = url.pathname;

    if (isSensitivePath(path)) {
        return false;
    }
    if (path === '/service-worker.js') {
        return false; // the worker script itself is handled by the browser, not this cache
    }
    // Static assets collected by Django's staticfiles app: CSS, JS, images, icons.
    if (path.startsWith('/static/')) {
        return true;
    }
    return false;
}

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function (cache) {
                return cache.addAll(PRECACHE_URLS);
            })
            .then(function () {
                return self.skipWaiting();
            })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys()
            .then(function (keys) {
                return Promise.all(
                    keys
                        .filter(function (key) { return key !== CACHE_NAME; })
                        .map(function (key) { return caches.delete(key); })
                );
            })
            .then(function () {
                return self.clients.claim();
            })
    );
});

self.addEventListener('fetch', function (event) {
    const request = event.request;

    // Never intercept mutations. Let POST/PUT/PATCH/DELETE go straight to
    // the network exactly as if this service worker didn't exist.
    if (request.method !== 'GET') {
        return;
    }

    const url = new URL(request.url);

    // Only ever handle same-origin requests; leave third-party requests
    // (CDNs for Tailwind/Font Awesome/Alpine.js, etc.) untouched.
    if (url.origin !== self.location.origin) {
        return;
    }

    // Full-page navigations: network-first, offline fallback on failure.
    // The fetched page is deliberately never written to any cache, so
    // authenticated/sensitive pages can never end up stored on the device.
    if (request.mode === 'navigate') {
        event.respondWith(networkFirstNavigation(request));
        return;
    }

    // Safe static sub-resources (CSS/JS/images/icons): cache-first for speed.
    if (isSafeToCache(url)) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Everything else (including any sensitive-module fetch/XHR call):
    // fall through and let the browser handle it against the network
    // directly. Nothing here is read from or written to the cache.
});

async function networkFirstNavigation(request) {
    try {
        const response = await fetch(request);
        return response;
    } catch (err) {
        const cache = await caches.open(CACHE_NAME);
        const offlinePage = await cache.match(OFFLINE_URL);
        if (offlinePage) {
            return offlinePage;
        }
        return new Response(
            '<h1>Offline</h1><p>Hoza Investment is unavailable right now.</p>',
            { status: 503, headers: { 'Content-Type': 'text/html' } }
        );
    }
}

async function cacheFirst(request) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) {
        return cached;
    }
    try {
        const response = await fetch(request);
        if (response && response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        const fallback = await cache.match(request);
        if (fallback) {
            return fallback;
        }
        throw err;
    }
}
