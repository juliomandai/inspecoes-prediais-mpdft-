---
description: "Task list for Sistema de Registro de Achados de Inspeção Predial"
---

# Tasks: Sistema de Registro de Achados de Inspeção Predial

**Input**: Design documents from `specs/001-registro-achados/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/routes.md ✅

**Tests**: Not requested — no test tasks generated.

**Stack**: Python 3.11 · Django 4.2 LTS · Bootstrap 5 · SQLite/PostgreSQL · Waitress

**Organization**: Tasks grouped by user story for independent delivery.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: Maps to user story from spec.md (US1, US2, US3)
- File paths relative to repository root

## Path Conventions

- Django project config: `src/mpdft_inspecoes/`
- App sources: `src/apps/<app>/`
- Templates: `src/apps/<app>/templates/<app>/` and `src/templates/`
- Static files: `src/static/`
- Media (photos): `src/media/` (gitignored)
- Management commands: `src/apps/management/commands/`

---

## Phase 1: Setup

**Purpose**: Project initialization and base structure

- [X] T001 Create full directory tree as per plan.md: `src/mpdft_inspecoes/`, `src/apps/edificacoes/`, `src/apps/inspecoes/`, `src/apps/management/commands/`, `src/templates/registration/`, `src/static/js/`, `src/static/css/`, `src/media/`, `tests/`
- [X] T002 Initialize Django project: `django-admin startproject mpdft_inspecoes src/` — produces `src/manage.py` and `src/mpdft_inspecoes/` with settings.py, urls.py, wsgi.py
- [X] T003 [P] Create `src/requirements.txt` with pinned versions: `Django==4.2.*`, `Pillow`, `python-decouple`, `waitress`, `pytest-django`
- [X] T004 [P] Create `.env.example` at project root with all variables: `SECRET_KEY`, `DEBUG=True`, `DATABASE_URL=sqlite:///db.sqlite3`, `MEDIA_ROOT`, `ALLOWED_HOSTS=localhost,127.0.0.1`
- [X] T005 [P] Configure `src/mpdft_inspecoes/settings.py`: load all values from `.env` via python-decouple; set `INSTALLED_APPS`, `TEMPLATES` with `APP_DIRS=True`, `DATABASES` from `DATABASE_URL`, `MEDIA_ROOT`/`MEDIA_URL`, `STATIC_URL`, `LOGIN_URL='/login/'`, `LOGIN_REDIRECT_URL='/'`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required before any user story can be built

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create Django apps: run `python manage.py startapp edificacoes src/apps/edificacoes` and `python manage.py startapp inspecoes src/apps/inspecoes`; register both in `INSTALLED_APPS` in `src/mpdft_inspecoes/settings.py`
- [X] T007 [P] Create `src/templates/base.html`: Bootstrap 5 via CDN, responsive navbar with project name and login/logout link (conditional on `request.user.is_authenticated`), `{% block content %}`, django messages display with Bootstrap alert classes
- [X] T008 Create `src/templates/registration/login.html`: extends base.html; username + password form fields with CSRF token; error message display; submit button "Entrar"
- [X] T009 Configure `src/mpdft_inspecoes/urls.py`: include `django.contrib.auth.urls` (login/logout), `apps.edificacoes.urls` with `namespace='edificacoes'`, `apps.inspecoes.urls` with `namespace='inspecoes'`; serve `MEDIA_URL` in `DEBUG` mode via `static()`
- [X] T010 [P] Create `src/apps/management/__init__.py` and `src/apps/management/commands/__init__.py`; add `'apps.management'` to `INSTALLED_APPS`

**Checkpoint**: Base project runs (`python manage.py runserver`), login page accessible at `/login/`

---

## Phase 3: User Story 1 — Registrar nova inspeção com achados completos (Priority: P1) ⭐ MVP

**Goal**: Servidor da SPO cria uma nova inspeção, preenche achados com todos os campos técnicos (incluindo GUT automático e análise de risco), faz upload de fotos, e visualiza o resultado.

