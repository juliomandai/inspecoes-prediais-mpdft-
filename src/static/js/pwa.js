'use strict';

// ── Registro do Service Worker ─────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(reg => {
        // Ouvir mensagens do SW (achado sincronizado via background sync)
        navigator.serviceWorker.addEventListener('message', event => {
          if (event.data && event.data.tipo === 'achado_sincronizado') {
            atualizarBannerOffline();
          }
        });
      })
      .catch(err => console.warn('[PWA] Falha ao registrar SW:', err));
  });
}

// ── IndexedDB ──────────────────────────────────────────────────────────────────
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

async function salvarAchadoOffline(dados) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_pendentes', 'readwrite');
    const req = tx.objectStore('achados_pendentes').add({
      dados: dados,
      sincronizado: 0,
      criado_em: new Date().toISOString(),
    });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function contarPendentes() {
  try {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('achados_pendentes', 'readonly');
      const req = tx.objectStore('achados_pendentes').index('sincronizado').count(0);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return 0;
  }
}

async function obterPendentes() {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_pendentes', 'readonly');
    const req = tx.objectStore('achados_pendentes').index('sincronizado').getAll(0);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function marcarSincronizado(id) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_pendentes', 'readwrite');
    const store = tx.objectStore('achados_pendentes');
    const r = store.get(id);
    r.onsuccess = () => {
      const obj = r.result;
      if (obj) { obj.sincronizado = 1; store.put(obj); }
      resolve();
    };
    r.onerror = () => reject(r.error);
  });
}

// ── Banner offline ──────────────────────────────────────────────────────────────
async function atualizarBannerOffline() {
  const banner = document.getElementById('banner-offline');
  if (!banner) return;
  const pendentes = await contarPendentes();
  const offline = !navigator.onLine;

  if (!offline && pendentes === 0) {
    banner.classList.add('d-none');
    return;
  }

  banner.classList.remove('d-none');

  if (offline) {
    banner.className = 'alert alert-warning mb-0 rounded-0 text-center py-2 small no-print';
    const txt = pendentes > 0
      ? `<i class="bi bi-wifi-off"></i> <strong>Modo offline</strong> — ${pendentes} achado(s) aguardando sincronização quando o WiFi retornar`
      : '<i class="bi bi-wifi-off"></i> <strong>Modo offline</strong> — formulários serão salvos localmente e enviados ao reconectar';
    banner.innerHTML = txt;
  } else {
    // Online mas com pendentes
    banner.className = 'alert alert-info mb-0 rounded-0 text-center py-2 small no-print';
    banner.innerHTML =
      `<i class="bi bi-arrow-repeat"></i> ${pendentes} achado(s) offline aguardando sincronização — ` +
      `<a href="#" onclick="window.pwaSync(event)" class="fw-bold">sincronizar agora</a>`;
  }
}

// ── Sincronização manual ────────────────────────────────────────────────────────
window.pwaSync = async function (event) {
  if (event) event.preventDefault();
  if (!navigator.onLine) { alert('Sem conexão WiFi. Aguarde a rede retornar.'); return; }

  const pendentes = await obterPendentes();
  if (pendentes.length === 0) { atualizarBannerOffline(); return; }

  const banner = document.getElementById('banner-offline');
  if (banner) {
    banner.className = 'alert alert-info mb-0 rounded-0 text-center py-2 small no-print';
    banner.innerHTML = '<i class="bi bi-arrow-repeat pwa-spin"></i> Sincronizando achados offline...';
  }

  let ok = 0, erro = 0;

  for (const item of pendentes) {
    try {
      const resp = await fetch('/api/achados/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) { await marcarSincronizado(item.id); ok++; }
      else { erro++; }
    } catch { erro++; }
  }

  if (banner) {
    if (ok > 0 && erro === 0) {
      banner.className = 'alert alert-success mb-0 rounded-0 text-center py-2 small no-print';
      banner.innerHTML =
        `<i class="bi bi-check-circle"></i> ${ok} achado(s) sincronizado(s) com sucesso! ` +
        `<a href="javascript:location.reload()" class="fw-bold">Recarregar página</a>`;
      setTimeout(() => banner.classList.add('d-none'), 6000);
    } else {
      banner.className = 'alert alert-danger mb-0 rounded-0 text-center py-2 small no-print';
      banner.innerHTML =
        `<i class="bi bi-exclamation-triangle"></i> ${ok} sincronizado(s), ${erro} com erro. ` +
        `<a href="#" onclick="window.pwaSync(event)" class="fw-bold">Tentar novamente</a>`;
    }
  }
};

// ── Eventos de conexão ─────────────────────────────────────────────────────────
window.addEventListener('online', () => {
  atualizarBannerOffline();
  // Disparar background sync se suportado
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    navigator.serviceWorker.ready.then(reg => reg.sync.register('sync-achados')).catch(() => {});
  } else {
    window.pwaSync();
  }
});

window.addEventListener('offline', () => atualizarBannerOffline());

// Inicializar ao carregar página
document.addEventListener('DOMContentLoaded', () => atualizarBannerOffline());

// ── Exportar para uso no formulário ───────────────────────────────────────────
window.salvarAchadoOffline = salvarAchadoOffline;
