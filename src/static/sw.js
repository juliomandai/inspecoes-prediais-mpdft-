'use strict';

// ── Versão dos caches — incrementar ao publicar novas versões ─────────────────
const CACHE_PAGINAS  = 'inspecoes-paginas-v2';
const CACHE_ESTATICO = 'inspecoes-estatico-v2';
const CACHES_VALIDOS = [CACHE_PAGINAS, CACHE_ESTATICO];

// ── Install ────────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_ESTATICO)
      .then(cache => cache.addAll(['/offline/']))
      .catch(e => console.warn('[SW] pré-cache falhou:', e))
  );
});

// ── Activate ───────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys =>
        Promise.all(keys.filter(k => !CACHES_VALIDOS.includes(k)).map(k => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

// ── Fetch ──────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);

  // Não interceptar: não-GET, admin, media
  if (req.method !== 'GET') return;
  if (url.pathname.startsWith('/admin/')) return;
  if (url.pathname.startsWith('/media/')) return;

  // Recursos estáticos e CDN externos → cache primeiro
  if (url.pathname.startsWith('/static/') || url.origin !== self.location.origin) {
    event.respondWith(estrategiaCacheFirst(req, CACHE_ESTATICO));
    return;
  }

  // Páginas da aplicação → rede primeiro com fallback para cache
  event.respondWith(estrategiaNetworkFirst(req, CACHE_PAGINAS));
});

async function estrategiaCacheFirst(req, cacheName) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const cache = await caches.open(cacheName);
      cache.put(req, resp.clone());
    }
    return resp;
  } catch {
    return new Response('', { status: 503, statusText: 'Offline' });
  }
}

async function estrategiaNetworkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const resp = await fetch(req);
    if (resp.ok) cache.put(req, resp.clone());
    return resp;
  } catch {
    const cached = await cache.match(req);
    if (cached) return cached;
    // Página de fallback para navegação
    if (req.mode === 'navigate') {
      const pg = await caches.match('/offline/');
      if (pg) return pg;
    }
    return new Response(
      '<h1>Sem conexão</h1><p>Esta página não está disponível offline.</p>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}

// ── Background Sync ────────────────────────────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'sync-achados') {
    event.waitUntil(sincronizarAchadosPendentes());
  }
});

// ── IndexedDB helpers (contexto do SW) ────────────────────────────────────────
function abrirDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('inspecoes-offline', 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('achados_pendentes')) {
        const store = db.createObjectStore('achados_pendentes', { keyPath: 'id', autoIncrement: true });
        store.createIndex('sincronizado', 'sincronizado');
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

async function sincronizarAchadosPendentes() {
  let db;
  try { db = await abrirDB(); } catch { return; }

  const pendentes = await new Promise((resolve, reject) => {
    const tx = db.transaction('achados_pendentes', 'readonly');
    const req = tx.objectStore('achados_pendentes').index('sincronizado').getAll(0);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  for (const item of pendentes) {
    try {
      const resp = await fetch('/api/achados/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) {
        await new Promise(resolve => {
          const tx = db.transaction('achados_pendentes', 'readwrite');
          const store = tx.objectStore('achados_pendentes');
          const r = store.get(item.id);
          r.onsuccess = () => {
            const obj = r.result;
            if (obj) { obj.sincronizado = 1; store.put(obj); }
            resolve();
          };
          r.onerror = resolve;
        });
        const clients = await self.clients.matchAll({ includeUncontrolled: true });
        clients.forEach(c => c.postMessage({ tipo: 'achado_sincronizado', itemId: item.id }));
      }
    } catch { /* tenta no próximo sync */ }
  }
}
