const CACHE_NAME = 'wine-stock-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/manifest.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Bypass cache for Firebase APIs, Google Auth, and Gemini API calls
  if (
    url.hostname.includes('googleapis.com') ||
    url.hostname.includes('firebaseapp.com') ||
    url.hostname.includes('firebase.com') ||
    url.hostname.includes('identitytoolkit') ||
    url.pathname.includes('/__/auth/')
  ) {
    return; // Use default network fetching
  }

  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      if (cachedResponse) {
        // Fetch new version in background to update cache (stale-while-revalidate)
        fetch(e.request)
          .then((networkResponse) => {
            if (networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(e.request, networkResponse));
            }
          })
          .catch(() => {}); // Ignore network failure when offline
        return cachedResponse;
      }

      return fetch(e.request).then((response) => {
        // Cache static files (styles, scripts, images, fonts) dynamically
        if (
          response.status === 200 &&
          (e.request.destination === 'style' ||
           e.request.destination === 'script' ||
           e.request.destination === 'image' ||
           e.request.destination === 'font')
        ) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, responseClone));
        }
        return response;
      });
    })
  );
});
