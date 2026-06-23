'use strict';

// ── Versão dos caches — incrementar ao publicar novas versões ─────────────────
const CACHE_PAGINAS  = 'inspecoes-paginas-v7';
const CACHE_ESTATICO = 'inspecoes-estatico-v7';
// Fotos de achados pré-cacheadas pela preparação para campo (ver pwa.js).
const CACHE_FOTOS    = 'inspecoes-fotos-v7';
const CACHES_VALIDOS = [CACHE_PAGINAS, CACHE_ESTATICO, CACHE_FOTOS];

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

  // Não interceptar: não-GET, admin
  if (req.method !== 'GET') return;
  if (url.pathname.startsWith('/admin/')) return;

  // Fotos (/media): servir do cache se a preparação para campo já as baixou.
  // Não popula automaticamente — apenas a preparação coloca fotos no cache.
  if (url.pathname.startsWith('/media/')) {
    event.respondWith(estrategiaFotoOffline(req));
    return;
  }

  // Recursos estáticos e CDN externos → cache primeiro
  if (url.pathname.startsWith('/static/') || url.origin !== self.location.origin) {
    event.respondWith(estrategiaCacheFirst(req, CACHE_ESTATICO));
    return;
  }

  // Páginas da aplicação → rede primeiro com fallback para cache
  event.respondWith(estrategiaNetworkFirst(req, CACHE_PAGINAS));
});

// Placeholder SVG para fotos não disponíveis offline.
const FOTO_PLACEHOLDER =
  '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">' +
  '<rect width="100" height="100" fill="#e9ecef"/>' +
  '<text x="50" y="46" font-size="9" fill="#6c757d" text-anchor="middle">foto</text>' +
  '<text x="50" y="58" font-size="9" fill="#6c757d" text-anchor="middle">offline</text></svg>';

async function estrategiaFotoOffline(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    // Online: serve da rede sem cachear (a preparação cuida do que precisa offline).
    return await fetch(req);
  } catch {
    return new Response(FOTO_PLACEHOLDER, {
      headers: { 'Content-Type': 'image/svg+xml' },
    });
  }
}

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
    const req = indexedDB.open('inspecoes-offline', 2);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('achados_pendentes')) {
        const s = db.createObjectStore('achados_pendentes', { keyPath: 'id', autoIncrement: true });
        s.createIndex('sincronizado', 'sincronizado');
      }
      if (!db.objectStoreNames.contains('achados_edicao_pendentes')) {
        const s = db.createObjectStore('achados_edicao_pendentes', { keyPath: 'id', autoIncrement: true });
        s.createIndex('sincronizado', 'sincronizado');
        s.createIndex('achado_pk', 'achado_pk');
      }
      if (!db.objectStoreNames.contains('achados_preparados')) {
        const s = db.createObjectStore('achados_preparados', { keyPath: 'achado_pk' });
        s.createIndex('esp_pk', 'esp_pk');
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

async function sincronizarAchadosPendentes() {
  let db;
  try { db = await abrirDB(); } catch { return; }

  // Sincronizar criações
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
          tx.objectStore('achados_pendentes').delete(item.id);
          tx.oncomplete = resolve;
          tx.onerror = resolve;
        });
        const clients = await self.clients.matchAll({ includeUncontrolled: true });
        clients.forEach(c => c.postMessage({ tipo: 'achado_sincronizado', itemId: item.id }));
      }
    } catch { /* tenta no próximo sync */ }
  }

  // Sincronizar edições
  const edicoes = await new Promise((resolve, reject) => {
    const tx = db.transaction('achados_edicao_pendentes', 'readonly');
    const req = tx.objectStore('achados_edicao_pendentes').index('sincronizado').getAll(0);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  for (const item of edicoes) {
    try {
      const resp = await fetch('/api/achados/' + item.achado_pk + '/sincronizar-edicao/', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) {
        await new Promise(resolve => {
          const tx = db.transaction('achados_edicao_pendentes', 'readwrite');
          tx.objectStore('achados_edicao_pendentes').delete(item.id);
          tx.oncomplete = resolve;
          tx.onerror = resolve;
        });
        const clients = await self.clients.matchAll({ includeUncontrolled: true });
        clients.forEach(c => c.postMessage({ tipo: 'edicao_sincronizada', itemId: item.id }));
      }
    } catch { /* tenta no próximo sync */ }
  }
}
