# Sincronização Offline em Alto Volume (Achados + Fotos) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar a sincronização offline robusta em sessões de alto volume (dezenas de achados, várias fotos cada) desacoplando o envio do texto do achado do envio das fotos, comprimindo fotos no cliente antes de armazená-las, e adicionando retry de rede + relato de progresso separado.

**Architecture:** Todo o código vive nos assets PWA já existentes (`static/js/pwa.js`, `static/sw.js`) e no app Django `apps.inspecoes`. Um novo object store `fotos_pendentes` no IndexedDB (bump de versão v2→v3) guarda fotos já comprimidas aguardando upload, desacopladas da fila de achados (`achados_pendentes`/`achados_edicao_pendentes`). Um novo endpoint `POST /api/achados/<pk>/fotos/sincronizar/` recebe uma foto por vez. Nenhuma migração de banco é necessária — o modelo `Foto` não muda, só ganha um segundo caminho de entrada no servidor.

Decisões completas em `docs/superpowers/specs/2026-07-31-sincronizacao-offline-volume-design.md` (10 ADRs) — este plano as implementa; não repete o raciocínio, só referencia.

**Tech Stack:** Django 5.2, SQLite, Pillow (compressão server-side já existe em `apps/inspecoes/imagens.py`), pytest-django, JavaScript vanilla (Canvas API, IndexedDB, Fetch).

**Convenções de ambiente (todos os comandos):**
- Diretório do projeto: `C:\Users\jtman\OneDrive - MPDFT\Trabalho - MPDFT\Inspeções Promotorias\Inspeções prediais MPDFT`
- Ativar venv antes de rodar Python: `.venv\Scripts\activate`
- Comandos `manage.py` e `pytest` rodam de dentro de `src\`
- Python do venv: `..\.venv\Scripts\python.exe`

**Descobertas desta fase de planejamento que ajustam o design** (documentadas aqui, não no design doc, que já está fechado):
1. **`achado_sincronizar`/`achado_sincronizar_edicao` não precisam de nenhuma mudança** para a compatibilidade retroativa (ADR-06 do design). Elas já fazem `dados.get('fotos', [])` — itens novos simplesmente não populam mais esse campo, e o loop existente vira um no-op automático. Nenhum `if`/`else` de formato é necessário.
2. **`comprimir_imagem()` (Pillow, servidor) já existe** em `apps/inspecoes/imagens.py` e já é chamada tanto por `foto_upload` quanto pelos loops de fotos em `achado_sincronizar`/`achado_sincronizar_edicao`. A compressão client-side (ADR-02) é *adicional*, não substitui a do servidor — uma foto passa por ambas (cliente: 1600px/q0.7 ; servidor: reforça ≤2000px/q80, que na prática vira um no-op de redimensionamento já que a imagem chega menor que 2000px, só re-codifica). Isso é esperado, não é bug.
3. **`static/sw.js` precisa mudar**, ao contrário do que o design apontou como "fora de escopo". Ele tem sua própria cópia de `abrirDB()` (para o Background Sync API) fixada na versão 2. Se `pwa.js` abrir o banco na versão 3 primeiro, uma chamada posterior de `sw.js` com versão 2 lança `VersionError` e quebra o Service Worker inteiro. Pior: se o Background Sync do navegador chegar a disparar (é raro, mas existe), ele sincroniza o texto do achado sem promover as fotos da fila (`achado_id_local`→`pk_servidor`), órfãs para sempre. Task 4 cobre os dois problemas.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/apps/inspecoes/views.py` (modificar) | extrai `_criar_foto_do_upload`; novo endpoint `achado_sincronizar_foto` |
| `src/apps/inspecoes/urls.py` (modificar) | rota do novo endpoint |
| `src/apps/inspecoes/tests/test_sync_foto.py` (criar) | testes do novo endpoint |
| `src/static/js/pwa.js` (modificar) | IndexedDB v3 (`fotos_pendentes`); `comprimirFoto`; CRUD da fila de fotos; `fetchComRetry`; `pwaSync` em 2 fases; banner separado; alerta de armazenamento |
| `src/static/sw.js` (modificar) | espelha o schema v3; promove fotos pendentes após sync em background |
| `src/apps/inspecoes/templates/inspecoes/achado_form.html` (modificar) | usa `comprimirFoto`/`salvarFotoOffline` em vez de `fotoParaB64`, na criação e na edição offline |

---

## Task 1: Endpoint de sincronização de foto individual (servidor)

**Files:**
- Modify: `src/apps/inspecoes/views.py:499-530`
- Modify: `src/apps/inspecoes/urls.py:69-75`
- Create: `src/apps/inspecoes/tests/test_sync_foto.py`

- [x] **Step 1: Escrever os testes do novo endpoint (falhando)**

Crie `src/apps/inspecoes/tests/test_sync_foto.py`:

```python
import json
import pytest
from datetime import date
from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model


@pytest.fixture
def cenario(db, client):
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='X', data_inspecao=date.today(),
    )
    achado = Achado.objects.create(
        especialidade=esp, localizacao='Subsolo', verificacao='Infiltração',
        grupo_tecnico='estrutura', requisito_afetado='durabilidade',
        gravidade=2, urgencia=2, tendencia=2, prioridade_risco=3,
    )
    return {'u': u, 'esp': esp, 'achado': achado}


def _png_minimo():
    return (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')


@pytest.mark.django_db
def test_sincronizar_foto_cria_foto_no_achado(client, cenario):
    from apps.inspecoes.models import Foto
    achado = cenario['achado']
    arquivo = SimpleUploadedFile('subsolo.png', _png_minimo(), content_type='image/png')
    resp = client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[achado.pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 201
    assert json.loads(resp.content)['ok'] is True
    assert Foto.objects.filter(achado=achado).count() == 1


@pytest.mark.django_db
def test_sincronizar_foto_rejeita_sem_arquivo(client, cenario):
    resp = client.post(reverse('inspecoes:achado_sincronizar_foto', args=[cenario['achado'].pk]))
    assert resp.status_code == 400
    assert json.loads(resp.content)['erro'] == 'Nenhum arquivo enviado.'


@pytest.mark.django_db
def test_sincronizar_foto_rejeita_formato_invalido(client, cenario):
    arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
    resp = client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[cenario['achado'].pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 400
    assert json.loads(resp.content)['erro'] == 'Formato inválido. Use JPEG ou PNG.'


@pytest.mark.django_db
def test_sincronizar_foto_funciona_com_especialidade_finalizada(client, cenario):
    """ADR-10 do design: uma foto pendente deve poder subir mesmo que a
    especialidade já tenha sido finalizada nesse meio-tempo."""
    from apps.inspecoes.models import Foto
    esp = cenario['esp']
    esp.status = 'finalizada'
    esp.save()
    arquivo = SimpleUploadedFile('subsolo.png', _png_minimo(), content_type='image/png')
    resp = client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[cenario['achado'].pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 201
    assert Foto.objects.filter(achado=cenario['achado']).count() == 1


@pytest.mark.django_db
def test_sincronizar_foto_nao_exige_csrf_token():
    """O endpoint é usado pela fila de sincronização offline (pwa.js), que não
    tem acesso a um token CSRF renderizado em página — precisa ser csrf_exempt,
    igual aos demais endpoints de sync (achado_sincronizar,
    achado_sincronizar_edicao)."""
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
    U = get_user_model()
    u = U.objects.create_user(username='maria', password='1', is_staff=True)
    edif = Edificacao.objects.create(nome='Sede 2')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='X', data_inspecao=date.today(),
    )
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=1, tendencia=1, prioridade_risco=3,
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(u)
    arquivo = SimpleUploadedFile('subsolo.png', _png_minimo(), content_type='image/png')
    resp = csrf_client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[achado.pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_foto_upload_continua_funcionando_apos_refatoracao(client, cenario):
    """Garante que extrair _criar_foto_do_upload não quebrou o endpoint online
    existente (usado pelo upload AJAX na edição, com conexão)."""
    from apps.inspecoes.models import Foto
    arquivo = SimpleUploadedFile('online.png', _png_minimo(), content_type='image/png')
    resp = client.post(
        reverse('inspecoes:foto_upload', args=[cenario['achado'].pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 200
    body = json.loads(resp.content)
    assert 'id' in body and 'url' in body
    assert Foto.objects.filter(achado=cenario['achado']).count() == 1
```

- [x] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_sync_foto.py -v`
Expected: FAIL (`NoReverseMatch` para `inspecoes:achado_sincronizar_foto`)

- [x] **Step 3: Extrair `_criar_foto_do_upload` e refatorar `foto_upload`**

Em `src/apps/inspecoes/views.py`, localize (linhas 508-530):

```python
def foto_valida(content_type, tamanho):
    return erro_validacao_foto(content_type, tamanho) is None


@login_required
@require_POST
def foto_upload(request, achado_pk):
    achado = get_object_or_404(Achado.objects.select_related('especialidade'), pk=achado_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    erro = erro_validacao_foto(arquivo.content_type, arquivo.size)
    if erro:
        return JsonResponse({'erro': erro}, status=400)

    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
    foto = Foto.objects.create(
        achado=achado,
        arquivo=cf,
        nome_original=nome,
        tamanho_bytes=tamanho,
    )
    return JsonResponse({'id': foto.pk, 'url': foto.arquivo.url, 'nome': foto.nome_original})
```

Substitua por:

```python
def foto_valida(content_type, tamanho):
    return erro_validacao_foto(content_type, tamanho) is None


def _criar_foto_do_upload(achado, arquivo):
    """Valida e cria uma Foto a partir de um UploadedFile.

    Retorna (foto, None) em sucesso, ou (None, mensagem_erro) se inválida.
    Compartilhado entre o upload online (foto_upload) e a fila de
    sincronização offline (achado_sincronizar_foto) — mesma validação e
    mesma compressão nos dois caminhos.
    """
    erro = erro_validacao_foto(arquivo.content_type, arquivo.size)
    if erro:
        return None, erro
    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
    foto = Foto.objects.create(
        achado=achado,
        arquivo=cf,
        nome_original=nome,
        tamanho_bytes=tamanho,
    )
    return foto, None


@login_required
@require_POST
def foto_upload(request, achado_pk):
    achado = get_object_or_404(Achado.objects.select_related('especialidade'), pk=achado_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    foto, erro = _criar_foto_do_upload(achado, arquivo)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    return JsonResponse({'id': foto.pk, 'url': foto.arquivo.url, 'nome': foto.nome_original})
```

- [x] **Step 4: Adicionar o novo endpoint `achado_sincronizar_foto`**

Em `src/apps/inspecoes/views.py`, localize o fim de `achado_sincronizar_edicao` (a linha com `'fotos_salvas': fotos_salvas, 'fotos_excluidas': fotos_excluidas,\n    })`, por volta da linha 922, logo antes do comentário `# ── Análise — helper compartilhado`. Adicione, entre os dois:

```python
@login_required
@csrf_exempt
@require_POST
def achado_sincronizar_foto(request, pk):
    """
    Recebe UMA foto (multipart) da fila de sincronização offline e a anexa
    ao achado. Desacoplada de achado_sincronizar/achado_sincronizar_edicao
    (ver docs/superpowers/specs/2026-07-31-sincronizacao-offline-volume-design.md,
    ADR-01): uma foto grande ou instável não deve impedir o texto do achado
    de chegar ao servidor, nem vice-versa.

    Não verifica `pode_editar` da especialidade — ADR-10: uma foto que já
    estava na fila local deve poder subir mesmo que a especialidade tenha
    sido finalizada nesse meio-tempo.
    """
    achado = get_object_or_404(Achado, pk=pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    foto, erro = _criar_foto_do_upload(achado, arquivo)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    return JsonResponse({'ok': True, 'foto_pk': foto.pk}, status=201)
```

