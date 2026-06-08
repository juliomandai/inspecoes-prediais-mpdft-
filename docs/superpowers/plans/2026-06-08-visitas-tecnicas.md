# Módulo de Visitas Técnicas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um módulo de registro de visitas técnicas (organizado por localidade, filtrado por data) ao app `inspecoes`, com uma nova página inicial que permite escolher entre "Inspeção Predial" e "Visita Técnica".

**Architecture:** Tudo dentro do app Django existente `apps.inspecoes`. Novos modelos `VisitaTecnica` e `VisitaFoto`, novas views/urls/templates seguindo os padrões já usados pelas inspeções (login obrigatório, segurança por nome do responsável, `LogAcesso`, fotos com câmera no mobile). A raiz `/` passa a ser um menu; a lista de inspeções move para `/inspecoes/`.

**Tech Stack:** Django 5.2, SQLite, Bootstrap 5, pytest-django, Pillow.

**Convenções de ambiente (todos os comandos):**
- Diretório do projeto: `C:\Users\jtman\OneDrive - MPDFT\Trabalho - MPDFT\Inspeções Promotorias\Inspeções prediais MPDFT`
- Ativar venv antes de rodar Python: `.venv\Scripts\activate`
- Comandos `manage.py` e `pytest` rodam de dentro de `src\`
- Python do venv: `..\.venv\Scripts\python.exe`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/pytest.ini` (criar) | Configuração do pytest-django |
| `src/apps/inspecoes/models.py` (modificar) | `VisitaTecnica`, `VisitaFoto`, +2 tipos no `LogAcesso` |
| `src/apps/inspecoes/migrations/0007_visitas.py` (gerado) | Migração dos novos modelos |
| `src/apps/inspecoes/forms.py` (modificar) | `VisitaTecnicaForm`, `VisitaFilterForm` |
| `src/apps/inspecoes/views.py` (modificar) | `home` + 8 views de visita + helpers de permissão |
| `src/apps/inspecoes/urls.py` (modificar) | rota `home` na raiz, mover lista p/ `/inspecoes/`, rotas de visita |
| `src/apps/inspecoes/admin.py` (modificar) | registrar `VisitaTecnica` e `VisitaFoto` |
| `src/templates/base.html` (modificar) | atalhos de menu para os dois módulos |
| `src/apps/inspecoes/templates/inspecoes/home.html` (criar) | menu com dois cartões |
| `src/apps/inspecoes/templates/inspecoes/visita_localidades.html` (criar) | lista de localidades |
| `src/apps/inspecoes/templates/inspecoes/visita_list.html` (criar) | visitas de uma localidade + filtro por data |
| `src/apps/inspecoes/templates/inspecoes/visita_form.html` (criar) | criação/edição + fotos |
| `src/apps/inspecoes/templates/inspecoes/visita_detail.html` (criar) | visualização completa |
| `src/apps/inspecoes/tests/__init__.py` (criar) | pacote de testes |
| `src/apps/inspecoes/tests/test_visitas.py` (criar) | testes do módulo |

---

## Task 1: Infraestrutura de testes (pytest)

**Files:**
- Create: `src/pytest.ini`
- Create: `src/apps/inspecoes/tests/__init__.py`
- Create: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Criar `src/pytest.ini`**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = mpdft_inspecoes.settings
python_files = tests.py test_*.py *_tests.py
```

- [ ] **Step 2: Criar o pacote de testes**

Crie o arquivo vazio `src/apps/inspecoes/tests/__init__.py` (conteúdo: nenhum).

> Nota: existe hoje `src/apps/inspecoes/` sem `tests.py`. Não há conflito ao criar o pacote `tests/`.

- [ ] **Step 3: Criar um teste de fumaça para validar a infra**

Arquivo `src/apps/inspecoes/tests/test_visitas.py`:

```python
import pytest


@pytest.mark.django_db
def test_infra_pytest_funciona():
    from apps.edificacoes.models import Edificacao
    edif = Edificacao.objects.create(nome="Predio Teste")
    assert edif.pk is not None
```

- [ ] **Step 4: Rodar o teste**

Run (de dentro de `src\`, com venv ativo): `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/pytest.ini src/apps/inspecoes/tests/__init__.py src/apps/inspecoes/tests/test_visitas.py
git commit -m "test: configura pytest-django e teste de fumaça"
```

---

## Task 2: Modelos VisitaTecnica e VisitaFoto + tipos no LogAcesso

**Files:**
- Modify: `src/apps/inspecoes/models.py`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever os testes de modelo (falhando)**

Adicione ao final de `src/apps/inspecoes/tests/test_visitas.py`:

```python
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from apps.edificacoes.models import Edificacao


@pytest.fixture
def edificacao(db):
    return Edificacao.objects.create(nome="Promotoria Central")


@pytest.mark.django_db
def test_cria_visita_valida(edificacao):
    from apps.inspecoes.models import VisitaTecnica
    v = VisitaTecnica.objects.create(
        edificacao=edificacao,
        data_visita=date.today(),
        responsavel="Maria Souza",
        motivo="Vistoria de rotina",
        achados="Sem anomalias relevantes.",
        conclusoes_encaminhamentos="Nada a encaminhar.",
    )
    assert v.pk is not None
    assert str(v) == f"Promotoria Central — {date.today():%d/%m/%Y}"


@pytest.mark.django_db
def test_data_visita_futura_invalida(edificacao):
    from apps.inspecoes.models import VisitaTecnica
    v = VisitaTecnica(
        edificacao=edificacao,
        data_visita=date.today() + timedelta(days=1),
        responsavel="Maria Souza",
        motivo="x", achados="x", conclusoes_encaminhamentos="x",
    )
    with pytest.raises(ValidationError):
        v.full_clean()


@pytest.mark.django_db
def test_visita_foto_vinculada(edificacao):
    from apps.inspecoes.models import VisitaTecnica, VisitaFoto
    from django.core.files.base import ContentFile
    v = VisitaTecnica.objects.create(
        edificacao=edificacao, data_visita=date.today(),
        responsavel="X", motivo="x", achados="x", conclusoes_encaminhamentos="x",
    )
    f = VisitaFoto.objects.create(
        visita=v,
        arquivo=ContentFile(b"fake", name="foto.jpg"),
        nome_original="foto.jpg",
        tamanho_bytes=4,
    )
    assert v.fotos.count() == 1
    assert f.visita_id == v.pk


