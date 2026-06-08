# Módulo de Visitas Técnicas — Design

**Data:** 2026-06-08
**Projeto:** Inspeções Prediais MPDFT
**Status:** Aprovado para planejamento

---

## 1. Objetivo

Adicionar ao sistema um módulo para **registro de visitas técnicas**, convivendo
com o módulo de inspeções prediais já existente. Cada visita é organizada por
**localidade** (edificação já cadastrada) e consultável com **filtro por data**.

Cada visita registra: data, local, responsável, motivo, achados (texto livre),
fotos e conclusões/encaminhamentos.

---

## 2. Decisões de design (definidas no brainstorming)

| Tema | Decisão |
|---|---|
| Achados da visita | **Texto livre** (um campo único), não estruturado como o achado de inspeção |
| Responsável e permissão | Registra um **profissional responsável**; só ele (ou staff/superusuário) edita/exclui |
| Relatório/PDF | **Não** por enquanto — apenas registrar e consultar na tela |
| Navegação | **Escolhe a localidade primeiro**, depois vê as visitas daquela localidade |
| Estrutura | **Sem novo app Django** — tudo dentro do app `inspecoes` |
| Página inicial | Vira um **menu** com escolha entre "Inspeção Predial" e "Visita Técnica" |
| Fotos | No nível da **visita** (não por achado), upload na criação, com câmera no mobile |

---

## 3. Arquitetura

Todo o código vive no app existente `apps.inspecoes`, seguindo os padrões já
estabelecidos (login obrigatório, Bootstrap 5, fotos com câmera no mobile,
registro no `LogAcesso`, segurança por nome do responsável).

### 3.1 Página inicial (novo menu)

Hoje a raiz `/` abre a lista de inspeções. Passa a abrir uma **tela de escolha**
com dois cartões:

- **Inspeção Predial** → lista de inspeções (movida para `/inspecoes/`)
- **Visita Técnica** → tela de visitas (`/visitas/`)

A barra de navegação superior ganha atalhos para os dois módulos. Nada das
inspeções é removido — apenas reorganizado sob o novo menu.

> Impacto: o nome de URL `inspecoes:list` é mantido (apenas o `path` muda de `''`
> para `'inspecoes/'`), então os `{% url 'inspecoes:list' %}` existentes continuam
> válidos. `LOGIN_REDIRECT_URL = '/'` passa a cair na nova home.

---

## 4. Modelo de dados

Adicionados em `apps/inspecoes/models.py`.

### 4.1 `VisitaTecnica`

| Campo | Tipo | Observação |
|---|---|---|
| `edificacao` | FK → `edificacoes.Edificacao` (PROTECT) | A localidade |
| `data_visita` | DateField | Data da visita (não pode ser futura) |
| `responsavel` | CharField(200) | Nome do profissional; pré-preenchido com o usuário logado |
| `motivo` | TextField | Motivo da visita |
| `achados` | TextField | Texto livre — o que foi observado |
| `conclusoes_encaminhamentos` | TextField | Conclusões e encaminhamentos |
| `criado_por` | FK → User (SET_NULL, null=True) | Auditoria |
| `criado_em` | DateTimeField(auto_now_add) | |
| `atualizado_em` | DateTimeField(auto_now) | |

- `Meta.ordering = ['-data_visita', '-criado_em']`
- `clean()`: `data_visita` não pode ser futura (mesma validação de
  `InspecaoEspecialidade`).

### 4.2 `VisitaFoto`

Espelha o modelo `Foto` das inspeções.

| Campo | Tipo |
|---|---|
| `visita` | FK → `VisitaTecnica` (CASCADE, related_name='fotos') |
| `arquivo` | ImageField (upload para `visitas/AAAA/MM/<visita_id>/<uuid>.<ext>`) |
| `nome_original` | CharField(255) |
| `tamanho_bytes` | IntegerField |
| `data_upload` | DateTimeField(auto_now_add) |

### 4.3 `LogAcesso`

Adicionar dois tipos ao `TIPO_CHOICES` existente:
- `('visita_criada', 'Visita técnica criada')`
- `('visita_excluida', 'Visita técnica excluída')`

> Alteração de `choices` gera migração (alteração de campo), mas é um no-op no
> banco.

---

## 5. Navegação e telas