**Independent Test**: Criar inspeção → adicionar achado com G=4, U=3, T=5 (GUT=60) → fazer upload de uma foto → verificar que o índice GUT=60 foi persistido, a foto aparece vinculada ao achado e a inspeção aparece na lista.

### Edificacao — modelo e administração (pré-requisito do formulário de inspeção)

- [X] T011 [P] [US1] Create `Edificacao` model in `src/apps/edificacoes/models.py`: fields `id` (PK auto), `nome` (CharField 200, unique), `endereco` (TextField 500, blank=True), `ativo` (BooleanField default=True), `criado_em` (DateTimeField auto_now_add); `__str__` returns `nome`; `Meta.ordering = ['nome']`
- [X] T012 [US1] Create and apply migration for Edificacao: `python manage.py makemigrations edificacoes` → `python manage.py migrate`
- [X] T013 [P] [US1] Create `EdificacaoForm` in `src/apps/edificacoes/forms.py`: fields `nome`, `endereco`; `clean_nome()` validates uniqueness case-insensitive (excluding current instance on update)
- [X] T014 [P] [US1] Create edificacoes views in `src/apps/edificacoes/views.py`: `EdificacaoListView` (ListView, `@staff_member_required`), `EdificacaoCreateView` (CreateView, `@staff_member_required`, success_url to list), `EdificacaoUpdateView` (UpdateView, `@staff_member_required`, success_url to list)
- [X] T015 [P] [US1] Create `src/apps/edificacoes/urls.py` (app_name='edificacoes'): `path('edificacoes/', ListView, name='list')`, `path('edificacoes/nova/', CreateView, name='create')`, `path('edificacoes/<int:pk>/editar/', UpdateView, name='update')`
- [X] T016 [P] [US1] Create `EdificacaoAdmin` in `src/apps/edificacoes/admin.py`: `list_display=['nome','ativo','criado_em']`, `list_filter=['ativo']`, `search_fields=['nome']`, `list_editable=['ativo']`
- [X] T017 [US1] Create edificacoes templates: `src/apps/edificacoes/templates/edificacoes/list.html` (table: nome, endereço, status ativo, link editar; botão "Nova Edificação" para staff) and `src/apps/edificacoes/templates/edificacoes/form.html` (form com campos nome e endereço, submit, link voltar)

### Inspecao — modelo, formulário e views

- [X] T018 [P] [US1] Create `Inspecao` model in `src/apps/inspecoes/models.py`: fields `edificacao` (FK→Edificacao PROTECT), `profissional` (CharField 200), `especialidade` (CharField choices: civil/mecânica/elétrica), `data_inspecao` (DateField), `status` (CharField choices: em_andamento/finalizada, default em_andamento), `criado_em` (auto_now_add), `atualizado_em` (auto_now); `clean()` raises ValidationError if `data_inspecao > date.today()`; property `achados_count` returns `self.achados.count()`
- [X] T019 [US1] Create and apply migration for Inspecao: `python manage.py makemigrations inspecoes` → `python manage.py migrate`
- [X] T020 [P] [US1] Create `InspecaoForm` in `src/apps/inspecoes/forms.py`: `edificacao` as `ModelChoiceField(queryset=Edificacao.objects.filter(ativo=True))`; `profissional` CharField; `especialidade` ChoiceField; `data_inspecao` DateField with `initial=date.today`, `widget=DateInput(type='date')`
- [X] T021 [P] [US1] Create `InspecaoListView` in `src/apps/inspecoes/views.py`: `@login_required`; GET `/`; filters from query params (`edificacao_id`, `data_inicio`, `data_fim`, `especialidade`); `.annotate(num_achados=Count('achados'))`; `order_by('-data_inspecao')`
- [X] T022 [P] [US1] Create `InspecaoCreateView` in `src/apps/inspecoes/views.py`: `@login_required`; GET/POST `/inspecoes/nova/`; on valid save: `status='em_andamento'`, redirect to `InspecaoDetailView`
- [X] T023 [P] [US1] Create `InspecaoDetailView` in `src/apps/inspecoes/views.py`: `@login_required`; GET `/inspecoes/<pk>/`; loads inspection + `prefetch_related('achados__fotos')`; passes `pode_editar = (inspecao.status == 'em_andamento')` to template context
- [X] T024 [P] [US1] Create `InspecaoFinalizarView` in `src/apps/inspecoes/views.py`: `@login_required`; POST `/inspecoes/<pk>/finalizar/`; raises Http404 if not found; returns 400 if already `finalizada`; returns error message if zero achados; sets `status='finalizada'`; redirects to detail
- [X] T025 [P] [US1] Create `src/apps/inspecoes/urls.py` (app_name='inspecoes'): paths for `/`, `inspecoes/nova/`, `inspecoes/<pk>/`, `inspecoes/<pk>/finalizar/`, `inspecoes/<pk>/achados/novo/`, `achados/<pk>/editar/`, `achados/<pk>/fotos/`, `fotos/<pk>/`