@pytest.mark.django_db
def test_logacesso_tem_tipos_de_visita():
    from apps.inspecoes.models import LogAcesso
    tipos = dict(LogAcesso.TIPO_CHOICES)
    assert "visita_criada" in tipos
    assert "visita_excluida" in tipos
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -v`
Expected: FAIL (ImportError / AttributeError — `VisitaTecnica` não existe)

- [ ] **Step 3: Adicionar os modelos**

No fim de `src/apps/inspecoes/models.py`, **antes** da classe `LogAcesso`, adicione:

```python
def visita_foto_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    hoje = date.today()
    return f'visitas/{hoje.year}/{hoje.month:02d}/{instance.visita_id}/{uuid.uuid4()}.{ext}'


class VisitaTecnica(models.Model):
    edificacao = models.ForeignKey(
        'edificacoes.Edificacao',
        on_delete=models.PROTECT,
        verbose_name='Localidade',
        related_name='visitas',
    )
    data_visita = models.DateField('Data da visita')
    responsavel = models.CharField('Profissional responsável', max_length=200)
    motivo = models.TextField('Motivo da visita')
    achados = models.TextField('Achados da visita', blank=True)
    conclusoes_encaminhamentos = models.TextField('Conclusões e encaminhamentos', blank=True)
    criado_por = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='visitas_criadas',
        verbose_name='Criado por',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_visita', '-criado_em']
        verbose_name = 'Visita técnica'
        verbose_name_plural = 'Visitas técnicas'

    def __str__(self):
        return f'{self.edificacao} — {self.data_visita:%d/%m/%Y}'

    def clean(self):
        if self.data_visita and self.data_visita > date.today():
            raise ValidationError({'data_visita': 'A data da visita não pode ser futura.'})


class VisitaFoto(models.Model):
    visita = models.ForeignKey(VisitaTecnica, on_delete=models.CASCADE, related_name='fotos', verbose_name='Visita')
    arquivo = models.ImageField('Foto', upload_to=visita_foto_upload_path)
    nome_original = models.CharField(max_length=255)
    tamanho_bytes = models.IntegerField(default=0)
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_upload']
        verbose_name = 'Foto de visita'
        verbose_name_plural = 'Fotos de visita'

    def __str__(self):
        return self.nome_original
```

- [ ] **Step 4: Adicionar os tipos de log**

Em `src/apps/inspecoes/models.py`, dentro da classe `LogAcesso`, no `TIPO_CHOICES`, adicione as duas linhas ao final da lista (antes do `]`):

```python
        ('visita_criada', 'Visita técnica criada'),
        ('visita_excluida', 'Visita técnica excluída'),
```

- [ ] **Step 5: Gerar e aplicar a migração**

Run:
```
..\.venv\Scripts\python.exe manage.py makemigrations inspecoes
..\.venv\Scripts\python.exe manage.py migrate
```
Expected: cria `0007_*.py`, aplica sem erro.

- [ ] **Step 6: Rodar os testes**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -v`
Expected: PASS (todos)

- [ ] **Step 7: Commit**

```bash
git add src/apps/inspecoes/models.py src/apps/inspecoes/migrations/
git commit -m "feat: modelos VisitaTecnica e VisitaFoto + tipos de log de visita"
```

---

## Task 3: Registro no admin

**Files:**
- Modify: `src/apps/inspecoes/admin.py`

- [ ] **Step 1: Atualizar o import**

Em `src/apps/inspecoes/admin.py`, linha 2, troque por:

```python
from .models import Inspecao, InspecaoEspecialidade, Achado, Foto, LogAcesso, VisitaTecnica, VisitaFoto
```

- [ ] **Step 2: Adicionar as classes admin**

Antes da linha `@admin.register(LogAcesso)`, adicione:

```python
class VisitaFotoInline(admin.TabularInline):
    model = VisitaFoto
    extra = 0
    readonly_fields = ['nome_original', 'tamanho_bytes', 'data_upload']


@admin.register(VisitaTecnica)
class VisitaTecnicaAdmin(admin.ModelAdmin):
    list_display = ['edificacao', 'data_visita', 'responsavel', 'criado_em']
    list_filter = ['edificacao']
    search_fields = ['responsavel', 'edificacao__nome', 'motivo']
    date_hierarchy = 'data_visita'
    inlines = [VisitaFotoInline]
```

- [ ] **Step 3: Verificar**

Run: `..\.venv\Scripts\python.exe manage.py check`
Expected: "System check identified no issues"

- [ ] **Step 4: Commit**

```bash
git add src/apps/inspecoes/admin.py
git commit -m "feat: registra VisitaTecnica no admin"
```

---

## Task 4: Formulários (VisitaTecnicaForm e VisitaFilterForm)

**Files:**
- Modify: `src/apps/inspecoes/forms.py`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever o teste do form (falhando)**

Adicione ao fim de `test_visitas.py`:

```python
@pytest.mark.django_db
def test_visita_form_valido(edificacao):
    from apps.inspecoes.forms import VisitaTecnicaForm
    form = VisitaTecnicaForm(data={
        'data_visita': date.today().isoformat(),
        'responsavel': 'João',
        'motivo': 'Vistoria',
        'achados': 'ok',
        'conclusoes_encaminhamentos': 'ok',
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_visita_form_rejeita_data_futura(edificacao):
    from apps.inspecoes.forms import VisitaTecnicaForm
    form = VisitaTecnicaForm(data={
        'data_visita': (date.today() + timedelta(days=2)).isoformat(),
        'responsavel': 'João', 'motivo': 'x',
        'achados': 'x', 'conclusoes_encaminhamentos': 'x',
    })
    assert not form.is_valid()
    assert 'data_visita' in form.errors
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k visita_form -v`
Expected: FAIL (ImportError — `VisitaTecnicaForm` não existe)

- [ ] **Step 3: Implementar os forms**

No topo de `src/apps/inspecoes/forms.py`, atualize o import dos modelos para incluir `VisitaTecnica`:

```python
from .models import Inspecao, InspecaoEspecialidade, Achado, OpcaoCampo, VisitaTecnica
```

Ao final de `src/apps/inspecoes/forms.py`, adicione:

```python
class VisitaTecnicaForm(forms.ModelForm):
    data_visita = forms.DateField(
        label='Data da visita',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = VisitaTecnica
        fields = ['data_visita', 'responsavel', 'motivo', 'achados', 'conclusoes_encaminhamentos']
        widgets = {
            'responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'achados': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'conclusoes_encaminhamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'responsavel': 'Profissional responsável',
            'motivo': 'Motivo da visita',
            'achados': 'Achados da visita',
            'conclusoes_encaminhamentos': 'Conclusões e encaminhamentos',
        }

    def clean_data_visita(self):
        data = self.cleaned_data['data_visita']
        if data and data > date.today():
            raise forms.ValidationError('A data da visita não pode ser futura.')
        return data


class VisitaFilterForm(forms.Form):
    data_inicio = forms.DateField(
        required=False, label='Data de',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    data_fim = forms.DateField(
        required=False, label='Data até',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
```

