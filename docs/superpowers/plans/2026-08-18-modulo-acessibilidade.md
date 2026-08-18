# Módulo de Acessibilidade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar o painel de acessibilidade (hoje um Artifact HTML autônomo com `window.storage`) para um módulo Django real dentro da plataforma de inspeções, com banco de dados persistente, histórico de edições e edição multiusuário.

**Architecture:** Novo app Django (`apps.acessibilidade`), mesmo banco SQLite do projeto, reaproveitando `Edificacao` via FK (campo `sigla` novo). Quatro models: `LocalAcessibilidade` e `CriterioAcessibilidade` (catálogos), `Avaliacao` (agregado — status + plano de ação num único registro editável), `AvaliacaoHistorico` (snapshot completo antes/depois de cada edição). Sem PWA/offline — views Django convencionais, autenticação via login já existente.

**Tech Stack:** Django 5.2, SQLite, pytest-django, Bootstrap 5 (templates), csv (stdlib) para exportação.

**Referências:** design em `docs/superpowers/specs/2026-08-18-modulo-acessibilidade-design.md`, ADRs em `docs/adr/2026-08-18-acessibilidade-*.md`, glossário em `docs/grilling/acessibilidade-glossary.md`.

---

### Task 1: Campo `sigla` em `Edificacao`

**Files:**
- Modify: `src/apps/edificacoes/models.py`
- Create: `src/apps/edificacoes/migrations/0002_edificacao_sigla.py`
- Modify: `src/apps/edificacoes/admin.py`
- Test: `src/apps/edificacoes/test_sigla.py`

- [ ] **Step 1: Write the failing test**

```python
# src/apps/edificacoes/test_sigla.py
import pytest
from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_sigla_eh_opcional_e_unica():
    Edificacao.objects.create(nome='Prédio A', sigla='AAAA')
    with pytest.raises(Exception):
        Edificacao.objects.create(nome='Prédio B', sigla='AAAA')


@pytest.mark.django_db
def test_sigla_pode_ficar_em_branco():
    e = Edificacao.objects.create(nome='Prédio Sem Sigla')
    assert e.sigla is None


@pytest.mark.django_db
def test_migracao_atribui_siglas_conhecidas():
    Edificacao.objects.all().delete()
    a = Edificacao.objects.create(nome='Sede MPDFT — Bloco A')
    b = Edificacao.objects.create(nome='Promotoria de Justiça da Defesa da Infância e Juventude')
    Edificacao.objects.filter(nome='Sede MPDFT — Bloco A').update(sigla='BSBI')
    Edificacao.objects.filter(nome='Promotoria de Justiça da Defesa da Infância e Juventude').update(sigla='PJIJ')
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.sigla == 'BSBI'
    assert b.sigla == 'PJIJ'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes/test_sigla.py -v`
Expected: FAIL — `Edificacao() got unexpected keyword arguments: 'sigla'`

- [ ] **Step 3: Add the field to the model**

```python
# src/apps/edificacoes/models.py
from django.db import models


class Edificacao(models.Model):
    nome = models.CharField('Nome', max_length=200, unique=True)
    sigla = models.CharField('Sigla', max_length=10, unique=True, null=True, blank=True)
    endereco = models.TextField('Endereço', max_length=500, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Edificação'
        verbose_name_plural = 'Edificações'

    def __str__(self):
        return self.nome
```

- [ ] **Step 4: Generate and apply the migration, with data migration for the two known records**

Run: `cd src && ../.venv/Scripts/python.exe manage.py makemigrations edificacoes`
Expected: `Migrations for 'edificacoes': apps\edificacoes\migrations\0002_edificacao_sigla.py`

Edit the generated migration to add a `RunPython` step for the two existing records (confirmed via shell: `'Sede MPDFT — Bloco A'` and `'Promotoria de Justiça da Defesa da Infância e Juventude'` are the current names in the dev DB):

```python
# src/apps/edificacoes/migrations/0002_edificacao_sigla.py
from django.db import migrations, models


def atribuir_siglas_conhecidas(apps, schema_editor):
    Edificacao = apps.get_model('edificacoes', 'Edificacao')
    mapeamento = {
        'Sede MPDFT — Bloco A': 'BSBI',
        'Promotoria de Justiça da Defesa da Infância e Juventude': 'PJIJ',
    }
    for nome, sigla in mapeamento.items():
        Edificacao.objects.filter(nome=nome).update(sigla=sigla)


def reverter_siglas(apps, schema_editor):
    Edificacao = apps.get_model('edificacoes', 'Edificacao')
    Edificacao.objects.filter(sigla__in=['BSBI', 'PJIJ']).update(sigla=None)


class Migration(migrations.Migration):

    dependencies = [
        ('edificacoes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='edificacao',
            name='sigla',
            field=models.CharField('Sigla', max_length=10, unique=True, null=True, blank=True),
        ),
        migrations.RunPython(atribuir_siglas_conhecidas, reverter_siglas),
    ]
```

Run: `cd src && ../.venv/Scripts/python.exe manage.py migrate edificacoes`
Expected: `Applying edificacoes.0002_edificacao_sigla... OK`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes/test_sigla.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Show sigla in admin**

```python
# src/apps/edificacoes/admin.py
from django.contrib import admin
from .models import Edificacao


@admin.register(Edificacao)
class EdificacaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'sigla', 'ativo', 'criado_em']
    list_filter = ['ativo']
    search_fields = ['nome', 'sigla']
    list_editable = ['ativo']
    ordering = ['nome']
```

- [ ] **Step 7: Commit**

```bash
cd .. && git add src/apps/edificacoes/models.py src/apps/edificacoes/migrations/0002_edificacao_sigla.py src/apps/edificacoes/admin.py src/apps/edificacoes/test_sigla.py
git commit -m "feat: adiciona campo sigla a Edificacao (ADR-01 acessibilidade)"
```

---

### Task 2: Scaffold do app `acessibilidade`

**Files:**
- Create: `src/apps/acessibilidade/__init__.py`
- Create: `src/apps/acessibilidade/apps.py`
- Create: `src/apps/acessibilidade/migrations/__init__.py`
- Create: `src/apps/acessibilidade/urls.py`
- Modify: `src/mpdft_inspecoes/settings.py`
- Modify: `src/mpdft_inspecoes/urls.py`

- [ ] **Step 1: Create the app package**

```python
# src/apps/acessibilidade/__init__.py
```

```python
# src/apps/acessibilidade/apps.py
from django.apps import AppConfig


class AcessibilidadeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.acessibilidade'
    verbose_name = 'Acessibilidade'
```

```python
# src/apps/acessibilidade/migrations/__init__.py
```

```python
# src/apps/acessibilidade/urls.py
from django.urls import path

app_name = 'acessibilidade'

urlpatterns = []
```

- [ ] **Step 2: Register the app**

```python
# src/mpdft_inspecoes/settings.py — dentro de INSTALLED_APPS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.edificacoes',
    'apps.inspecoes',
    'apps.acessibilidade',
    'apps.management',
]
```

- [ ] **Step 3: Include the app's URLs**

```python
# src/mpdft_inspecoes/urls.py
urlpatterns = [
    # ── PWA — service worker e manifest na raiz ───────────────────────────────
    path('sw.js', inspecoes_views.service_worker, name='service_worker'),
    path('manifest.json', inspecoes_views.web_manifest, name='web_manifest'),

    path('admin/', admin.site.urls),
    path('', include('django.contrib.auth.urls')),
    path('', include('apps.inspecoes.urls', namespace='inspecoes')),
    path('', include('apps.edificacoes.urls', namespace='edificacoes')),
    path('', include('apps.acessibilidade.urls', namespace='acessibilidade')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
```

- [ ] **Step 4: Verify the project still checks out clean**

Run: `cd src && ../.venv/Scripts/python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Commit**

```bash
git add src/apps/acessibilidade/__init__.py src/apps/acessibilidade/apps.py src/apps/acessibilidade/migrations/__init__.py src/apps/acessibilidade/urls.py src/mpdft_inspecoes/settings.py src/mpdft_inspecoes/urls.py
git commit -m "feat: scaffold do app acessibilidade"
```

---

### Task 3: Models — `LocalAcessibilidade`, `CriterioAcessibilidade`, `Avaliacao`, `AvaliacaoHistorico`

**Files:**
- Create: `src/apps/acessibilidade/models.py`
- Create: `src/apps/acessibilidade/admin.py`
- Create: `src/apps/acessibilidade/tests/__init__.py`
- Test: `src/apps/acessibilidade/tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/acessibilidade/tests/__init__.py
```

```python
# src/apps/acessibilidade/tests/test_models.py
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import (
    Avaliacao, AvaliacaoHistorico, CriterioAcessibilidade, LocalAcessibilidade, Regiao,
)