```
/                                   → Menu: "Inspeção Predial" | "Visita Técnica"

/inspecoes/                         → (atual) lista de inspeções prediais

/visitas/                           → Lista de LOCALIDADES (todas as edificações
                                      ativas) com a contagem de visitas de cada uma
   └─ clica numa localidade
/visitas/localidade/<edif_pk>/      → Lista das visitas DAQUELA localidade,
                                      com filtro por data (de / até) e botão
                                      "Nova Visita"
        ├─ /visitas/localidade/<edif_pk>/nova/  → formulário de criação
        └─ clica numa visita
/visitas/<pk>/                      → Detalhe (todos os campos + galeria de fotos)
        ├─ /visitas/<pk>/editar/    → edição
        └─ /visitas/<pk>/excluir/   → exclusão (POST)
```

A tela de localidades lista **todas as edificações ativas**, mesmo as sem visita,
para permitir registrar a primeira visita de qualquer local.

### 5.1 Templates novos
- `home.html` — menu com os dois cartões
- `visita_localidades.html` — lista de localidades + contagem
- `visita_list.html` — visitas de uma localidade + filtro por data
- `visita_form.html` — criação/edição (com seção de fotos)
- `visita_detail.html` — visualização completa

### 5.2 `base.html`
Atalhos no menu superior para "Inspeções" (`/inspecoes/`) e "Visitas" (`/visitas/`).

---

## 6. Segurança

- Qualquer usuário **logado** cria e visualiza visitas.
- **Editar/excluir**: somente o **responsável**
  (`request.user.get_full_name() == visita.responsavel`) ou **staff/superusuário**.
  Reaproveita a mesma lógica de `_pode_editar_especialidade` / template guard já
  usada nas inspeções.

---

## 7. Log de acesso

Registrar via helper `_log()` existente:
- `visita_criada` — ao criar uma visita
- `visita_excluida` — ao excluir uma visita

Formato de descrição consistente com os logs atuais (inclui localidade e
responsável).

---

## 8. Fotos

- **Na criação**: campo de upload com botões **Câmera** (`capture="environment"`
  para câmera traseira no mobile) e **Galeria**, com pré-visualização — idêntico
  ao `achado_form.html` atual. As fotos são enviadas junto com o formulário.
- **Na edição**: adicionar novas fotos e excluir existentes via AJAX (mesmo
  padrão de `foto_upload` / `foto_delete`).
- **Validação**: JPEG/PNG, máx. 10 MB (constantes `ALLOWED_CONTENT_TYPES` e
  `MAX_UPLOAD_SIZE` já existentes).

---

## 9. Arquivos afetados (todos no app `inspecoes`)

| Arquivo | Mudança |
|---|---|
| `models.py` | `VisitaTecnica`, `VisitaFoto`, +2 tipos no `LogAcesso` |
| `forms.py` | `VisitaTecnicaForm` (e filtro de data, se necessário) |
| `views.py` | `home`, `visita_localidades`, `visita_list`, `visita_create`, `visita_detail`, `visita_update`, `visita_delete`, `visita_foto_upload`, `visita_foto_delete` |
| `urls.py` | novas rotas + `home` na raiz + mover lista de inspeções p/ `/inspecoes/` |
| `admin.py` | registrar `VisitaTecnica` e `VisitaFoto` |
| templates | `home.html`, `visita_localidades.html`, `visita_list.html`, `visita_form.html`, `visita_detail.html`; ajuste em `base.html` |
| migração | nova (modelos + choices do log) |

---

## 10. Backups

Sem ação necessária: o backup automático diário e o ZIP por inspeção já copiam
`db.sqlite3` e a pasta `media/` por completo, de modo que as visitas e suas fotos
entram nos backups automaticamente.

---

## 11. Testes

- **pytest-django** (já presente):
  - criação de visita com campos válidos
  - validação de `data_visita` futura
  - regra de permissão: responsável edita/exclui; outro usuário comum é barrado;
    staff consegue
  - filtro por data na lista da localidade
  - upload de foto vinculada à visita
- **Verificação**: `manage.py check` sem erros e um teste rápido do fluxo no
  navegador (escolher módulo → localidade → nova visita → detalhe).

---

## 12. Fora de escopo (YAGNI)

- Geração de PDF / impressão da visita (pode ser adicionado depois).
- Achados estruturados com matriz GUT para visitas.
- Vínculo entre visita técnica e inspeção predial.
- Modo PWA offline para o formulário de visita (avaliar futuramente).