> `date` já está importado no topo de `forms.py` (`from datetime import date`).

- [ ] **Step 4: Rodar os testes**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k visita_form -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/inspecoes/forms.py src/apps/inspecoes/tests/test_visitas.py
git commit -m "feat: VisitaTecnicaForm e VisitaFilterForm"
```

---

## Task 5: Página inicial (menu) + reorganização de URLs + navbar

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Modify: `src/templates/base.html`
- Create: `src/apps/inspecoes/templates/inspecoes/home.html`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever o teste de roteamento (falhando)**

Adicione ao fim de `test_visitas.py`:

```python
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def usuario_logado(db, client):
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='123', first_name='Ze', last_name='Silva')
    client.force_login(u)
    return u


@pytest.mark.django_db
def test_home_mostra_menu(client, usuario_logado):
    resp = client.get(reverse('inspecoes:home'))
    assert resp.status_code == 200
    assert b'Inspe' in resp.content
    assert b'Visita' in resp.content


@pytest.mark.django_db
def test_lista_inspecoes_em_inspecoes_url(client, usuario_logado):
    resp = client.get(reverse('inspecoes:list'))
    assert resp.status_code == 200
    assert resp.request['PATH_INFO'] == '/inspecoes/'
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k "home or inspecoes_url" -v`
Expected: FAIL (NoReverseMatch para `inspecoes:home`)

- [ ] **Step 3: Adicionar a view `home`**

Em `src/apps/inspecoes/views.py`, logo após a seção `# ── Erros ──` (antes de `# ── Inspeções`), adicione:

```python
# ── Página inicial (menu) ─────────────────────────────────────────────────────

@login_required
def home(request):
    return render(request, 'inspecoes/home.html')
```

- [ ] **Step 4: Reorganizar as URLs**

Em `src/apps/inspecoes/urls.py`, troque o bloco "Listagem e configurações" por:

```python
    # ── Página inicial (menu) ──────────────────────────────────────────────────
    path('', views.home, name='home'),

    # ── Listagem e configurações ───────────────────────────────────────────────
    path('inspecoes/', views.inspecao_list, name='list'),
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('logs/', views.log_acesso, name='log_acesso'),
```

> O nome `list` é mantido — todos os `{% url 'inspecoes:list' %}` continuam válidos, agora apontando para `/inspecoes/`.

- [ ] **Step 5: Criar o template `home.html`**

Arquivo `src/apps/inspecoes/templates/inspecoes/home.html`:

```html
{% extends 'base.html' %}
{% block title %}Início — Inspeções Prediais MPDFT{% endblock %}

{% block content %}
<div class="text-center mb-4">
  <h2 class="mb-1">O que você deseja registrar?</h2>
  <p class="text-muted">Escolha um dos módulos abaixo</p>
</div>

<div class="row justify-content-center g-4">
  <div class="col-md-5">
    <a href="{% url 'inspecoes:list' %}" class="text-decoration-none">
      <div class="card h-100 shadow-sm border-primary">
        <div class="card-body text-center py-5">
          <i class="bi bi-building-check text-primary" style="font-size:3rem;"></i>
          <h4 class="mt-3 mb-2 text-dark">Inspeção Predial</h4>
          <p class="text-muted mb-0">Registro estruturado com matriz GUT, achados e análise por especialidade.</p>
        </div>
      </div>
    </a>
  </div>
  <div class="col-md-5">
    <a href="{% url 'inspecoes:visita_localidades' %}" class="text-decoration-none">
      <div class="card h-100 shadow-sm border-success">
        <div class="card-body text-center py-5">
          <i class="bi bi-clipboard-check text-success" style="font-size:3rem;"></i>
          <h4 class="mt-3 mb-2 text-dark">Visita Técnica</h4>
          <p class="text-muted mb-0">Registro de visitas por localidade, com motivo, achados, fotos e encaminhamentos.</p>
        </div>
      </div>
    </a>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Atualizar a navbar**

Em `src/templates/base.html`, localize o bloco de itens de navegação (a `<ul class="navbar-nav me-auto">`) e substitua o item "Inspeções" por dois itens. Troque este trecho:

```html
        <li class="nav-item">
          <a class="nav-link" href="/"><i class="bi bi-list-ul"></i> Inspeções</a>
        </li>
```

por:

```html
        <li class="nav-item">
          <a class="nav-link" href="{% url 'inspecoes:list' %}"><i class="bi bi-building-check"></i> Inspeções</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{% url 'inspecoes:visita_localidades' %}"><i class="bi bi-clipboard-check"></i> Visitas</a>
        </li>
```

> A marca (brand) com `href="/"` agora leva ao menu inicial — comportamento desejado.

- [ ] **Step 7: Rodar os testes**

> A view `visita_localidades` ainda não existe; o template `home.html` e a navbar usam `{% url 'inspecoes:visita_localidades' %}`. Para não quebrar agora, **a Task 6 cria essa rota**. Execute o teste deste passo somente após a Task 6. Por ora, rode apenas a verificação de sintaxe:

Run: `..\.venv\Scripts\python.exe manage.py check`
Expected: pode acusar `NoReverseMatch` apenas em runtime de template; `check` deve passar. Se `check` falhar por causa do `{% url %}`, prossiga para a Task 6 e rode os testes ao final dela.

- [ ] **Step 8: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/templates/base.html src/apps/inspecoes/templates/inspecoes/home.html
git commit -m "feat: pagina inicial com menu e move lista de inspecoes para /inspecoes/"
```

---

## Task 6: Lista de localidades das visitas

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Create: `src/apps/inspecoes/templates/inspecoes/visita_localidades.html`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever o teste (falhando)**

Adicione ao fim de `test_visitas.py`:

```python
@pytest.mark.django_db
def test_lista_localidades_mostra_edificacoes_ativas(client, usuario_logado):
    from apps.edificacoes.models import Edificacao
    Edificacao.objects.create(nome="Sede A")
    Edificacao.objects.create(nome="Sede Inativa", ativo=False)
    resp = client.get(reverse('inspecoes:visita_localidades'))
    assert resp.status_code == 200
    assert b'Sede A' in resp.content
    assert b'Sede Inativa' not in resp.content
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k localidades -v`
Expected: FAIL (NoReverseMatch `inspecoes:visita_localidades`)

- [ ] **Step 3: Adicionar a view**