### Achado — modelo, formulário e views

- [X] T026 [P] [US1] Add `Achado` model to `src/apps/inspecoes/models.py`: fields from data-model.md (inspecao FK CASCADE, localizacao/200, sub_localizacao/200 blank, verificacao/300, grupo_tecnico choices, descricao_nao_conformidade TextField, requisito_afetado choices, gravidade/urgencia/tendencia IntegerField 1-5, gut_total IntegerField editable=False, prioridade_risco IntegerField choices 1-3, recomendacao TextField, direcionamento choices, prazo_meses IntegerField choices); `save()` sets `gut_total = gravidade * urgencia * tendencia` before calling super; `clean()` validates each of G/U/T between 1-5 and raises PermissionDenied if `self.inspecao.status == 'finalizada'`
- [X] T027 [US1] Create and apply migration for Achado: `python manage.py makemigrations inspecoes` → `python manage.py migrate`
- [X] T028 [P] [US1] Create `AchadoForm` in `src/apps/inspecoes/forms.py`: all required fields; G/U/T as `IntegerField(min_value=1, max_value=5, widget=NumberInput(attrs={'min':1,'max':5}))`; `gut_total` as `IntegerField(widget=HiddenInput(), required=False)`; choices fields use `Select` widgets with labeled option groups
- [X] T029 [P] [US1] Create `AchadoCreateView` and `AchadoUpdateView` in `src/apps/inspecoes/views.py`: both `@login_required`; both raise `PermissionDenied` if `inspecao.status == 'finalizada'`; `CreateView` initializes `inspecao` from URL `pk`; on success redirect to `InspecaoDetailView` with success message

### Foto — modelo, upload e deleção

- [X] T030 [P] [US1] Add `Foto` model to `src/apps/inspecoes/models.py`: `achado` FK CASCADE; `arquivo` ImageField with `upload_to=foto_upload_path` function (returns `fotos/<ano>/<mes>/<achado_id>/<uuid4>.<ext>`); `nome_original` CharField 255; `tamanho_bytes` IntegerField; `data_upload` auto_now_add; `post_delete` signal deletes physical file with `arquivo.storage.delete(arquivo.name)`
- [X] T031 [US1] Create and apply migration for Foto: `python manage.py makemigrations inspecoes` → `python manage.py migrate`
- [X] T032 [P] [US1] Create `FotoUploadView` (POST `/achados/<pk>/fotos/`) and `FotoDeleteView` (DELETE `/fotos/<pk>/`) in `src/apps/inspecoes/views.py`: Upload validates `content_type in ['image/jpeg','image/png']` and `size <= 10MB`; on success returns `JsonResponse({'id':foto.id,'url':foto.arquivo.url,'nome':foto.nome_original})`; Delete returns `HttpResponse(status=204)`; both raise `PermissionDenied` if inspeção `finalizada`

### GUT calculator e admin

