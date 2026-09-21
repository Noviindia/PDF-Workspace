// PDF Workspace Service Worker
const CACHE_NAME = 'pdf-workspace-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Let network requests proceed normally
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