Em `src/apps/inspecoes/views.py`, ao final do arquivo, adicione uma nova seção:

```python
# ── Visitas técnicas ──────────────────────────────────────────────────────────

@login_required
def visita_localidades(request):
    from apps.edificacoes.models import Edificacao
    localidades = (
        Edificacao.objects.filter(ativo=True)
        .annotate(num_visitas=Count('visitas', distinct=True))
        .order_by('nome')
    )
    return render(request, 'inspecoes/visita_localidades.html', {
        'localidades': localidades,
    })
```

> `Count` já está importado no topo de `views.py` (`from django.db.models import Count, Q, Min`).

- [ ] **Step 4: Adicionar a rota**

Em `src/apps/inspecoes/urls.py`, antes do bloco `# ── PWA`, adicione:

```python
    # ── Visitas técnicas ───────────────────────────────────────────────────────
    path('visitas/', views.visita_localidades, name='visita_localidades'),
```

- [ ] **Step 5: Criar o template**

Arquivo `src/apps/inspecoes/templates/inspecoes/visita_localidades.html`:

```html
{% extends 'base.html' %}
{% block title %}Visitas Técnicas — Inspeções Prediais MPDFT{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h2 class="mb-0"><i class="bi bi-clipboard-check"></i> Visitas Técnicas</h2>
  <a href="{% url 'inspecoes:home' %}" class="btn btn-outline-secondary btn-sm">
    <i class="bi bi-arrow-left"></i> Início
  </a>
</div>
<p class="text-muted">Escolha a localidade para ver ou registrar visitas.</p>

{% if localidades %}
<div class="row g-3">
  {% for loc in localidades %}
  <div class="col-md-4">
    <a href="{% url 'inspecoes:visita_list' loc.pk %}" class="text-decoration-none">
      <div class="card h-100 shadow-sm">
        <div class="card-body">
          <h5 class="card-title text-dark mb-1">{{ loc.nome }}</h5>
          <span class="badge bg-secondary">{{ loc.num_visitas }} visita(s)</span>
        </div>
      </div>
    </a>
  </div>
  {% endfor %}
</div>
{% else %}
<div class="alert alert-info"><i class="bi bi-info-circle"></i> Nenhuma localidade ativa cadastrada.</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Rodar os testes (incluindo os da Task 5)**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k "home or inspecoes_url or localidades" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/visita_localidades.html
git commit -m "feat: lista de localidades das visitas tecnicas"
```

---

## Task 7: Lista de visitas por localidade (com filtro por data)

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Create: `src/apps/inspecoes/templates/inspecoes/visita_list.html`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever o teste (falhando)**

```python
@pytest.mark.django_db
def test_visita_list_filtra_por_data(client, usuario_logado, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date(2026, 1, 10),
                                 responsavel="A", motivo="m1", achados="x", conclusoes_encaminhamentos="x")
    VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date(2026, 6, 10),
                                 responsavel="A", motivo="m2", achados="x", conclusoes_encaminhamentos="x")
    url = reverse('inspecoes:visita_list', args=[edificacao.pk])
    resp = client.get(url, {'data_inicio': '2026-05-01', 'data_fim': '2026-12-31'})
    assert resp.status_code == 200
    assert b'm2' in resp.content
    assert b'm1' not in resp.content
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k visita_list -v`
Expected: FAIL (NoReverseMatch `inspecoes:visita_list`)

- [ ] **Step 3: Atualizar o import de forms na view**

Em `src/apps/inspecoes/views.py`, localize a linha:

```python
from .forms import InspecaoForm, EspecialidadeForm, AchadoForm, InspecaoFilterForm
```
e troque por:

```python
from .forms import InspecaoForm, EspecialidadeForm, AchadoForm, InspecaoFilterForm, VisitaTecnicaForm, VisitaFilterForm
```

- [ ] **Step 4: Adicionar a view**

Após `visita_localidades` em `views.py`, adicione:

```python
@login_required
def visita_list(request, edif_pk):
    from apps.edificacoes.models import Edificacao
    edificacao = get_object_or_404(Edificacao, pk=edif_pk)
    form = VisitaFilterForm(request.GET or None)
    visitas = edificacao.visitas.all()
    if form.is_valid():
        if form.cleaned_data.get('data_inicio'):
            visitas = visitas.filter(data_visita__gte=form.cleaned_data['data_inicio'])
        if form.cleaned_data.get('data_fim'):
            visitas = visitas.filter(data_visita__lte=form.cleaned_data['data_fim'])
    return render(request, 'inspecoes/visita_list.html', {
        'edificacao': edificacao,
        'filter_form': form,
        'visitas': visitas,
    })
```

- [ ] **Step 5: Adicionar a rota**

Em `src/apps/inspecoes/urls.py`, no bloco "Visitas técnicas", adicione abaixo de `visita_localidades`:

```python
    path('visitas/localidade/<int:edif_pk>/', views.visita_list, name='visita_list'),
```

- [ ] **Step 6: Criar o template**

Arquivo `src/apps/inspecoes/templates/inspecoes/visita_list.html`:

```html
{% extends 'base.html' %}
{% block title %}Visitas — {{ edificacao.nome }}{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
  <div>
    <h3 class="mb-0">{{ edificacao.nome }}</h3>
    <small class="text-muted">Visitas técnicas</small>
  </div>
  <div class="d-flex gap-2">
    <a href="{% url 'inspecoes:visita_localidades' %}" class="btn btn-outline-secondary">
      <i class="bi bi-arrow-left"></i> Localidades
    </a>
    <a href="{% url 'inspecoes:visita_create' edificacao.pk %}" class="btn btn-success">
      <i class="bi bi-plus-lg"></i> Nova Visita
    </a>
  </div>
</div>

<div class="card mb-4">
  <div class="card-body">
    <form method="get" class="row g-2 align-items-end">
      <div class="col-md-3">
        <label class="form-label small">{{ filter_form.data_inicio.label }}</label>
        {{ filter_form.data_inicio }}
      </div>
      <div class="col-md-3">
        <label class="form-label small">{{ filter_form.data_fim.label }}</label>
        {{ filter_form.data_fim }}
      </div>
      <div class="col-md-3 d-flex gap-1">
        <button type="submit" class="btn btn-secondary btn-sm"><i class="bi bi-funnel"></i> Filtrar</button>
        <a href="{% url 'inspecoes:visita_list' edificacao.pk %}" class="btn btn-outline-secondary btn-sm">Limpar</a>
      </div>
    </form>
  </div>
</div>

{% if visitas %}
<div class="table-responsive">
  <table class="table table-hover table-bordered align-middle">
    <thead class="table-primary">
      <tr>
        <th>Data</th>
        <th>Responsável</th>
        <th>Motivo</th>
        <th class="text-center">Fotos</th>
        <th class="text-center">Ação</th>
      </tr>
    </thead>
    <tbody>
      {% for v in visitas %}
      <tr>
        <td>{{ v.data_visita|date:"d/m/Y" }}</td>
        <td>{{ v.responsavel }}</td>
        <td>{{ v.motivo|truncatechars:60 }}</td>
        <td class="text-center">{{ v.fotos.count }}</td>
        <td class="text-center">
          <a href="{% url 'inspecoes:visita_detail' v.pk %}" class="btn btn-sm btn-outline-primary">
            <i class="bi bi-eye"></i> Ver
          </a>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="alert alert-info">
  <i class="bi bi-info-circle"></i> Nenhuma visita registrada para esta localidade.
  <a href="{% url 'inspecoes:visita_create' edificacao.pk %}">Registrar a primeira visita.</a>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Rodar os testes**

> Usa `{% url 'inspecoes:visita_create' %}` e `visita_detail`, criados nas Tasks 8 e 9. O teste deste passo (`test_visita_list_filtra_por_data`) renderiza o template e falhará por `NoReverseMatch` até a Task 9. Rode-o ao final da Task 9.

Por ora: `..\.venv\Scripts\python.exe manage.py check` — Expected: sem erros.

- [ ] **Step 8: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/visita_list.html
git commit -m "feat: lista de visitas por localidade com filtro por data"
```

