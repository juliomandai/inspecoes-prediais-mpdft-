'use strict';

// ── Registro do Service Worker ─────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(reg => {
        navigator.serviceWorker.addEventListener('message', event => {
          if (event.data && (event.data.tipo === 'achado_sincronizado' || event.data.tipo === 'edicao_sincronizada')) {
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
    const req = indexedDB.open('inspecoes-offline', 3);
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
      // v3: fila de fotos já comprimidas aguardando upload, desacoplada do
      // achado (ver docs/superpowers/specs/2026-07-31-sincronizacao-offline-volume-design.md).
      // IMPORTANTE: static/sw.js tem sua própria cópia deste schema (Background
      // Sync roda fora do contexto da página) — mudanças aqui devem ser
      // espelhadas lá também (ver Task 4 do plano).
      if (!db.objectStoreNames.contains('fotos_pendentes')) {
        const s = db.createObjectStore('fotos_pendentes', { keyPath: 'id', autoIncrement: true });
        s.createIndex('achado_id_local', 'achado_id_local');
        s.createIndex('pk_servidor', 'pk_servidor');
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = () => reject(req.error);
  });
}

// ── Criação offline ────────────────────────────────────────────────────────────
// IMPORTANTE: resolvemos no tx.oncomplete (commit), não no req.onsuccess. O
// chamador navega (window.location.href) logo após o await; se resolvêssemos no
// onsuccess, a navegação abortaria a transação ANTES do commit e o registro se
// perderia (bug observado no tablet: fila sempre vazia após salvar offline).
async function salvarAchadoOffline(dados) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_pendentes', 'readwrite');
    let novoId;
    const req = tx.objectStore('achados_pendentes').add({
      dados: dados,
      sincronizado: 0,
      criado_em: new Date().toISOString(),
    });
    req.onsuccess = () => { novoId = req.result; };
    tx.oncomplete = () => resolve(novoId);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error('transação abortada'));
  });
}

// ── Edição offline ─────────────────────────────────────────────────────────────
async function salvarEdicaoOffline(dados) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_edicao_pendentes', 'readwrite');
    let novoId;
    const req = tx.objectStore('achados_edicao_pendentes').add({
      achado_pk: dados.achado_pk,
      dados: dados,
      sincronizado: 0,
      criado_em: new Date().toISOString(),
    });
    req.onsuccess = () => { novoId = req.result; };
    tx.oncomplete = () => resolve(novoId);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error('transação abortada'));
  });
}

// ── Fila de fotos pendentes (desacoplada do achado) ────────────────────────────
// Cada foto é comprimida no momento da captura (comprimirFoto) e gravada aqui
// já pronta para upload. Fotos de um achado criado offline referenciam o
// achado_id_local (o `id` local em achados_pendentes) até o achado sincronizar
// e ganhar um pk de servidor — só então pk_servidor é preenchido e a foto
// entra na leva de envio (ver promoverFotosPendentes, chamada em pwaSync).
// Fotos de edição de um achado já existente recebem pk_servidor direto, sem
// espera, pois o achado editado já existe no servidor.
const FOTO_MAX_DIMENSAO = 1600;
const FOTO_QUALIDADE = 0.7;

function comprimirFoto(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      // Guarda a parte síncrona: se getContext/drawImage/toBlob lançarem (ex.:
      // canvas 2d indisponível), rejeitamos em vez de deixar a Promise pendurada
      // para sempre — sem isso, um await comprimirFoto(...) travaria a fila
      // inteira de sincronização sem erro nenhum aparecer para o usuário.
      try {
        let largura = img.naturalWidth;
        let altura = img.naturalHeight;
        if (largura > FOTO_MAX_DIMENSAO || altura > FOTO_MAX_DIMENSAO) {
          if (largura >= altura) {
            altura = Math.round(altura * (FOTO_MAX_DIMENSAO / largura));
            largura = FOTO_MAX_DIMENSAO;
          } else {
            largura = Math.round(largura * (FOTO_MAX_DIMENSAO / altura));
            altura = FOTO_MAX_DIMENSAO;
          }
        }
        const canvas = document.createElement('canvas');
        canvas.width = largura;
        canvas.height = altura;
        canvas.getContext('2d').drawImage(img, 0, 0, largura, altura);
        canvas.toBlob(
          blob => blob ? resolve(blob) : reject(new Error('Falha ao comprimir imagem')),
          'image/jpeg',
          FOTO_QUALIDADE
        );
      } catch (e) {
        reject(e);
      }
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Falha ao carregar imagem')); };
    img.src = url;
  });
}

