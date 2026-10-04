/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

declare const self: ServiceWorkerGlobalScope;

const CACHE = `cache-${version}`;
const ASSETS = [...build, ...files];

self.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await cache.addAll(ASSETS);
      await self.skipWaiting();
    })
  );
});

self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then(async (keys) => {
      for (const key of keys) {
        if (key !== CACHE) await caches.delete(key);
      }
      await self.clients.claim();
    })
  );
});

self.addEventListener('fetch', (event: FetchEvent) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Do not cache personal forecasts across accounts or serve them as current offline.
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;

  // Cache-first strategy for static app assets
  if (ASSETS.includes(url.pathname)) {
    event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
    return;
  }
});

// Push notification listener
self.addEventListener('push', (event: PushEvent) => {
  let data: any = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data = { body: event.data.text() };
    }
  }
  const title = data.title || 'Commute Check Update';
  const urlToOpen =
    data.url || (data.has_route_hazard ? '/#route-visualizer' : '/#route-visualizer');
  const options: NotificationOptions = {
    body: data.body || 'Check your commute weather decision.',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: {
      url: urlToOpen,
      has_route_hazard: Boolean(data.has_route_hazard),
      hazard_count: data.hazard_count ?? 0,
      primary_hazard_location: data.primary_hazard_location ?? ''
    }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click listener
self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();
  let urlToOpen = event.notification.data?.url || '/#route-visualizer';
  if (urlToOpen === '/dashboard' || urlToOpen === '/') {
    urlToOpen = '/#route-visualizer';
  }
  const targetUrl = new URL(urlToOpen, self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        const clientUrl = new URL(client.url);
        if (
          clientUrl.origin === self.location.origin &&
          (clientUrl.pathname === '/' || clientUrl.pathname === '/dashboard')
        ) {
          if ('navigate' in client && typeof (client as any).navigate === 'function') {
            (client as any).navigate(targetUrl);
          }
          if ('focus' in client) {
            return client.focus();
          }
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});