---

## Task 8: Criar visita (com fotos)

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Create: `src/apps/inspecoes/templates/inspecoes/visita_form.html`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever o teste (falhando)**

```python
@pytest.mark.django_db
def test_cria_visita_via_post_com_foto(client, usuario_logado, edificacao):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.inspecoes.models import VisitaTecnica, LogAcesso
    # PNG 1x1 mínimo válido
    png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
           b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
           b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    foto = SimpleUploadedFile('v.png', png, content_type='image/png')
    url = reverse('inspecoes:visita_create', args=[edificacao.pk])
    resp = client.post(url, {
        'data_visita': date.today().isoformat(),
        'responsavel': 'Ze Silva',
        'motivo': 'Vistoria geral',
        'achados': 'tudo certo',
        'conclusoes_encaminhamentos': 'nada',
        'fotos': [foto],
    })
    assert resp.status_code == 302
    v = VisitaTecnica.objects.get(edificacao=edificacao)
    assert v.responsavel == 'Ze Silva'
    assert v.criado_por_id == usuario_logado.pk
    assert v.fotos.count() == 1
    assert LogAcesso.objects.filter(tipo='visita_criada').exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k cria_visita_via_post -v`
Expected: FAIL (NoReverseMatch `inspecoes:visita_create`)

- [ ] **Step 3: Adicionar a view**

Após `visita_list` em `views.py`, adicione:

```python
@login_required
def visita_create(request, edif_pk):
    from apps.edificacoes.models import Edificacao
    edificacao = get_object_or_404(Edificacao, pk=edif_pk)
    initial = {'responsavel': request.user.get_full_name()}
    form = VisitaTecnicaForm(request.POST or None, initial=initial)
    if form.is_valid():
        visita = form.save(commit=False)
        visita.edificacao = edificacao
        visita.criado_por = request.user
        visita.save()
        for arquivo in request.FILES.getlist('fotos'):
            if arquivo.content_type in ALLOWED_CONTENT_TYPES and arquivo.size <= MAX_UPLOAD_SIZE:
                VisitaFoto.objects.create(
                    visita=visita,
                    arquivo=arquivo,
                    nome_original=arquivo.name,
                    tamanho_bytes=arquivo.size,
                )
        _log(request, 'visita_criada',
             f'Visita técnica criada em "{edificacao.nome}" ({visita.data_visita:%d/%m/%Y}) por {visita.responsavel}.')
        messages.success(request, 'Visita técnica registrada com sucesso.')
        return redirect('inspecoes:visita_detail', pk=visita.pk)
    return render(request, 'inspecoes/visita_form.html', {
        'form': form,
        'edificacao': edificacao,
        'fotos_existentes': [],
    })
```

> Atualize o import de modelos no topo de `views.py` para incluir `VisitaTecnica, VisitaFoto`:
> ```python
> from .models import Inspecao, InspecaoEspecialidade, Achado, Foto, OpcaoCampo, LogAcesso, VisitaTecnica, VisitaFoto
> ```

- [ ] **Step 4: Adicionar a rota**

Em `urls.py`, no bloco "Visitas técnicas":

```python
    path('visitas/localidade/<int:edif_pk>/nova/', views.visita_create, name='visita_create'),
```

- [ ] **Step 5: Criar o template do formulário**

Arquivo `src/apps/inspecoes/templates/inspecoes/visita_form.html`:

```html
{% extends 'base.html' %}
{% block title %}{% if visita %}Editar Visita{% else %}Nova Visita{% endif %} — {{ edificacao.nome }}{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h4 class="mb-0">{% if visita %}Editar Visita{% else %}Nova Visita Técnica{% endif %}</h4>
    <small class="text-muted">{{ edificacao.nome }}</small>
  </div>
  {% if visita %}
  <a href="{% url 'inspecoes:visita_detail' visita.pk %}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-left"></i> Voltar</a>
  {% else %}
  <a href="{% url 'inspecoes:visita_list' edificacao.pk %}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-arrow-left"></i> Voltar</a>
  {% endif %}
</div>

<form method="post" enctype="multipart/form-data" id="visita-form">
  {% csrf_token %}
  <div class="card mb-3">
    <div class="card-body">
      <div class="row g-3">
        <div class="col-md-4">
          <label for="{{ form.data_visita.id_for_label }}" class="form-label">{{ form.data_visita.label }}</label>
          {{ form.data_visita }}
          {% if form.data_visita.errors %}<div class="text-danger small mt-1">{{ form.data_visita.errors }}</div>{% endif %}
        </div>
        <div class="col-md-8">
          <label for="{{ form.responsavel.id_for_label }}" class="form-label">{{ form.responsavel.label }}</label>
          {{ form.responsavel }}
          {% if form.responsavel.errors %}<div class="text-danger small mt-1">{{ form.responsavel.errors }}</div>{% endif %}
        </div>
        <div class="col-12">
          <label for="{{ form.motivo.id_for_label }}" class="form-label">{{ form.motivo.label }}</label>
          {{ form.motivo }}
        </div>
        <div class="col-12">
          <label for="{{ form.achados.id_for_label }}" class="form-label">{{ form.achados.label }}</label>
          {{ form.achados }}
        </div>
        <div class="col-12">
          <label for="{{ form.conclusoes_encaminhamentos.id_for_label }}" class="form-label">{{ form.conclusoes_encaminhamentos.label }}</label>
          {{ form.conclusoes_encaminhamentos }}
        </div>
      </div>
    </div>
  </div>

  <div class="card mb-3">
    <div class="card-header fw-bold"><i class="bi bi-camera"></i> Fotos</div>
    <div class="card-body">
      {% if fotos_existentes %}
      <div id="fotos-grid" class="d-flex flex-wrap gap-2 mb-3">
        {% for foto in fotos_existentes %}
        <div class="position-relative" id="foto-{{ foto.pk }}">
          <img src="{{ foto.arquivo.url }}" alt="{{ foto.nome_original }}"
               style="height:100px;width:100px;object-fit:cover;border:1px solid #dee2e6;border-radius:4px;">
          <button type="button" class="btn btn-danger btn-sm position-absolute top-0 end-0"
                  style="padding:1px 5px;font-size:.7rem;" onclick="deletarFoto({{ foto.pk }})" title="Excluir foto">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>
        {% endfor %}
      </div>
      {% else %}
      <div id="fotos-grid" class="d-flex flex-wrap gap-2 mb-3"></div>
      {% endif %}
      <div id="preview-grid" class="d-flex flex-wrap gap-2 mb-3"></div>
      <label class="form-label">Fotografar / selecionar fotos <span class="text-muted fw-normal">(JPEG ou PNG, máx. 10 MB)</span></label>
      <div class="d-flex gap-2 flex-wrap">
        <label class="btn btn-outline-primary btn-sm mb-0" style="cursor:pointer;">
          <i class="bi bi-camera"></i> Câmera
          <input type="file" name="fotos" id="foto-camera" accept="image/*" capture="environment" multiple class="d-none">
        </label>
        <label class="btn btn-outline-secondary btn-sm mb-0" style="cursor:pointer;">
          <i class="bi bi-image"></i> Galeria / Arquivo
          <input type="file" name="fotos" id="foto-arquivo" accept="image/jpeg,image/png" multiple class="d-none">
        </label>
      </div>
      <div id="upload-status" class="mt-2"></div>
    </div>
  </div>

  {% if form.non_field_errors %}<div class="alert alert-danger">{{ form.non_field_errors }}</div>{% endif %}

  <div class="d-flex gap-2 mb-4">
    <button type="submit" class="btn btn-primary"><i class="bi bi-check-lg"></i> Salvar Visita</button>
    {% if visita %}
    <a href="{% url 'inspecoes:visita_detail' visita.pk %}" class="btn btn-outline-secondary">Cancelar</a>
    {% else %}
    <a href="{% url 'inspecoes:visita_list' edificacao.pk %}" class="btn btn-outline-secondary">Cancelar</a>
    {% endif %}
  </div>
</form>
{% endblock %}

{% block extra_js %}
<script>
(function () {
  var CSRF = "{{ csrf_token }}";
  {% if visita %}var UPLOAD_URL = "{% url 'inspecoes:visita_foto_upload' visita.pk %}";{% endif %}

  function mostrarPreview(files) {
    var grid = document.getElementById('preview-grid');
    Array.from(files).forEach(function (file) {
      if (!file.type.match(/image\/(jpeg|png)/)) return;
      var reader = new FileReader();
      reader.onload = function (e) {
        var div = document.createElement('div');
        div.className = 'position-relative';
        div.innerHTML = '<img src="' + e.target.result + '" style="height:100px;width:100px;object-fit:cover;border:2px dashed #0d6efd;border-radius:4px;">';
        grid.appendChild(div);
      };
      reader.readAsDataURL(file);
    });
  }

  {% if visita %}
  function uploadAjax(files) {
    var statusDiv = document.getElementById('upload-status');
    Array.from(files).forEach(function (file) {
      var fd = new FormData();
      fd.append('arquivo', file);
      fetch(UPLOAD_URL, {method: 'POST', headers: {'X-CSRFToken': CSRF}, body: fd})
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.erro) { statusDiv.innerHTML += '<div class="text-danger small">' + data.erro + '</div>'; return; }
          var div = document.createElement('div');
          div.className = 'position-relative'; div.id = 'foto-' + data.id;
          div.innerHTML = '<img src="' + data.url + '" style="height:100px;width:100px;object-fit:cover;border:1px solid #dee2e6;border-radius:4px;">' +
            '<button type="button" class="btn btn-danger btn-sm position-absolute top-0 end-0" style="padding:1px 5px;font-size:.7rem;" onclick="deletarFoto(' + data.id + ')"><i class="bi bi-x-lg"></i></button>';
          document.getElementById('fotos-grid').appendChild(div);
        });
    });
  }
  document.getElementById('foto-camera').addEventListener('change', function () { uploadAjax(this.files); this.value=''; });
  document.getElementById('foto-arquivo').addEventListener('change', function () { uploadAjax(this.files); this.value=''; });
  window.deletarFoto = function (pk) {
    if (!confirm('Excluir esta foto?')) return;
    fetch('/visitas/fotos/' + pk + '/', {method: 'DELETE', headers: {'X-CSRFToken': CSRF}})
      .then(function (r) { if (r.status === 204) { var el = document.getElementById('foto-' + pk); if (el) el.remove(); } });
  };
  {% else %}
  document.getElementById('foto-camera').addEventListener('change', function () { mostrarPreview(this.files); });
  document.getElementById('foto-arquivo').addEventListener('change', function () { mostrarPreview(this.files); });
  {% endif %}
})();
</script>
{% endblock %}
```

- [ ] **Step 6: Rodar o teste**

> Usa `visita_detail` (Task 9) no redirect. O POST redireciona para `visita_detail`; o teste só checa `status_code == 302` e os objetos no banco, sem seguir o redirect — portanto **passa já aqui**, mesmo antes do template de detalhe existir (a rota `visita_detail` precisa existir para o `redirect()` resolver). Como `visita_detail` ainda não tem rota, adicione a rota mínima agora OU rode este teste ao final da Task 9.

Decisão: rode ao final da Task 9.
Por ora: `..\.venv\Scripts\python.exe manage.py check` — Expected: sem erros.