- [x] **Step 5: Adicionar a rota**

Em `src/apps/inspecoes/urls.py`, localize:

```python
    path('api/achados/<int:pk>/sincronizar-edicao/', views.achado_sincronizar_edicao, name='achado_sincronizar_edicao'),
]
```

Substitua por:

```python
    path('api/achados/<int:pk>/sincronizar-edicao/', views.achado_sincronizar_edicao, name='achado_sincronizar_edicao'),
    path('api/achados/<int:pk>/fotos/sincronizar/', views.achado_sincronizar_foto, name='achado_sincronizar_foto'),
]
```

- [x] **Step 6: Rodar os testes novos e os de regressão**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_sync_foto.py apps/inspecoes/tests/test_validacao_foto.py apps/inspecoes/tests/test_sync_edicao.py -v`
Expected: PASS (todos — os dois arquivos existentes confirmam que a refatoração de `foto_upload` e os endpoints antigos não quebraram)

- [x] **Step 7: Rodar a suíte completa e o check do Django**

Run:
```
..\.venv\Scripts\python.exe -m pytest -v
..\.venv\Scripts\python.exe manage.py check
```
Expected: todos os testes PASS; "System check identified no issues"

- [x] **Step 8: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/tests/test_sync_foto.py
git commit -m "feat: endpoint de sincronizacao de foto individual, desacoplado do achado"
```

---

## Task 2: pwa.js — schema IndexedDB v3 e fila de fotos pendentes

**Files:**
- Modify: `src/static/js/pwa.js:18-41` (bump de versão + novo store)
- Modify: `src/static/js/pwa.js` (novas funções, inseridas após `salvarEdicaoOffline`)

- [x] **Step 1: Bump da versão do IndexedDB e novo object store**

Em `src/static/js/pwa.js`, localize `function abrirDB()` (linhas 19-41):

```javascript
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
```

Substitua por (versão 2→3, novo store `fotos_pendentes`):

```javascript
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
```

- [x] **Step 2: Adicionar compressão e funções da fila de fotos**

Em `src/static/js/pwa.js`, logo após o fim de `salvarEdicaoOffline` (depois da linha `}` que fecha essa função, antes da declaração `async function obterAchadoPreparado(achadoPk) {`), insira:

```javascript
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
```

- [x] **Step 3: Verificação manual no navegador**