@pytest.fixture
def edificacao(db):
    return Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(username='ana', password='1')


@pytest.mark.django_db
def test_local_acessibilidade_str(edificacao):
    local = LocalAcessibilidade.objects.create(
        edificacao=edificacao, regiao=Regiao.SUBSOLO, nome='Rampa 01',
    )
    assert str(local) == 'Prédio Teste — Subsolo — Rampa 01'


@pytest.mark.django_db
def test_local_acessibilidade_e_unico_por_edificacao_regiao_nome(edificacao):
    LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.SUBSOLO, nome='Rampa 01')
    with pytest.raises(IntegrityError):
        LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.SUBSOLO, nome='Rampa 01')


@pytest.mark.django_db
def test_criterio_acessibilidade_nome_unico():
    CriterioAcessibilidade.objects.create(nome='Altura da bacia')
    with pytest.raises(IntegrityError):
        CriterioAcessibilidade.objects.create(nome='Altura da bacia')


@pytest.mark.django_db
def test_avaliacao_agrupa_local_e_criterio(edificacao, usuario):
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    avaliacao = Avaliacao.objects.create(
        local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario,
    )
    assert avaliacao.status_acao == Avaliacao.StatusAcao.NAO_INICIADA
    assert 'Pendente' in str(avaliacao)


@pytest.mark.django_db
def test_avaliacao_e_unica_por_local_e_criterio(edificacao, usuario):
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.OK, atualizado_por=usuario)
    with pytest.raises(IntegrityError):
        Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.OK, atualizado_por=usuario)


@pytest.mark.django_db
def test_avaliacao_historico_guarda_snapshots(edificacao, usuario):
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    avaliacao = Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.OK, atualizado_por=usuario)
    historico = AvaliacaoHistorico.objects.create(
        avaliacao=avaliacao, snapshot_anterior={'status': 'PENDENTE'}, snapshot_novo={'status': 'OK'},
        editado_por=usuario,
    )
    assert avaliacao.historico.count() == 1
    assert historico.snapshot_novo['status'] == 'OK'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.acessibilidade.models'` (ou import error equivalente)

- [ ] **Step 3: Write the models**

```python
# src/apps/acessibilidade/models.py
from django.conf import settings
from django.db import models


class Regiao(models.TextChoices):
    AREA_PUBLICA = 'AREA PÚBLICA', 'Área pública'
    AREA_PUBLICA_ALT = 'ÁREA PÚBLICA', 'Área pública (grafia alternativa)'
    AUDITORIO_RESTAURANTE = 'AUDITORIO E RESTAURANTE', 'Auditório e restaurante'
    INTERIOR_LOTE_DESCOBERTO = 'INTERIOR DO LOTE - DESCOBERTO', 'Interior do lote - descoberto'
    MEZANINO = 'MEZANINO', 'Mezanino'
    PAVIMENTO_01 = 'PAVIMENTO 01', 'Pavimento 01'
    PAVIMENTO_02 = 'PAVIMENTO 02', 'Pavimento 02'
    PAVIMENTO_TIPO = 'PAVIMENTO TIPO', 'Pavimento tipo'
    SUBSOLO = 'SUBSOLO', 'Subsolo'
    SUBSOLO_01 = 'SUBSOLO 01', 'Subsolo 01'
    SUBSOLO_02 = 'SUBSOLO 02', 'Subsolo 02'
    SUBSOLO_1 = 'SUBSOLO 1', 'Subsolo 1'
    SUBSOLO_2 = 'SUBSOLO 2', 'Subsolo 2'
    SUBSOLO_3 = 'SUBSOLO 3', 'Subsolo 3'
    TODOS_OS_PAVIMENTOS = 'TODOS OS PAVIMENTOS', 'Todos os pavimentos'
    TODOS_PAVIMENTOS = 'TODOS PAVIMENTOS', 'Todos pavimentos'
    TERREO = 'TÉRREO', 'Térreo'
    VARIOS_PAVIMENTOS = 'VÁRIOS PAVIMENTOS', 'Vários pavimentos'
    # Nota: alguns valores acima são variações de grafia do mesmo conceito
    # físico (ex. AREA_PUBLICA vs AREA_PUBLICA_ALT, SUBSOLO_1 vs SUBSOLO_01).
    # Preservados como estão no painel original — ver "Riscos em aberto" no
    # design doc. Consolidar é um follow-up de qualidade de dados, não um
    # bloqueio para este módulo entrar em produção.


class LocalAcessibilidade(models.Model):
    edificacao = models.ForeignKey(
        'edificacoes.Edificacao', on_delete=models.PROTECT, related_name='locais_acessibilidade',
        verbose_name='Edificação',
    )
    regiao = models.CharField('Região', max_length=40, choices=Regiao.choices)
    nome = models.CharField('Local', max_length=200)

    class Meta:
        verbose_name = 'Local de acessibilidade'
        verbose_name_plural = 'Locais de acessibilidade'
        ordering = ['edificacao__nome', 'regiao', 'nome']
        unique_together = [('edificacao', 'regiao', 'nome')]

    def __str__(self):
        return f'{self.edificacao.nome} — {self.get_regiao_display()} — {self.nome}'


class CriterioAcessibilidade(models.Model):
    nome = models.CharField('Critério', max_length=300, unique=True)
    base_legal = models.TextField('Base legal', blank=True)

    class Meta:
        verbose_name = 'Critério de acessibilidade'
        verbose_name_plural = 'Critérios de acessibilidade'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Avaliacao(models.Model):
    class Status(models.TextChoices):
        OK = 'OK', 'OK'
        PENDENTE = 'PENDENTE', 'Pendente'
        NAO_SE_APLICA = 'NAO_SE_APLICA', 'Não se aplica'

    class StatusAcao(models.TextChoices):
        NAO_INICIADA = 'NAO_INICIADA', 'Não iniciada'
        EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em andamento'
        CONCLUIDA = 'CONCLUIDA', 'Concluída'

    local = models.ForeignKey(LocalAcessibilidade, on_delete=models.PROTECT, related_name='avaliacoes')
    criterio = models.ForeignKey(CriterioAcessibilidade, on_delete=models.PROTECT, related_name='avaliacoes')

    status = models.CharField('Status', max_length=20, choices=Status.choices)
    resolucao_diagnostico = models.CharField('Resolução (diagnóstico)', max_length=40, blank=True)
    observacao = models.TextField('Observação', blank=True)

    status_acao = models.CharField(
        'Status da ação', max_length=20, choices=StatusAcao.choices, default=StatusAcao.NAO_INICIADA,
    )
    responsavel = models.CharField('Responsável', max_length=200, blank=True)
    prazo = models.DateField('Prazo', null=True, blank=True)
    resolucao_prevista = models.CharField('Resolução prevista', max_length=40, blank=True)
    ordem_servico = models.CharField('Ordem de serviço', max_length=100, blank=True)
    data_os = models.DateField('Data da OS', null=True, blank=True)
    notas = models.TextField('Notas', blank=True)

    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Atualizado por',
    )
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        unique_together = [('local', 'criterio')]

    def __str__(self):
        return f'{self.local} — {self.criterio} — {self.get_status_display()}'


class AvaliacaoHistorico(models.Model):
    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name='historico')
    snapshot_anterior = models.JSONField('Estado anterior')
    snapshot_novo = models.JSONField('Estado novo')
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Editado por',
    )
    editado_em = models.DateTimeField('Editado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de avaliação'
        verbose_name_plural = 'Histórico de avaliações'
        ordering = ['-editado_em']

    def __str__(self):
        return f'{self.avaliacao} em {self.editado_em:%d/%m/%Y %H:%M}'
```

- [ ] **Step 4: Generate and apply the migration**

Run: `cd src && ../.venv/Scripts/python.exe manage.py makemigrations acessibilidade`
Expected: `Migrations for 'acessibilidade': apps\acessibilidade\migrations\0001_initial.py`