- [ ] **Step 7: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/visita_form.html
git commit -m "feat: criacao de visita tecnica com upload de fotos"
```

---

## Task 9: Detalhe da visita

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Create: `src/apps/inspecoes/templates/inspecoes/visita_detail.html`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever o teste (falhando)**

```python
@pytest.mark.django_db
def test_visita_detail_exibe_dados(client, usuario_logado, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel="Carla", motivo="Inspecao eletrica", achados="achado X",
        conclusoes_encaminhamentos="encaminhar Y")
    resp = client.get(reverse('inspecoes:visita_detail', args=[v.pk]))
    assert resp.status_code == 200
    assert b'Carla' in resp.content
    assert b'achado X' in resp.content
    assert b'encaminhar Y' in resp.content
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k visita_detail -v`
Expected: FAIL (NoReverseMatch `inspecoes:visita_detail`)

- [ ] **Step 3: Adicionar a view + helper de permissão**

Após `visita_create` em `views.py`, adicione:

```python
def _pode_editar_visita(user, visita):
    if user.is_staff or user.is_superuser:
        return True
    return user.get_full_name() == visita.responsavel


@login_required
def visita_detail(request, pk):
    visita = get_object_or_404(
        VisitaTecnica.objects.select_related('edificacao').prefetch_related('fotos'),
        pk=pk,
    )
    return render(request, 'inspecoes/visita_detail.html', {
        'visita': visita,
        'pode_editar': _pode_editar_visita(request.user, visita),
    })
```

- [ ] **Step 4: Adicionar a rota**

Em `urls.py`, no bloco "Visitas técnicas":

```python
    path('visitas/<int:pk>/', views.visita_detail, name='visita_detail'),
```

- [ ] **Step 5: Criar o template**

Arquivo `src/apps/inspecoes/templates/inspecoes/visita_detail.html`:

```html
{% extends 'base.html' %}
{% block title %}Visita — {{ visita.edificacao.nome }} — {{ visita.data_visita|date:"d/m/Y" }}{% endblock %}