- [X] T033 [P] [US1] Create `src/static/js/gut_calculator.js`: listen to `input` events on `#id_gravidade`, `#id_urgencia`, `#id_tendencia`; compute `G * U * T`; display result in element `#gut-display`; show suggested priority based on faixas (75-125 → Crítico, 20-74 → Regular, 1-19 → Mínimo) as informational badge; handle empty/non-numeric inputs by showing `—`
- [X] T034 [P] [US1] Create `InspecaoAdmin` and `AchadoTabularInline` in `src/apps/inspecoes/admin.py`: `AchadoTabularInline(TabularInline)` for Achado; `InspecaoAdmin` with `list_display=['edificacao','profissional','especialidade','status','data_inspecao','criado_em']`, `list_filter=['status','especialidade','edificacao']`, `search_fields=['profissional','edificacao__nome']`, `inlines=[AchadoTabularInline]`

### Templates US1

- [X] T035 [US1] Create `src/apps/inspecoes/templates/inspecoes/list.html`: extends base.html; filter form (edificação select, especialidade select, submit, "Limpar"); table with columns: Edificação, Data, Profissional, Especialidade, Status (Bootstrap badge), Nº Achados, Ação; "Nova Inspeção" button top-right
- [X] T036 [US1] Create `src/apps/inspecoes/templates/inspecoes/form.html`: extends base.html; form with edificação dropdown, profissional text input, especialidade select, data_inspecao date input; submit "Criar Inspeção"; link "Cancelar" back to list
- [X] T037 [US1] Create `src/apps/inspecoes/templates/inspecoes/detail.html`: header card (edificação, data, profissional, especialidade, status badge); achados table (localização, sub-loc, GUT total, prioridade colored badge, direcionamento); conditional buttons: "Adicionar Achado" and "Finalizar Inspeção" (with JS confirm dialog) only when `pode_editar`; each achado row links to edit if `pode_editar`
- [X] T038 [US1] Create `src/apps/inspecoes/templates/inspecoes/achado_form.html`: extends base.html; sections: (1) Localização (localização + sub-localização); (2) Identificação (verificação + grupo técnico); (3) Diagnóstico (descrição + requisito afetado); (4) Matriz GUT (three 1-5 inputs side-by-side + `#gut-display` badge + prioridade select with suggestion); (5) Recomendação (texto + direcionamento select + prazo select); (6) Fotos (upload input multiple + existing fotos grid with delete button per photo); loads `gut_calculator.js`; submit "Salvar Achado"

**Checkpoint**: US1 fully functional — criar inspeção, adicionar achados com GUT automático, upload de fotos, finalizar inspeção, visualizar resultado

---

## Phase 4: User Story 2 — Retomar inspeção em andamento (Priority: P2)

**Goal**: Servidor encontra inspeção em andamento na lista, reabre e continua preenchendo achados onde parou.

**Independent Test**: Criar inspeção + 1 achado → fechar navegador → reabrir sistema → localizar inspeção com badge "Em andamento" → reabrir → verificar achado existente intacto → adicionar segundo achado.

- [X] T039 [P] [US2] Add `status` query-param filter to `InspecaoListView` in `src/apps/inspecoes/views.py`: filter queryset by `status` when param present; add status counts to context (`em_andamento_count`, `finalizada_count`) for display in template
- [X] T040 [US2] Update `src/apps/inspecoes/templates/inspecoes/list.html`: add status filter buttons (Todas / Em andamento / Finalizadas) with active state; color-code status badges (em_andamento=`badge bg-warning text-dark`, finalizada=`badge bg-success`); add "Continuar" quick-action button for rows with `em_andamento` status, linking to `/inspecoes/<id>/`
- [X] T041 [P] [US2] Extend `AchadoUpdateView` in `src/apps/inspecoes/views.py` to pass existing `Foto` queryset (`achado.fotos.all()`) to template context as `fotos_existentes`; handle inline foto deletion via the existing `FotoDeleteView` (JS fetch DELETE call from template)
- [X] T042 [US2] Create `src/apps/inspecoes/templates/inspecoes/achado_edit.html`: same layout as `achado_form.html` but all fields pre-populated from instance; section (6) shows existing fotos grid (thumbnail + "Excluir" button per foto via JS fetch DELETE + DOM removal on success) before upload input; page title "Editar Achado"; GUT calculator active

