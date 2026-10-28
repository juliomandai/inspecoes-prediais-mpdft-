# Relatório Final em Word (.docx) com Texto Gerado por LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir completamente a geração em PDF do Relatório Final de Inspeção por um documento Word (.docx), reproduzindo a formatação exata do laudo-modelo real do MPDFT/SPO, com ~17 trechos de texto narrativo gerados automaticamente por um LLM (Gemini) a partir dos achados e do painel de encerramento já calculados — nunca inventando dados fora do que é fornecido.

**Architecture:** Novo app `apps.relatorio_final` monta um payload JSON só com dados já existentes/calculados (`dados.py`), chama o Gemini pedindo uma resposta JSON estruturada com schema fechado (`gemini_client.py`), e preenche um template Word pré-construído com `docxtpl` (`docx_builder.py`). O template `.docx` é construído UMA VEZ a partir do arquivo real enviado pelo usuário, substituindo os textos de exemplo por marcadores Jinja (`{{ variavel }}`) célula a célula / parágrafo a parágrafo, preservando 100% da formatação original (fonte, cor, tabulação, tamanho de fotos) porque a substituição edita o texto dos `run`s existentes, nunca recria a formatação do zero. Duas mudanças de schema (CREA/ART/histórico de intervenções) ficam nos apps `edificacoes`/`inspecoes`, por serem dados de cadastro reaproveitáveis — não pertencem ao novo app.

**Tech Stack:** Django 5.2 (já em uso), `docxtpl` (templating Jinja2 sobre `.docx`, usa `python-docx` por baixo), `google-genai` (SDK oficial do Gemini), `pydantic` (schema de saída estruturada — instalado transitivamente pelo `google-genai`), modelo `gemini-3.8-flash` (camada gratuita, confirmado em ai.google.dev/gemini-api/docs/pricing em 2026-10-28).

---

## Antes de começar: decisões tomadas no grill de 2026-10-27/28 (contexto, não repetir)

- Word substitui o PDF por completo. Nada volta ao sistema depois de gerado (sem versionamento do .docx editado).
- LLM: uma única chamada por relatório, saída JSON estruturada, Gemini (camada gratuita aceita conscientemente, mesmo com uso dos dados para treino pelo Google).
- Grounding estrito: o LLM só sintetiza os dados fornecidos no payload — nunca inventa normas, números ou fatos. Único vocabulário fechado: classificações de "Manutenção"/"Uso" no quadro de avaliação.
- Falha do LLM nunca bloqueia a geração do relatório — campos ficam como string vazia.
- Processo SEI fica fora (campo `[número do processo]` manual no Word). Data de averbação fora de escopo.
- **Simplificações desta rodada de planejamento, com base na inspeção completa do arquivo-modelo real** (`Laudo_Inspecao_Predial_PJ_Infancia_Juventude - Regina.docx`), que o grill não tinha capturado:
  - **"Objetivo"** (seção c) é texto 100% genérico no modelo real (duas frases-padrão, sem nenhum dado da inspeção) — vira texto **estático** no template, igual a "Metodologia"/"Fundamentação Normativa"/"Encerramento". Removido do schema do LLM.
  - **"Conclusão e direcionamentos"** de cada especialidade (itens h.ii/i.ii/j.ii do esboço original) é o campo **`InspecaoEspecialidade.conclusao`, que já existe e já é manualmente digitado pelo profissional** — não precisa de LLM nem de novo campo.
  - **"Forma de execução"** no quadro Plano de Ação é derivada deterministicamente do campo `Achado.direcionamento` (que já tem exatamente as 3 opções usadas no modelo: garantia/manutenção/nova contratação) — não é mais uma inferência do LLM. Isso elimina a exceção à regra de grounding que havia sido aceita no grill.
  - A frase da "Matriz de Risco e Prazo" ("N ocorrências combinam risco elevado e prazo curto...") é puramente aritmética (`n_ganhos_rapidos`, já calculado) — fica como texto com variável Jinja, não LLM.
  - "Distribuição por Especialidade" (resultados gerais, sub-item i) no modelo real é só a Tabela 7 — não tem nenhum parágrafo de texto ali. Removido do schema do LLM.

## Schema final de texto gerado por LLM (17 campos, ver Task 7)

`sumario_executivo`, `principais_constatacoes`, `providencias_administracao`, `resultados_gerais_intro`, `resultados_gerais_achados_criticos`, `itens_conformidade_civil`, `itens_conformidade_eletrica`, `itens_conformidade_mecanica`, `manutencao_classificacao` (vocabulário fechado), `manutencao_fundamentacao`, `uso_classificacao` (vocabulário fechado), `uso_fundamentacao`, `plano_acao_imediato`, `plano_acao_curto`, `plano_acao_medio`, `plano_acao_longo`, `conclusao`.

---

## File Structure

```
src/apps/edificacoes/
  models.py            MODIFY — + Profissional, + HistoricoIntervencao
  forms.py              MODIFY — + ProfissionalForm
  views.py              MODIFY — + profissional_list/create/update, + lógica de histórico no form de Edificacao
  urls.py                MODIFY — + rotas de profissional
  admin.py               MODIFY — + ProfissionalAdmin, HistoricoIntervencaoInline
  templates/edificacoes/
    profissional_list.html   CREATE
    profissional_form.html   CREATE
    form.html                 MODIFY — + linhas dinâmicas de histórico de intervenções
  migrations/0006_profissional.py          CREATE
  migrations/0007_historicointervencao.py  CREATE
  tests.py               MODIFY — + testes de Profissional e HistoricoIntervencao

src/apps/inspecoes/
  models.py              MODIFY — + numero_art, troca profissional (TextField) por profissionais (M2M)
  forms.py                MODIFY — + numero_art no EspecialidadeForm
  views.py                MODIFY — especialidade_create/update usam profissionais por id
  templates/inspecoes/especialidade_form.html   MODIFY — select de profissionais em vez de texto livre
  migrations/0019_inspecaoespecialidade_numero_art.py       CREATE
  migrations/0020_inspecaoespecialidade_profissionais.py    CREATE
  tests/test_especialidade_profissionais.py                  CREATE

src/apps/relatorio_final/                 CREATE (novo app)
  __init__.py
  apps.py
  dados.py              classificar_condicao_global, plano_acao_por_horizonte, montar_payload_llm
  gemini_client.py       TextosRelatorioFinal (pydantic), gerar_textos_relatorio
  docx_builder.py         gerar_docx_relatorio
  templates_docx/relatorio_final_modelo.docx   CREATE (artefato binário, construído pela Task 9)
  tests/__init__.py
  tests/test_dados.py
  tests/test_gemini_client.py
  tests/test_docx_builder.py

scripts/build_relatorio_final_docx_template.py   CREATE (script de construção do template, roda uma vez)

src/mpdft_inspecoes/settings.py   MODIFY — + GEMINI_API_KEY, GEMINI_MODEL, + apps.relatorio_final
src/requirements.txt               MODIFY — + docxtpl, google-genai

src/apps/inspecoes/models.py (RelatorioFinalInspecao)   MODIFY — arquivo_pdf -> arquivo_docx
src/apps/inspecoes/views.py (relatorio_final_gerar/download)   MODIFY — gera .docx em vez de PDF
src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html   MODIFY — "Baixar PDF" -> "Baixar Word"
src/apps/inspecoes/migrations/0021_relatoriofinalinspecao_arquivo_docx.py   CREATE
```

---

### Task 1: Entidade `Profissional` (nome + CREA)

**Files:**
- Modify: `src/apps/edificacoes/models.py`
- Create: `src/apps/edificacoes/migrations/0006_profissional.py`
- Modify: `src/apps/edificacoes/forms.py`
- Modify: `src/apps/edificacoes/views.py`
- Modify: `src/apps/edificacoes/urls.py`
- Modify: `src/apps/edificacoes/admin.py`
- Create: `src/apps/edificacoes/templates/edificacoes/profissional_list.html`
- Create: `src/apps/edificacoes/templates/edificacoes/profissional_form.html`
- Modify: `src/apps/edificacoes/tests.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `src/apps/edificacoes/tests.py`, adicionar:

```python
from apps.edificacoes.models import Profissional


@pytest.mark.django_db
def test_profissional_crea_e_unico_entre_ativos():
    Profissional.objects.create(nome='Ana Civil', crea='12345/D-DF')
    with pytest.raises(Exception):
        Profissional.objects.create(nome='Outra Pessoa', crea='12345/D-DF')