{% block content %}
<div class="card mb-4">
  <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
    <div>
      <h4 class="mb-0">{{ visita.edificacao.nome }}</h4>
      <small class="text-muted">Visita técnica — {{ visita.data_visita|date:"d/m/Y" }}</small>
    </div>
    <div class="d-flex gap-2 flex-wrap">
      <a href="{% url 'inspecoes:visita_list' visita.edificacao.pk %}" class="btn btn-outline-secondary btn-sm">
        <i class="bi bi-arrow-left"></i> Voltar
      </a>
      {% if pode_editar %}
      <a href="{% url 'inspecoes:visita_update' visita.pk %}" class="btn btn-outline-primary btn-sm">
        <i class="bi bi-pencil"></i> Editar
      </a>
      <form method="post" action="{% url 'inspecoes:visita_delete' visita.pk %}"
            onsubmit="return confirm('Excluir esta visita? As fotos vinculadas também serão removidas.');">
        {% csrf_token %}
        <button type="submit" class="btn btn-danger btn-sm"><i class="bi bi-trash"></i> Excluir</button>
      </form>
      {% endif %}
    </div>
  </div>
  <div class="card-body">
    <p><strong>Responsável:</strong> {{ visita.responsavel }}</p>
    <p><strong>Motivo:</strong><br>{{ visita.motivo|linebreaksbr }}</p>
    <p><strong>Achados:</strong><br>{{ visita.achados|linebreaksbr|default:"—" }}</p>
    <p><strong>Conclusões e encaminhamentos:</strong><br>{{ visita.conclusoes_encaminhamentos|linebreaksbr|default:"—" }}</p>

    {% if visita.fotos.all %}
    <hr>
    <strong>Fotos</strong>
    <div class="d-flex flex-wrap gap-2 mt-2">
      {% for foto in visita.fotos.all %}
      <a href="{{ foto.arquivo.url }}" target="_blank" title="{{ foto.nome_original }}">
        <img src="{{ foto.arquivo.url }}" alt="{{ foto.nome_original }}"
             style="height:90px;width:90px;object-fit:cover;border:1px solid #dee2e6;border-radius:4px;">
      </a>
      {% endfor %}
    </div>
    {% endif %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Rodar todos os testes pendentes (Tasks 7, 8, 9)**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -v`
Expected: PASS (todos os testes, incluindo `test_visita_list_filtra_por_data` e `test_cria_visita_via_post_com_foto`)

- [ ] **Step 7: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/visita_detail.html
git commit -m "feat: detalhe da visita tecnica + permissao de edicao"
```

---

## Task 10: Editar e excluir visita (com segurança e log)

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever os testes (falhando)**

```python
@pytest.mark.django_db
def test_outro_usuario_nao_exclui_visita(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    U = get_user_model()
    dono = U.objects.create_user(username='dona', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    outro = U.objects.create_user(username='outro', password='1', first_name='Beto', last_name='Reis')
    client.force_login(outro)
    resp = client.post(reverse('inspecoes:visita_delete', args=[v.pk]))
    assert resp.status_code == 302
    assert VisitaTecnica.objects.filter(pk=v.pk).exists()  # não excluiu


@pytest.mark.django_db
def test_responsavel_exclui_visita(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica, LogAcesso
    U = get_user_model()
    dono = U.objects.create_user(username='dona2', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    client.force_login(dono)
    resp = client.post(reverse('inspecoes:visita_delete', args=[v.pk]))
    assert resp.status_code == 302
    assert not VisitaTecnica.objects.filter(pk=v.pk).exists()
    assert LogAcesso.objects.filter(tipo='visita_excluida').exists()


@pytest.mark.django_db
def test_responsavel_edita_visita(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    U = get_user_model()
    dono = U.objects.create_user(username='dona3', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='antigo', achados='x', conclusoes_encaminhamentos='x')
    client.force_login(dono)
    resp = client.post(reverse('inspecoes:visita_update', args=[v.pk]), {
        'data_visita': date.today().isoformat(), 'responsavel': 'Ana Lima',
        'motivo': 'novo motivo', 'achados': 'x', 'conclusoes_encaminhamentos': 'x',
    })
    assert resp.status_code == 302
    v.refresh_from_db()
    assert v.motivo == 'novo motivo'
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k "exclui or edita" -v`
Expected: FAIL (NoReverseMatch `visita_update`/`visita_delete`)

- [ ] **Step 3: Adicionar as views**

Após `visita_detail` em `views.py`, adicione:

```python
def _acesso_negado_visita(request, visita):
    messages.error(
        request,
        f'Acesso negado. Apenas o responsável ("{visita.responsavel}") pode realizar esta ação.',
    )
    return redirect('inspecoes:visita_detail', pk=visita.pk)


@login_required
def visita_update(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    form = VisitaTecnicaForm(request.POST or None, instance=visita)
    if form.is_valid():
        form.save()
        messages.success(request, 'Visita atualizada com sucesso.')
        return redirect('inspecoes:visita_detail', pk=visita.pk)
    return render(request, 'inspecoes/visita_form.html', {
        'form': form,
        'edificacao': visita.edificacao,
        'visita': visita,
        'fotos_existentes': visita.fotos.all(),
    })


@login_required
@require_POST
def visita_delete(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    edif_pk = visita.edificacao_id
    _log(request, 'visita_excluida',
         f'Visita técnica excluída de "{visita.edificacao.nome}" ({visita.data_visita:%d/%m/%Y}).')
    visita.delete()
    messages.success(request, 'Visita excluída com sucesso.')
    return redirect('inspecoes:visita_list', edif_pk=edif_pk)
```

- [ ] **Step 4: Adicionar as rotas**

Em `urls.py`, no bloco "Visitas técnicas":

```python
    path('visitas/<int:pk>/editar/', views.visita_update, name='visita_update'),
    path('visitas/<int:pk>/excluir/', views.visita_delete, name='visita_delete'),
```

- [ ] **Step 5: Rodar os testes**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k "exclui or edita" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/tests/test_visitas.py
git commit -m "feat: editar/excluir visita com seguranca por responsavel e log"
```

---

## Task 11: Upload e exclusão de fotos da visita (AJAX, para a edição)

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Test: `src/apps/inspecoes/tests/test_visitas.py`

- [ ] **Step 1: Escrever os testes (falhando)**

```python
@pytest.mark.django_db
def test_upload_foto_visita_ajax(client, usuario_logado, edificacao):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.inspecoes.models import VisitaTecnica
    png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
           b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
           b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='X', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    foto = SimpleUploadedFile('a.png', png, content_type='image/png')
    resp = client.post(reverse('inspecoes:visita_foto_upload', args=[v.pk]), {'arquivo': foto})
    assert resp.status_code == 200
    assert resp.json()['id']
    assert v.fotos.count() == 1


@pytest.mark.django_db
def test_delete_foto_visita(client, usuario_logado, edificacao):
    from django.core.files.base import ContentFile
    from apps.inspecoes.models import VisitaTecnica, VisitaFoto
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='X', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    f = VisitaFoto.objects.create(visita=v, arquivo=ContentFile(b'x', name='a.jpg'),
                                  nome_original='a.jpg', tamanho_bytes=1)
    resp = client.delete(reverse('inspecoes:visita_foto_delete', args=[f.pk]))
    assert resp.status_code == 204
    assert v.fotos.count() == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k "foto_visita or delete_foto_visita" -v`
Expected: FAIL (NoReverseMatch)

- [ ] **Step 3: Adicionar as views**

Após `visita_delete` em `views.py`, adicione:

```python
@login_required
@require_POST
def visita_foto_upload(request, visita_pk):
    visita = get_object_or_404(VisitaTecnica, pk=visita_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    if arquivo.content_type not in ALLOWED_CONTENT_TYPES:
        return JsonResponse({'erro': 'Formato inválido. Use JPEG ou PNG.'}, status=400)
    if arquivo.size > MAX_UPLOAD_SIZE:
        return JsonResponse({'erro': 'Arquivo muito grande. Máximo: 10 MB.'}, status=400)
    foto = VisitaFoto.objects.create(
        visita=visita, arquivo=arquivo,
        nome_original=arquivo.name, tamanho_bytes=arquivo.size,
    )
    return JsonResponse({'id': foto.pk, 'url': foto.arquivo.url, 'nome': foto.nome_original})


@login_required
@require_http_methods(['DELETE'])
def visita_foto_delete(request, pk):
    foto = get_object_or_404(VisitaFoto, pk=pk)
    foto.delete()
    return HttpResponse(status=204)
```

- [ ] **Step 4: Adicionar as rotas**

Em `urls.py`, no bloco "Visitas técnicas":

```python
    path('visitas/<int:visita_pk>/fotos/', views.visita_foto_upload, name='visita_foto_upload'),
    path('visitas/fotos/<int:pk>/', views.visita_foto_delete, name='visita_foto_delete'),
```

- [ ] **Step 5: Rodar os testes**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -k "foto_visita or delete_foto_visita" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/tests/test_visitas.py
git commit -m "feat: upload/exclusao de fotos da visita via AJAX"
```

---

## Task 12: Verificação final

**Files:** nenhum novo (validação)

- [ ] **Step 1: Rodar a suíte completa**

Run: `..\.venv\Scripts\python.exe -m pytest apps/inspecoes/tests/test_visitas.py -v`
Expected: PASS (todos)

- [ ] **Step 2: Verificação do sistema**

Run: `..\.venv\Scripts\python.exe manage.py check`
Expected: "System check identified no issues"

- [ ] **Step 3: Conferir migrações pendentes**

Run: `..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
Expected: "No changes detected"

- [ ] **Step 4: Teste manual no navegador**

Run (servidor de desenvolvimento): `..\.venv\Scripts\python.exe manage.py runserver`
Verifique manualmente:
1. `/` mostra o menu com os dois cartões
2. "Inspeção Predial" abre `/inspecoes/` (lista existente, intacta)
3. "Visita Técnica" abre a lista de localidades
4. Escolher uma localidade → "Nova Visita" → preencher + anexar foto → salvar
5. Detalhe mostra os dados e a foto
6. Editar e excluir funcionam para o responsável
7. Filtro por data na lista da localidade funciona

- [ ] **Step 5: Commit final (se houver ajustes)**

```bash
git add -A
git commit -m "chore: verificacao final do modulo de visitas tecnicas"
git push origin main
```

---

## Self-Review (cobertura da spec)

- ✅ Modelos `VisitaTecnica`/`VisitaFoto` (Task 2) — spec §4
- ✅ Página inicial com menu + mover lista p/ `/inspecoes/` (Task 5) — spec §3.1
- ✅ Navegação localidade→visitas com filtro por data (Tasks 6, 7) — spec §5
- ✅ Criar/detalhe/editar/excluir (Tasks 8, 9, 10) — spec §5
- ✅ Segurança por responsável (Task 10) — spec §6
- ✅ Log de acesso `visita_criada`/`visita_excluida` (Tasks 2, 8, 10) — spec §7
- ✅ Fotos na criação + AJAX na edição, câmera no mobile (Tasks 8, 11) — spec §8
- ✅ Admin (Task 3) — spec §9
- ✅ Testes (todas as tasks) — spec §11
- ✅ Backups: sem ação (incluídos automaticamente) — spec §10
- ✅ Fora de escopo respeitado: sem PDF, sem GUT, sem PWA na visita — spec §12