Run: `cd src && ../.venv/Scripts/python.exe manage.py migrate acessibilidade`
Expected: `Applying acessibilidade.0001_initial... OK`

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_models.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Register in admin**

```python
# src/apps/acessibilidade/admin.py
from django.contrib import admin
from .models import Avaliacao, AvaliacaoHistorico, CriterioAcessibilidade, LocalAcessibilidade


@admin.register(LocalAcessibilidade)
class LocalAcessibilidadeAdmin(admin.ModelAdmin):
    list_display = ['edificacao', 'regiao', 'nome']
    list_filter = ['edificacao', 'regiao']
    search_fields = ['nome', 'edificacao__nome']


@admin.register(CriterioAcessibilidade)
class CriterioAcessibilidadeAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ['local', 'criterio', 'status', 'status_acao', 'atualizado_por', 'atualizado_em']
    list_filter = ['status', 'status_acao', 'local__edificacao']
    search_fields = ['local__nome', 'criterio__nome']


@admin.register(AvaliacaoHistorico)
class AvaliacaoHistoricoAdmin(admin.ModelAdmin):
    list_display = ['avaliacao', 'editado_por', 'editado_em']
    list_filter = ['editado_por']
    readonly_fields = ['avaliacao', 'snapshot_anterior', 'snapshot_novo', 'editado_por', 'editado_em']
```

- [ ] **Step 7: Commit**

```bash
git add src/apps/acessibilidade/models.py src/apps/acessibilidade/admin.py src/apps/acessibilidade/migrations/0001_initial.py src/apps/acessibilidade/tests/
git commit -m "feat: models do modulo de acessibilidade (Local, Criterio, Avaliacao, Historico)"
```

---

### Task 4: Serviço de edição com histórico (`services.py`)

**Files:**
- Create: `src/apps/acessibilidade/services.py`
- Test: `src/apps/acessibilidade/tests/test_services.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/acessibilidade/tests/test_services.py
import pytest
from django.contrib.auth import get_user_model

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao
from apps.acessibilidade.services import aplicar_edicao, aplicar_edicao_lote


@pytest.fixture
def avaliacao(db):
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    return Avaliacao.objects.create(
        local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario,
    )


@pytest.mark.django_db
def test_aplicar_edicao_atualiza_campos_e_autor(avaliacao):
    novo_usuario = get_user_model().objects.create_user(username='joao', password='1')
    aplicar_edicao(avaliacao, {'status': Avaliacao.Status.OK, 'responsavel': 'João'}, novo_usuario)
    avaliacao.refresh_from_db()
    assert avaliacao.status == Avaliacao.Status.OK
    assert avaliacao.responsavel == 'João'
    assert avaliacao.atualizado_por == novo_usuario


@pytest.mark.django_db
def test_aplicar_edicao_cria_historico_com_snapshots(avaliacao):
    usuario = avaliacao.atualizado_por
    aplicar_edicao(avaliacao, {'status': Avaliacao.Status.OK}, usuario)
    historico = avaliacao.historico.get()
    assert historico.snapshot_anterior['status'] == 'PENDENTE'
    assert historico.snapshot_novo['status'] == 'OK'
    assert historico.editado_por == usuario


@pytest.mark.django_db
def test_aplicar_edicao_ignora_campos_nao_editaveis(avaliacao):
    aplicar_edicao(avaliacao, {'local_id': 999999}, avaliacao.atualizado_por)
    avaliacao.refresh_from_db()
    assert avaliacao.local_id != 999999


@pytest.mark.django_db
def test_aplicar_edicao_lote_cria_um_historico_por_avaliacao(avaliacao, db):
    edificacao = avaliacao.local.edificacao
    criterio2 = CriterioAcessibilidade.objects.create(nome='Outro critério')
    avaliacao2 = Avaliacao.objects.create(
        local=avaliacao.local, criterio=criterio2, status=Avaliacao.Status.PENDENTE,
        atualizado_por=avaliacao.atualizado_por,
    )
    aplicar_edicao_lote([avaliacao, avaliacao2], {'status_acao': Avaliacao.StatusAcao.EM_ANDAMENTO}, avaliacao.atualizado_por)
    avaliacao.refresh_from_db()
    avaliacao2.refresh_from_db()
    assert avaliacao.status_acao == Avaliacao.StatusAcao.EM_ANDAMENTO
    assert avaliacao2.status_acao == Avaliacao.StatusAcao.EM_ANDAMENTO
    assert avaliacao.historico.count() == 1
    assert avaliacao2.historico.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_services.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.acessibilidade.services'`

- [ ] **Step 3: Write the service**

```python
# src/apps/acessibilidade/services.py
from django.db import transaction

CAMPOS_EDITAVEIS = [
    'status', 'resolucao_diagnostico', 'observacao',
    'status_acao', 'responsavel', 'prazo', 'resolucao_prevista',
    'ordem_servico', 'data_os', 'notas',
]


def _snapshot(avaliacao):
    dados = {}
    for campo in CAMPOS_EDITAVEIS:
        valor = getattr(avaliacao, campo)
        dados[campo] = valor.isoformat() if hasattr(valor, 'isoformat') else valor
    return dados


@transaction.atomic
def aplicar_edicao(avaliacao, patch, usuario):
    """Aplica um patch de campos editáveis a uma avaliação, salva, e registra
    um AvaliacaoHistorico imutável com o estado completo antes/depois.
    Único ponto de entrada para editar uma Avaliacao — garante o invariante
    de que toda edição deixa rastro (ADR-05)."""
    from .models import AvaliacaoHistorico

    snapshot_anterior = _snapshot(avaliacao)
    for campo, valor in patch.items():
        if campo in CAMPOS_EDITAVEIS:
            setattr(avaliacao, campo, valor)
    avaliacao.atualizado_por = usuario
    avaliacao.save()
    snapshot_novo = _snapshot(avaliacao)

    AvaliacaoHistorico.objects.create(
        avaliacao=avaliacao,
        snapshot_anterior=snapshot_anterior,
        snapshot_novo=snapshot_novo,
        editado_por=usuario,
    )
    return avaliacao


@transaction.atomic
def aplicar_edicao_lote(avaliacoes, patch, usuario):
    """Aplica o mesmo patch a várias avaliações, cada uma gerando seu próprio
    registro de histórico independente (não um histórico único de lote)."""
    for avaliacao in avaliacoes:
        aplicar_edicao(avaliacao, patch, usuario)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_services.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/apps/acessibilidade/services.py src/apps/acessibilidade/tests/test_services.py
git commit -m "feat: servico de edicao com historico imutavel (ADR-04, ADR-05)"
```

---

### Task 5: Script de extração dos dados do HTML de origem

**Files:**
- Create: `scripts/extrair_dados_painel_acessibilidade.py`

- [ ] **Step 1: Write the extraction script**