**Checkpoint**: Em_andamento inspections visually distinct in list; existing findings editable; photos manageable from edit form

---

## Phase 5: User Story 3 — Consultar inspeções registradas (Priority: P3)

**Goal**: Servidor filtra lista de inspeções por múltiplos critérios e visualiza inspeção finalizada com todos os achados e fotos em modo somente leitura.

**Independent Test**: Com ≥3 inspeções de edificações e especialidades distintas, filtrar por edificação específica → verificar que apenas inspeções daquela edificação aparecem; abrir inspeção finalizada → verificar que botões editar/adicionar estão ocultos e achados com fotos são exibidos.

- [X] T043 [P] [US3] Create `InspecaoFilterForm` in `src/apps/inspecoes/forms.py`: fields `edificacao` (ModelChoiceField, optional), `data_inicio` (DateField optional), `data_fim` (DateField optional), `especialidade` (ChoiceField with blank option, optional), `profissional` (CharField optional); all fields `required=False`
- [X] T044 [US3] Integrate `InspecaoFilterForm` into `InspecaoListView` in `src/apps/inspecoes/views.py`: instantiate form with `request.GET`; apply each non-empty filter to queryset; add Django `Paginator(queryset, 20)`; pass `filter_form`, `page_obj`, and `total_count` to context
- [X] T045 [US3] Update `src/apps/inspecoes/templates/inspecoes/list.html`: replace simple filters with full `InspecaoFilterForm` (edificação dropdown, data de/até date inputs, especialidade select, profissional text, "Filtrar" button, "Limpar filtros" link); pagination controls (previous/next, page numbers, total count); current filter summary shown when filters are active
- [X] T046 [US3] Update `src/apps/inspecoes/templates/inspecoes/detail.html` for finalized inspections: when `not pode_editar`, hide "Adicionar Achado" and "Finalizar" buttons; show each achado in an accordion/card with full field details (all fields visible) and fotos as thumbnails with lightbox (`data-bs-toggle="modal"`); add print button (`onclick="window.print()"`) with `@media print` CSS to hide navbar/buttons

**Checkpoint**: Full filter form functional with pagination; finalized inspections viewable in read-only with all photos

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Data retention, error handling, validation and operational readiness

- [X] T047 [P] Create management command `src/apps/management/commands/purge_old_inspecoes.py`: query `Inspecao.objects.filter(data_inspecao__lt=date.today()-timedelta(days=180))`; for each, delete all `Foto` files via `foto.arquivo.delete()`; then delete `Inspecao` (cascades to Achado and Foto records); support `--dry-run` flag that prints count without deleting; print summary at end
- [X] T048 [P] Create `src/templates/404.html` and `src/templates/403.html`: extends base.html; friendly message in Portuguese; large status code display; "Voltar à lista de inspeções" link; register `handler404` and `handler403` in `src/mpdft_inspecoes/urls.py`; set `DEBUG=False` in test to verify
- [X] T049 Create `src/apps/management/commands/carregar_fixture_demo.py`: creates (idempotent) — 1 `Edificacao` named "Sede MPDFT — Bloco A"; 1 `Inspecao` (profissional="Demo SPO", especialidade=civil, data=today, status=em_andamento); 2 `Achado` records with different prioridades (P1 and P3); prints login info and URL to access
- [X] T050 [P] Security configuration in `src/mpdft_inspecoes/settings.py`: set `X_FRAME_OPTIONS='DENY'`, `SECURE_CONTENT_TYPE_NOSNIFF=True`; verify all POST forms have `{% csrf_token %}`; set `FILE_UPLOAD_MAX_MEMORY_SIZE=10485760` (10 MB); add note in quickstart.md that in production `DEBUG=False` and `MEDIA` files must be served by a reverse proxy (Nginx/IIS), not Django
- [X] T051 Run quickstart.md validation: follow all steps end-to-end — install deps in venv, apply migrations, create superuser, run `carregar_fixture_demo`, login, create new inspection, add finding with G=5/U=4/T=3 (GUT=60), upload photo, verify GUT=60 displayed, verify photo appears, finalize inspection, verify read-only mode, apply filters in list. Validated 2026-06-23 via automated Playwright run against the current schema (Inspecao → InspecaoEspecialidade → Achado, introduced after this task was written): login, create inspeção, add especialidade, add achado (GUT=60 confirmed both in form and detail page), upload photo (thumbnail confirmed), finalize especialidade (read-only confirmed — "Novo Achado" hidden), filter list by status. Found and fixed a stale bug in `carregar_fixture_demo` (referenced removed `Inspecao.especialidade`/`profissional` fields from before the multi-especialidade refactor); full test suite (110 tests) still passes after the fix.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2; within US1: T011→T012→T013 (Edificacao must exist before Inspecao form), T018→T019→T020 (model before migration before form), T025→T026→T028 (Achado model before migration before views), T029→T030→T031 (Foto after Achado)
- **US2 (Phase 4)**: Depends on US1 completion — AchadoUpdateView must exist (T029) before extending it (T041)
- **US3 (Phase 5)**: Depends on US1 completion — InspecaoListView (T021) must exist before adding full filter (T044)
- **Polish (Phase N)**: Depends on all user stories complete

