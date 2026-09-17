import { registerRoute } from 'workbox-routing';
import { CacheFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';

// Cache full-resolution plates on demand (CacheFirst, 1 year TTL)
registerRoute(
  ({ url }) => url.pathname.includes('/static/plates/full/'),
  new CacheFirst({
    cacheName: 'plates-full-cache',
    plugins: [
      new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 365 }),
      new CacheableResponsePlugin({ statuses: [0, 200] }),
    ],
  }),
);
