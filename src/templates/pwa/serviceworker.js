{% load static %}
/*
 * VMS service worker.
 * Static assets: cache-first. Pages: network-only with an offline fallback,
 * so authenticated financial data is never served stale from cache.
 */
const CACHE_NAME = 'vms-v1';
const OFFLINE_URL = '/offline/';

const PRECACHE_URLS = [
    OFFLINE_URL,
    "{% static 'pwa/icon-192.png' %}",
    "{% static 'pwa/icon-512.png' %}",
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);

    // Page navigations: network-only, offline fallback. Never cache HTML.
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(() => caches.match(OFFLINE_URL))
        );
        return;
    }

    // Same-origin static assets: cache-first, populate on miss.
    if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then((cached) => {
                if (cached) return cached;
                return fetch(request).then((response) => {
                    if (response.ok) {
                        const copy = response.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                    }
                    return response;
                });
            })
        );
    }
    // Everything else (media, API, cross-origin CDNs) goes straight to the network.
});