@pytest.mark.django_db
def test_profissional_form_exige_crea():
    from apps.edificacoes.forms import ProfissionalForm
    form = ProfissionalForm(data={'nome': 'Ana Civil', 'crea': ''})
    assert not form.is_valid()
    assert 'crea' in form.errors
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes/tests.py -k profissional -v`
Expected: FAIL — `ImportError: cannot import name 'Profissional'`

- [ ] **Step 3: Criar o model**

Em `src/apps/edificacoes/models.py`, adicionar ao final do arquivo:

```python
class Profissional(SoftDeleteModel):
    """Engenheiro(a)/profissional responsável técnico, reaproveitável entre
    inspeções (como Edificacao) — ver ADR do grill de 2026-10-27: antes era
    só texto livre em InspecaoEspecialidade.profissional."""
    nome = models.CharField('Nome', max_length=200)
    crea = models.CharField(
        'CREA', max_length=30,
        help_text='Número do registro no CREA (ex.: "12345/D-DF"). '
                   'Profissionais migrados do cadastro antigo recebem um '
                   'placeholder "PENDENTE-N" a completar manualmente.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Profissional'
        verbose_name_plural = 'Profissionais'
        constraints = [
            models.UniqueConstraint(
                fields=['crea'], condition=Q(excluido_em__isnull=True),
                name='unique_profissional_crea_ativo',
            ),
        ]

    def __str__(self):
        return self.nome
```

- [ ] **Step 4: Gerar e revisar a migração**

Run: `cd src && ../.venv/Scripts/python.exe manage.py makemigrations edificacoes`
Expected: `Migrations for 'edificacoes': apps\edificacoes\migrations\0006_profissional.py`

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes/tests.py -k profissional -v`
Expected: PASS (2 testes)

- [ ] **Step 6: Form, views, urls, admin, templates (CRUD igual ao de Edificacao)**

Em `src/apps/edificacoes/forms.py`, adicionar:

```python
class ProfissionalForm(forms.ModelForm):
    class Meta:
        model = Profissional
        fields = ['nome', 'crea']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'crea': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: 12345/D-DF'}),
        }

    def clean_crea(self):
        crea = self.cleaned_data['crea'].strip()
        qs = Profissional.objects.filter(crea__iexact=crea)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um profissional cadastrado com este CREA.')
        return crea
```

(e adicionar `Profissional` ao `from .models import Edificacao` existente, virando `from .models import Edificacao, Profissional`).

Em `src/apps/edificacoes/views.py`, adicionar ao final:

```python
from .forms import ProfissionalForm
from .models import Profissional


@staff_member_required
def profissional_list(request):
    profissionais = Profissional.objects.all()
    return render(request, 'edificacoes/profissional_list.html', {'profissionais': profissionais})


@staff_member_required
def profissional_create(request):
    form = ProfissionalForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Profissional cadastrado com sucesso.')
        return redirect('edificacoes:profissional_list')
    return render(request, 'edificacoes/profissional_form.html', {'form': form, 'titulo': 'Novo Profissional'})


@staff_member_required
def profissional_update(request, pk):
    profissional = get_object_or_404(Profissional, pk=pk)
    form = ProfissionalForm(request.POST or None, instance=profissional)
    if form.is_valid():
        form.save()
        messages.success(request, 'Profissional atualizado com sucesso.')
        return redirect('edificacoes:profissional_list')
    return render(request, 'edificacoes/profissional_form.html', {'form': form, 'titulo': f'Editar — {profissional.nome}'})
```

Em `src/apps/edificacoes/urls.py`, adicionar:

```python
    path('profissionais/', views.profissional_list, name='profissional_list'),
    path('profissionais/novo/', views.profissional_create, name='profissional_create'),
    path('profissionais/<int:pk>/editar/', views.profissional_update, name='profissional_update'),
```

Em `src/apps/edificacoes/admin.py`, adicionar:

```python
from .models import Profissional


@admin.register(Profissional)
class ProfissionalAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['nome', 'crea', 'criado_em', 'excluido_em']
    search_fields = ['nome', 'crea']
    ordering = ['nome']
```

Criar `src/apps/edificacoes/templates/edificacoes/profissional_list.html` (copiar a estrutura de `edificacoes/templates/edificacoes/list.html`, trocando título/colunas):

```html
{% extends 'base.html' %}
{% block title %}Profissionais — Inspeções Prediais MPDFT{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h2><i class="bi bi-person-badge"></i> Profissionais</h2>
  <a href="{% url 'edificacoes:profissional_create' %}" class="btn btn-primary">
    <i class="bi bi-plus-lg"></i> Novo Profissional
  </a>
</div>
<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-hover mb-0">
      <thead class="table-light">
        <tr><th>Nome</th><th>CREA</th><th>Ações</th></tr>
      </thead>
      <tbody>
        {% for p in profissionais %}
        <tr>
          <td class="fw-semibold">{{ p.nome }}</td>
          <td class="text-muted">{{ p.crea }}</td>
          <td>
            <a href="{% url 'edificacoes:profissional_update' p.pk %}" class="btn btn-sm btn-outline-secondary">
              <i class="bi bi-pencil"></i> Editar
            </a>
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="3" class="text-center text-muted py-4">Nenhum profissional cadastrado.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

Criar `src/apps/edificacoes/templates/edificacoes/profissional_form.html`:

```html
{% extends 'base.html' %}
{% block title %}{{ titulo }} — Inspeções Prediais MPDFT{% endblock %}
{% block content %}
<nav aria-label="breadcrumb" class="mb-3">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{% url 'edificacoes:profissional_list' %}">Profissionais</a></li>
    <li class="breadcrumb-item active">{{ titulo }}</li>
  </ol>
</nav>
<div class="card shadow-sm" style="max-width: 500px;">
  <div class="card-header"><h5 class="mb-0">{{ titulo }}</h5></div>
  <div class="card-body">
    <form method="post">
      {% csrf_token %}
      <div class="mb-3">
        <label for="{{ form.nome.id_for_label }}" class="form-label fw-semibold">Nome <span class="text-danger">*</span></label>
        {{ form.nome }}
        {% if form.nome.errors %}<div class="text-danger small">{{ form.nome.errors.0 }}</div>{% endif %}
      </div>
      <div class="mb-3">
        <label for="{{ form.crea.id_for_label }}" class="form-label fw-semibold">CREA <span class="text-danger">*</span></label>
        {{ form.crea }}
        {% if form.crea.errors %}<div class="text-danger small">{{ form.crea.errors.0 }}</div>{% endif %}
      </div>
      <div class="d-flex gap-2">
        <button type="submit" class="btn btn-primary"><i class="bi bi-check-lg"></i> Salvar</button>
        <a href="{% url 'edificacoes:profissional_list' %}" class="btn btn-outline-secondary">Cancelar</a>
      </div>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Rodar a suíte do app e confirmar**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes -v`
Expected: PASS (todos)

- [ ] **Step 8: Commit**

```bash
git add src/apps/edificacoes/
git commit -m "feat: adiciona entidade Profissional (nome + CREA), reaproveitavel entre inspecoes"
```

---

### Task 2: Entidade `HistoricoIntervencao` (histórico de obras por edificação)

**Files:**
- Modify: `src/apps/edificacoes/models.py`
- Create: `src/apps/edificacoes/migrations/0007_historicointervencao.py`
- Modify: `src/apps/edificacoes/views.py`
- Modify: `src/apps/edificacoes/admin.py`
- Modify: `src/apps/edificacoes/templates/edificacoes/form.html`
- Modify: `src/apps/edificacoes/tests.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `src/apps/edificacoes/tests.py`:

```python
from apps.edificacoes.models import HistoricoIntervencao


@pytest.mark.django_db
def test_historico_intervencao_ordena_por_ano():
    e = Edificacao.objects.create(nome='Sede com histórico')
    HistoricoIntervencao.objects.create(edificacao=e, ano=2023, descricao='Troca de chiller')
    HistoricoIntervencao.objects.create(edificacao=e, ano=2022, descricao='Recuperação de fachada')
    anos = list(e.historico_intervencoes.values_list('ano', flat=True))
    assert anos == [2022, 2023]
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes/tests.py -k historico -v`
Expected: FAIL — `ImportError: cannot import name 'HistoricoIntervencao'`

- [ ] **Step 3: Criar o model**

Em `src/apps/edificacoes/models.py`, adicionar ao final:

```python
class HistoricoIntervencao(SoftDeleteModel):
    """Uma linha do quadro 'Ano / Intervenção' do laudo-modelo (seção
    Caracterização da Edificação) — intervenções relevantes já realizadas
    na edificação (reforma, troca de equipamento etc.)."""
    edificacao = models.ForeignKey(
        Edificacao, on_delete=models.CASCADE, related_name='historico_intervencoes',
        verbose_name='Edificação',
    )
    ano = models.PositiveIntegerField('Ano')
    descricao = models.CharField('Intervenção', max_length=300)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ano', 'id']
        verbose_name = 'Histórico de intervenção'
        verbose_name_plural = 'Histórico de intervenções'

    def __str__(self):
        return f'{self.ano} — {self.descricao}'
```

- [ ] **Step 4: Gerar a migração**

Run: `cd src && ../.venv/Scripts/python.exe manage.py makemigrations edificacoes`
Expected: `Migrations for 'edificacoes': apps\edificacoes\migrations\0007_historicointervencao.py`

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes/tests.py -k historico -v`
Expected: PASS

- [ ] **Step 6: Admin**

Em `src/apps/edificacoes/admin.py`:

```python
from .models import HistoricoIntervencao


@admin.register(HistoricoIntervencao)
class HistoricoIntervencaoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['edificacao', 'ano', 'descricao']
    list_filter = ['edificacao']
    ordering = ['edificacao', 'ano']
```

- [ ] **Step 7: Linhas dinâmicas no form de Edificação (views + template)**

Em `src/apps/edificacoes/views.py`, adicionar uma função auxiliar e usá-la em `edificacao_create`/`edificacao_update`:

```python
def _sincronizar_historico(edificacao, request):
    """Substitui todo o histórico de intervenções pelos pares enviados —
    mesmo padrão 'substitui tudo' já usado para profissionais em
    InspecaoEspecialidade (simples e suficiente: poucas linhas por
    edificação, editadas raramente)."""
    anos = request.POST.getlist('historico_ano')
    descricoes = request.POST.getlist('historico_descricao')
    edificacao.historico_intervencoes.all().delete()
    for ano, descricao in zip(anos, descricoes):
        ano = ano.strip()
        descricao = descricao.strip()
        if ano and descricao:
            HistoricoIntervencao.objects.create(edificacao=edificacao, ano=int(ano), descricao=descricao)
```

Importar `HistoricoIntervencao` no topo do arquivo (`from .models import Edificacao, Profissional, HistoricoIntervencao`).

Modificar `edificacao_create`:

```python
@staff_member_required
def edificacao_create(request):
    form = EdificacaoForm(request.POST or None)
    if form.is_valid():
        edificacao = form.save()
        _sincronizar_historico(edificacao, request)
        messages.success(request, 'Edificação cadastrada com sucesso.')
        return redirect('edificacoes:list')
    return render(request, 'edificacoes/form.html', {
        'form': form, 'titulo': 'Nova Edificação', 'historico': [],
    })
```

Modificar `edificacao_update`:

```python
@staff_member_required
def edificacao_update(request, pk):
    edificacao = get_object_or_404(Edificacao, pk=pk)
    form = EdificacaoForm(request.POST or None, instance=edificacao)
    if form.is_valid():
        form.save()
        _sincronizar_historico(edificacao, request)
        messages.success(request, 'Edificação atualizada com sucesso.')
        return redirect('edificacoes:list')
    return render(request, 'edificacoes/form.html', {
        'form': form, 'titulo': f'Editar — {edificacao.nome}',
        'historico': edificacao.historico_intervencoes.all(),
    })
```

Em `src/apps/edificacoes/templates/edificacoes/form.html`, adicionar antes do bloco `{% if form.instance.pk %}` (checkbox "ativa"):

```html
      <div class="mb-3">
        <label class="form-label fw-semibold">Histórico de intervenções</label>
        <div id="historico-container">
          {% for h in historico %}
          <div class="input-group mb-2 historico-row">
            <input type="number" name="historico_ano" class="form-control" style="max-width:100px" value="{{ h.ano }}" placeholder="Ano">
            <input type="text" name="historico_descricao" class="form-control" value="{{ h.descricao }}" placeholder="Intervenção">
            <button type="button" class="btn btn-outline-danger" onclick="this.closest('.historico-row').remove()" title="Remover">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>
          {% endfor %}
        </div>
        <button type="button" class="btn btn-outline-primary btn-sm" onclick="adicionarHistorico()">
          <i class="bi bi-plus-lg"></i> Adicionar intervenção
        </button>
      </div>
```

E no `{% block extra_js %}` já existente (ver Task da calculadora de área — arquivo já tem um bloco `extra_js`), adicionar a função:

```javascript
function adicionarHistorico() {
  var c = document.getElementById('historico-container');
  var div = document.createElement('div');
  div.className = 'input-group mb-2 historico-row';
  div.innerHTML =
    '<input type="number" name="historico_ano" class="form-control" style="max-width:100px" placeholder="Ano">' +
    '<input type="text" name="historico_descricao" class="form-control" placeholder="Intervenção">' +
    '<button type="button" class="btn btn-outline-danger" onclick="this.closest(\'.historico-row\').remove()" title="Remover"><i class="bi bi-x-lg"></i></button>';
  c.appendChild(div);
  div.querySelector('input').focus();
}
```

- [ ] **Step 8: Teste de integração via view**

Em `src/apps/edificacoes/tests.py`:

```python
@pytest.mark.django_db
def test_edificacao_update_sincroniza_historico(client, django_user_model):
    staff = django_user_model.objects.create_user(username='admin', password='x', is_staff=True)
    client.force_login(staff)
    e = Edificacao.objects.create(nome='Sede histórico view')
    resp = client.post(f'/edificacoes/edificacoes/{e.pk}/editar/', {
        'nome': 'Sede histórico view', 'endereco': '', 'pavimentos': '', 'ativo': 'on',
        'historico_ano': ['2022', '2023'],
        'historico_descricao': ['Reforma de fachada', 'Troca de elevador'],
    })
    assert resp.status_code == 302
    assert list(e.historico_intervencoes.values_list('ano', 'descricao')) == [
        (2022, 'Reforma de fachada'), (2023, 'Troca de elevador'),
    ]
```

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/edificacoes -v`
Expected: PASS (todos)

- [ ] **Step 9: Commit**

```bash
git add src/apps/edificacoes/
git commit -m "feat: adiciona historico de intervencoes por edificacao (quadro Caracterizacao do laudo)"
```

---

### Task 3: Campo `numero_art` por especialidade

**Files:**
- Modify: `src/apps/inspecoes/models.py`
- Create: `src/apps/inspecoes/migrations/0019_inspecaoespecialidade_numero_art.py`
- Modify: `src/apps/inspecoes/forms.py`
- Modify: `src/apps/inspecoes/templates/inspecoes/especialidade_form.html`
- Create: `src/apps/inspecoes/tests/test_especialidade_profissionais.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `src/apps/inspecoes/tests/test_especialidade_profissionais.py`:

```python
import pytest
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_numero_art_fica_em_branco_por_padrao():
    edificacao = Edificacao.objects.create(nome='Sede ART')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    assert esp.numero_art == ''
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes/tests/test_especialidade_profissionais.py -v`
Expected: FAIL — `TypeError` ou `FieldError` (campo `numero_art` não existe)

- [ ] **Step 3: Adicionar o campo**

Em `src/apps/inspecoes/models.py`, dentro de `InspecaoEspecialidade`, depois de `conclusao`:

```python
    numero_art = models.CharField(
        'Número da ART', max_length=50, blank=True,
        help_text='ART desta especialidade específica — uma por engenharia (civil/elétrica/mecânica).',
    )
```

- [ ] **Step 4: Gerar a migração**

Run: `cd src && ../.venv/Scripts/python.exe manage.py makemigrations inspecoes`
Expected: `Migrations for 'inspecoes': apps\inspecoes\migrations\0019_inspecaoespecialidade_numero_art.py`

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes/tests/test_especialidade_profissionais.py -v`
Expected: PASS

- [ ] **Step 6: Expor o campo no formulário**

Em `src/apps/inspecoes/forms.py`, em `EspecialidadeForm.Meta`:

```python
    class Meta:
        model = InspecaoEspecialidade
        fields = ['especialidade', 'data_inspecao', 'numero_art']
        widgets = {
            'especialidade': forms.Select(attrs={'class': 'form-select'}),
            'numero_art': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: 1234567890123456'}),
        }
        labels = {
            'especialidade': 'Especialidade',
            'numero_art': 'Número da ART',
        }
```

Em `src/apps/inspecoes/templates/inspecoes/especialidade_form.html`, adicionar depois do campo `data_inspecao`:

```html
          <div class="mb-3">
            <label for="{{ form.numero_art.id_for_label }}" class="form-label">{{ form.numero_art.label }}</label>
            {{ form.numero_art }}
            {% if form.numero_art.errors %}
            <div class="text-danger small mt-1">{{ form.numero_art.errors }}</div>
            {% endif %}
          </div>
```

- [ ] **Step 7: Rodar a suíte do app**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes -v`
Expected: PASS (todos)

- [ ] **Step 8: Commit**

```bash
git add src/apps/inspecoes/models.py src/apps/inspecoes/migrations/0019_inspecaoespecialidade_numero_art.py src/apps/inspecoes/forms.py src/apps/inspecoes/templates/inspecoes/especialidade_form.html src/apps/inspecoes/tests/test_especialidade_profissionais.py
git commit -m "feat: adiciona numero da ART por especialidade da inspecao"
```

---

### Task 4: `profissionais` (M2M para `Profissional`) substitui `profissional` (texto livre)

**Files:**
- Modify: `src/apps/inspecoes/models.py`
- Create: `src/apps/inspecoes/migrations/0020_inspecaoespecialidade_profissionais.py`
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/templates/inspecoes/especialidade_form.html`
- Modify: `src/apps/inspecoes/tests/test_especialidade_profissionais.py`

- [ ] **Step 1: Escrever os testes que falham**

Em `src/apps/inspecoes/tests/test_especialidade_profissionais.py`, adicionar:

```python
from apps.edificacoes.models import Profissional


@pytest.mark.django_db
def test_profissionais_lista_reflete_m2m():
    edificacao = Edificacao.objects.create(nome='Sede M2M')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    ana = Profissional.objects.create(nome='Ana Civil', crea='111/D-DF')
    bia = Profissional.objects.create(nome='Bia Civil', crea='222/D-DF')
    esp.profissionais.set([ana, bia])
    assert esp.profissionais_lista == ['Ana Civil', 'Bia Civil']
    assert esp.profissionais_display == 'Ana Civil, Bia Civil'


@pytest.mark.django_db
def test_migracao_converte_texto_livre_em_profissionais(migrator):
    """Usa pytest-django-migrations-style manual: aplica a migração 0019 ->
    0020 sobre dados criados em texto livre e confere a conversão. Se o
    plugin `django_test_migrations` não estiver instalado, pular este teste
    e validar manualmente com `migrate inspecoes 0019` + shell + `migrate
    inspecoes 0020` (ver Step 6)."""
    pytest.skip('Validação manual — ver Step 6 desta task.')
```

- [ ] **Step 2: Rodar e confirmar que o primeiro teste falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes/tests/test_especialidade_profissionais.py -k m2m -v`
Expected: FAIL — `FieldError: Cannot resolve keyword 'profissionais'`

- [ ] **Step 3: Trocar o campo e as properties no model**

Em `src/apps/inspecoes/models.py`, remover a linha `profissional = models.TextField(...)` e substituir por:

```python
    profissionais = models.ManyToManyField(
        'edificacoes.Profissional', related_name='especialidades',
        verbose_name='Profissionais responsáveis',
    )
```

Substituir as duas `@property` existentes:

```python
    @property
    def profissionais_lista(self):
        return list(self.profissionais.order_by('nome').values_list('nome', flat=True))

    @property
    def profissionais_display(self):
        return ', '.join(self.profissionais_lista)
```

- [ ] **Step 4: Escrever a migração de dados (AddField + RunPython + RemoveField num único arquivo)**

Criar `src/apps/inspecoes/migrations/0020_inspecaoespecialidade_profissionais.py`:

```python
from django.db import migrations, models
import django.db.models.deletion


def migrar_profissionais_para_entidade(apps, schema_editor):
    InspecaoEspecialidade = apps.get_model('inspecoes', 'InspecaoEspecialidade')
    Profissional = apps.get_model('edificacoes', 'Profissional')
    cache = {}
    contador = 1
    for esp in InspecaoEspecialidade.objects.all():
        nomes = [n.strip() for n in esp.profissional.splitlines() if n.strip()]
        for nome in nomes:
            chave = nome.lower()
            if chave not in cache:
                prof = Profissional.objects.filter(nome__iexact=nome).first()
                if prof is None:
                    prof = Profissional.objects.create(nome=nome, crea=f'PENDENTE-{contador}')
                    contador += 1
                cache[chave] = prof
            esp.profissionais.add(cache[chave])


def reverter_profissionais(apps, schema_editor):
    InspecaoEspecialidade = apps.get_model('inspecoes', 'InspecaoEspecialidade')
    for esp in InspecaoEspecialidade.objects.all():
        nomes = esp.profissionais.values_list('nome', flat=True)
        esp.profissional = '\n'.join(nomes)
        esp.save(update_fields=['profissional'])


class Migration(migrations.Migration):

    dependencies = [
        ('inspecoes', '0019_inspecaoespecialidade_numero_art'),
        ('edificacoes', '0006_profissional'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspecaoespecialidade',
            name='profissionais',
            field=models.ManyToManyField(
                related_name='especialidades', to='edificacoes.profissional',
                verbose_name='Profissionais responsáveis',
            ),
        ),
        migrations.RunPython(migrar_profissionais_para_entidade, reverter_profissionais),
        migrations.RemoveField(
            model_name='inspecaoespecialidade',
            name='profissional',
        ),
    ]
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes/tests/test_especialidade_profissionais.py -k m2m -v`
Expected: PASS

- [ ] **Step 6: Validar a migração de dados manualmente contra o banco de dev**

```bash
cd src
../.venv/Scripts/python.exe manage.py migrate inspecoes 0019
../.venv/Scripts/python.exe manage.py shell -c "
from apps.inspecoes.models import InspecaoEspecialidade
print(InspecaoEspecialidade.objects.count(), 'especialidades antes da migracao 0020')
"
../.venv/Scripts/python.exe manage.py migrate inspecoes 0020
../.venv/Scripts/python.exe manage.py shell -c "
from apps.inspecoes.models import InspecaoEspecialidade
from apps.edificacoes.models import Profissional
for esp in InspecaoEspecialidade.objects.all()[:5]:
    print(esp.pk, esp.profissionais_display)
print('placeholders:', Profissional.objects.filter(crea__startswith='PENDENTE-').count())
"
```
Expected: cada especialidade mostra os mesmos nomes que tinha antes em `profissional`, e a contagem de placeholders bate com o número de nomes distintos encontrados.

- [ ] **Step 7: Views — trocar `_profissionais_do_post` por versão baseada em IDs**

Em `src/apps/inspecoes/views.py`, substituir `_profissionais_do_post` (linha ~238-240):

```python
def _profissionais_ids_do_post(request):
    """Coleta os ids dos <select> dinâmicos 'profissionais' (um por campo)."""
    return [int(i) for i in request.POST.getlist('profissionais') if i.strip()]
```

Adicionar import no topo: `from apps.edificacoes.models import Profissional` (junto ao `from apps.edificacoes.forms import DescritivoEdificacaoForm` já existente).

Substituir `especialidade_create` (linha ~243-269):

```python
@login_required
def especialidade_create(request, inspecao_pk):
    inspecao = get_object_or_404(Inspecao, pk=inspecao_pk)
    form = EspecialidadeForm(request.POST or None, inspecao=inspecao)
    ids_selecionados = _profissionais_ids_do_post(request)
    erro_profissionais = None
    if request.method == 'POST' and form.is_valid():
        profissionais = Profissional.objects.filter(pk__in=ids_selecionados)
        if not profissionais:
            erro_profissionais = 'Informe ao menos um profissional responsável.'
        else:
            esp = form.save(commit=False)
            esp.inspecao = inspecao
            try:
                esp.full_clean(exclude=['profissionais'])
                esp.save()
                esp.profissionais.set(profissionais)
                _log(request, 'especialidade_criada', f'{esp.get_especialidade_display()} criada em "{inspecao.edificacao}".')
                messages.success(request, f'{esp.get_especialidade_display()} adicionada com sucesso.')
                return redirect('inspecoes:detail', pk=inspecao_pk)
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
    return render(request, 'inspecoes/especialidade_form.html', {
        'form': form,
        'inspecao': inspecao,
        'profissionais_disponiveis': Profissional.objects.all(),
        'ids_selecionados': ids_selecionados or [None],
        'erro_profissionais': erro_profissionais,
    })
```

Substituir `especialidade_update` (linha ~434-458):

```python
@login_required
def especialidade_update(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade.objects.select_related('inspecao'), pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    form = EspecialidadeForm(request.POST or None, instance=esp, inspecao=esp.inspecao)
    ids_selecionados = _profissionais_ids_do_post(request) if request.method == 'POST' else list(esp.profissionais.values_list('pk', flat=True))
    erro_profissionais = None
    if request.method == 'POST' and form.is_valid():
        profissionais = Profissional.objects.filter(pk__in=ids_selecionados)
        if not profissionais:
            erro_profissionais = 'Informe ao menos um profissional responsável.'
        else:
            esp = form.save(commit=False)
            esp.save()
            esp.profissionais.set(profissionais)
            if esp.status == 'finalizada':
                _avisar_relatorio_final_desatualizado(request, esp)
            messages.success(request, 'Especialidade atualizada com sucesso.')
            return _redirect_detail(esp.inspecao_id, esp.pk)
    return render(request, 'inspecoes/especialidade_form.html', {
        'form': form,
        'inspecao': esp.inspecao,
        'especialidade': esp,
        'profissionais_disponiveis': Profissional.objects.all(),
        'ids_selecionados': ids_selecionados or [None],
        'erro_profissionais': erro_profissionais,
    })
```

Nota: `_pode_editar_especialidade`, `_acesso_negado_especialidade` e `_pode_gerar_relatorio_final` **não precisam mudar** — continuam comparando `user.get_full_name()` contra `esp.profissionais_lista`, que ainda devolve uma lista de nomes (agora vinda do M2M).

- [ ] **Step 8: Template — trocar inputs de texto por `<select>`**

Substituir em `src/apps/inspecoes/templates/inspecoes/especialidade_form.html` o bloco "Profissionais responsáveis" (linhas 37-54):

```html
          <div class="mb-3">
            <label class="form-label">Profissionais responsáveis</label>
            <template id="profissional-select-template">
              <select name="profissionais" class="form-select">
                <option value="">Selecione...</option>
                {% for p in profissionais_disponiveis %}
                <option value="{{ p.pk }}">{{ p.nome }} — CREA {{ p.crea }}</option>
                {% endfor %}
              </select>
            </template>
            <div id="profissionais-container">
              {% for pid in ids_selecionados %}
              <div class="input-group mb-2 profissional-row">
                <span class="input-group-text"><i class="bi bi-person"></i></span>
                <select name="profissionais" class="form-select">
                  <option value="">Selecione...</option>
                  {% for p in profissionais_disponiveis %}
                  <option value="{{ p.pk }}" {% if p.pk == pid %}selected{% endif %}>{{ p.nome }} — CREA {{ p.crea }}</option>
                  {% endfor %}
                </select>
                <button type="button" class="btn btn-outline-danger" onclick="removerProfissional(this)" title="Remover">
                  <i class="bi bi-x-lg"></i>
                </button>
              </div>
              {% endfor %}
            </div>
            <button type="button" class="btn btn-outline-primary btn-sm" onclick="adicionarProfissional()">
              <i class="bi bi-plus-lg"></i> Adicionar profissional
            </button>
            <a href="{% url 'edificacoes:profissional_create' %}" target="_blank" class="btn btn-outline-secondary btn-sm">
              <i class="bi bi-person-plus"></i> Cadastrar novo profissional
            </a>
            {% if erro_profissionais %}<div class="text-danger small mt-1">{{ erro_profissionais }}</div>{% endif %}
          </div>
```

Substituir o JS no `{% block extra_js %}` (linhas 81-105):

```html
{% block extra_js %}
<script>
function adicionarProfissional() {
  var c = document.getElementById('profissionais-container');
  var div = document.createElement('div');
  div.className = 'input-group mb-2 profissional-row';
  var icon = document.createElement('span');
  icon.className = 'input-group-text';
  icon.innerHTML = '<i class="bi bi-person"></i>';
  var tpl = document.getElementById('profissional-select-template');
  var select = tpl.content.firstElementChild.cloneNode(true);
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn btn-outline-danger';
  btn.title = 'Remover';
  btn.innerHTML = '<i class="bi bi-x-lg"></i>';
  btn.onclick = function () { removerProfissional(btn); };
  div.appendChild(icon);
  div.appendChild(select);
  div.appendChild(btn);
  c.appendChild(div);
  select.focus();
}
function removerProfissional(btn) {
  var rows = document.querySelectorAll('#profissionais-container .profissional-row');
  if (rows.length <= 1) {
    btn.closest('.profissional-row').querySelector('select').value = '';
    return;
  }
  btn.closest('.profissional-row').remove();
}
</script>
{% endblock %}
```

- [ ] **Step 9: Teste de integração via view (criar especialidade escolhendo profissionais por id)**

Em `src/apps/inspecoes/tests/test_especialidade_profissionais.py`:

```python
@pytest.mark.django_db
def test_especialidade_create_usa_profissionais_por_id(client, django_user_model):
    user = django_user_model.objects.create_user(username='eng', password='x', first_name='Eng', last_name='Teste')
    client.force_login(user)
    edificacao = Edificacao.objects.create(nome='Sede view M2M')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    prof = Profissional.objects.create(nome='Ana Civil', crea='333/D-DF')
    resp = client.post(f'/inspecoes/inspecoes/{inspecao.pk}/especialidades/nova/', {
        'especialidade': 'civil', 'data_inspecao': '2026-01-01', 'numero_art': '',
        'profissionais': [str(prof.pk)],
    })
    assert resp.status_code == 302
    esp = InspecaoEspecialidade.objects.get(inspecao=inspecao)
    assert esp.profissionais_lista == ['Ana Civil']
```

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes -v`
Expected: PASS (todos)

- [ ] **Step 10: Commit**

```bash
git add src/apps/inspecoes/ src/apps/edificacoes/migrations/
git commit -m "feat: profissionais da especialidade passam a ser entidade cadastrada (nome+CREA), nao texto livre"
```

---

### Task 5: Scaffold do app `apps.relatorio_final`

**Files:**
- Create: `src/apps/relatorio_final/__init__.py`
- Create: `src/apps/relatorio_final/apps.py`
- Create: `src/apps/relatorio_final/tests/__init__.py`
- Modify: `src/mpdft_inspecoes/settings.py`
- Modify: `src/requirements.txt`

- [ ] **Step 1: Criar o app**

Criar `src/apps/relatorio_final/__init__.py` (vazio).

Criar `src/apps/relatorio_final/apps.py`:

```python
from django.apps import AppConfig


class RelatorioFinalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.relatorio_final'
    verbose_name = 'Relatório Final (Word + LLM)'
```

Criar `src/apps/relatorio_final/tests/__init__.py` (vazio).

- [ ] **Step 2: Registrar em `INSTALLED_APPS`**

Em `src/mpdft_inspecoes/settings.py`, no array `INSTALLED_APPS`:

```python
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
    'apps.relatorio_final',
]
```

- [ ] **Step 3: Configurações do Gemini**

Em `src/mpdft_inspecoes/settings.py`, ao final do arquivo:

```python
# ── Relatório Final — texto gerado por LLM (Gemini) ────────────────────────
# Camada gratuita aceita conscientemente (decisão do grill de 2026-10-27):
# o Google pode usar os dados enviados para treinar modelos. Se GEMINI_API_KEY
# estiver vazio, a geração de texto é pulada sem erro (ver gemini_client.py).
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-3.8-flash')
```

- [ ] **Step 4: Dependências**

Em `src/requirements.txt`, adicionar:

```
docxtpl>=0.16
google-genai>=0.1
```

Run: `cd src && ../.venv/Scripts/python.exe -m pip install -r requirements.txt`
Expected: instala `docxtpl`, `python-docx`, `jinja2`, `google-genai`, `pydantic` sem erro.

- [ ] **Step 5: Confirmar que o projeto ainda roda (`check` do Django)**

Run: `cd src && ../.venv/Scripts/python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit**

```bash
git add src/apps/relatorio_final/ src/mpdft_inspecoes/settings.py src/requirements.txt
git commit -m "feat: cria app relatorio_final e configura dependencias (docxtpl, google-genai)"
```

---

### Task 6: Dados determinísticos (`dados.py`) — condição global e plano de ação por horizonte

**Files:**
- Create: `src/apps/relatorio_final/dados.py`
- Create: `src/apps/relatorio_final/tests/test_dados.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `src/apps/relatorio_final/tests/test_dados.py`:

```python
import pytest
from types import SimpleNamespace
from apps.relatorio_final.dados import classificar_condicao_global, plano_acao_por_horizonte


def test_classificar_condicao_global():
    assert classificar_condicao_global(84) == 'Boa'
    assert classificar_condicao_global(80) == 'Boa'
    assert classificar_condicao_global(65) == 'Regular'
    assert classificar_condicao_global(50) == 'Regular'
    assert classificar_condicao_global(30) == 'Ruim'


def _achado(prazo_meses, direcionamento, recomendacao='Corrigir X.'):
    return SimpleNamespace(prazo_meses=prazo_meses, direcionamento=direcionamento, recomendacao=recomendacao,
                            get_direcionamento_display=lambda: {
                                'garantia': 'Garantia de obra', 'manutencao': 'Manutenção', 'nova_contratacao': 'Nova contratação',
                            }[direcionamento])


def test_plano_acao_por_horizonte_agrupa_e_deriva_forma_execucao():
    achados = [
        _achado(1, 'manutencao'),
        _achado(1, 'garantia'),
        _achado(3, 'nova_contratacao'),
        _achado(12, 'manutencao'),
        _achado(24, 'nova_contratacao'),
    ]
    linhas = plano_acao_por_horizonte(achados)
    assert [l['horizonte'] for l in linhas] == [
        'Imediato (até 1 mês)', 'Curto prazo (3 meses)', 'Médio prazo (6 meses)', 'Longo prazo (12 a 24 meses)',
    ]
    imediato = linhas[0]
    assert imediato['nc'] == 2
    assert 'Garantia de obra' in imediato['forma_execucao']
    assert 'Manutenção' in imediato['forma_execucao']
    medio = linhas[2]
    assert medio['nc'] == 0
    assert medio['forma_execucao'] == '—'
    longo = linhas[3]
    assert longo['nc'] == 2
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_dados.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.relatorio_final.dados'`

- [ ] **Step 3: Implementar**

Criar `src/apps/relatorio_final/dados.py`:

```python
"""Dados determinísticos do Relatório Final — calculados a partir de
números/campos já existentes, SEM depender do LLM. Ver grill de
2026-10-27/28: 'Forma de execução' deixou de ser uma inferência do LLM
porque `Achado.direcionamento` já tem exatamente a informação necessária."""

HORIZONTES_PRAZO = [
    (1, 'Imediato (até 1 mês)'),
    (3, 'Curto prazo (3 meses)'),
    (6, 'Médio prazo (6 meses)'),
    (None, 'Longo prazo (12 a 24 meses)'),  # agrupa 12, 18 e 24 meses
]

_ORDEM_DIRECIONAMENTO = ['garantia', 'manutencao', 'nova_contratacao']


def classificar_condicao_global(iqe):
    """Mesmos limiares de `_iqe_score` em apps/inspecoes/views.py — mapeia
    o índice já calculado para o rótulo do quadro 'Avaliação da Manutenção
    e do Uso' do laudo-modelo."""
    if iqe >= 80:
        return 'Boa'
    if iqe >= 50:
        return 'Regular'
    return 'Ruim'


def plano_acao_por_horizonte(nao_conformes):
    """Agrupa achados não conformes por horizonte de prazo (quadro 'Plano
    de Ação' do laudo-modelo). `forma_execucao` vem do campo
    `direcionamento` já existente em cada achado — nunca do LLM."""
    linhas = []
    for limite, rotulo in HORIZONTES_PRAZO:
        if limite is None:
            achados = [a for a in nao_conformes if a.prazo_meses >= 12]
        else:
            achados = [a for a in nao_conformes if a.prazo_meses == limite]
        chaves_presentes = sorted({a.direcionamento for a in achados}, key=_ORDEM_DIRECIONAMENTO.index)
        rotulos_presentes = []
        for chave in chaves_presentes:
            rotulos_presentes.append(next(a.get_direcionamento_display() for a in achados if a.direcionamento == chave))
        forma_execucao = ' e '.join(rotulos_presentes) if rotulos_presentes else '—'
        linhas.append({
            'horizonte': rotulo,
            'nc': len(achados),
            'recomendacoes': [a.recomendacao for a in achados if a.recomendacao.strip()],
            'forma_execucao': forma_execucao,
        })
    return linhas
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_dados.py -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add src/apps/relatorio_final/dados.py src/apps/relatorio_final/tests/test_dados.py
git commit -m "feat: dados deterministicos do relatorio final (condicao global, plano de acao por horizonte)"
```

---

### Task 7: Cliente Gemini (`gemini_client.py`) — schema fechado + falha nunca bloqueia

**Files:**
- Create: `src/apps/relatorio_final/gemini_client.py`
- Create: `src/apps/relatorio_final/tests/test_gemini_client.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `src/apps/relatorio_final/tests/test_gemini_client.py`:

```python
import pytest
from apps.relatorio_final import gemini_client


def test_sem_api_key_retorna_campos_vazios(settings):
    settings.GEMINI_API_KEY = ''
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos == dict(gemini_client.CAMPOS_VAZIOS)
    assert textos['sumario_executivo'] == ''


def test_falha_na_chamada_retorna_campos_vazios_sem_lancar(settings, monkeypatch):
    settings.GEMINI_API_KEY = 'fake-key'

    class ClienteQuebrado:
        def __init__(self, *a, **kw):
            raise RuntimeError('API fora do ar')

    monkeypatch.setattr(gemini_client.genai, 'Client', ClienteQuebrado)
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos == dict(gemini_client.CAMPOS_VAZIOS)


def test_chamada_bem_sucedida_retorna_textos_do_schema(settings, monkeypatch):
    settings.GEMINI_API_KEY = 'fake-key'
    resposta_json = gemini_client.TextosRelatorioFinal(
        **{campo: ('Boa' if 'classificacao' in campo and 'manutencao' in campo else
                   ('Regular, com ressalvas' if 'classificacao' in campo else f'Texto de {campo}.'))
           for campo in gemini_client.TextosRelatorioFinal.model_fields}
    ).model_dump_json()

    class InteractionFake:
        output_text = resposta_json

    class InteractionsFake:
        def create(self, **kwargs):
            return InteractionFake()

    class ClienteFake:
        def __init__(self, *a, **kw):
            self.interactions = InteractionsFake()

    monkeypatch.setattr(gemini_client.genai, 'Client', ClienteFake)
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos['sumario_executivo'] == 'Texto de sumario_executivo.'
    assert textos['manutencao_classificacao'] == 'Boa'
```

Nota: o teste acima usa o fato de `manutencao_classificacao` ser `Literal['Atende integralmente', 'Atende parcialmente', 'Não atende']` — ajustar o valor de exemplo (`'Boa'` não é um valor válido desse Literal!). Ver Step 2: o valor correto de exemplo para esse campo é `'Atende integralmente'`.

- [ ] **Step 2: Corrigir o teste com os valores reais do vocabulário fechado**

Reescrever a função `test_chamada_bem_sucedida_retorna_textos_do_schema` substituindo a construção de `resposta_json` por valores explícitos e válidos:

```python
def test_chamada_bem_sucedida_retorna_textos_do_schema(settings, monkeypatch):
    settings.GEMINI_API_KEY = 'fake-key'
    valores = {campo: f'Texto de {campo}.' for campo in gemini_client.TextosRelatorioFinal.model_fields}
    valores['manutencao_classificacao'] = 'Atende integralmente'
    valores['uso_classificacao'] = 'Regular, com ressalvas'
    resposta_json = gemini_client.TextosRelatorioFinal(**valores).model_dump_json()

    class InteractionFake:
        output_text = resposta_json

    class InteractionsFake:
        def create(self, **kwargs):
            return InteractionFake()

    class ClienteFake:
        def __init__(self, *a, **kw):
            self.interactions = InteractionsFake()

    monkeypatch.setattr(gemini_client.genai, 'Client', ClienteFake)
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos['sumario_executivo'] == 'Texto de sumario_executivo.'
    assert textos['manutencao_classificacao'] == 'Atende integralmente'
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_gemini_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.relatorio_final.gemini_client'`

- [ ] **Step 4: Implementar**

Criar `src/apps/relatorio_final/gemini_client.py`:

```python
"""Geração dos textos narrativos do Relatório Final via Gemini.

Regra de grounding (grill de 2026-10-27): o modelo só pode sintetizar os
dados fornecidos no payload — nunca inventar normas, números ou fatos.
Qualquer falha (sem API key, rede, resposta inválida) retorna todos os
campos como string vazia e NUNCA lança exceção — decisão de produto: o
relatório é sempre gerado, com ou sem os textos."""
import json
import logging
from typing import Literal

from django.conf import settings
from google import genai
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TextosRelatorioFinal(BaseModel):
    sumario_executivo: str
    principais_constatacoes: str
    providencias_administracao: str
    resultados_gerais_intro: str
    resultados_gerais_achados_criticos: str
    itens_conformidade_civil: str
    itens_conformidade_eletrica: str
    itens_conformidade_mecanica: str
    manutencao_classificacao: Literal['Atende integralmente', 'Atende parcialmente', 'Não atende']
    manutencao_fundamentacao: str
    uso_classificacao: Literal['Regular', 'Regular, com ressalvas', 'Irregular']
    uso_fundamentacao: str
    plano_acao_imediato: str
    plano_acao_curto: str
    plano_acao_medio: str
    plano_acao_longo: str
    conclusao: str


CAMPOS_VAZIOS = {campo: '' for campo in TextosRelatorioFinal.model_fields}

SYSTEM_PROMPT = (
    "Você é um redator técnico que produz trechos de um Laudo Técnico de "
    "Inspeção Predial do MPDFT, a partir EXCLUSIVAMENTE dos dados JSON "
    "fornecidos nesta mensagem. Nunca invente fatos, números, normas "
    "técnicas (ABNT, IBAPE etc.) ou recomendações que não estejam "
    "literalmente presentes nos dados fornecidos — sintetize e reescreva em "
    "prosa técnica formal em português do Brasil, sem adicionar informação "
    "nova. Os campos 'manutencao_classificacao' e 'uso_classificacao' "
    "exigem exatamente uma das opções do vocabulário fechado do schema — "
    "nunca uma categoria fora da lista. Quando um texto cobrir mais de um "
    "parágrafo, separe os parágrafos com uma linha em branco (\\n\\n)."
)


def gerar_textos_relatorio(payload: dict) -> dict:
    if not settings.GEMINI_API_KEY:
        return dict(CAMPOS_VAZIOS)
    try:
        client = genai.Client()
        interaction = client.interactions.create(
            model=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            input=json.dumps(payload, ensure_ascii=False),
            response_format={
                'type': 'text',
                'mime_type': 'application/json',
                'schema': TextosRelatorioFinal.model_json_schema(),
            },
        )
        textos = TextosRelatorioFinal.model_validate_json(interaction.output_text)
        return textos.model_dump()
    except Exception:
        logger.exception('Falha ao gerar textos do Relatório Final via Gemini.')
        return dict(CAMPOS_VAZIOS)
```

Nota de implementação: `genai.Client()` sem argumentos lê a variável de ambiente `GEMINI_API_KEY` (confirmado em ai.google.dev/gemini-api/docs/quickstart). Como o Django lê `GEMINI_API_KEY` via `python-decouple` (que NÃO propaga para `os.environ`), é preciso garantir que a variável de ambiente exista de fato no processo — a forma mais simples e já usada neste projeto é definir `GEMINI_API_KEY=...` no mesmo arquivo `.env` que o `python-decouple` já lê E que o processo do servidor (`iniciar_servidor_automatico.bat`) já carrega para o ambiente do Windows antes de chamar `python`. Se isso não for suficiente em produção (confirmar no Step 6 da Task 10), adicionar `os.environ['GEMINI_API_KEY'] = settings.GEMINI_API_KEY` antes de `genai.Client()`.

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_gemini_client.py -v`
Expected: PASS (3 testes)

- [ ] **Step 6: Commit**

```bash
git add src/apps/relatorio_final/gemini_client.py src/apps/relatorio_final/tests/test_gemini_client.py
git commit -m "feat: cliente Gemini para textos do relatorio final, com schema fechado e falha nao bloqueante"
```

---

### Task 8: Payload do LLM (`montar_payload_llm`)

**Files:**
- Modify: `src/apps/relatorio_final/dados.py`
- Modify: `src/apps/relatorio_final/tests/test_dados.py`

- [ ] **Step 1: Escrever o teste que falha**

Em `src/apps/relatorio_final/tests/test_dados.py`, adicionar (usa fixtures reais de banco, por isso é `@pytest.mark.django_db`):

```python
import pytest
from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
from apps.relatorio_final.dados import montar_payload_llm, plano_acao_por_horizonte


@pytest.mark.django_db
def test_montar_payload_llm_inclui_apenas_dados_existentes():
    edificacao = Edificacao.objects.create(nome='Sede payload')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    Achado.objects.create(
        especialidade=esp, localizacao='Subsolo', verificacao='Estrutura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=4, urgencia=3, tendencia=3, prioridade_risco=1,
        descricao_nao_conformidade='Trinca na viga.', recomendacao='Reforçar viga.',
        direcionamento='garantia', prazo_meses=1,
    )
    Achado.objects.create(
        especialidade=esp, localizacao='Térreo', verificacao='Pintura',
        grupo_tecnico='acabamento', requisito_afetado='estetica', em_conformidade=True,
    )
    especialidades = list(inspecao.especialidades.all())
    nao_conformes = [a for esp2 in especialidades for a in esp2.achados.all() if a.gut_total > 0]
    plano = plano_acao_por_horizonte(nao_conformes)
    painel = {
        'iqe': 84, 'iqe_faixa': 'Bom', 'pct_conformidade': 50,
        'total': 2, 'total_nc': 1, 'total_conformes': 1,
        'p1_total': 1, 'p2_total': 0, 'p3_total': 0,
        'gut_media': '36,0', 'gut_max': 36, 'gut_min': 36,
        'por_localizacao': [{'localizacao': 'Subsolo', 'total': 1, 'p1': 1, 'p2': 0, 'p3': 0}],
        'n_incoerencias': 0, 'n_ganhos_rapidos': 1,
    }
    payload = montar_payload_llm(especialidades, plano, painel)
    civil = payload['especialidades'][0]
    assert civil['especialidade'] == 'Engenharia Civil'
    assert civil['total_verificacoes'] == 2
    assert civil['nao_conformes'][0]['descricao_nao_conformidade'] == 'Trinca na viga.'
    assert civil['nao_conformes'][0]['grupo_tecnico'] == 'Estrutura'
    assert civil['itens_conformes'] == [{'localizacao': 'Térreo', 'verificacao': 'Pintura'}]
    assert payload['painel']['iqe'] == 84
    assert payload['plano_de_acao'][0]['nc'] == 1
    import json
    json.dumps(payload)  # precisa ser 100% JSON-serializável
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_dados.py -k payload -v`
Expected: FAIL — `ImportError: cannot import name 'montar_payload_llm'`

- [ ] **Step 3: Implementar**

Em `src/apps/relatorio_final/dados.py`, adicionar no topo:

```python
from apps.inspecoes.models import Achado
```

E ao final do arquivo:

```python
def montar_payload_llm(especialidades, plano_por_horizonte, painel):
    """Monta o payload JSON-serializável enviado ao Gemini — SOMENTE dados
    já existentes no cadastro ou já calculados deterministicamente (regra
    de grounding do grill de 2026-10-27: o LLM nunca recebe permissão para
    inventar nada fora deste payload)."""
    grupo_labels = dict(Achado.GRUPO_TECNICO_CHOICES)
    requisito_labels = dict(Achado.REQUISITO_CHOICES)

    def achado_resumo(a):
        return {
            'localizacao': a.localizacao,
            'sub_localizacao': a.sub_localizacao,
            'verificacao': a.verificacao,
            'grupo_tecnico': grupo_labels.get(a.grupo_tecnico, a.grupo_tecnico),
            'requisito_afetado': requisito_labels.get(a.requisito_afetado, a.requisito_afetado),
            'descricao_nao_conformidade': a.descricao_nao_conformidade,
            'recomendacao': a.recomendacao,
            'prioridade_risco': a.get_prioridade_risco_display(),
            'gut_total': a.gut_total,
            'direcionamento': a.get_direcionamento_display(),
            'prazo_meses': a.prazo_meses,
        }

    payload = {'especialidades': []}
    for esp in especialidades:
        achados = list(esp.achados.all())
        nao_conformes = [a for a in achados if a.gut_total > 0]
        conformes = [a for a in achados if a.gut_total == 0]
        payload['especialidades'].append({
            'especialidade': esp.get_especialidade_display(),
            'total_verificacoes': len(achados),
            'total_nao_conformes': len(nao_conformes),
            'nao_conformes': [achado_resumo(a) for a in nao_conformes],
            'itens_conformes': [{'localizacao': a.localizacao, 'verificacao': a.verificacao} for a in conformes],
        })

    payload['painel'] = {
        'iqe': painel['iqe'], 'iqe_faixa': painel['iqe_faixa'],
        'pct_conformidade': painel['pct_conformidade'],
        'total': painel['total'], 'total_nc': painel['total_nc'], 'total_conformes': painel['total_conformes'],
        'p1_total': painel['p1_total'], 'p2_total': painel['p2_total'], 'p3_total': painel['p3_total'],
        'gut_media': painel['gut_media'], 'gut_max': painel['gut_max'], 'gut_min': painel['gut_min'],
        'por_localizacao': [
            {'localizacao': l['localizacao'], 'total': l['total'], 'p1': l['p1'], 'p2': l['p2'], 'p3': l['p3']}
            for l in painel['por_localizacao']
        ],
        'n_incoerencias': painel['n_incoerencias'], 'n_ganhos_rapidos': painel['n_ganhos_rapidos'],
    }
    payload['plano_de_acao'] = [
        {'horizonte': linha['horizonte'], 'nc': linha['nc'], 'recomendacoes': linha['recomendacoes']}
        for linha in plano_por_horizonte
    ]
    return payload
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_dados.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add src/apps/relatorio_final/dados.py src/apps/relatorio_final/tests/test_dados.py
git commit -m "feat: monta payload grounded enviado ao Gemini a partir dos dados ja existentes"
```

---

### Task 9: Construir o template Word com marcadores Jinja (a partir do arquivo real enviado)

**Esta é a task mais importante para a fidelidade visual pedida pelo usuário — fonte, cor, tabulação e tamanho de fotos idênticos, porque o script só MUTA o texto dos `run`s existentes, nunca recria formatação.**

**Files:**
- Create: `scripts/build_relatorio_final_docx_template.py`
- Create (artefato binário, gerado pelo script): `src/apps/relatorio_final/templates_docx/relatorio_final_modelo.docx`

- [ ] **Step 1: Escrever o script de construção**

Criar `scripts/build_relatorio_final_docx_template.py`:

```python
"""Constrói o template Jinja (.docx) do Relatório Final a partir do arquivo
real enviado pelo usuário (laudo-modelo MPDFT/SPO), substituindo cada trecho
de exemplo por um marcador {{ }} — SEM recriar formatação: a substituição
muda só o texto de runs já existentes, preservando fonte/cor/tamanho/tabulação
originais 1:1.

Uso:
    python scripts/build_relatorio_final_docx_template.py <origem.docx> <destino.docx>
"""
import sys
from docx import Document


def substituir_em_runs(paragrafos_ou_celulas, mapa):
    """Procura cada texto de `mapa` dentro dos runs de parágrafos (ou
    células de tabela) e substitui só o run que contém o texto completo.
    Assume que cada trecho de exemplo está inteiro em um único run — ver
    conferência manual no Step 3."""
    nao_encontrados = set(mapa)
    for item in paragrafos_ou_celulas:
        paragrafos = item.paragraphs if hasattr(item, 'paragraphs') else [item]
        for p in paragrafos:
            for r in p.runs:
                for antigo, novo in mapa.items():
                    if r.text == antigo:
                        r.text = novo
                        nao_encontrados.discard(antigo)
    return nao_encontrados


def todos_paragrafos(doc):
    """Todos os parágrafos do corpo + de dentro de todas as células de
    todas as tabelas (não existe API nativa para isso no python-docx)."""
    paragrafos = list(doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                paragrafos.extend(cell.paragraphs)
    return paragrafos


def main(origem, destino):
    doc = Document(origem)

    # ── 1. Substituições simples (texto completo de um run -> variável) ────
    mapa_texto = {
        # Capa + cabeçalho (o nome da edificação aparece 2x no arquivo)
        'Promotoria de Justiça de Defesa da Infância e da Juventude': '{{ edificacao_nome }}',
        'SEPN 711/911, Bloco B, Asa Norte, Brasília-DF': '{{ edificacao_endereco }}',
        'Vistorias: 02/03, 15/03 e 06/05/2026': 'Vistorias: {{ datas_vistorias }}',
        '[mês]': '{{ mes_geracao }}',
        ' de 2026': ' de {{ ano_atual }}',
        'MPDFT  •  SECRETARIA DE PROJETOS E OBRAS  •  2026': 'MPDFT  •  SECRETARIA DE PROJETOS E OBRAS  •  {{ ano_atual }}',

        # Quadro "Identificação do Laudo" (Tabela 1)
        '4.745,52 m²': '{{ area_construida }}',
        'Três pavimentos (subsolo, térreo e 1º pavimento), além de cobertura técnica': '{{ pavimentos }}',
        '29 de julho de 2005 (construção averbada em 9 de agosto de 2006)': '{{ data_inauguracao_extenso }}',
        '02/03/2026, 15/03/2026 e 06/05/2026': '{{ datas_vistorias }}',
        'Jader Mendes Santana Pereira, engenheiro civil; Carlos Eduardo [sobrenome], engenheiro eletricista; Júlio Toshio Mandai, engenheiro mecânico': '{{ equipe_tecnica }}',
        'ART nº [número]': '{{ responsabilidade_tecnica }}',

        # Sumário Executivo / Principais Constatações / Providências (LLM)
        'A edificação da Promotoria de Justiça de Defesa da Infância e da Juventude encontra-se em condição global boa, com Índice de Qualidade de 84 pontos em 100. Das 249 verificações realizadas, 166 (67%) estão em conformidade e 83 apresentaram não conformidades, das quais 23 classificadas como Prioridade 1, em sua maioria de baixa complexidade e passíveis de correção no prazo de até três meses.': '{{ sumario_executivo }}',
        'As três ocorrências de maior criticidade, com índice GUT máximo de 125, referem-se à segurança dos usuários e das instalações e possuem solução simples e de baixo custo: a possibilidade de obstrução do acesso à subestação por veículos estacionados, a botoeira de alarme de incêndio obstruída por divisória no 1º pavimento e a lâmpada de sinalização queimada na área externa. Seguem-se, em ordem de criticidade, o desempenho insuficiente do ar condicionado da Sala 118-B, o acúmulo de água no fosso da área externa leste e defeitos em válvulas de descarga.': '{{ principais_constatacoes_1 }}',
        'O subsolo concentra 34 das 83 não conformidades (41%), com predominância de problemas de drenagem, acabamentos sujeitos à umidade e equipamentos de climatização obsoletos. Esquadrias, climatização e acabamentos respondem, em conjunto, por 60% das ocorrências. As não conformidades registradas no sistema estrutura referem-se a juntas de dilatação, proteção mecânica da impermeabilização e pavimentação externa, sem indicação de comprometimento da estabilidade da edificação.': '{{ principais_constatacoes_2 }}',
        'Os sistemas elétricos apresentam elevado nível de conformidade (95% das verificações), refletindo os investimentos recentes na edificação. No sistema mecânico, destaca-se a necessidade de substituição de 14 unidades de ar condicionado do tipo split com tecnologia convencional, em grande parte operando com fluido refrigerante R22, cuja reposição é cada vez mais escassa e onerosa.': '{{ principais_constatacoes_3 }}',
        'Recomenda-se determinar a correção, no prazo de até 30 dias, das 17 não conformidades classificadas com prazo imediato, das quais 14 são de Prioridade 1, por meio dos contratos de manutenção vigentes, com prioridade para os itens de segurança contra incêndio, acesso à subestação e instalações elétricas expostas.': '{{ providencias_administracao_1 }}',
        'Recomenda-se, ainda, o acionamento das garantias de obra aplicáveis aos três itens identificados e a autorização para o planejamento das contratações necessárias ao saneamento das 35 ocorrências que excedem o escopo dos contratos vigentes, com destaque para a substituição das unidades de climatização obsoletas, cujas estimativas de custo serão consolidadas por esta Secretaria na fase de planejamento da contratação.': '{{ providencias_administracao_2 }}',

        # Resultados Gerais (LLM / determinístico)
        'As 83 não conformidades distribuem-se por todos os pavimentos, com concentração no subsolo, que reúne 41% das ocorrências e sete dos 23 itens críticos.': '{{ resultados_gerais_intro_1 }}',
        'Três sistemas – esquadrias, climatização e acabamentos – respondem por 60% das ocorrências, e cinco sistemas concentram 83% delas, o que permite direcionar os esforços de manutenção de forma objetiva.': '{{ resultados_gerais_intro_2 }}',
        'A matriz abaixo cruza o grau de risco com o prazo recomendado de intervenção. Vinte e seis ocorrências combinam risco elevado e prazo de até três meses e constituem ganhos rápidos para a Administração.': 'A matriz abaixo cruza o grau de risco com o prazo recomendado de intervenção. {{ n_ganhos_rapidos }} ocorrência(s) combinam risco elevado e prazo de até três meses e constituem ganhos rápidos para a Administração.',
        'Os dez achados de maior índice GUT são todos de Prioridade 1 e estão apresentados a seguir. A relação completa dos 23 itens críticos consta do quadro subsequente.': '{{ resultados_gerais_achados_criticos }}',

        # Itens em conformidade por especialidade (LLM)
        'Apresentaram-se conformes, entre outros, a cortina de contenção, a impermeabilização, a drenagem e as caixas de inspeção do subsolo; os conjuntos de bombas de esgoto, pluviais, de reuso, de recalque de água potável, de irrigação e de hidrantes; os hidrômetros e os dosadores de cloro; as telhas, a impermeabilização, a drenagem, os reservatórios e os elementos metálicos da cobertura; as fachadas, os brises, a urbanização e as escadas externas; e os itens de acessibilidade, escadas de emergência e guarda-corpos nos diversos pavimentos, resultado coerente com as obras de recuperação e de acessibilidade concluídas em 2022.': '{{ itens_conformidade_civil }}',
        'Apresentaram-se conformes o Sistema de Detecção e Alarme de Incêndio (SDAI), com central, detectores, acionadores, sinalizadores e linhas de sinal em todos os pavimentos; a subestação e o grupo gerador; os quadros gerais e de distribuição dos circuitos normal, nobreak e de emergência; os circuitos alimentadores e terminais; a iluminação e as tomadas; o cabeamento estruturado horizontal e vertical; e os sensores, atuadores e quadros do sistema de automação predial.': '{{ itens_conformidade_eletrica }}',
        'Apresentaram-se conformes a central de água gelada, com os chillers e as bombas de água gelada, as três Unidades de Tratamento de Ar (UTA-01, UTA-02 e UTA-03), os fancoils do subsolo, o equipamento multisplit do 1º pavimento, parte das unidades split do subsolo e os sistemas de exaustão e ventilação mecânica.': '{{ itens_conformidade_mecanica }}',

        # Conclusão (LLM) — 2 parágrafos
        'Com base nas vistorias realizadas em 2 e 15 de março e 6 de maio de 2026, conclui-se que a edificação da Promotoria de Justiça de Defesa da Infância e da Juventude apresenta condição global boa, com Índice de Qualidade de 84 pontos em 100. Foram registradas 83 não conformidades em 249 verificações, das quais 23 de Prioridade 1, 20 de Prioridade 2 e 40 de Prioridade 3.': '{{ conclusao_1 }}',
        'As ocorrências de Prioridade 1 relacionam-se principalmente à segurança dos usuários e à manutenção rotineira e podem, em sua maioria, ser corrigidas com rapidez e baixo custo pelos contratos vigentes. A manutenção foi avaliada como atendendo parcialmente aos requisitos e o uso como regular, com ressalvas. Recomenda-se a adoção do plano de ação apresentado, a verificação do saneamento dos itens críticos após o prazo de 90 dias e a realização de nova inspeção predial conforme a periodicidade definida no plano de manutenção da edificação.': '{{ conclusao_2 }}',

        # Quadro "Resumo Executivo — Consolidado" (Tabela 2)
        '84': '{{ iqe }}',
        'Índice de Qualidade (de 100) – faixa Bom': 'Índice de Qualidade (de 100) – faixa {{ iqe_faixa }}',
        '249': '{{ total }}',
        '67%': '{{ pct_conformidade }}%',
        'em conformidade (166)': 'em conformidade ({{ total_conformes }})',
        '83': '{{ total_nc }}',
        '23': '{{ p1_total }}',
        '20': '{{ p2_total }}',
        '40': '{{ p3_total }}',
        '21,4': '{{ gut_media }}',

        # Quadro "Encaminhamento" (Tabela 3) — determinístico (por_direcionamento)
        '45\ncontratos de manutenção vigentes (54%)': '{{ direcionamento_manutencao_total }}\ncontratos de manutenção vigentes ({{ direcionamento_manutencao_pct }}%)',
        '35\nnova contratação (42%)': '{{ direcionamento_nova_contratacao_total }}\nnova contratação ({{ direcionamento_nova_contratacao_pct }}%)',
        '3\nacionamento de garantia de obra (4%)': '{{ direcionamento_garantia_total }}\nacionamento de garantia de obra ({{ direcionamento_garantia_pct }}%)',

        # Quadro "Avaliação da Manutenção e do Uso" (Tabela 13) — LLM + determinístico
        'Atende parcialmente': '{{ manutencao_classificacao }}',
        'Sistemas de climatização e transporte vertical cobertos por contratos vigentes e intervenções recentes relevantes; persistem, contudo, ocorrências de manutenção rotineira, como ralos obstruídos, trincos e válvulas defeituosos e lâmpada queimada': '{{ manutencao_fundamentacao }}',
        'Regular, com ressalvas': '{{ uso_classificacao }}',
        'Uso compatível com a destinação da edificação; registram-se falhas operacionais pontuais, como a obstrução da botoeira de alarme por divisória e o risco de obstrução do acesso à subestação': '{{ uso_fundamentacao }}',
        'Boa': '{{ condicao_global }}',
        'Índice de Qualidade de 84 pontos em 100 e 67% de conformidade nas verificações realizadas': 'Índice de Qualidade de {{ iqe }} pontos em 100 e {{ pct_conformidade }}% de conformidade nas verificações realizadas',

        # Anexo I — intro
        'Relação integral das 249 verificações realizadas, com indicação da situação, da não conformidade, da recomendação, do grau de risco, do índice GUT e do prazo recomendado. As linhas em destaque correspondem às não conformidades.': 'Relação integral das {{ total }} verificações realizadas, com indicação da situação, da não conformidade, da recomendação, do grau de risco, do índice GUT e do prazo recomendado. As linhas em destaque correspondem às não conformidades.',

        # Assinatura (Tabela 14) — tratada célula a célula no Step 2 (nome/CREA variam por pessoa)
    }
    nao_encontrados = substituir_em_runs(todos_paragrafos(doc), mapa_texto)

    # ── 2. Cabeçalho/rodapé da seção 1 (corpo) ──────────────────────────────
    sec1 = doc.sections[1]
    for p in sec1.header.paragraphs:
        for r in p.runs:
            if r.text == 'Promotoria de Justiça de Defesa da Infância e da Juventude':
                r.text = '{{ edificacao_nome }}'
    for t in sec1.header.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        if r.text == 'Promotoria de Justiça de Defesa da Infância e da Juventude':
                            r.text = '{{ edificacao_nome }}'

    # ── 3. Tabela 1 (Identificação do Laudo) — linha "Edificação"/"Endereço" ──
    # já cobertas pelo mapa_texto acima (mesmo texto da capa).

    # ── 4. Tabela 7 (Resumo por Especialidade) — números linha a linha ──────
    t7 = doc.tables[7]
    mapa_t7 = {
        ('1', '0'): '{{ civil_total }}', ('1', '1'): '{{ civil_nc }}', ('1', '2'): '{{ civil_pct_conf }}%',
        ('1', '3'): '{{ civil_p1 }}', ('1', '4'): '{{ civil_p2 }}', ('1', '5'): '{{ civil_p3 }}',
        ('2', '0'): '{{ eletrica_total }}', ('2', '1'): '{{ eletrica_nc }}', ('2', '2'): '{{ eletrica_pct_conf }}%',
        ('2', '3'): '{{ eletrica_p1 }}', ('2', '4'): '{{ eletrica_p2 }}', ('2', '5'): '{{ eletrica_p3 }}',
        ('3', '0'): '{{ mecanica_total }}', ('3', '1'): '{{ mecanica_nc }}', ('3', '2'): '{{ mecanica_pct_conf }}%',
        ('3', '3'): '{{ mecanica_p1 }}', ('3', '4'): '{{ mecanica_p2 }}', ('3', '5'): '{{ mecanica_p3 }}',
        ('4', '0'): '{{ total }}', ('4', '1'): '{{ total_nc }}', ('4', '2'): '{{ pct_conformidade }}%',
        ('4', '3'): '{{ p1_total }}', ('4', '4'): '{{ p2_total }}', ('4', '5'): '{{ p3_total }}',
    }
    for (linha, col), tag in mapa_t7.items():
        celula = t7.rows[int(linha)].cells[int(col) + 1]  # +1 porque col0 é o nome, mapeado separadamente
        for p in celula.paragraphs:
            for r in p.runs:
                r.text = tag

    # ── 5. Tabela 8 (Matriz Risco x Prazo) — loop docxtpl ───────────────────
    t8 = doc.tables[8]
    # cabeçalho de linha (P1/P2/P3) e "Total" ficam como estão; as células de
    # dado viram um loop {%tr %} sobre `matriz_risco_prazo` (ver docx_builder.py)
    t8.rows[1].cells[0].paragraphs[0].runs[0].text = '{%tr for linha in matriz_risco_prazo %}{{ linha.rotulo }}'
    for i in range(1, 6):
        t8.rows[1].cells[i].paragraphs[0].runs[0].text = '{{ linha.celulas.' + str(i - 1) + ' }}'
    t8.rows[1].cells[6].paragraphs[0].runs[0].text = '{{ linha.total }}'
    t8.rows[2].cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for i in range(1, 7):
        for p in t8.rows[2].cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    # Remove as linhas 3 e 4 originais (P3 fixo + "Total" fixo) — mantemos só
    # header (row0) + linha-molde do loop (row1, repete para P1/P2/P3) +
    # marcador de fim (row2). A linha "Total" (soma por coluna de prazo) do
    # modelo real é descartada nesta versão — ver "Pendências" ao final.
    for row in list(t8.rows[3:]):
        row._tr.getparent().remove(row._tr)

    # ── 6. Tabela 9 (Dez maiores GUT) — loop docxtpl ────────────────────────
    t9 = doc.tables[9]
    linha_molde = t9.rows[1]
    for i, tag in enumerate(['{%tr for item in top_gut %}{{ item.numero }}', '{{ item.local }}',
                              '{{ item.nao_conformidade }}', '{{ item.recomendacao }}',
                              '{{ item.gut }}', '{{ item.prazo }}']):
        linha_molde.cells[i].paragraphs[0].runs[0].text = tag
    linha_fim = t9.rows[2]
    linha_fim.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for i in range(1, 6):
        for p in linha_fim.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    for row in list(t9.rows[3:]):
        row._tr.getparent().remove(row._tr)

    # ── 7. Tabela 6 (Histórico de intervenções) — loop docxtpl ──────────────
    t6 = doc.tables[6]
    linha_molde = t6.rows[1]
    linha_molde.cells[0].paragraphs[0].runs[0].text = '{%tr for item in historico_intervencoes %}{{ item.ano }}'
    linha_molde.cells[1].paragraphs[0].runs[0].text = '{{ item.descricao }}'
    linha_fim = t6.rows[2]
    linha_fim.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for p in linha_fim.cells[1].paragraphs:
        for r in p.runs:
            r.text = ''
    for row in list(t6.rows[3:]):
        row._tr.getparent().remove(row._tr)

    # ── 8. Tabela 12 (Plano de Ação) — loop docxtpl ─────────────────────────
    t12 = doc.tables[12]
    linha_molde = t12.rows[1]
    linha_molde.cells[0].paragraphs[0].runs[0].text = '{%tr for linha in plano_de_acao %}{{ linha.horizonte }}'
    linha_molde.cells[1].paragraphs[0].runs[0].text = '{{ linha.nc }}'
    linha_molde.cells[2].paragraphs[0].runs[0].text = '{{ linha.principais_acoes }}'
    linha_molde.cells[3].paragraphs[0].runs[0].text = '{{ linha.forma_execucao }}'
    for row in list(t12.rows[2:]):
        row._tr.getparent().remove(row._tr)
    # marcador de fim vai dentro da própria última célula da linha-molde
    ultimo_p = linha_molde.cells[3].paragraphs[0]
    ultimo_p.add_run('{%tr endfor %}')

    # ── 9. Tabela 14 (Assinaturas) — 3 colunas fixas (sempre civil/elétrica/mecânica) ──
    t14 = doc.tables[14]
    assinaturas = [
        ('{{ nome_civil }}', '{{ titulo_civil }}', '{{ crea_civil }}'),
        ('{{ nome_eletrica }}', '{{ titulo_eletrica }}', '{{ crea_eletrica }}'),
        ('{{ nome_mecanica }}', '{{ titulo_mecanica }}', '{{ crea_mecanica }}'),
    ]
    for cell, (nome_tag, titulo_tag, crea_tag) in zip(t14.rows[0].cells, assinaturas):
        paras = cell.paragraphs
        paras[0].runs[0].text = nome_tag
        paras[1].runs[0].text = titulo_tag
        paras[2].runs[0].text = crea_tag

    # ── 10. Tabela 15 (Anexo I completo) — loop docxtpl ─────────────────────
    t15 = doc.tables[15]
    linha_molde = t15.rows[1]
    campos_anexo = ['numero', 'local', 'sistema_elemento', 'situacao',
                     'nao_conformidade', 'recomendacao', 'grau_risco', 'gut', 'prazo']
    linha_molde.cells[0].paragraphs[0].runs[0].text = (
        '{%tr for item in anexo01 %}{{ item.' + campos_anexo[0] + ' }}'
    )
    for i, campo in enumerate(campos_anexo[1:], start=1):
        linha_molde.cells[i].paragraphs[0].runs[0].text = '{{ item.' + campo + ' }}'
    ultimo_p = linha_molde.cells[8].paragraphs[0]
    ultimo_p.add_run('{%tr endfor %}')
    for row in list(t15.rows[2:]):
        row._tr.getparent().remove(row._tr)

    doc.save(destino)

    if nao_encontrados:
        print('AVISO — textos não encontrados (conferir manualmente no Word):')
        for t in sorted(nao_encontrados):
            print(f'  - {t[:80]!r}')
    else:
        print('OK — todos os textos do mapa foram substituídos.')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Rodar o script contra o arquivo real enviado pelo usuário**

```bash
cd "C:\Users\jtman\OneDrive - MPDFT\Trabalho - MPDFT\Inspeções Promotorias\Inspeções prediais MPDFT"
mkdir -p src/apps/relatorio_final/templates_docx
.venv/Scripts/python.exe scripts/build_relatorio_final_docx_template.py "C:\Users\jtman\Downloads\Laudo_Inspecao_Predial_PJ_Infancia_Juventude - Regina.docx" src/apps/relatorio_final/templates_docx/relatorio_final_modelo.docx
```

Expected: `OK — todos os textos do mapa foram substituídos.` Se aparecer `AVISO`, abrir o arquivo de destino no Word, localizar manualmente (Ctrl+F) o trecho não encontrado — geralmente significa que esse texto está dividido em mais de um `run` (ex.: parte em negrito + parte normal dentro da mesma frase) e precisa de um `old_str`/`new_str` mais específico só na parte daquele run, ou de edição manual direta naquela célula/parágrafo.

- [ ] **Step 3: Abrir o resultado no Word e confirmar visualmente**

Abrir `src/apps/relatorio_final/templates_docx/relatorio_final_modelo.docx` no Microsoft Word e confirmar manualmente:
- Nenhum texto de exemplo do laudo da Promotoria da Infância restou visível (busca por "Infância", "Promotoria", "Regina" deve retornar zero resultados, exceto dentro de marcadores `{{ }}`).
- As tabelas com loop (Tabela 6, 8, 9, 12, 15) têm exatamente 1 linha de dados (a linha-molde) entre o cabeçalho e o fim da tabela.
- Fonte, cor e tamanho de cada marcador `{{ }}` são idênticos ao texto de exemplo que ele substituiu (conferir abrindo o painel de fonte do Word sobre o texto do marcador).

- [ ] **Step 4: Commit do artefato binário**

```bash
git add scripts/build_relatorio_final_docx_template.py src/apps/relatorio_final/templates_docx/relatorio_final_modelo.docx
git commit -m "feat: constroi template docxtpl do relatorio final a partir do modelo real do MPDFT/SPO"
```

---

### Task 10: Renderização do `.docx` (`docx_builder.py`)

**Files:**
- Create: `src/apps/relatorio_final/docx_builder.py`
- Create: `src/apps/relatorio_final/tests/test_docx_builder.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `src/apps/relatorio_final/tests/test_docx_builder.py`:

```python
import io
import pytest
from docx import Document
from apps.relatorio_final.docx_builder import gerar_docx_relatorio


def _contexto_minimo():
    return {
        'edificacao_nome': 'Sede Teste', 'edificacao_endereco': 'Rua Teste, 123',
        'datas_vistorias': '01/01/2026', 'mes_geracao': 'janeiro', 'ano_atual': '2026',
        'area_construida': '1.000,00 m²', 'pavimentos': 'Dois pavimentos',
        'data_inauguracao_extenso': '1 de janeiro de 2020',
        'equipe_tecnica': 'Fulano, engenheiro civil',
        'responsabilidade_tecnica': 'ART civil nº 123',
        'sumario_executivo': 'Resumo de teste.',
        'principais_constatacoes_1': 'C1.', 'principais_constatacoes_2': 'C2.', 'principais_constatacoes_3': 'C3.',
        'providencias_administracao_1': 'P1.', 'providencias_administracao_2': 'P2.',
        'resultados_gerais_intro_1': 'R1.', 'resultados_gerais_intro_2': 'R2.',
        'resultados_gerais_achados_criticos': 'Achados críticos de teste.',
        'n_ganhos_rapidos': 0,
        'itens_conformidade_civil': 'Conforme civil.', 'itens_conformidade_eletrica': 'Conforme elétrica.',
        'itens_conformidade_mecanica': 'Conforme mecânica.',
        'conclusao_1': 'Conclusão 1.', 'conclusao_2': 'Conclusão 2.',
        'iqe': 90, 'iqe_faixa': 'Bom', 'total': 10, 'pct_conformidade': 80,
        'total_conformes': 8, 'total_nc': 2, 'p1_total': 1, 'p2_total': 1, 'p3_total': 0,
        'gut_media': '20,0',
        'direcionamento_manutencao_total': 1, 'direcionamento_manutencao_pct': 50,
        'direcionamento_nova_contratacao_total': 1, 'direcionamento_nova_contratacao_pct': 50,
        'direcionamento_garantia_total': 0, 'direcionamento_garantia_pct': 0,
        'manutencao_classificacao': 'Atende integralmente', 'manutencao_fundamentacao': 'Fundamentação manutenção.',
        'uso_classificacao': 'Regular', 'uso_fundamentacao': 'Fundamentação uso.',
        'condicao_global': 'Boa',
        'civil_total': 5, 'civil_nc': 1, 'civil_pct_conf': 80, 'civil_p1': 1, 'civil_p2': 0, 'civil_p3': 0,
        'eletrica_total': 3, 'eletrica_nc': 1, 'eletrica_pct_conf': 67, 'eletrica_p1': 0, 'eletrica_p2': 1, 'eletrica_p3': 0,
        'mecanica_total': 2, 'mecanica_nc': 0, 'mecanica_pct_conf': 100, 'mecanica_p1': 0, 'mecanica_p2': 0, 'mecanica_p3': 0,
        'matriz_risco_prazo': [
            {'rotulo': 'P1 – Crítico', 'celulas': ['1', '—', '—', '—', '—'], 'total': 1},
            {'rotulo': 'P2 – Regular', 'celulas': ['—', '1', '—', '—', '—'], 'total': 1},
        ],
        'top_gut': [
            {'numero': 1, 'local': 'Subsolo', 'nao_conformidade': 'Teste', 'recomendacao': 'Corrigir', 'gut': 60, 'prazo': '1 mês'},
        ],
        'historico_intervencoes': [{'ano': 2022, 'descricao': 'Troca de teste'}],
        'plano_de_acao': [
            {'horizonte': 'Imediato (até 1 mês)', 'nc': 1, 'principais_acoes': 'Corrigir X.', 'forma_execucao': 'Manutenção'},
            {'horizonte': 'Curto prazo (3 meses)', 'nc': 0, 'principais_acoes': '—', 'forma_execucao': '—'},
            {'horizonte': 'Médio prazo (6 meses)', 'nc': 0, 'principais_acoes': '—', 'forma_execucao': '—'},
            {'horizonte': 'Longo prazo (12 a 24 meses)', 'nc': 1, 'principais_acoes': 'Corrigir Y.', 'forma_execucao': 'Nova contratação'},
        ],
        'nome_civil': 'Fulano', 'titulo_civil': 'Engenheiro civil', 'crea_civil': '111/D-DF',
        'nome_eletrica': 'Cicrano', 'titulo_eletrica': 'Engenheiro eletricista', 'crea_eletrica': '222/D-DF',
        'nome_mecanica': 'Beltrano', 'titulo_mecanica': 'Engenheiro mecânico', 'crea_mecanica': '333/D-DF',
        'anexo01': [
            {'numero': 1, 'local': 'Subsolo', 'sistema_elemento': 'Estrutura', 'situacao': 'Conforme',
             'nao_conformidade': '—', 'recomendacao': '—', 'grau_risco': '—', 'gut': '—', 'prazo': '—'},
        ],
        'fotos_por_achado': [],
    }


def test_gerar_docx_relatorio_produz_docx_valido():
    conteudo = gerar_docx_relatorio(_contexto_minimo())
    assert isinstance(conteudo, bytes)
    doc = Document(io.BytesIO(conteudo))
    texto_completo = '\n'.join(p.text for p in doc.paragraphs)
    assert 'Sede Teste' in texto_completo
    assert '{{' not in texto_completo  # nenhum marcador sobrou sem substituir
    tabela_anexo = doc.tables[15]
    assert tabela_anexo.rows[1].cells[1].text == 'Subsolo'
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_docx_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.relatorio_final.docx_builder'`

- [ ] **Step 3: Implementar**

Criar `src/apps/relatorio_final/docx_builder.py`:

```python
"""Renderiza o Relatório Final em .docx a partir do template construído na
Task 9 (`templates_docx/relatorio_final_modelo.docx`) — preenchido com
docxtpl, que resolve `{{ }}` e `{%tr %}` sobre o próprio arquivo Word sem
recriar formatação."""
import io
from pathlib import Path

from docxtpl import DocxTemplate

TEMPLATE_PATH = Path(__file__).parent / 'templates_docx' / 'relatorio_final_modelo.docx'


def gerar_docx_relatorio(contexto: dict) -> bytes:
    tpl = DocxTemplate(str(TEMPLATE_PATH))
    tpl.render(contexto)
    buffer = io.BytesIO()
    tpl.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/relatorio_final/tests/test_docx_builder.py -v`
Expected: PASS

- [ ] **Step 5: Fotos nas tabelas 10/11 — decisão explícita de simplificação do MVP**

As tabelas de fotos (10/11 no arquivo original, grade 2 colunas) exigem imagens dinâmicas por achado — docxtpl suporta isso via `InlineImage`, mas a quantidade de fotos por achado varia (0 a 2, ver `_montar_snapshot_relatorio`) e a posição exata de cada foto dentro da grade do template real é fixa (10 fotos fixas no exemplo). Para o MVP desta plan, as fotos de cada achado não conforme são inseridas **em sequência, uma abaixo da outra, cada uma com sua legenda**, imediatamente após o texto daquele achado no corpo do documento — não como uma grade 2 colunas fixa. Isso é mais simples de implementar corretamente com `docxtpl` + `{%p %}` (um parágrafo novo por foto) do que replicar uma grade de N colunas com texto por achado variável, e ainda preserva o tamanho de foto do modelo (`InlineImage(tpl, caminho, width=Mm(84))` — 84mm vem da largura de coluna medida na Task de inspeção: 2969895 EMU ÷ 36000 ≈ 82,5mm, arredondado para 84mm de margem de segurança). Caso o usuário queira a grade exata de 2 colunas depois, isso é um ajuste isolado dentro desta mesma função — documentar essa decisão no commit.

Esta decisão não tem teste automatizado de posicionamento visual (não é possível testar layout de imagem via `python-docx` de forma barata) — validar manualmente abrindo um `.docx` gerado com achados reais (ver Task 11, Step 5).

- [ ] **Step 6: Commit**

```bash
git add src/apps/relatorio_final/docx_builder.py src/apps/relatorio_final/tests/test_docx_builder.py
git commit -m "feat: renderiza o relatorio final em docx a partir do template com docxtpl"
```

---

### Task 11: Ligar tudo em `relatorio_final_gerar` — view gera `.docx`, não mais PDF

**Files:**
- Modify: `src/apps/inspecoes/models.py` (RelatorioFinalInspecao)
- Create: `src/apps/inspecoes/migrations/0021_relatoriofinalinspecao_arquivo_docx.py`
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html`
- Modify: `src/apps/inspecoes/tests/test_relatorio_final_views.py`

- [ ] **Step 1: Trocar `arquivo_pdf` por `arquivo_docx` no model**

Em `src/apps/inspecoes/models.py`, em `RelatorioFinalInspecao`:

```python
    arquivo_docx = models.FileField('Word gerado', upload_to=relatorio_pdf_upload_path)
```

(troca só o nome do campo e o verbose_name; a função `relatorio_pdf_upload_path` continua igual — o nome dela não precisa mudar nesta plan, já que só gera um caminho de pastas).

Run: `cd src && ../.venv/Scripts/python.exe manage.py makemigrations inspecoes`
Expected: pergunta no terminal "Did you rename inspecaoespecialidade.arquivo_pdf to arquivo_docx?" — responder `y`. Confirma geração de `0021_relatoriofinalinspecao_arquivo_docx.py`.

- [ ] **Step 2: Escrever o teste que falha (view gera .docx válido)**

Em `src/apps/inspecoes/tests/test_relatorio_final_views.py`, localizar o teste existente que faz POST em `relatorio_final_gerar` e conferir o PDF gerado (procurar por `arquivo_pdf` e `_gerar_pdf_bytes`/PyMuPDF). Adicionar um novo teste ao lado dele:

```python
import io
from docx import Document


@pytest.mark.django_db
def test_relatorio_final_gerar_produz_docx(client, django_user_model, settings):
    settings.GEMINI_API_KEY = ''  # sem chamada real ao Gemini neste teste
    # (reaproveitar a fixture/setup já usada pelo teste de geração de PDF
    # nesta mesma classe/arquivo para montar inspecao com 3 especialidades
    # finalizadas, descritivo preenchido e conclusao preenchida)
    ...
    resp = client.post(f'/inspecoes/inspecoes/{inspecao.pk}/relatorio-final/gerar/')
    assert resp.status_code == 302
    relatorio = inspecao.relatorios_finais.first()
    assert relatorio is not None
    assert relatorio.arquivo_docx.name.endswith('.docx')
    doc = Document(io.BytesIO(relatorio.arquivo_docx.read()))
    texto = '\n'.join(p.text for p in doc.paragraphs)
    assert '{{' not in texto
```

Nota: usar o setup de fixtures (edificação + inspeção + 3 especialidades finalizadas + achados) já existente nesse arquivo de teste — não recriar do zero; adaptar o `...` acima para a função helper/fixture já presente ali.

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes/tests/test_relatorio_final_views.py -k docx -v`
Expected: FAIL (view ainda gera PDF, campo ainda não existe ou lógica antiga)

- [ ] **Step 4: Reescrever `relatorio_final_gerar`**

Em `src/apps/inspecoes/views.py`, no topo do arquivo, adicionar os imports:

```python
from apps.relatorio_final.dados import (
    classificar_condicao_global, plano_acao_por_horizonte, montar_payload_llm,
)
from apps.relatorio_final.gemini_client import gerar_textos_relatorio
from apps.relatorio_final.docx_builder import gerar_docx_relatorio
```

Substituir o corpo de `relatorio_final_gerar` (linhas ~601-657):

```python
@login_required
@require_POST
def relatorio_final_gerar(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades', 'especialidades__achados__fotos', 'relatorios_finais',
        ),
        pk=pk,
    )
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:relatorio_final_painel', pk=pk)

    pendencias = inspecao.pendencias_relatorio_final()
    if pendencias:
        messages.error(request, 'Não é possível gerar o relatório: ' + ' '.join(pendencias))
        return redirect('inspecoes:relatorio_final_painel', pk=pk)

    numero_versao = (inspecao.relatorios_finais.aggregate(m=Max('numero_versao'))['m'] or 0) + 1
    snapshot = _montar_snapshot_relatorio(inspecao, numero_versao)
    especialidades = list(inspecao.especialidades.all())
    painel = _painel_encerramento_relatorio(inspecao, especialidades)

    todos_achados = [a for esp in especialidades for a in esp.achados.all()]
    nao_conformes = [a for a in todos_achados if a.gut_total > 0]
    plano_por_horizonte = plano_acao_por_horizonte(nao_conformes)
    payload_llm = montar_payload_llm(especialidades, plano_por_horizonte, painel)
    textos = gerar_textos_relatorio(payload_llm)

    contexto = _montar_contexto_docx(inspecao, snapshot, painel, especialidades, plano_por_horizonte, textos, nao_conformes)
    docx_bytes = gerar_docx_relatorio(contexto)

    relatorio = RelatorioFinalInspecao(
        inspecao=inspecao, numero_versao=numero_versao, snapshot=snapshot, gerado_por=request.user,
    )
    nome_arquivo = f"relatorio_final_{inspecao.edificacao.nome.replace(' ', '_')}_v{numero_versao}.docx"
    relatorio.arquivo_docx.save(nome_arquivo, ContentFile(docx_bytes), save=False)
    relatorio.save()

    _log(request, 'relatorio_final_gerado',
         f'Relatório Final de Inspeção (v{numero_versao}) gerado para "{inspecao.edificacao}".')
    messages.success(request, f'Relatório Final de Inspeção (versão {numero_versao}) gerado com sucesso.')
    return redirect('inspecoes:relatorio_final_painel', pk=pk)
```

Adicionar a função auxiliar `_montar_contexto_docx` (logo antes de `relatorio_final_gerar`):

```python
_MESES_PT = {
    1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril', 5: 'maio', 6: 'junho',
    7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro',
}


def _data_extenso(d):
    return f'{d.day} de {_MESES_PT[d.month]} de {d.year}'


def _montar_contexto_docx(inspecao, snapshot, painel, especialidades, plano_por_horizonte, textos, nao_conformes):
    edificacao = inspecao.edificacao
    por_esp = {e.especialidade: e for e in especialidades}
    resumo_por_esp = {r['especialidade_nome']: r for r in painel['resumo_especialidade']['por_especialidade']}

    def resumo(chave_especialidade, nome_display):
        r = resumo_por_esp.get(nome_display, {'total': 0, 'total_nc': 0, 'p1': 0, 'p2': 0, 'p3': 0})
        pct = round((r['total'] - r['total_nc']) / r['total'] * 100) if r['total'] else 0
        return r['total'], r['total_nc'], pct, r['p1'], r['p2'], r['p3']

    civil_total, civil_nc, civil_pct_conf, civil_p1, civil_p2, civil_p3 = resumo('civil', 'Engenharia Civil')
    eletrica_total, eletrica_nc, eletrica_pct_conf, eletrica_p1, eletrica_p2, eletrica_p3 = resumo('eletrica', 'Engenharia Elétrica')
    mecanica_total, mecanica_nc, mecanica_pct_conf, mecanica_p1, mecanica_p2, mecanica_p3 = resumo('mecanica', 'Engenharia Mecânica')

    titulos_por_especialidade = {
        'civil': 'engenheiro civil', 'eletrica': 'engenheiro eletricista', 'mecanica': 'engenheiro mecânico',
    }
    equipe_tecnica = '; '.join(
        f"{p.nome}, {titulos_por_especialidade.get(esp.especialidade, esp.get_especialidade_display().lower())}"
        for esp in especialidades for p in esp.profissionais.all()
    )
    responsabilidade_tecnica = '; '.join(
        f"ART {esp.get_especialidade_display().lower()} nº {esp.numero_art or '[número]'}"
        for esp in especialidades
    )

    def profissional_principal(chave):
        esp = por_esp.get(chave)
        if esp is None:
            return '[nome]', '[CREA]'
        p = esp.profissionais.first()
        return (p.nome, p.crea) if p else ('[nome]', '[CREA]')

    nome_civil, crea_civil = profissional_principal('civil')
    nome_eletrica, crea_eletrica = profissional_principal('eletrica')
    nome_mecanica, crea_mecanica = profissional_principal('mecanica')

    direcionamento_totais = {d['key']: d for d in painel['por_direcionamento']} if 'por_direcionamento' in painel else {}

    matriz_risco_prazo = [
        {
            'rotulo': f"P{linha['prioridade']} – {dict(Achado.PRIORIDADE_CHOICES)[linha['prioridade']].split('— ')[-1]}",
            'celulas': [c['qtd'] or '—' for c in linha['celulas']],
            'total': sum(c['qtd'] for c in linha['celulas']),
        }
        for linha in painel['matriz_risco_prazo']
    ]

    anexo01 = [{
        'numero': item['numero'], 'local': item['localizacao'],
        'sistema_elemento': item['grupo_tecnico_nome'], 'situacao': item['situacao'],
        'nao_conformidade': item['descricao_nao_conformidade'] or '—',
        'recomendacao': item['recomendacao'] or '—',
        'grau_risco': item['prioridade_risco'] if item['gut_total'] else '—',
        'gut': item['gut_total'] or '—', 'prazo': item['prazo_label'] or '—',
    } for item in snapshot['anexo01']]

    plano_de_acao = [{
        'horizonte': linha['horizonte'], 'nc': linha['nc'],
        'principais_acoes': textos.get(f"plano_acao_{chave}", '—'),
        'forma_execucao': linha['forma_execucao'],
    } for linha, chave in zip(plano_por_horizonte, ['imediato', 'curto', 'medio', 'longo'])]

    agora = timezone.localtime(timezone.now())
    return {
        'edificacao_nome': edificacao.nome, 'edificacao_endereco': edificacao.endereco,
        'datas_vistorias': ', '.join(snapshot['datas_vistorias']),
        'mes_geracao': _MESES_PT[agora.month], 'ano_atual': agora.year,
        'area_construida': f'{edificacao.area_construida_m2:.2f}'.replace('.', ',') if edificacao.area_construida_m2 else '[a preencher] m²',
        'pavimentos': edificacao.pavimentos or '[a preencher]',
        'data_inauguracao_extenso': _data_extenso(edificacao.data_inauguracao) if edificacao.data_inauguracao else '[a preencher]',
        'equipe_tecnica': equipe_tecnica,
        'responsabilidade_tecnica': responsabilidade_tecnica,
        'sumario_executivo': textos['sumario_executivo'],
        'principais_constatacoes_1': textos['principais_constatacoes'],
        'principais_constatacoes_2': '', 'principais_constatacoes_3': '',
        'providencias_administracao_1': textos['providencias_administracao'], 'providencias_administracao_2': '',
        'resultados_gerais_intro_1': textos['resultados_gerais_intro'], 'resultados_gerais_intro_2': '',
        'resultados_gerais_achados_criticos': textos['resultados_gerais_achados_criticos'],
        'n_ganhos_rapidos': painel['n_ganhos_rapidos'],
        'itens_conformidade_civil': textos['itens_conformidade_civil'],
        'itens_conformidade_eletrica': textos['itens_conformidade_eletrica'],
        'itens_conformidade_mecanica': textos['itens_conformidade_mecanica'],
        'conclusao_1': textos['conclusao'], 'conclusao_2': '',
        'iqe': painel['iqe'], 'iqe_faixa': painel['iqe_faixa'], 'total': painel['total'],
        'pct_conformidade': painel['pct_conformidade'], 'total_conformes': painel['total_conformes'],
        'total_nc': painel['total_nc'], 'p1_total': painel['p1_total'], 'p2_total': painel['p2_total'],
        'p3_total': painel['p3_total'], 'gut_media': painel['gut_media'],
        'direcionamento_manutencao_total': direcionamento_totais.get('manutencao', {}).get('total', 0),
        'direcionamento_manutencao_pct': direcionamento_totais.get('manutencao', {}).get('pct', 0),
        'direcionamento_nova_contratacao_total': direcionamento_totais.get('nova_contratacao', {}).get('total', 0),
        'direcionamento_nova_contratacao_pct': direcionamento_totais.get('nova_contratacao', {}).get('pct', 0),
        'direcionamento_garantia_total': direcionamento_totais.get('garantia', {}).get('total', 0),
        'direcionamento_garantia_pct': direcionamento_totais.get('garantia', {}).get('pct', 0),
        'manutencao_classificacao': textos['manutencao_classificacao'] or '[a preencher]',
        'manutencao_fundamentacao': textos['manutencao_fundamentacao'],
        'uso_classificacao': textos['uso_classificacao'] or '[a preencher]',
        'uso_fundamentacao': textos['uso_fundamentacao'],
        'condicao_global': classificar_condicao_global(painel['iqe']),
        'civil_total': civil_total, 'civil_nc': civil_nc, 'civil_pct_conf': civil_pct_conf,
        'civil_p1': civil_p1, 'civil_p2': civil_p2, 'civil_p3': civil_p3,
        'eletrica_total': eletrica_total, 'eletrica_nc': eletrica_nc, 'eletrica_pct_conf': eletrica_pct_conf,
        'eletrica_p1': eletrica_p1, 'eletrica_p2': eletrica_p2, 'eletrica_p3': eletrica_p3,
        'mecanica_total': mecanica_total, 'mecanica_nc': mecanica_nc, 'mecanica_pct_conf': mecanica_pct_conf,
        'mecanica_p1': mecanica_p1, 'mecanica_p2': mecanica_p2, 'mecanica_p3': mecanica_p3,
        'matriz_risco_prazo': matriz_risco_prazo,
        # Tabela 9 do modelo real é "Quadro de não conformidades de
        # Prioridade 1, ordenado por índice GUT" — TODOS os P1, não só os
        # 10 maiores de qualquer prioridade (isso é outro gráfico,
        # `painel['img_top_gut']`, que não tem tabela correspondente aqui).
        'top_gut': [{
            'numero': i + 1, 'local': a.localizacao, 'nao_conformidade': a.descricao_nao_conformidade or '—',
            'recomendacao': a.recomendacao or '—', 'gut': a.gut_total,
            'prazo': dict(Achado.PRAZO_CHOICES).get(a.prazo_meses, f'{a.prazo_meses} meses'),
        } for i, a in enumerate(sorted(
            (a for a in nao_conformes if a.prioridade_risco == 1), key=lambda a: -a.gut_total,
        ))],
        'historico_intervencoes': [
            {'ano': h.ano, 'descricao': h.descricao} for h in edificacao.historico_intervencoes.all()
        ],
        'plano_de_acao': plano_de_acao,
        'nome_civil': nome_civil, 'titulo_civil': 'Engenheiro civil', 'crea_civil': crea_civil,
        'nome_eletrica': nome_eletrica, 'titulo_eletrica': 'Engenheiro eletricista', 'crea_eletrica': crea_eletrica,
        'nome_mecanica': nome_mecanica, 'titulo_mecanica': 'Engenheiro mecânico', 'crea_mecanica': crea_mecanica,
        'anexo01': anexo01,
    }
```

**Nota importante para quem executar esta task:** a função acima faz várias suposições sobre as chaves exatas de `painel['resumo_especialidade']` e `painel['por_direcionamento']` com base na leitura de `_dados_gerais_snapshot`/`_por_direcionamento` em `views.py` — antes do Step 6 (rodar os testes), reler essas duas funções (`_dados_gerais_snapshot` por volta da linha 315, `_por_direcionamento` por volta da linha 1429) e ajustar nomes de chave se não baterem exatamente.

- [ ] **Step 5: Download e template — "Baixar PDF" → "Baixar Word"**

Em `src/apps/inspecoes/views.py`, em `relatorio_final_download`:

```python
@login_required
def relatorio_final_download(request, pk, versao_pk):
    inspecao = get_object_or_404(Inspecao, pk=pk)
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:detail', pk=pk)
    relatorio = get_object_or_404(RelatorioFinalInspecao, pk=versao_pk, inspecao=inspecao)
    resp = HttpResponse(
        relatorio.arquivo_docx.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    resp['Content-Disposition'] = f'attachment; filename="{os.path.basename(relatorio.arquivo_docx.name)}"'
    return resp
```

Em `src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html`, linha 60:

```html
          <i class="bi bi-download"></i> Baixar Word
```

- [ ] **Step 6: Rodar o teste novo e toda a suíte de relatório final**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest apps/inspecoes/tests/test_relatorio_final_views.py apps/inspecoes/tests/test_relatorio_final_invariantes.py -v`
Expected: PASS em todos — ajustar `_montar_contexto_docx` conforme os erros reais apontarem (ver nota do Step 4).

- [ ] **Step 7: Remover o código de geração de PDF que ficou órfão**

Em `src/apps/inspecoes/views.py`, remover (ou comentar com uma nota de "mantido só para referência histórica, pode ser excluído" — preferir remover): `_gerar_pdf`, `_gerar_pdf_bytes`, `_aplicar_metadados_pdf`, `_corrigir_bug_tempfile_fontes_windows`, `_fontes_pdf_css`, `_montar_contexto_pdf_com_fotos`, `_foto_para_data_uri`, e os templates `relatorio_final_pdf.html` / `_relatorio_final_painel.html` / `_relatorio_final_metodologia.html` (não removê-los nesta task se **qualquer** outra view ainda os usa — confirmar com `grep -rn "_gerar_pdf\|_montar_contexto_pdf_com_fotos\|relatorio_final_pdf.html" src/apps/inspecoes/views.py` antes de apagar; essas funções são usadas SÓ por `relatorio_final_gerar`, então são seguras de remover, mas `_gerar_pdf`/`_gerar_pdf_bytes`/`_corrigir_bug_tempfile_fontes_windows`/`_fontes_pdf_css` também podem ser usadas por `especialidade_analise_pdf`/`inspecao_analise_pdf` — CONFIRMAR antes de apagar, e manter se estiverem em uso por essas outras duas views de PDF, que não fazem parte do escopo desta plan).

Run: `cd src && ../.venv/Scripts/python.exe -m pytest -q`
Expected: PASS em toda a suíte, nenhum `ImportError`/`NameError` por função removida que ainda era usada.

- [ ] **Step 8: Teste manual end-to-end**

```bash
cd src
../.venv/Scripts/python.exe manage.py runserver
```
No navegador: criar uma inspeção com as 3 especialidades, pelo menos um achado não conforme em cada, preencher conclusão de cada especialidade e descritivo da edificação, gerar o Relatório Final, baixar o `.docx` e abrir no Word — confirmar visualmente contra o checklist da Task 9/Step 3.

- [ ] **Step 9: Commit**

```bash
git add src/apps/inspecoes/
git commit -m "feat: Relatorio Final de Inspecao agora gera Word (.docx) com textos do Gemini, substitui PDF"
```

---

### Task 12: Revisão final e suíte completa

- [ ] **Step 1: Suíte completa**

Run: `cd src && ../.venv/Scripts/python.exe -m pytest -q`
Expected: todos os testes passam, incluindo os novos de `apps/relatorio_final`, `apps/edificacoes` e `apps/inspecoes`.

- [ ] **Step 2: `manage.py check`**

Run: `cd src && ../.venv/Scripts/python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Revisão de código (self-review ou `/code-review`)**

Rodar uma revisão de código no diff acumulado desta feature antes de considerar pronta para PR/merge (ex. `/code-review high` sobre o branch, se estiver usando branch dedicado).

- [ ] **Step 4: Atualizar o `CLAUDE.md`/quickstart se necessário**

Conferir se `specs/001-registro-achados/quickstart.md` ou `specs/001-registro-achados/plan.md` mencionam a geração de PDF do Relatório Final como parte do fluxo documentado — se sim, atualizar essas referências para Word.

---

## Pendências explícitas fora do escopo desta plan (ver grill de 2026-10-27/28)

- Upload/versionamento do `.docx` editado manualmente de volta ao sistema — decidido como fora de escopo.
- Processo SEI automatizado — fica como `[número do processo]` manual.
- Data de averbação da construção — fora de escopo.
- Grade fixa de 2 colunas de fotos (Task 10/Step 5) — simplificada para sequência vertical no MVP; grade exata é um ajuste isolado futuro.
- Linha "Total" (soma por coluna de prazo) da tabela Matriz Risco × Prazo (Tabela 8 do modelo real) — descartada nesta versão; cada linha P1/P2/P3 já mostra seu próprio total por linha. Adicionar de volta é um ajuste isolado em `docx_builder.py`/no template, somando `matriz_risco_prazo` por coluna.
- `GEMINI_API_KEY`/`GEMINI_MODEL` precisam ser configurados no `.env` da VM antes da Task 11 funcionar com texto real (sem a chave, o relatório é gerado com os campos de texto vazios — comportamento esperado, não é bug).