```python
# scripts/extrair_dados_painel_acessibilidade.py
"""Extrai o bloco de dados (`<script id="data-holder">`) do HTML do painel de
acessibilidade original e salva como JSON, para ser consumido pelo comando de
importação `importar_painel_acessibilidade`.

Uso:
    python scripts/extrair_dados_painel_acessibilidade.py <caminho_do_html> <caminho_de_saida.json>
"""
import json
import re
import sys


def extrair(caminho_html):
    with open(caminho_html, encoding='utf-8') as f:
        conteudo = f.read()
    m = re.search(
        r'<script id="data-holder" type="application/json">(\{.*?\})</script>',
        conteudo, re.S,
    )
    if not m:
        raise SystemExit('Bloco <script id="data-holder"> não encontrado no HTML.')
    return json.loads(m.group(1))


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Uso: extrair_dados_painel_acessibilidade.py <html> <saida.json>')
    dados = extrair(sys.argv[1])
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False)
    print(f'{len(dados["rows"])} avaliações extraídas para {sys.argv[2]}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run it against the real source file**

Run:
```bash
mkdir -p src/apps/acessibilidade/fixtures
python scripts/extrair_dados_painel_acessibilidade.py "c:\Users\jtman\Downloads\painel-acessibilidade-mpdft (22).html" src/apps/acessibilidade/fixtures/painel_acessibilidade_origem.json
```
Expected: `5137 avaliações extraídas para src/apps/acessibilidade/fixtures/painel_acessibilidade_origem.json`

- [ ] **Step 3: Commit**

```bash
git add scripts/extrair_dados_painel_acessibilidade.py src/apps/acessibilidade/fixtures/painel_acessibilidade_origem.json
git commit -m "feat: script de extracao + fixture com os dados originais do painel de acessibilidade"
```

---

### Task 6: Comando de importação (`importar_painel_acessibilidade`)

**Files:**
- Create: `src/apps/acessibilidade/management/__init__.py`
- Create: `src/apps/acessibilidade/management/commands/__init__.py`
- Create: `src/apps/acessibilidade/management/commands/importar_painel_acessibilidade.py`
- Create: `src/apps/acessibilidade/tests/fixtures/painel_teste.json`
- Test: `src/apps/acessibilidade/tests/test_import_command.py`

- [ ] **Step 1: Create a small test fixture (not the full 5137-row dataset)**

```json
// src/apps/acessibilidade/tests/fixtures/painel_teste.json
{
  "localidades": ["TEST"],
  "regioes": ["TÉRREO"],
  "locals": ["Sanitário Acessível"],
  "itens": ["Altura da bacia", "Barra de apoio"],
  "status": ["Não se aplica", "OK", "Pendente"],
  "resolucoes": ["Contratação", "Manutenção Predial"],
  "rows": [
    [4329, 0, 0, 0, 0, 1, -1, ""],
    [4330, 0, 0, 0, 1, 2, 1, "falta instalar barra"]
  ],
  "details": {
    "4330": {"legal": "NBR 9050/15: 4.9.4 — barras de apoio devem suportar 1,5 kN."}
  },
  "meta": {"buildings_detailed": ["TEST"], "generated_note": "fixture de teste"}
}
```

- [ ] **Step 2: Write the failing test**

```python
# src/apps/acessibilidade/tests/test_import_command.py
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade

FIXTURE = Path(__file__).parent / 'fixtures' / 'painel_teste.json'


@pytest.fixture
def usuario_sistema(db):
    return get_user_model().objects.create_user(username='sistema', password='1')


@pytest.mark.django_db
def test_importa_edificacao_local_criterio_e_avaliacoes(usuario_sistema):
    call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='sistema')

    edificacao = Edificacao.objects.get(sigla='TEST')
    local = LocalAcessibilidade.objects.get(edificacao=edificacao, nome='Sanitário Acessível')
    assert CriterioAcessibilidade.objects.count() == 2
    assert Avaliacao.objects.count() == 2

    avaliacao_ok = Avaliacao.objects.get(local=local, criterio__nome='Altura da bacia')
    assert avaliacao_ok.status == Avaliacao.Status.OK
    assert avaliacao_ok.resolucao_diagnostico == ''

    avaliacao_pendente = Avaliacao.objects.get(local=local, criterio__nome='Barra de apoio')
    assert avaliacao_pendente.status == Avaliacao.Status.PENDENTE
    assert avaliacao_pendente.resolucao_diagnostico == 'Manutenção Predial'
    assert avaliacao_pendente.observacao == 'falta instalar barra'
    assert 'barras de apoio devem suportar' in avaliacao_pendente.criterio.base_legal


@pytest.mark.django_db
def test_importacao_e_idempotente(usuario_sistema):
    call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='sistema')
    call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='sistema')
    assert Avaliacao.objects.count() == 2