async function salvarFotoOffline({ achadoIdLocal, achadoPkExistente, blob, nome }) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('fotos_pendentes', 'readwrite');
    let novoId;
    const req = tx.objectStore('fotos_pendentes').add({
      achado_id_local: achadoIdLocal || null,
      pk_servidor: achadoPkExistente || null,
      blob: blob,
      nome: nome || 'foto.jpg',
      criado_em: new Date().toISOString(),
    });
    req.onsuccess = () => { novoId = req.result; };
    tx.oncomplete = () => resolve(novoId);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error('transação abortada'));
  });
}

async function obterFotosPendentes() {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('fotos_pendentes', 'readonly');
    const req = tx.objectStore('fotos_pendentes').getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function descartarFotoPendente(id) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('fotos_pendentes', 'readwrite');
    tx.objectStore('fotos_pendentes').delete(id);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

// Após o achado pai sincronizar, associa suas fotos pendentes ao pk real de
// servidor — só a partir daí elas entram na leva de envio (ver pwaSync).
async function promoverFotosPendentes(achadoIdLocal, pkServidor) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('fotos_pendentes', 'readwrite');
    const store = tx.objectStore('fotos_pendentes');
    const req = store.index('achado_id_local').getAll(achadoIdLocal);
    req.onsuccess = () => {
      req.result.forEach(item => {
        item.pk_servidor = pkServidor;
        store.put(item);
      });
    };
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

async function contarFotosPendentes() {
  try {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('fotos_pendentes', 'readonly');
      const req = tx.objectStore('fotos_pendentes').count();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return 0;
  }
}

async function obterAchadoPreparado(achadoPk) {
  try {
    const db = await abrirDB();
    return new Promise((resolve) => {
      const tx = db.transaction('achados_preparados', 'readonly');
      const req = tx.objectStore('achados_preparados').get(achadoPk);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => resolve(null);
    });
  } catch {
    return null;
  }
}

// ── Preparar especialidade para campo (automático ao visualizar a aba) ─────────
// Nomes de cache espelham os do Service Worker (sw.js) — manter em sincronia.
const CACHE_PAGINAS = 'inspecoes-paginas-v7';
const CACHE_FOTOS   = 'inspecoes-fotos-v7';

// Evita repreparar a mesma especialidade a cada troca de aba na mesma sessão.
const espPreparadas = new Set();

async function cachearURL(cacheName, url) {
  try {
    const resp = await fetch(url, { credentials: 'include' });
    if (resp.ok) {
      const cache = await caches.open(cacheName);
      await cache.put(url, resp.clone());
    }
  } catch { /* offline ou erro de rede — ignora */ }
}

function badgeEstado(badgeEl, classe, html) {
  if (!badgeEl) return;
  badgeEl.className = 'badge ms-1 ' + classe;
  badgeEl.innerHTML = html;
  badgeEl.classList.remove('d-none');
}

// Prepara uma especialidade para uso offline: cacheia a página atual (detalhe),
// o formulário de novo achado, e — para cada achado — a página de edição e as
// fotos existentes; salva o baseline de cada achado para o diff de campos tocados.
window.prepararEspecialidadeParaCampo = async function (espPk, badgeEl, achadoCreateUrl, forcar) {
  if (!navigator.onLine) return;                 // silencioso: não há como preparar offline
  if (!forcar && espPreparadas.has(espPk)) return;
  if (!('caches' in window)) return;

  badgeEstado(badgeEl, 'bg-secondary', '<i class="bi bi-arrow-repeat pwa-spin"></i> Preparando…');
  try {
    const resp = await fetch('/api/especialidades/' + espPk + '/achados-para-campo/', {
      credentials: 'include',
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const achados = await resp.json();

    const db = await abrirDB();

    // Substitui as preparações antigas desta especialidade pelos baselines atuais.
    await new Promise((resolve, reject) => {
      const tx = db.transaction('achados_preparados', 'readwrite');
      const store = tx.objectStore('achados_preparados');
      const req = store.index('esp_pk').getAllKeys(espPk);
      req.onsuccess = () => {
        req.result.forEach(k => store.delete(k));
        achados.forEach(a => store.put({ achado_pk: a.pk, esp_pk: espPk, dados: a }));
      };
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });

    // Páginas: detalhe atual da inspeção + formulário de novo achado.
    await cachearURL(CACHE_PAGINAS, location.pathname);
    if (achadoCreateUrl) await cachearURL(CACHE_PAGINAS, achadoCreateUrl);

    // Por achado: página de edição + fotos existentes.
    for (const a of achados) {
      if (a.editar_url) await cachearURL(CACHE_PAGINAS, a.editar_url);
      for (const f of (a.fotos || [])) {
        if (f.url) await cachearURL(CACHE_FOTOS, f.url);
      }
    }

    espPreparadas.add(espPk);
    badgeEstado(badgeEl, 'bg-success',
      '<i class="bi bi-cloud-check"></i> Pronto offline ✓ (' + achados.length + ')');
  } catch (err) {
    badgeEstado(badgeEl, 'bg-warning text-dark',
      '<i class="bi bi-exclamation-triangle"></i> Falha ao preparar');
  }
};

// ── Contagem de pendentes (criação + edição) ───────────────────────────────────
async function contarPendentes() {
  try {
    const db = await abrirDB();
    const [criacao, edicao] = await Promise.all([
      new Promise((resolve, reject) => {
        const tx = db.transaction('achados_pendentes', 'readonly');
        const req = tx.objectStore('achados_pendentes').index('sincronizado').count(0);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      }),
      new Promise((resolve, reject) => {
        const tx = db.transaction('achados_edicao_pendentes', 'readonly');
        const req = tx.objectStore('achados_edicao_pendentes').index('sincronizado').count(0);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      }),
    ]);
    return criacao + edicao;
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

async function obterEdicoesPendentes() {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_edicao_pendentes', 'readonly');
    const req = tx.objectStore('achados_edicao_pendentes').index('sincronizado').getAll(0);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// Após sincronizar com sucesso, removemos o item da fila (em vez de marcar
// sincronizado=1) para o IndexedDB não crescer indefinidamente.
async function descartarPendente(id) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_pendentes', 'readwrite');
    tx.objectStore('achados_pendentes').delete(id);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

async function descartarEdicaoPendente(id) {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('achados_edicao_pendentes', 'readwrite');
    tx.objectStore('achados_edicao_pendentes').delete(id);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
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

  const [pendentes, edicoes] = await Promise.all([obterPendentes(), obterEdicoesPendentes()]);
  if (pendentes.length === 0 && edicoes.length === 0) { atualizarBannerOffline(); return; }

  const banner = document.getElementById('banner-offline');
  if (banner) {
    banner.className = 'alert alert-info mb-0 rounded-0 text-center py-2 small no-print';
    banner.innerHTML = '<i class="bi bi-arrow-repeat pwa-spin"></i> Sincronizando achados offline...';
  }

  let ok = 0, erro = 0, ultimoErro = '';

  async function detalheErro(resp) {
    try {
      const j = await resp.clone().json();
      if (j && j.erro) return 'HTTP ' + resp.status + ' — ' + j.erro;
    } catch { /* corpo não-JSON */ }
    return 'HTTP ' + resp.status;
  }

  // Sincronizar criações
  for (const item of pendentes) {
    try {
      const resp = await fetch('/api/achados/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) { await descartarPendente(item.id); ok++; }
      else { erro++; ultimoErro = await detalheErro(resp); }
    } catch (e) { erro++; ultimoErro = 'sem resposta do servidor (' + (e.message || e) + ')'; }
  }

  // Sincronizar edições
  for (const item of edicoes) {
    try {
      const resp = await fetch('/api/achados/' + item.achado_pk + '/sincronizar-edicao/', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) { await descartarEdicaoPendente(item.id); ok++; }
      else { erro++; ultimoErro = await detalheErro(resp); }
    } catch (e) { erro++; ultimoErro = 'sem resposta do servidor (' + (e.message || e) + ')'; }
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
        `<i class="bi bi-exclamation-triangle"></i> ${ok} sincronizado(s), ${erro} com erro` +
        (ultimoErro ? ` (${ultimoErro})` : '') + '. ' +
        `<a href="#" onclick="window.pwaSync(event)" class="fw-bold">Tentar novamente</a>`;
    }
  }
};

// ── Eventos de conexão ─────────────────────────────────────────────────────────
window.addEventListener('online', () => {
  atualizarBannerOffline();
  // Sincroniza em PRIMEIRO PLANO ao reconectar — caminho confiável enquanto o
  // app está aberto. O background sync do SW não dispara de forma confiável
  // (sobretudo em HTTP por IP de rede), então não dependemos dele aqui.
  window.pwaSync();
});

window.addEventListener('offline', () => atualizarBannerOffline());

document.addEventListener('DOMContentLoaded', async () => {
  await atualizarBannerOffline();
  // App reaberto já online com pendências (ex.: foi fechado offline): sincroniza.
  if (navigator.onLine && (await contarPendentes()) > 0) window.pwaSync();
});

// Ao voltar o foco para o app (tablet retomado do segundo plano) já online
// com pendências, tenta sincronizar — complementa o evento 'online'.
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState !== 'visible') return;
  if (navigator.onLine && (await contarPendentes()) > 0) window.pwaSync();
});

// ── Exportar para uso nos formulários ─────────────────────────────────────────
window.salvarAchadoOffline = salvarAchadoOffline;
window.salvarEdicaoOffline = salvarEdicaoOffline;
window.obterAchadoPreparado = obterAchadoPreparado;