Inicie o servidor (`..\.venv\Scripts\python.exe manage.py runserver` de dentro de `src\`), abra qualquer página logada no Chrome, abra o DevTools → Console, e rode:

```javascript
indexedDB.open('inspecoes-offline').onsuccess = e => console.log([...e.target.result.objectStoreNames]);
```

Expected: `["achados_edicao_pendentes", "achados_pendentes", "achados_preparados", "fotos_pendentes"]` (a nova store aparece; nenhum dado das stores existentes foi perdido — abra a aba Application → IndexedDB no DevTools e confira que `achados_pendentes` etc. continuam com o conteúdo de antes, se havia algum).

Teste as novas funções diretamente no console (elas ainda não são exportadas para `window`, mas o Console do DevTools tem acesso ao escopo do módulo carregado via `<script>` não-module, então rode a partir da página que carrega `pwa.js`):

```javascript
// cole no console de uma pagina que carrega static/js/pwa.js
fetch('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
  .then(r => r.blob())
  .then(b => new File([b], 'teste.png', { type: 'image/png' }))
  .then(f => comprimirFoto(f))
  .then(blob => console.log('comprimida:', blob.size, 'bytes', blob.type));
```

Expected: loga `comprimida: <N> bytes image/jpeg` sem erro (a imagem de teste é 1×1px, então `blob.size` será pequeno — o importante é não haver exceção e o tipo ser `image/jpeg`).

- [x] **Step 4: Commit**

```bash
git add src/static/js/pwa.js
git commit -m "feat: schema IndexedDB v3 e fila de fotos pendentes desacoplada"
```

---

## Task 3: pwa.js — retry com backoff, sincronização em 2 fases e banner separado

**Files:**
- Modify: `src/static/js/pwa.js` (nova função `fetchComRetry`, antes de `pwaSync`)
- Modify: `src/static/js/pwa.js` (`atualizarBannerOffline`, `pwaSync`, listeners de evento, exports)

- [x] **Step 1: Adicionar `fetchComRetry`**

Em `src/static/js/pwa.js`, logo antes do comentário `// ── Banner offline`, insira:

```javascript
// ── Retry com backoff (só para falhas de rede — fetch() rejeitando) ────────────
// Uma resposta HTTP de erro (4xx/5xx) NÃO lança exceção em fetch(), então não é
// re-tentada aqui — só timeout/sem-resposta, típico de sinal fraco em campo.
async function fetchComRetry(url, opts, tentativas, esperas) {
  tentativas = tentativas || 3;
  esperas = esperas || [2000, 5000];
  for (let i = 0; i < tentativas; i++) {
    try {
      return await fetch(url, opts);
    } catch (e) {
      if (i === tentativas - 1) throw e;
      await new Promise(r => setTimeout(r, esperas[Math.min(i, esperas.length - 1)]));
    }
  }
}
```

- [x] **Step 2: Reescrever `atualizarBannerOffline` para contar fotos separadamente**

Substitua a função `atualizarBannerOffline` inteira (do `async function atualizarBannerOffline() {` até o `}` correspondente) por:

```javascript
async function atualizarBannerOffline() {
  const banner = document.getElementById('banner-offline');
  if (!banner) return;
  const [pendentes, fotosPendentes] = await Promise.all([contarPendentes(), contarFotosPendentes()]);
  const totalPendente = pendentes + fotosPendentes;
  const offline = !navigator.onLine;

  if (!offline && totalPendente === 0) {
    banner.classList.add('d-none');
    return;
  }

  banner.classList.remove('d-none');

  if (offline) {
    banner.className = 'alert alert-warning mb-0 rounded-0 text-center py-2 small no-print';
    const txt = totalPendente > 0
      ? `<i class="bi bi-wifi-off"></i> <strong>Modo offline</strong> — ${pendentes} achado(s) e ${fotosPendentes} foto(s) aguardando sincronização quando o WiFi retornar`
      : '<i class="bi bi-wifi-off"></i> <strong>Modo offline</strong> — formulários serão salvos localmente e enviados ao reconectar';
    banner.innerHTML = txt;
  } else {
    banner.className = 'alert alert-info mb-0 rounded-0 text-center py-2 small no-print';
    banner.innerHTML =
      `<i class="bi bi-arrow-repeat"></i> ${pendentes} achado(s) e ${fotosPendentes} foto(s) offline aguardando sincronização — ` +
      `<a href="#" onclick="window.pwaSync(event)" class="fw-bold">sincronizar agora</a>`;
  }
}
```

- [x] **Step 3: Reescrever `pwaSync` em duas fases (achados, depois fotos)**

Substitua a função `window.pwaSync` inteira (do `window.pwaSync = async function (event) {` até o `};` correspondente) por:

```javascript
window.pwaSync = async function (event) {
  if (event) event.preventDefault();
  if (!navigator.onLine) { alert('Sem conexão WiFi. Aguarde a rede retornar.'); return; }

  const [pendentes, edicoes, fotosIniciais] = await Promise.all([
    obterPendentes(), obterEdicoesPendentes(), obterFotosPendentes(),
  ]);
  if (pendentes.length === 0 && edicoes.length === 0 && fotosIniciais.length === 0) {
    atualizarBannerOffline();
    return;
  }

  const banner = document.getElementById('banner-offline');
  if (banner) {
    banner.className = 'alert alert-info mb-0 rounded-0 text-center py-2 small no-print';
    banner.innerHTML = '<i class="bi bi-arrow-repeat pwa-spin"></i> Sincronizando achados offline...';
  }

  async function detalheErro(resp) {
    try {
      const j = await resp.clone().json();
      if (j && j.erro) return 'HTTP ' + resp.status + ' — ' + j.erro;
    } catch { /* corpo não-JSON */ }
    return 'HTTP ' + resp.status;
  }

  let achadosOk = 0, achadosErro = 0, ultimoErroAchado = '';

  // Fase 1a — sincronizar criações (texto do achado). Itens de sessões
  // anteriores ao formato antigo, com fotos ainda embutidas em item.dados.fotos,
  // continuam funcionando sem tratamento especial — o servidor já processa
  // esse campo quando presente e ignora quando ausente.
  for (const item of pendentes) {
    try {
      const resp = await fetchComRetry('/api/achados/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) {
        const data = await resp.json();
        await promoverFotosPendentes(item.id, data.achado_pk);
        await descartarPendente(item.id);
        achadosOk++;
      } else {
        achadosErro++; ultimoErroAchado = await detalheErro(resp);
      }
    } catch (e) { achadosErro++; ultimoErroAchado = 'sem resposta do servidor (' + (e.message || e) + ')'; }
  }

  // Fase 1b — sincronizar edições. O achado editado já tem pk de servidor;
  // fotos novas da edição já foram salvas na fila com pk_servidor preenchido
  // (ver achado_form.html), não precisam de promoção.
  for (const item of edicoes) {
    try {
      const resp = await fetchComRetry('/api/achados/' + item.achado_pk + '/sincronizar-edicao/', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) { await descartarEdicaoPendente(item.id); achadosOk++; }
      else { achadosErro++; ultimoErroAchado = await detalheErro(resp); }
    } catch (e) { achadosErro++; ultimoErroAchado = 'sem resposta do servidor (' + (e.message || e) + ')'; }
  }

  // Fase 2 — sincronizar fotos, uma de cada vez (serial: em sinal fraco,
  // requisições paralelas tendem a disputar banda e falhar juntas). Só as que
  // já têm pk_servidor (achado pai confirmado no servidor) são enviadas; as
  // demais aguardam a próxima rodada.
  const fotosProntas = (await obterFotosPendentes()).filter(f => f.pk_servidor);
  let fotosOk = 0, fotosErro = 0, ultimoErroFoto = '';
  for (const item of fotosProntas) {
    try {
      const fd = new FormData();
      fd.append('arquivo', item.blob, item.nome || 'foto.jpg');
      const resp = await fetchComRetry('/api/achados/' + item.pk_servidor + '/fotos/sincronizar/', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
        body: fd,
      });
      if (resp.ok) { await descartarFotoPendente(item.id); fotosOk++; }
      else { fotosErro++; ultimoErroFoto = await detalheErro(resp); }
    } catch (e) { fotosErro++; ultimoErroFoto = 'sem resposta do servidor (' + (e.message || e) + ')'; }
  }

  const fotosRestantes = await contarFotosPendentes();

  if (banner) {
    if (achadosErro === 0 && fotosErro === 0 && fotosRestantes === 0) {
      banner.className = 'alert alert-success mb-0 rounded-0 text-center py-2 small no-print';
      banner.innerHTML =
        `<i class="bi bi-check-circle"></i> ${achadosOk} achado(s) e ${fotosOk} foto(s) sincronizados com sucesso! ` +
        `<a href="javascript:location.reload()" class="fw-bold">Recarregar página</a>`;
      setTimeout(() => banner.classList.add('d-none'), 6000);
    } else if (achadosErro === 0 && fotosErro === 0) {
      banner.className = 'alert alert-info mb-0 rounded-0 text-center py-2 small no-print';
      banner.innerHTML =
        `<i class="bi bi-arrow-repeat"></i> ${achadosOk} achado(s) sincronizados. ` +
        `Fotos: ${fotosOk} enviada(s), ${fotosRestantes} pendente(s) (achado pai ainda sincronizando ou tentando de novo). ` +
        `<a href="#" onclick="window.pwaSync(event)" class="fw-bold">Sincronizar agora</a>`;
    } else {
      banner.className = 'alert alert-danger mb-0 rounded-0 text-center py-2 small no-print';
      banner.innerHTML =
        `<i class="bi bi-exclamation-triangle"></i> ${achadosOk} achado(s) sincronizado(s), ${achadosErro} com erro` +
        (ultimoErroAchado ? ` (${ultimoErroAchado})` : '') + `. ` +
        `Fotos: ${fotosOk} enviada(s), ${fotosErro} com erro` +
        (ultimoErroFoto ? ` (${ultimoErroFoto})` : '') + `, ${fotosRestantes} pendente(s). ` +
        `<a href="#" onclick="window.pwaSync(event)" class="fw-bold">Tentar novamente</a>`;
    }
  }
};
```

- [x] **Step 4: Atualizar os listeners de `DOMContentLoaded` e `visibilitychange`**

Substitua:

```javascript
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
```

por:

```javascript
async function haPendencias() {
  return (await contarPendentes()) > 0 || (await contarFotosPendentes()) > 0;
}

document.addEventListener('DOMContentLoaded', async () => {
  await atualizarBannerOffline();
  // App reaberto já online com pendências (ex.: foi fechado offline): sincroniza.
  if (navigator.onLine && (await haPendencias())) window.pwaSync();
});

// Ao voltar o foco para o app (tablet retomado do segundo plano) já online
// com pendências, tenta sincronizar — complementa o evento 'online'.
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState !== 'visible') return;
  if (navigator.onLine && (await haPendencias())) window.pwaSync();
});
```

- [x] **Step 5: Verificação manual — simular alto volume offline**

Com o servidor rodando e logado numa inspeção com uma especialidade preparada para campo (aba já visitada online pelo menos uma vez):

1. DevTools → Network → marque "Offline".
2. Crie 3 achados novos, cada um com 2 fotos (câmera do notebook ou "Escolher arquivo").
3. DevTools → Application → IndexedDB → `inspecoes-offline` → confira `achados_pendentes` (3 itens) e `fotos_pendentes` (6 itens, todos com `pk_servidor: null` e `achado_id_local` preenchido).
4. Desmarque "Offline". O evento `online` deve dispersar `pwaSync()` automaticamente.
5. Observe o banner: deve mostrar progresso e, ao concluir, "3 achado(s) e 6 foto(s) sincronizados com sucesso!".
6. Confira no admin do Django (`/admin/inspecoes/foto/`) que as 6 fotos existem, cada uma vinculada ao achado correto.
7. Repita os passos 1-3, mas desta vez, antes de desmarcar "Offline", abra o Console e rode `fetch('/api/achados/sincronizar/')` — confirme que ele falha (rede offline). Desmarque "Offline" e confirme que a sincronização ainda funciona normalmente (retry não deixou nada travado).

Expected: todos os achados e fotos aparecem no servidor; nenhum acoplamento — mesmo que uma foto específica falhe (pode simular removendo o achado pelo admin antes de sincronizar as fotos, forçando 404), os demais achados e fotos continuam sincronizando.

- [x] **Step 6: Commit**

```bash
git add src/static/js/pwa.js
git commit -m "feat: sincronizacao offline em 2 fases com retry de rede e banner separado"
```

---

## Task 4: sw.js — espelhar schema v3 e promoção em background sync

**Files:**
- Modify: `src/static/sw.js`

- [x] **Step 1: Bump de versão e novo store (espelhando pwa.js)**

Em `src/static/sw.js`, localize `function abrirDB()` (linhas 121-143):

```javascript
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
```

Substitua por:

```javascript
function abrirDB() {
  return new Promise((resolve, reject) => {
    // IMPORTANTE: mesma versão e mesmo schema de static/js/pwa.js. Se este
    // número ficar atrás do usado em pwa.js, indexedDB.open aqui lança
    // VersionError (não é permitido abrir com versão MENOR que a atual) e
    // quebra o Service Worker inteiro na próxima ativação.
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

// Promove as fotos pendentes de um achado local para o pk de servidor, assim
// que esse achado sincroniza em background — evita órfãos: sem isso, se o
// Background Sync do navegador chegar a disparar (ver comentário em
// sincronizarAchadosPendentes), as fotos daquele achado ficariam presas para
// sempre, já que o item de achados_pendentes que as referenciava foi apagado.
async function promoverFotosPendentes(db, achadoIdLocal, pkServidor) {
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
```

- [x] **Step 2: Promover fotos após sync de criação em background**

Em `src/static/sw.js`, dentro de `sincronizarAchadosPendentes()`, localize:

```javascript
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
```

Substitua por:

```javascript
  for (const item of pendentes) {
    try {
      const resp = await fetch('/api/achados/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(item.dados),
      });
      if (resp.ok) {
        const data = await resp.json();
        await promoverFotosPendentes(db, item.id, data.achado_pk);
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
```

> Nota: o Background Sync não sobe as fotos em si (só as promove) — o
> comentário em `pwa.js` já documenta que este projeto não depende do
> Background Sync como caminho confiável; ele é um reforço best-effort. A
> próxima vez que o app abrir em primeiro plano com sinal, `pwaSync()` (Task 3)
> encontra as fotos já promovidas (`pk_servidor` preenchido) e as envia
> normalmente. Duplicar aqui o envio de fotos ampliaria a superfície de código
> rodando fora da página sem ganho prático — fora de escopo (YAGNI).

- [x] **Step 3: Bump da versão dos caches do Service Worker**

Como o próprio arquivo `sw.js` muda, incremente a versão dos caches para forçar todos os clientes a buscar a nova versão do arquivo. Em `src/static/sw.js`, localize:

```javascript
const CACHE_PAGINAS  = 'inspecoes-paginas-v7';
const CACHE_ESTATICO = 'inspecoes-estatico-v7';
// Fotos de achados pré-cacheadas pela preparação para campo (ver pwa.js).
const CACHE_FOTOS    = 'inspecoes-fotos-v7';
```

Substitua `v7` por `v8` nas três linhas:

```javascript
const CACHE_PAGINAS  = 'inspecoes-paginas-v8';
const CACHE_ESTATICO = 'inspecoes-estatico-v8';
// Fotos de achados pré-cacheadas pela preparação para campo (ver pwa.js).
const CACHE_FOTOS    = 'inspecoes-fotos-v8';
```

Em `src/static/js/pwa.js`, localize (perto do topo, seção "Preparar especialidade para campo"):

```javascript
const CACHE_PAGINAS = 'inspecoes-paginas-v7';
const CACHE_FOTOS   = 'inspecoes-fotos-v7';
```

Substitua por:

```javascript
const CACHE_PAGINAS = 'inspecoes-paginas-v8';
const CACHE_FOTOS   = 'inspecoes-fotos-v8';
```

- [x] **Step 4: Verificação manual**

Com o servidor rodando, abra a página no Chrome, DevTools → Application → Service Workers: confirme que uma nova versão do SW é instalada (ou force via "Update on reload"). Em Application → Cache Storage, confirme que os caches `-v8` aparecem e os `-v7` são removidos após a ativação (o `activate` listener já limpa caches fora de `CACHES_VALIDOS`).

Rode no Console:
```javascript
indexedDB.open('inspecoes-offline').onsuccess = e => console.log(e.target.result.version, [...e.target.result.objectStoreNames]);
```
Expected: `3 ["achados_edicao_pendentes", "achados_pendentes", "achados_preparados", "fotos_pendentes"]` — sem erro `VersionError` no console.

- [x] **Step 5: Commit**

```bash
git add src/static/sw.js src/static/js/pwa.js
git commit -m "fix: espelha schema IndexedDB v3 no service worker e evita fotos orfas em background sync"
```

---

## Task 5: achado_form.html — compressão e fila de fotos na criação offline

**Files:**
- Modify: `src/apps/inspecoes/templates/inspecoes/achado_form.html:252-335`

- [x] **Step 1: Substituir o bloco de interceptação offline (criação)**

Em `src/apps/inspecoes/templates/inspecoes/achado_form.html`, substitua o `<script>` inteiro da seção `// ── Interceptação offline (somente na criação)` (linhas 251-335, do `<script>` de abertura ao `</script>` de fechamento) por:

```html
<script>
// ── Interceptação offline (somente na criação) ─────────────────────────────
(function () {
  var form = document.getElementById('achado-form');
  if (!form || form.dataset.modo !== 'criar') return;

  // Coleta fotos selecionadas (File) — a compressão acontece no submit.
  var fotosColetadas = [];

  document.getElementById('foto-camera').addEventListener('change', function () {
    Array.from(this.files).forEach(f => fotosColetadas.push(f));
  });
  document.getElementById('foto-arquivo').addEventListener('change', function () {
    Array.from(this.files).forEach(f => fotosColetadas.push(f));
  });

  form.addEventListener('submit', async function (e) {
    if (navigator.onLine) return; // online → envio normal
    e.preventDefault();

    var btn = form.querySelector('button[type=submit]');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass"></i> Salvando...'; }

    var esp_pk    = parseInt(form.dataset.espPk);
    var detalheUrl = form.dataset.detalheUrl;

    function val(id) {
      var el = document.getElementById(id);
      return el ? el.value : '';
    }
    function checked(id) {
      var el = document.getElementById(id);
      return el ? el.checked : false;
    }

    var dados = {
      esp_pk: esp_pk,
      localizacao: val('id_localizacao'),
      sub_localizacao: val('id_sub_localizacao'),
      verificacao: val('id_verificacao'),
      grupo_tecnico: val('id_grupo_tecnico'),
      em_conformidade: checked('id_em_conformidade'),
      descricao_nao_conformidade: val('id_descricao_nao_conformidade'),
      requisito_afetado: val('id_requisito_afetado'),
      gravidade: parseInt(val('id_gravidade')) || 1,
      urgencia: parseInt(val('id_urgencia')) || 1,
      tendencia: parseInt(val('id_tendencia')) || 1,
      prioridade_risco: parseInt(val('id_prioridade_risco')) || 3,
      recomendacao: val('id_recomendacao'),
      direcionamento: val('id_direcionamento'),
      prazo_meses: parseInt(val('id_prazo_meses')) || 12,
    };

    try {
      // 1. Salva o TEXTO do achado primeiro — pequeno e rápido, chega ao
      //    servidor mesmo em rede ruim. achadoIdLocal é o `id` local
      //    (IndexedDB), usado para vincular as fotos até o achado ganhar um
      //    pk de servidor na sincronização (ver pwa.js: promoverFotosPendentes).
      var achadoIdLocal = await window.salvarAchadoOffline(dados);

      // 2. Cada foto é comprimida (canvas, ~200-500KB) e vai para a fila
      //    separada de fotos — se uma foto falhar ao comprimir ou ao
      //    sincronizar depois, não afeta o achado nem as demais fotos.
      for (var foto of fotosColetadas) {
        if (!foto.type.match(/image\/(jpeg|png)/)) continue;
        if (foto.size > 10 * 1024 * 1024) continue; // teto pré-compressão (arquivo original patologicamente grande)
        try {
          var blob = await window.comprimirFoto(foto);
          await window.salvarFotoOffline({ achadoIdLocal: achadoIdLocal, blob: blob, nome: foto.name });
        } catch {}
      }

      if (window.verificarArmazenamento) window.verificarArmazenamento();

      // Redirecionar para a página de detalhe (do cache do SW)
      window.location.href = detalheUrl;
    } catch (err) {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg"></i> Salvar Achado'; }
      alert('Erro ao salvar offline: ' + err.message);
    }
  });
})();
</script>
```

- [x] **Step 2: Verificação manual**

Com o servidor rodando: DevTools → Network → Offline. Crie um achado com 2 fotos grandes (fotos reais de câmera, se possível, ou qualquer JPEG/PNG de alguns MB). Confirme:
- O formulário salva sem travar (a compressão roda antes do redirect).
- DevTools → Application → IndexedDB → `achados_pendentes` tem 1 item **sem** campo `fotos` (ou com array vazio).
- `fotos_pendentes` tem 2 itens, cada um com `blob` do tipo `image/jpeg` e tamanho bem menor que o arquivo original (confira em Application → IndexedDB, clique no item para ver o `Blob` e seu `size`).

Expected: nenhum erro no Console; achado e fotos aparecem corretamente na fila, já comprimidos.

- [x] **Step 3: Commit**

```bash
git add src/apps/inspecoes/templates/inspecoes/achado_form.html
git commit -m "feat: compressao client-side e fila de fotos separada na criacao offline de achado"
```

---

## Task 6: achado_form.html — compressão e fila de fotos na edição offline

**Files:**
- Modify: `src/apps/inspecoes/templates/inspecoes/achado_form.html` (bloco "Interceptação offline (modo edição)")

- [x] **Step 1: Atualizar a coleta de fotos no submit de edição offline**

Em `src/apps/inspecoes/templates/inspecoes/achado_form.html`, dentro do segundo `<script>` (`// ── Interceptação offline (modo edição)`), localize o trecho final do handler de `submit` (a partir de `// Fotos: novas (base64) + pks marcados para exclusão.` até o fim do `try`/`catch`):

```javascript
    // Fotos: novas (base64) + pks marcados para exclusão.
    dados.fotos = [];
    dados.fotos_excluir = window.fotoState.excluir.slice();

    async function fotoParaB64(file) {
      return new Promise((resolve, reject) => {
        var reader = new FileReader();
        reader.onload = e => resolve(e.target.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    for (var foto of window.fotoState.novas) {
      if (!foto.type.match(/image\/(jpeg|png)/)) continue;
      if (foto.size > 10 * 1024 * 1024) continue;
      try {
        var b64 = await fotoParaB64(foto);
        dados.fotos.push({ nome: foto.name, tipo: foto.type, dados_b64: b64 });
      } catch {}
    }

    try {
      await window.salvarEdicaoOffline(dados);
      window.location.href = detalheUrl;
    } catch (err) {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg"></i> Salvar Achado'; }
      alert('Erro ao salvar offline: ' + err.message);
    }
  });
})();
```

Substitua por:

```javascript
    // Exclusões de fotos (só pks, sem bytes — continua leve no payload de
    // texto). Fotos NOVAS não vão mais aqui: cada uma é comprimida e salva
    // na fila separada logo abaixo, já com o pk do achado (que já existe,
    // por ser edição — não precisa esperar nenhuma sincronização prévia).
    dados.fotos_excluir = window.fotoState.excluir.slice();

    try {
      await window.salvarEdicaoOffline(dados);

      for (var foto of window.fotoState.novas) {
        if (!foto.type.match(/image\/(jpeg|png)/)) continue;
        if (foto.size > 10 * 1024 * 1024) continue; // teto pré-compressão
        try {
          var blob = await window.comprimirFoto(foto);
          await window.salvarFotoOffline({ achadoPkExistente: achadoPk, blob: blob, nome: foto.name });
        } catch {}
      }

      if (window.verificarArmazenamento) window.verificarArmazenamento();

      window.location.href = detalheUrl;
    } catch (err) {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg"></i> Salvar Achado'; }
      alert('Erro ao salvar offline: ' + err.message);
    }
  });
})();
```

- [x] **Step 2: Verificação manual**

Pré-requisito: abra a página de detalhe da inspeção ONLINE pelo menos uma vez (para a aba da especialidade preparar o achado para campo — badge "Pronto offline ✓"). Depois:

1. DevTools → Network → Offline.
2. Abra a edição de um achado já preparado, mude o diagnóstico e adicione 2 fotos novas.
3. Salve. Confirme redirecionamento para o detalhe (servido do cache do SW).
4. DevTools → Application → IndexedDB → `achados_edicao_pendentes` tem 1 item sem fotos embutidas; `fotos_pendentes` tem 2 itens **já com `pk_servidor` preenchido** (o pk do achado editado — diferente da criação, que fica com `pk_servidor: null` até sincronizar).
5. Desmarque Offline, deixe sincronizar, confirme no servidor (`/achados/<pk>/`) que o diagnóstico mudou e as 2 fotos novas aparecem.

Expected: fotos da edição não esperam nenhuma promoção — vão para sincronização assim que houver rede, mesmo que o texto da edição ainda esteja tentando (fases independentes, ADR-01).

- [x] **Step 3: Commit**

```bash
git add src/apps/inspecoes/templates/inspecoes/achado_form.html
git commit -m "feat: compressao client-side e fila de fotos separada na edicao offline de achado"
```

---

## Task 7: pwa.js — alerta de armazenamento quase cheio

**Files:**
- Modify: `src/static/js/pwa.js` (nova função, exports, listener de `DOMContentLoaded`)

- [x] **Step 1: Adicionar `verificarArmazenamento`**

Em `src/static/js/pwa.js`, logo após a seção da fila de fotos pendentes (depois de `contarFotosPendentes`, antes de `// ── Retry com backoff`), insira:

```javascript
// ── Alerta de armazenamento quase cheio ─────────────────────────────────────
// Mesmo com fotos comprimidas (~200-500KB cada), uma sessão de campo muito
// longa em um tablet com pouco espaço livre pode se aproximar da cota do
// navegador. Aviso não bloqueia nada — só orienta a sincronizar mais cedo.
const ARMAZENAMENTO_LIMIAR = 0.8;

async function verificarArmazenamento() {
  if (!('storage' in navigator) || !navigator.storage.estimate) return;
  try {
    const { usage, quota } = await navigator.storage.estimate();
    if (quota && usage / quota > ARMAZENAMENTO_LIMIAR) {
      mostrarAvisoArmazenamento();
    }
  } catch { /* API indisponível neste navegador — ignora */ }
}

function mostrarAvisoArmazenamento() {
  if (document.getElementById('aviso-armazenamento')) return; // já exibido
  const banner = document.getElementById('banner-offline');
  if (!banner || !banner.parentNode) return;
  const div = document.createElement('div');
  div.id = 'aviso-armazenamento';
  div.className = 'alert alert-warning mb-0 rounded-0 text-center py-2 small no-print';
  div.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Armazenamento do dispositivo quase cheio — sincronize assim que tiver sinal.';
  banner.parentNode.insertBefore(div, banner.nextSibling);
}
```

- [x] **Step 2: Chamar na carga da página e exportar para os templates**

Em `src/static/js/pwa.js`, localize o listener `DOMContentLoaded`:

```javascript
document.addEventListener('DOMContentLoaded', async () => {
  await atualizarBannerOffline();
  // App reaberto já online com pendências (ex.: foi fechado offline): sincroniza.
  if (navigator.onLine && (await haPendencias())) window.pwaSync();
});
```

Substitua por:

```javascript
document.addEventListener('DOMContentLoaded', async () => {
  await atualizarBannerOffline();
  verificarArmazenamento();
  // App reaberto já online com pendências (ex.: foi fechado offline): sincroniza.
  if (navigator.onLine && (await haPendencias())) window.pwaSync();
});
```

No final do arquivo, localize:

```javascript
// ── Exportar para uso nos formulários ─────────────────────────────────────────
window.salvarAchadoOffline = salvarAchadoOffline;
window.salvarEdicaoOffline = salvarEdicaoOffline;
window.obterAchadoPreparado = obterAchadoPreparado;
```

Substitua por:

```javascript
// ── Exportar para uso nos formulários ─────────────────────────────────────────
window.salvarAchadoOffline = salvarAchadoOffline;
window.salvarEdicaoOffline = salvarEdicaoOffline;
window.obterAchadoPreparado = obterAchadoPreparado;
window.comprimirFoto = comprimirFoto;
window.salvarFotoOffline = salvarFotoOffline;
window.verificarArmazenamento = verificarArmazenamento;
```

- [x] **Step 2: Verificação manual**

No Console do navegador, com a página carregada:

```javascript
navigator.storage.estimate().then(e => console.log((e.usage / e.quota * 100).toFixed(1) + '%'));
```

Confirme que roda sem erro (o valor real de uso não importa para o teste — normalmente estará bem abaixo de 80%). Para simular o aviso disparando sem preencher 80% de cota real, rode manualmente:

```javascript
mostrarAvisoArmazenamento();
```

Expected: uma faixa amarela aparece logo abaixo do banner offline, com o texto de aviso. Recarregue a página para que ela suma (só é criada dinamicamente).

- [x] **Step 3: Commit**

```bash
git add src/static/js/pwa.js
git commit -m "feat: alerta proativo de armazenamento quase cheio no PWA offline"
```

---

## Task 8: Verificação manual fim-a-fim (cenário de subsolo)

**Files:** nenhum (só verificação)

- [x] **Step 1: Preparar o cenário**

Rode o servidor (`..\.venv\Scripts\python.exe manage.py runserver` de dentro de `src\`). Crie (ou reutilize) uma inspeção com uma especialidade. Abra o detalhe da inspeção **online** para que a aba prepare a especialidade para campo (badge "Pronto offline ✓").

- [x] **Step 2: Simular alto volume, offline**

DevTools → Network → Offline. Crie **10 achados** (representando uma fração da escala real de ~30-60 relatada), cada um com **3 fotos** (JPEG/PNG reais de alguns MB, para testar a compressão de verdade — fotos tiradas com celular e transferidas para o notebook servem bem). Edite **2 achados pré-existentes** offline, adicionando 1 foto nova a cada um.

- [x] **Step 3: Conferir o estado local antes de sincronizar**

DevTools → Application → IndexedDB → `inspecoes-offline`:
- `achados_pendentes`: 10 itens.
- `achados_edicao_pendentes`: 2 itens.
- `fotos_pendentes`: 32 itens (10×3 da criação, com `pk_servidor: null`; 2×1 da edição, com `pk_servidor` já preenchido).

Confira o tamanho de alguns blobs em `fotos_pendentes` — devem estar na faixa de 200-500KB, não nos vários MB originais.

- [x] **Step 4: Sincronizar e observar o banner**

Desmarque Offline. Observe o banner passar por: "Sincronizando achados offline..." → (se algo demorar) mensagem intermediária com contagem separada de achados/fotos → mensagem final de sucesso com contagem de achados **e** fotos.

- [x] **Step 5: Conferir o resultado no servidor**

No admin (`/admin/inspecoes/achado/` e `/admin/inspecoes/foto/`), confirme: 10 novos achados, cada um com 3 fotos (30 fotos novas); 2 achados editados com o diagnóstico atualizado e 1 foto nova cada (2 fotos); total 32 fotos novas. `fotos_pendentes` e `achados_pendentes`/`achados_edicao_pendentes` devem estar vazios no IndexedDB após o sucesso.

- [x] **Step 6: Testar o caso de rede instável (retry)**

Repita a criação de 3 achados com fotos offline. Antes de desmarcar "Offline" no DevTools, mude para "Slow 3G" ao invés de "Offline" (simula sinal fraco, não ausência total) e desmarque "Offline". Observe no Console (Network tab) se alguma requisição falha e é re-tentada — não deve haver itens marcados como "erro" só por causa da lentidão, graças ao `fetchComRetry`.

- [x] **Step 7: Confirmar o achado final no design doc**

Marque a seção "Riscos em aberto" do design doc como parcialmente mitigada — anote no achado de acompanhamento (se houver) ou apenas confirme verbalmente com o usuário que o teste de volume foi satisfatório antes de considerar o trabalho pronto para o próximo campo real.

Nenhum commit neste task — é validação, não código.