### Within US1 — critical sequence

```
T011 (Edificacao model) → T012 (migrate) → T013, T014, T015, T016 [parallel]
T017 (templates) depends on T014, T015
T018 (Inspecao model) → T019 (migrate) → T020, T021, T022, T023, T024 [parallel]
T025 (Achado model) → T026 (migrate) → T027, T028 [parallel]
T029 (Foto model) → T030 (migrate) → T031 (migrate) → T032 [parallel with T033]
T035, T036, T037, T038 (templates) → after respective views exist
```

### User Story Independence

- **US1 (P1)**: Can start after Phase 2 — no dependency on US2 or US3
- **US2 (P2)**: Depends on US1 (extends existing views and templates)
- **US3 (P3)**: Depends on US1 (extends InspecaoListView and detail template)
- US2 and US3 can be developed in parallel after US1 is complete

---

## Parallel Example: US1 Achado Phase

```bash
# After T019 (Inspecao migration applied), launch in parallel:
Task: "Create AchadoForm in src/apps/inspecoes/forms.py"  (T028)
Task: "Add Achado model to src/apps/inspecoes/models.py"  (T026, then T027 sequentially)

# After T027 (Achado migration applied), launch in parallel:
Task: "Create AchadoCreateView and AchadoUpdateView"      (T029)
Task: "Add Foto model to src/apps/inspecoes/models.py"    (T030)
Task: "Create gut_calculator.js"                          (T033)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — **CRITICAL, blocks everything**
3. Complete Phase 3: US1 in sequence (Edificacao → Inspecao → Achado → Foto → Templates)
4. **STOP and VALIDATE**: Create inspection, add finding, upload photo, verify GUT, finalize
5. Demo to SPO team if ready

### Incremental Delivery

1. Setup + Foundational → base project runs
2. US1 complete → Core inspection registration works (MVP — demo ready)
3. US2 complete → Save/resume flow verified
4. US3 complete → Full filter and readonly view
5. Polish complete → Data retention, error pages, production hardening

---

## Notes

- `[P]` tasks operate on different files with no blocking dependencies — safe to run concurrently
- `[Story]` label maps task to its user story for traceability
- Migrations must be applied sequentially (model → makemigrations → migrate) before dependent models can be created
- GUT total is always computed server-side in `Achado.save()`; the JS calculator is display-only
- `purge_old_inspecoes` command must be scheduled in Windows Task Scheduler before go-live
- Institutional approval for database use must be obtained from Júlio Mandai (SPO) before production deploy
- Stop at each user story checkpoint to validate independence before proceeding