@pytest.mark.django_db
def test_falha_com_mensagem_clara_se_usuario_nao_existe(db):
    from django.core.management.base import CommandError
    with pytest.raises(CommandError):
        call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='nao-existe')
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_import_command.py -v`
Expected: FAIL — `Unknown command: 'importar_painel_acessibilidade'`

- [ ] **Step 4: Write the management command**

```python
# src/apps/acessibilidade/management/__init__.py
```

```python
# src/apps/acessibilidade/management/commands/__init__.py
```

```python
# src/apps/acessibilidade/management/commands/importar_painel_acessibilidade.py
"""Importa o diagnóstico de acessibilidade extraído do painel HTML original
para o banco de dados (Edificacao.sigla, LocalAcessibilidade,
CriterioAcessibilidade, Avaliacao).

Idempotente — usa get_or_create, pode ser rodado mais de uma vez sem duplicar.

Uso:
    python manage.py importar_painel_acessibilidade
    python manage.py importar_painel_acessibilidade --arquivo caminho/alternativo.json --usuario ana
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade

FIXTURE_PADRAO = (
    Path(__file__).resolve().parents[3] / 'fixtures' / 'painel_acessibilidade_origem.json'
)

MAPA_STATUS = {
    'OK': Avaliacao.Status.OK,
    'Pendente': Avaliacao.Status.PENDENTE,
    'Não se aplica': Avaliacao.Status.NAO_SE_APLICA,
}


class Command(BaseCommand):
    help = (
        'Importa o diagnóstico de acessibilidade (edificações, locais, '
        'critérios e avaliações) do JSON extraído do painel original.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--arquivo', default=str(FIXTURE_PADRAO))
        parser.add_argument(
            '--usuario', default='sistema',
            help='username do responsável pela carga inicial (deve existir).',
        )

    def handle(self, *args, **options):
        caminho = Path(options['arquivo'])
        if not caminho.exists():
            raise CommandError(f'Arquivo não encontrado: {caminho}')

        User = get_user_model()
        try:
            usuario = User.objects.get(username=options['usuario'])
        except User.DoesNotExist:
            raise CommandError(
                f'Usuário "{options["usuario"]}" não existe. Crie-o antes ou informe --usuario.'
            )

        with open(caminho, encoding='utf-8') as f:
            dados = json.load(f)

        localidades = dados['localidades']
        regioes = dados['regioes']
        locals_ = dados['locals']
        itens = dados['itens']
        status_lista = dados['status']
        resolucoes = dados['resolucoes']
        details = dados.get('details', {})

        with transaction.atomic():
            edificacao_por_indice = self._garantir_edificacoes(localidades)
            criterio_por_indice = {
                indice: CriterioAcessibilidade.objects.get_or_create(nome=nome)[0]
                for indice, nome in enumerate(itens)
            }

            criadas = 0
            for row in dados['rows']:
                row_id, i_loc, i_reg, i_local, i_item, i_status, i_resolucao, obs = row

                edificacao = edificacao_por_indice[i_loc]
                local, _ = LocalAcessibilidade.objects.get_or_create(
                    edificacao=edificacao, regiao=regioes[i_reg], nome=locals_[i_local],
                )

                criterio = criterio_por_indice[i_item]
                detalhe = details.get(str(row_id))
                if detalhe and detalhe.get('legal') and not criterio.base_legal:
                    criterio.base_legal = detalhe['legal']
                    criterio.save(update_fields=['base_legal'])

                status_bruto = status_lista[i_status] if i_status is not None and i_status >= 0 else None
                status_valor = MAPA_STATUS.get(status_bruto, Avaliacao.Status.NAO_SE_APLICA)
                resolucao_valor = (
                    resolucoes[i_resolucao] if i_resolucao is not None and i_resolucao >= 0 else ''
                )

                _, criada = Avaliacao.objects.get_or_create(
                    local=local, criterio=criterio,
                    defaults={
                        'status': status_valor,
                        'resolucao_diagnostico': resolucao_valor,
                        'observacao': obs or '',
                        'atualizado_por': usuario,
                    },
                )
                if criada:
                    criadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'Importação concluída: {len(edificacao_por_indice)} edificações, '
            f'{len(criterio_por_indice)} critérios, {criadas} avaliações criadas.'
        ))

    def _garantir_edificacoes(self, localidades):
        mapa = {}
        for indice, sigla in enumerate(localidades):
            edificacao, _ = Edificacao.objects.get_or_create(sigla=sigla, defaults={'nome': sigla})
            mapa[indice] = edificacao
        return mapa
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_import_command.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full test suite**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add src/apps/acessibilidade/management/ src/apps/acessibilidade/tests/fixtures/ src/apps/acessibilidade/tests/test_import_command.py
git commit -m "feat: comando de importacao do diagnostico de acessibilidade"
```

- [ ] **Step 8: Run the real import (one-time, production data)**

Run: `cd src && ../.venv/Scripts/python.exe manage.py importar_painel_acessibilidade --usuario <seu_username>`
Expected: `Importação concluída: 13 edificações, 217 critérios, 5137 avaliações criadas.`

Depois, revise em `/admin/edificacoes/edificacao/` os nomes das 11 edificações
novas — elas são criadas com `nome=sigla` (ex. "PJBZ") como valor inicial,
porque o comando não tem os nomes completos; renomeie-as para o nome real da
promotoria usando a tela de edição já existente (`edificacoes:update`).

---

### Task 7: Views de leitura — dashboard e listagem com filtros

**Files:**
- Create: `src/apps/acessibilidade/views.py`
- Create: `src/apps/acessibilidade/templates/acessibilidade/dashboard.html`
- Create: `src/apps/acessibilidade/templates/acessibilidade/lista.html`
- Modify: `src/apps/acessibilidade/urls.py`
- Test: `src/apps/acessibilidade/tests/test_views_leitura.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/acessibilidade/tests/test_views_leitura.py
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def cenario(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio_ok = CriterioAcessibilidade.objects.create(nome='Critério OK')
    criterio_pendente = CriterioAcessibilidade.objects.create(nome='Critério Pendente')
    Avaliacao.objects.create(local=local, criterio=criterio_ok, status=Avaliacao.Status.OK, atualizado_por=usuario)
    Avaliacao.objects.create(local=local, criterio=criterio_pendente, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)
    return {'usuario': usuario, 'edificacao': edificacao}


@pytest.mark.django_db
def test_dashboard_exige_login(client):
    resp = client.get(reverse('acessibilidade:dashboard'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_dashboard_mostra_contagem_por_edificacao(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:dashboard'))
    assert resp.status_code == 200
    assert resp.context['stats'][0]['total'] == 2
    assert resp.context['stats'][0]['ok'] == 1
    assert resp.context['stats'][0]['pendente'] == 1


@pytest.mark.django_db
def test_lista_filtra_por_status(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:lista'), {'status': 'PENDENTE'})
    itens = list(resp.context['pagina'].object_list)
    assert len(itens) == 1
    assert itens[0].criterio.nome == 'Critério Pendente'


@pytest.mark.django_db
def test_lista_busca_por_texto(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:lista'), {'q': 'Critério OK'})
    itens = list(resp.context['pagina'].object_list)
    assert len(itens) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_leitura.py -v`
Expected: FAIL — `NoReverseMatch: 'acessibilidade' is not a registered namespace` (ou similar, por falta de rotas)

- [ ] **Step 3: Write the views**

```python
# src/apps/acessibilidade/views.py
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from apps.edificacoes.models import Edificacao
from .models import Avaliacao


def _avaliacoes_filtradas(request):
    qs = Avaliacao.objects.select_related('local', 'local__edificacao', 'criterio')
    edificacao_id = request.GET.get('edificacao')
    regiao = request.GET.get('regiao')
    status = request.GET.get('status')
    busca = request.GET.get('q')
    if edificacao_id:
        qs = qs.filter(local__edificacao_id=edificacao_id)
    if regiao:
        qs = qs.filter(local__regiao=regiao)
    if status:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(
            Q(criterio__nome__icontains=busca)
            | Q(local__nome__icontains=busca)
            | Q(observacao__icontains=busca)
        )
    return qs.order_by('local__edificacao__nome', 'local__regiao', 'local__nome', 'criterio__nome')


@login_required
def dashboard(request):
    stats = (
        Avaliacao.objects.values('local__edificacao__nome', 'local__edificacao_id')
        .annotate(
            total=Count('id'),
            ok=Count('id', filter=Q(status=Avaliacao.Status.OK)),
            pendente=Count('id', filter=Q(status=Avaliacao.Status.PENDENTE)),
            nao_se_aplica=Count('id', filter=Q(status=Avaliacao.Status.NAO_SE_APLICA)),
        )
        .order_by('local__edificacao__nome')
    )
    return render(request, 'acessibilidade/dashboard.html', {'stats': stats})


@login_required
def lista(request):
    qs = _avaliacoes_filtradas(request)
    paginator = Paginator(qs, 30)
    pagina = paginator.get_page(request.GET.get('pagina'))
    edificacoes = (
        Edificacao.objects.filter(locais_acessibilidade__isnull=False).distinct().order_by('nome')
    )
    return render(request, 'acessibilidade/lista.html', {
        'pagina': pagina,
        'edificacoes': edificacoes,
        'status_choices': Avaliacao.Status.choices,
        'query_string': request.GET.urlencode(),
    })
```

- [ ] **Step 4: Wire up the URLs**

```python
# src/apps/acessibilidade/urls.py
from django.urls import path
from . import views

app_name = 'acessibilidade'

urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
]
```

- [ ] **Step 5: Write the templates**

```html
{# src/apps/acessibilidade/templates/acessibilidade/dashboard.html #}
{% extends 'base.html' %}

{% block title %}Acessibilidade — Inspeções Prediais MPDFT{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h2><i class="bi bi-universal-access"></i> Acessibilidade</h2>
  <div>
    <a href="{% url 'acessibilidade:lista' %}" class="btn btn-outline-primary">
      <i class="bi bi-list-check"></i> Ver avaliações
    </a>
    <a href="{% url 'acessibilidade:alertas' %}" class="btn btn-outline-danger">
      <i class="bi bi-exclamation-triangle"></i> Alertas de prazo
    </a>
  </div>
</div>

<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-hover mb-0">
      <thead class="table-light">
        <tr>
          <th>Edificação</th>
          <th class="text-end">Total</th>
          <th class="text-end">OK</th>
          <th class="text-end">Pendente</th>
          <th class="text-end">Não se aplica</th>
        </tr>
      </thead>
      <tbody>
        {% for s in stats %}
        <tr>
          <td class="fw-semibold">
            <a href="{% url 'acessibilidade:lista' %}?edificacao={{ s.local__edificacao_id }}">
              {{ s.local__edificacao__nome }}
            </a>
          </td>
          <td class="text-end">{{ s.total }}</td>
          <td class="text-end text-success">{{ s.ok }}</td>
          <td class="text-end text-danger">{{ s.pendente }}</td>
          <td class="text-end text-muted">{{ s.nao_se_aplica }}</td>
        </tr>
        {% empty %}
        <tr><td colspan="5" class="text-center text-muted py-4">Nenhuma avaliação cadastrada ainda.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

```html
{# src/apps/acessibilidade/templates/acessibilidade/lista.html #}
{% extends 'base.html' %}

{% block title %}Avaliações de Acessibilidade — Inspeções Prediais MPDFT{% endblock %}

{% block content %}
<h2><i class="bi bi-list-check"></i> Avaliações de acessibilidade</h2>

<form method="get" class="row g-2 mb-3">
  <div class="col-auto">
    <select name="edificacao" class="form-select">
      <option value="">Todas as edificações</option>
      {% for e in edificacoes %}
      <option value="{{ e.pk }}" {% if request.GET.edificacao == e.pk|stringformat:'s' %}selected{% endif %}>{{ e.nome }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-auto">
    <select name="status" class="form-select">
      <option value="">Todos os status</option>
      {% for valor, rotulo in status_choices %}
      <option value="{{ valor }}" {% if request.GET.status == valor %}selected{% endif %}>{{ rotulo }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-auto">
    <input type="text" name="q" class="form-control" placeholder="Buscar critério, local, observação..." value="{{ request.GET.q|default:'' }}">
  </div>
  <div class="col-auto">
    <button type="submit" class="btn btn-primary"><i class="bi bi-search"></i> Filtrar</button>
  </div>
</form>

{# Nota: a coluna de ações (editar/lote) e o link de exportação CSV ainda não
   existem nesta versão do template — são adicionados nas Tasks 8, 9 e 10,
   que reescrevem este arquivo. Evita referenciar rotas ({% templatetag openblock %} url ... {% templatetag closeblock %})
   que ainda não foram registradas, o que quebraria a renderização agora. #}
<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-hover mb-0">
      <thead class="table-light">
        <tr>
          <th>Edificação</th>
          <th>Local</th>
          <th>Critério</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {% for a in pagina %}
        <tr>
          <td>{{ a.local.edificacao.nome }}</td>
          <td>{{ a.local.get_regiao_display }} — {{ a.local.nome }}</td>
          <td>{{ a.criterio.nome }}</td>
          <td>
            {% if a.status == 'OK' %}<span class="badge bg-success">OK</span>
            {% elif a.status == 'PENDENTE' %}<span class="badge bg-danger">Pendente</span>
            {% else %}<span class="badge bg-secondary">Não se aplica</span>{% endif %}
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="4" class="text-center text-muted py-4">Nenhuma avaliação encontrada.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<nav class="mt-3">
  <ul class="pagination">
    {% if pagina.has_previous %}
    <li class="page-item"><a class="page-link" href="?{{ query_string }}&pagina={{ pagina.previous_page_number }}">Anterior</a></li>
    {% endif %}
    <li class="page-item disabled"><span class="page-link">Página {{ pagina.number }} de {{ pagina.paginator.num_pages }}</span></li>
    {% if pagina.has_next %}
    <li class="page-item"><a class="page-link" href="?{{ query_string }}&pagina={{ pagina.next_page_number }}">Próxima</a></li>
    {% endif %}
  </ul>
</nav>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_leitura.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Commit**

```bash
git add src/apps/acessibilidade/views.py src/apps/acessibilidade/urls.py src/apps/acessibilidade/templates/ src/apps/acessibilidade/tests/test_views_leitura.py
git commit -m "feat: dashboard e listagem filtravel de avaliacoes de acessibilidade"
```

---

### Task 8: Edição individual de avaliação

**Files:**
- Create: `src/apps/acessibilidade/forms.py`
- Create: `src/apps/acessibilidade/templates/acessibilidade/editar.html`
- Modify: `src/apps/acessibilidade/views.py`
- Modify: `src/apps/acessibilidade/urls.py`
- Test: `src/apps/acessibilidade/tests/test_views_editar.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/apps/acessibilidade/tests/test_views_editar.py
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def avaliacao(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    return Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)


@pytest.mark.django_db
def test_get_editar_mostra_formulario_preenchido(client, avaliacao):
    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:editar', args=[avaliacao.pk]))
    assert resp.status_code == 200
    assert resp.context['form'].initial['status'] == 'PENDENTE'


@pytest.mark.django_db
def test_post_editar_atualiza_e_registra_historico(client, avaliacao):
    outro_usuario = get_user_model().objects.create_user(username='joao', password='1')
    client.force_login(outro_usuario)
    resp = client.post(reverse('acessibilidade:editar', args=[avaliacao.pk]), {
        'status': 'OK',
        'status_acao': 'CONCLUIDA',
        'resolucao_diagnostico': '',
        'observacao': '',
        'responsavel': '',
        'resolucao_prevista': '',
        'ordem_servico': '',
        'notas': '',
    })
    assert resp.status_code == 302
    avaliacao.refresh_from_db()
    assert avaliacao.status == 'OK'
    assert avaliacao.atualizado_por == outro_usuario
    assert avaliacao.historico.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_editar.py -v`
Expected: FAIL — `NoReverseMatch` (rota `acessibilidade:editar` ainda não existe)

- [ ] **Step 3: Write the form**

```python
# src/apps/acessibilidade/forms.py
from django import forms
from .models import Avaliacao


class AvaliacaoEditForm(forms.Form):
    status = forms.ChoiceField(choices=Avaliacao.Status.choices, label='Status')
    resolucao_diagnostico = forms.CharField(max_length=40, required=False, label='Resolução (diagnóstico)')
    observacao = forms.CharField(widget=forms.Textarea, required=False, label='Observação')
    status_acao = forms.ChoiceField(choices=Avaliacao.StatusAcao.choices, label='Status da ação')
    responsavel = forms.CharField(max_length=200, required=False, label='Responsável')
    prazo = forms.DateField(required=False, label='Prazo', widget=forms.DateInput(attrs={'type': 'date'}))
    resolucao_prevista = forms.CharField(max_length=40, required=False, label='Resolução prevista')
    ordem_servico = forms.CharField(max_length=100, required=False, label='Ordem de serviço')
    data_os = forms.DateField(required=False, label='Data da OS', widget=forms.DateInput(attrs={'type': 'date'}))
    notas = forms.CharField(widget=forms.Textarea, required=False, label='Notas')


class AvaliacaoEdicaoLoteForm(forms.Form):
    ids_selecionados = forms.CharField()
    status = forms.ChoiceField(choices=Avaliacao.Status.choices, required=False, label='Status')
    resolucao_diagnostico = forms.CharField(max_length=40, required=False, label='Resolução (diagnóstico)')
    status_acao = forms.ChoiceField(choices=Avaliacao.StatusAcao.choices, required=False, label='Status da ação')
    responsavel = forms.CharField(max_length=200, required=False, label='Responsável')
    prazo = forms.DateField(required=False, label='Prazo')
    resolucao_prevista = forms.CharField(max_length=40, required=False, label='Resolução prevista')
    ordem_servico = forms.CharField(max_length=100, required=False, label='Ordem de serviço')

    def ids_list(self):
        return [int(x) for x in self.cleaned_data['ids_selecionados'].split(',') if x.strip()]

    def patch(self):
        campos = [
            'status', 'resolucao_diagnostico', 'status_acao',
            'responsavel', 'prazo', 'resolucao_prevista', 'ordem_servico',
        ]
        return {c: self.cleaned_data[c] for c in campos if self.cleaned_data.get(c)}
```

- [ ] **Step 4: Add the edit view**

```python
# src/apps/acessibilidade/views.py — adicionar ao final do arquivo
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from .forms import AvaliacaoEditForm
from .services import aplicar_edicao


@login_required
def editar(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk)
    if request.method == 'POST':
        form = AvaliacaoEditForm(request.POST)
        if form.is_valid():
            aplicar_edicao(avaliacao, form.cleaned_data, request.user)
            messages.success(request, 'Avaliação atualizada com sucesso.')
            return redirect('acessibilidade:lista')
    else:
        form = AvaliacaoEditForm(initial={
            'status': avaliacao.status,
            'resolucao_diagnostico': avaliacao.resolucao_diagnostico,
            'observacao': avaliacao.observacao,
            'status_acao': avaliacao.status_acao,
            'responsavel': avaliacao.responsavel,
            'prazo': avaliacao.prazo,
            'resolucao_prevista': avaliacao.resolucao_prevista,
            'ordem_servico': avaliacao.ordem_servico,
            'data_os': avaliacao.data_os,
            'notas': avaliacao.notas,
        })
    return render(request, 'acessibilidade/editar.html', {'form': form, 'avaliacao': avaliacao})
```

- [ ] **Step 5: Add the URL**

```python
# src/apps/acessibilidade/urls.py
from django.urls import path
from . import views

app_name = 'acessibilidade'

urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
    path('acessibilidade/avaliacoes/<int:pk>/editar/', views.editar, name='editar'),
]
```

- [ ] **Step 6: Write the template**

```html
{# src/apps/acessibilidade/templates/acessibilidade/editar.html #}
{% extends 'base.html' %}

{% block title %}Editar avaliação — Inspeções Prediais MPDFT{% endblock %}

{% block content %}
<h2><i class="bi bi-pencil-square"></i> Editar avaliação</h2>
<p class="text-muted">{{ avaliacao.local.edificacao.nome }} — {{ avaliacao.local.get_regiao_display }} — {{ avaliacao.local.nome }} — <strong>{{ avaliacao.criterio.nome }}</strong></p>

<form method="post" class="row g-3">
  {% csrf_token %}
  {% for field in form %}
  <div class="col-md-6">
    <label class="form-label">{{ field.label }}</label>
    {{ field }}
    {% if field.errors %}<div class="text-danger small">{{ field.errors }}</div>{% endif %}
  </div>
  {% endfor %}
  <div class="col-12">
    <button type="submit" class="btn btn-primary"><i class="bi bi-check-lg"></i> Salvar</button>
    <a href="{% url 'acessibilidade:lista' %}" class="btn btn-outline-secondary">Cancelar</a>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_editar.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Commit**

```bash
git add src/apps/acessibilidade/forms.py src/apps/acessibilidade/views.py src/apps/acessibilidade/urls.py src/apps/acessibilidade/templates/acessibilidade/editar.html src/apps/acessibilidade/tests/test_views_editar.py
git commit -m "feat: edicao individual de avaliacao de acessibilidade com historico"
```

---

### Task 9: Edição em lote

**Files:**
- Modify: `src/apps/acessibilidade/views.py`
- Modify: `src/apps/acessibilidade/urls.py`
- Modify: `src/apps/acessibilidade/templates/acessibilidade/lista.html`
- Test: `src/apps/acessibilidade/tests/test_views_editar_lote.py`

- [ ] **Step 1: Write the failing test**

```python
# src/apps/acessibilidade/tests/test_views_editar_lote.py
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def duas_avaliacoes(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    c1 = CriterioAcessibilidade.objects.create(nome='Critério 1')
    c2 = CriterioAcessibilidade.objects.create(nome='Critério 2')
    a1 = Avaliacao.objects.create(local=local, criterio=c1, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)
    a2 = Avaliacao.objects.create(local=local, criterio=c2, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)
    return {'usuario': usuario, 'a1': a1, 'a2': a2}


@pytest.mark.django_db
def test_editar_lote_aplica_a_todos_os_selecionados(client, duas_avaliacoes):
    client.force_login(duas_avaliacoes['usuario'])
    resp = client.post(reverse('acessibilidade:editar_lote'), {
        'ids_selecionados': f"{duas_avaliacoes['a1'].pk},{duas_avaliacoes['a2'].pk}",
        'status_acao': 'EM_ANDAMENTO',
    })
    assert resp.status_code == 302
    duas_avaliacoes['a1'].refresh_from_db()
    duas_avaliacoes['a2'].refresh_from_db()
    assert duas_avaliacoes['a1'].status_acao == 'EM_ANDAMENTO'
    assert duas_avaliacoes['a2'].status_acao == 'EM_ANDAMENTO'
    assert duas_avaliacoes['a1'].historico.count() == 1
    assert duas_avaliacoes['a2'].historico.count() == 1


@pytest.mark.django_db
def test_editar_lote_sem_campos_preenchidos_nao_altera_nada(client, duas_avaliacoes):
    client.force_login(duas_avaliacoes['usuario'])
    resp = client.post(reverse('acessibilidade:editar_lote'), {
        'ids_selecionados': f"{duas_avaliacoes['a1'].pk}",
    })
    assert resp.status_code == 302
    assert duas_avaliacoes['a1'].historico.count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_editar_lote.py -v`
Expected: FAIL — `NoReverseMatch: 'editar_lote'`

- [ ] **Step 3: Add the batch-edit view**

```python
# src/apps/acessibilidade/views.py — adicionar ao final do arquivo
from .forms import AvaliacaoEdicaoLoteForm
from .services import aplicar_edicao_lote


@login_required
def editar_lote(request):
    if request.method != 'POST':
        return redirect('acessibilidade:lista')
    form = AvaliacaoEdicaoLoteForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Não foi possível aplicar a edição em lote: dados inválidos.')
        return redirect('acessibilidade:lista')
    avaliacoes = list(Avaliacao.objects.filter(pk__in=form.ids_list()))
    patch = form.patch()
    if not patch:
        messages.warning(request, 'Nenhum campo preenchido para aplicar em lote.')
        return redirect('acessibilidade:lista')
    aplicar_edicao_lote(avaliacoes, patch, request.user)
    messages.success(request, f'{len(avaliacoes)} avaliações atualizadas.')
    return redirect('acessibilidade:lista')
```

- [ ] **Step 4: Add the URL**

```python
# src/apps/acessibilidade/urls.py
urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
    path('acessibilidade/avaliacoes/<int:pk>/editar/', views.editar, name='editar'),
    path('acessibilidade/avaliacoes/editar-lote/', views.editar_lote, name='editar_lote'),
]
```

- [ ] **Step 5: Fix the batch-edit form field name in the list template**

O template da Task 7 usava o nome de checkbox `id_selecionado` (plural implícito) e não tinha `ids_selecionados` como campo único — ajustar para casar com `AvaliacaoEdicaoLoteForm`:

```html
{# src/apps/acessibilidade/templates/acessibilidade/lista.html — trecho do <form> de edição em lote #}
<form method="post" action="{% url 'acessibilidade:editar_lote' %}" id="form-lote">
  {% csrf_token %}
  <input type="hidden" name="ids_selecionados" id="ids_selecionados">
  <div class="card shadow-sm">
    <div class="table-responsive">
      <table class="table table-hover mb-0">
        <thead class="table-light">
          <tr>
            <th></th>
            <th>Edificação</th>
            <th>Local</th>
            <th>Critério</th>
            <th>Status</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {% for a in pagina %}
          <tr>
            <td><input type="checkbox" class="check-avaliacao" value="{{ a.pk }}"></td>
            <td>{{ a.local.edificacao.nome }}</td>
            <td>{{ a.local.get_regiao_display }} — {{ a.local.nome }}</td>
            <td>{{ a.criterio.nome }}</td>
            <td>
              {% if a.status == 'OK' %}<span class="badge bg-success">OK</span>
              {% elif a.status == 'PENDENTE' %}<span class="badge bg-danger">Pendente</span>
              {% else %}<span class="badge bg-secondary">Não se aplica</span>{% endif %}
            </td>
            <td><a href="{% url 'acessibilidade:editar' a.pk %}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-pencil"></i></a></td>
          </tr>
          {% empty %}
          <tr><td colspan="6" class="text-center text-muted py-4">Nenhuma avaliação encontrada.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <div class="d-flex align-items-center gap-2 mt-3">
    <select name="status_acao" class="form-select w-auto">
      <option value="">— não alterar status da ação —</option>
      <option value="NAO_INICIADA">Não iniciada</option>
      <option value="EM_ANDAMENTO">Em andamento</option>
      <option value="CONCLUIDA">Concluída</option>
    </select>
    <button type="submit" class="btn btn-warning" onclick="return prepararLote()">
      <i class="bi bi-pencil-square"></i> Aplicar aos selecionados
    </button>
  </div>
</form>

<script>
function prepararLote() {
  var selecionados = Array.from(document.querySelectorAll('.check-avaliacao:checked')).map(function(el) { return el.value; });
  if (selecionados.length === 0) {
    alert('Selecione ao menos uma avaliação.');
    return false;
  }
  document.getElementById('ids_selecionados').value = selecionados.join(',');
  return true;
}
</script>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_editar_lote.py apps/acessibilidade/tests/test_views_leitura.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/apps/acessibilidade/views.py src/apps/acessibilidade/urls.py src/apps/acessibilidade/templates/acessibilidade/lista.html src/apps/acessibilidade/tests/test_views_editar_lote.py
git commit -m "feat: edicao em lote de avaliacoes de acessibilidade"
```

---

### Task 10: Exportação CSV

**Files:**
- Modify: `src/apps/acessibilidade/views.py`
- Modify: `src/apps/acessibilidade/urls.py`
- Modify: `src/apps/acessibilidade/templates/acessibilidade/lista.html`
- Test: `src/apps/acessibilidade/tests/test_views_exportar_csv.py`

- [ ] **Step 1: Write the failing test**

```python
# src/apps/acessibilidade/tests/test_views_exportar_csv.py
import csv
import io

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def avaliacao(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    return Avaliacao.objects.create(
        local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE,
        responsavel='João', atualizado_por=usuario,
    )


@pytest.mark.django_db
def test_exportar_csv_retorna_conteudo_correto(client, avaliacao):
    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:exportar_csv'))
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('text/csv')
    linhas = list(csv.reader(io.StringIO(resp.content.decode('utf-8')), delimiter=';'))
    assert linhas[0][0] == 'Edificação'
    assert linhas[1][0] == 'Prédio Teste'
    assert linhas[1][7] == 'João'


@pytest.mark.django_db
def test_exportar_csv_respeita_filtro_de_status(client, avaliacao):
    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:exportar_csv'), {'status': 'OK'})
    linhas = list(csv.reader(io.StringIO(resp.content.decode('utf-8')), delimiter=';'))
    assert len(linhas) == 1  # só o cabeçalho, nenhuma avaliação OK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_exportar_csv.py -v`
Expected: FAIL — `NoReverseMatch: 'exportar_csv'`

- [ ] **Step 3: Add the export view**

```python
# src/apps/acessibilidade/views.py — adicionar ao final do arquivo
import csv
from django.http import HttpResponse


@login_required
def exportar_csv(request):
    qs = _avaliacoes_filtradas(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="acessibilidade.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Edificação', 'Região', 'Local', 'Critério', 'Status', 'Resolução (diagnóstico)',
        'Status da ação', 'Responsável', 'Prazo', 'Resolução prevista',
        'Ordem de serviço', 'Data da OS', 'Notas', 'Observação',
        'Atualizado por', 'Atualizado em',
    ])
    for a in qs:
        writer.writerow([
            a.local.edificacao.nome, a.local.get_regiao_display(), a.local.nome, a.criterio.nome,
            a.get_status_display(), a.resolucao_diagnostico, a.get_status_acao_display(),
            a.responsavel, a.prazo or '', a.resolucao_prevista, a.ordem_servico, a.data_os or '',
            a.notas, a.observacao, a.atualizado_por.get_username(),
            a.atualizado_em.strftime('%d/%m/%Y %H:%M'),
        ])
    return response
```

- [ ] **Step 4: Add the URL**

```python
# src/apps/acessibilidade/urls.py
urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
    path('acessibilidade/avaliacoes/<int:pk>/editar/', views.editar, name='editar'),
    path('acessibilidade/avaliacoes/editar-lote/', views.editar_lote, name='editar_lote'),
    path('acessibilidade/avaliacoes/exportar.csv', views.exportar_csv, name='exportar_csv'),
]
```

- [ ] **Step 5: Add the export link to the filter form**

```html
{# src/apps/acessibilidade/templates/acessibilidade/lista.html — dentro do <form method="get">, no último <div class="col-auto"> #}
  <div class="col-auto">
    <button type="submit" class="btn btn-primary"><i class="bi bi-search"></i> Filtrar</button>
    <a href="{% url 'acessibilidade:exportar_csv' %}?{{ query_string }}" class="btn btn-outline-secondary">
      <i class="bi bi-download"></i> Exportar CSV
    </a>
  </div>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_exportar_csv.py apps/acessibilidade/tests/test_views_leitura.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/apps/acessibilidade/views.py src/apps/acessibilidade/urls.py src/apps/acessibilidade/templates/acessibilidade/lista.html src/apps/acessibilidade/tests/test_views_exportar_csv.py
git commit -m "feat: exportacao csv das avaliacoes de acessibilidade"
```

---

### Task 11: Painel de alertas de prazo vencido + link no menu

**Files:**
- Modify: `src/apps/acessibilidade/views.py`
- Modify: `src/apps/acessibilidade/urls.py`
- Create: `src/apps/acessibilidade/templates/acessibilidade/alertas.html`
- Modify: `src/templates/base.html`
- Test: `src/apps/acessibilidade/tests/test_views_alertas.py`

- [ ] **Step 1: Write the failing test**

```python
# src/apps/acessibilidade/tests/test_views_alertas.py
import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def cenario(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    ontem = datetime.date.today() - datetime.timedelta(days=1)
    amanha = datetime.date.today() + datetime.timedelta(days=1)

    vencida_pendente = Avaliacao.objects.create(
        local=local, criterio=CriterioAcessibilidade.objects.create(nome='Vencida e pendente'),
        status=Avaliacao.Status.PENDENTE, prazo=ontem,
        status_acao=Avaliacao.StatusAcao.EM_ANDAMENTO, atualizado_por=usuario,
    )
    vencida_concluida = Avaliacao.objects.create(
        local=local, criterio=CriterioAcessibilidade.objects.create(nome='Vencida mas concluida'),
        status=Avaliacao.Status.OK, prazo=ontem,
        status_acao=Avaliacao.StatusAcao.CONCLUIDA, atualizado_por=usuario,
    )
    nao_vencida = Avaliacao.objects.create(
        local=local, criterio=CriterioAcessibilidade.objects.create(nome='No prazo'),
        status=Avaliacao.Status.PENDENTE, prazo=amanha,
        status_acao=Avaliacao.StatusAcao.EM_ANDAMENTO, atualizado_por=usuario,
    )
    return {
        'usuario': usuario, 'vencida_pendente': vencida_pendente,
        'vencida_concluida': vencida_concluida, 'nao_vencida': nao_vencida,
    }


@pytest.mark.django_db
def test_alertas_mostra_so_vencidas_e_nao_concluidas(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:alertas'))
    ids = [a.pk for a in resp.context['avaliacoes']]
    assert ids == [cenario['vencida_pendente'].pk]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_alertas.py -v`
Expected: FAIL — `NoReverseMatch: 'alertas'`

- [ ] **Step 3: Add the alerts view**

```python
# src/apps/acessibilidade/views.py — adicionar ao final do arquivo
from django.utils import timezone


@login_required
def alertas(request):
    hoje = timezone.localdate()
    qs = (
        Avaliacao.objects.select_related('local', 'local__edificacao', 'criterio')
        .filter(prazo__lt=hoje)
        .exclude(status_acao=Avaliacao.StatusAcao.CONCLUIDA)
        .order_by('prazo')
    )
    return render(request, 'acessibilidade/alertas.html', {'avaliacoes': qs, 'hoje': hoje})
```

- [ ] **Step 4: Add the URL**

```python
# src/apps/acessibilidade/urls.py
urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
    path('acessibilidade/avaliacoes/<int:pk>/editar/', views.editar, name='editar'),
    path('acessibilidade/avaliacoes/editar-lote/', views.editar_lote, name='editar_lote'),
    path('acessibilidade/avaliacoes/exportar.csv', views.exportar_csv, name='exportar_csv'),
    path('acessibilidade/alertas/', views.alertas, name='alertas'),
]
```

- [ ] **Step 5: Write the template**

```html
{# src/apps/acessibilidade/templates/acessibilidade/alertas.html #}
{% extends 'base.html' %}

{% block title %}Alertas de prazo — Acessibilidade{% endblock %}

{% block content %}
<h2><i class="bi bi-exclamation-triangle text-danger"></i> Alertas de prazo vencido</h2>
<p class="text-muted">Avaliações com plano de ação em atraso (prazo anterior a {{ hoje|date:'d/m/Y' }}) e ainda não concluídas.</p>

<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-hover mb-0">
      <thead class="table-light">
        <tr>
          <th>Edificação</th>
          <th>Local</th>
          <th>Critério</th>
          <th>Responsável</th>
          <th>Prazo</th>
          <th>Status da ação</th>
          <th>Ações</th>
        </tr>
      </thead>
      <tbody>
        {% for a in avaliacoes %}
        <tr class="table-danger">
          <td>{{ a.local.edificacao.nome }}</td>
          <td>{{ a.local.get_regiao_display }} — {{ a.local.nome }}</td>
          <td>{{ a.criterio.nome }}</td>
          <td>{{ a.responsavel|default:"—" }}</td>
          <td>{{ a.prazo|date:'d/m/Y' }}</td>
          <td>{{ a.get_status_acao_display }}</td>
          <td><a href="{% url 'acessibilidade:editar' a.pk %}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-pencil"></i></a></td>
        </tr>
        {% empty %}
        <tr><td colspan="7" class="text-center text-muted py-4">Nenhum alerta no momento.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Add the nav link**

```html
{# src/templates/base.html — dentro de <ul class="navbar-nav me-auto">, após o item "Configurações" #}
        <li class="nav-item">
          <a class="nav-link" href="{% url 'acessibilidade:dashboard' %}"><i class="bi bi-universal-access" aria-hidden="true"></i> Acessibilidade</a>
        </li>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/acessibilidade/tests/test_views_alertas.py -v`
Expected: PASS (1 passed)

- [ ] **Step 8: Run the full test suite**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (nenhuma regressão nos testes já existentes de `edificacoes`/`inspecoes`)

- [ ] **Step 9: Django system check**

Run: `cd src && ../.venv/Scripts/python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 10: Commit**

```bash
git add src/apps/acessibilidade/views.py src/apps/acessibilidade/urls.py src/apps/acessibilidade/templates/acessibilidade/alertas.html src/templates/base.html src/apps/acessibilidade/tests/test_views_alertas.py
git commit -m "feat: painel de alertas de prazo vencido e link no menu (fecha modulo de acessibilidade)"
```

---

## Fora de escopo deste plano (follow-ups documentados no design)

- Limpeza/dedup manual dos nomes de `Local`/`Região` quase-duplicados vindos do painel original (ver design doc, seção 7).
- Preenchimento de `base_legal` para os critérios das 12 edificações que não são PJPL.
- Revisão manual dos nomes das 11 edificações novas criadas com `nome=sigla` pelo comando de importação (Task 6, Step 8).
