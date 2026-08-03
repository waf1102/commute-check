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

	// Network-first caching strategy for /weather/forecast API calls
	if (url.pathname.includes('/weather/forecast')) {
		event.respondWith(
			fetch(event.request)
				.then((response) => {
					if (response.status === 200) {
						const copy = response.clone();
						caches.open(CACHE).then((cache) => cache.put(event.request, copy));
					}
					return response;
				})
				.catch(() => caches.match(event.request).then((cached) => cached || Response.error()))
		);
		return;
	}

	// Cache-first strategy for static app assets
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(
			caches.match(event.request).then((cached) => cached || fetch(event.request))
		);
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
	const options: NotificationOptions = {
		body: data.body || 'Check your commute weather decision.',
		icon: '/icons/icon-192.png',
		badge: '/icons/icon-192.png',
		data: { url: data.url || '/' }
	};
	event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click listener
self.addEventListener('notificationclick', (event: NotificationEvent) => {
	event.notification.close();
	const urlToOpen = event.notification.data?.url || '/';
	const targetUrl = new URL(urlToOpen, self.location.origin).href;

	event.waitUntil(
		self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
			for (const client of clientList) {
				if (client.url === targetUrl && 'focus' in client) {
					return client.focus();
				}
			}
			if (self.clients.openWindow) {
				return self.clients.openWindow(targetUrl);
			}
		})
	);
});
