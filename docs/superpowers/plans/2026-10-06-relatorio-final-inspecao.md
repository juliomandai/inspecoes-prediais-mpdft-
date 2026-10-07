# Relatório Final de Inspeção Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a professional, on closing the 3 specialty inspections (civil, elétrica, mecânica) of a building inspection, generate a versioned, immutable "Relatório Final de Inspeção" (PDF + structured snapshot) listing every finding with photos and ending in signature blocks, to instruct an ART filing with CREA.

**Architecture:** Two new text fields feed the report (`Edificacao.descritivo`, reusable across inspections; `InspecaoEspecialidade.conclusao`, required to finalize each specialty). A new `RelatorioFinalInspecao` entity (same app, `apps.inspecoes`) stores each generation as an immutable, versioned record — the rendered PDF plus a JSON snapshot that embeds its own copies of the photos used, so it survives later edits or retention purges of the live data. Generation is gated by an invariant method on `Inspecao` that returns the list of missing preconditions (3 specialties finalized, descritivo filled, conclusões filled, ≥2 photos per non-conforming finding) — nothing is silently skipped.

**Tech Stack:** Django 5.2, pytest-django, xhtml2pdf (`pisa`, already used by the existing "laudo" PDF export), Django's `default_storage`/`ContentFile` for file handling, Bootstrap 5 templates matching the existing app.

**Reference:** Design doc `docs/superpowers/specs/2026-10-06-relatorio-final-inspecao-design.md`, ADRs `docs/adr/2026-10-06-relatorio-encerramento-0{1-9}-*.md`, glossary `docs/grilling/relatorio-encerramento-glossary.md`.

**Note on scope:** Per the design doc, Section 6 (PDF layout/wording) is pending team review and may change — Task 10 below isolates that layout in its own template file (`relatorio_final_pdf.html`) precisely so a later wording change doesn't touch any Python code. Everything else (data model, invariants, permissions) is considered stable and safe to ship now.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/apps/edificacoes/models.py` | Modify: add `Edificacao.descritivo` |
| `src/apps/edificacoes/forms.py` | Modify: add `DescritivoEdificacaoForm` |
| `src/apps/inspecoes/models.py` | Modify: add `InspecaoEspecialidade.conclusao`, `LogAcesso` tipo, `RelatorioFinalInspecao` model, `Inspecao.pendencias_relatorio_final`/`pode_gerar_relatorio_final` |
| `src/apps/inspecoes/forms.py` | Modify: add `conclusao` to `EspecialidadeForm` |
| `src/apps/inspecoes/views.py` | Modify: `especialidade_finalizar` validation, `especialidade_reabrir` warning; add permission helper, snapshot/foto-copy helpers, PDF-bytes helper, and the 4 new views |
| `src/apps/inspecoes/urls.py` | Modify: 4 new routes |
| `src/apps/inspecoes/admin.py` | Modify: register `RelatorioFinalInspecao` (read-only) |
| `src/apps/inspecoes/templates/inspecoes/especialidade_form.html` | Modify: add conclusão textarea |
| `src/apps/inspecoes/templates/inspecoes/detail.html` | Modify: add link to the painel when inspection is closed |
| `src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html` | Create: status screen (pendências, edit descritivo, list/download versions, generate button) |
| `src/apps/inspecoes/templates/inspecoes/relatorio_final_pdf.html` | Create: the report's own layout (isolated — see Note on scope above) |
| `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py` | Create: tests for the gating logic |
| `src/apps/inspecoes/tests/test_relatorio_final_views.py` | Create: tests for permissions, generation, versioning, download, warnings |

---

### Task 1: `Edificacao.descritivo`

**Files:**
- Modify: `src/apps/edificacoes/models.py`
- Test: `src/apps/edificacoes/tests.py`

- [x] **Step 1: Write the failing test**

Append to `src/apps/edificacoes/tests.py`:

```python
import pytest
from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_descritivo_aceita_texto_livre_e_pode_ficar_vazio():
    e1 = Edificacao.objects.create(nome='Sede com descritivo', descritivo='Prédio de 3 pavimentos, construído em 1998.')
    e2 = Edificacao.objects.create(nome='Sede sem descritivo')
    assert e1.descritivo == 'Prédio de 3 pavimentos, construído em 1998.'
    assert e2.descritivo == ''
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/edificacoes/tests.py::test_descritivo_aceita_texto_livre_e_pode_ficar_vazio -v`
Expected: FAIL with `TypeError: Edificacao() got unexpected keyword arguments: 'descritivo'`

- [x] **Step 3: Add the field**

In `src/apps/edificacoes/models.py`, inside `class Edificacao(SoftDeleteModel):`, after `endereco`:

```python
    endereco = models.TextField('Endereço', max_length=500, blank=True)
    descritivo = models.TextField(
        'Descritivo', blank=True,
        help_text='Idade, tipo construtivo, uso etc. — reutilizado em todo '
                   'Relatório Final de Inspeção desta edificação.',
    )
```

- [x] **Step 4: Generate and apply the migration**

Run: `python manage.py makemigrations edificacoes`
Expected: `Migrations for 'edificacoes': ... + Add field descritivo to edificacao`

Rename the generated file to `0004_edificacao_descritivo.py` if Django picked an auto-generated name, then run:
Run: `python manage.py migrate`
Expected: `Applying edificacoes.0004_edificacao_descritivo... OK`

- [x] **Step 5: Run test to verify it passes**

Run: `pytest src/apps/edificacoes/tests.py::test_descritivo_aceita_texto_livre_e_pode_ficar_vazio -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add src/apps/edificacoes/models.py src/apps/edificacoes/migrations/0004_edificacao_descritivo.py src/apps/edificacoes/tests.py
git commit -m "feat: adiciona Edificacao.descritivo (ADR-08)"
```

---

### Task 2: `InspecaoEspecialidade.conclusao` + exigência na finalização

**Files:**
- Modify: `src/apps/inspecoes/models.py`
- Modify: `src/apps/inspecoes/views.py:327-339` (`especialidade_finalizar`)
- Test: `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py` (new)

- [ ] **Step 1: Write the failing test for the field**

Create `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py`:

```python
import pytest
from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado, Foto


@pytest.mark.django_db
def test_conclusao_aceita_texto_livre_e_pode_ficar_vazia():
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana', data_inspecao=date.today(),
    )
    assert esp.conclusao == ''
    esp.conclusao = 'Estrutura em bom estado geral; recomenda-se manutenção preventiva nos itens 3 e 7.'
    esp.save(update_fields=['conclusao'])
    esp.refresh_from_db()
    assert 'manutenção preventiva' in esp.conclusao
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py -v`
Expected: FAIL with `TypeError: InspecaoEspecialidade() got unexpected keyword arguments` (or `AttributeError` on `.conclusao`, depending on exact Django version's error) — the field doesn't exist yet.

- [ ] **Step 3: Add the field**

In `src/apps/inspecoes/models.py`, inside `class InspecaoEspecialidade(SoftDeleteModel):`, after `status`:

```python
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='em_andamento')
    conclusao = models.TextField(
        'Conclusão e direcionamentos', blank=True,
        help_text='Texto livre, redigido pelo profissional responsável — exigido '
                   'para finalizar esta especialidade.',
    )
```

- [ ] **Step 4: Generate and apply the migration**

Run: `python manage.py makemigrations inspecoes`
Expected: `Migrations for 'inspecoes': ... + Add field conclusao to inspecaoespecialidade`

Rename to `0016_inspecaoespecialidade_conclusao.py`, then:
Run: `python manage.py migrate`
Expected: `Applying inspecoes.0016_inspecaoespecialidade_conclusao... OK`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py -v`
Expected: PASS

- [ ] **Step 6: Write the failing test for the finalization requirement**

Append to the same test file:

```python
@pytest.mark.django_db
def test_finalizar_especialidade_exige_conclusao_preenchida():
    U = get_user_model()
    u = U.objects.create_user(username='ana', password='1', is_staff=True)
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana', data_inspecao=date.today(),
    )
    Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=1, tendencia=1, em_conformidade=True,
    )
    client = pytest.importorskip('django.test').Client()
    client.force_login(u)

    resp = client.post(reverse('inspecoes:especialidade_finalizar', kwargs={'pk': esp.pk}))
    esp.refresh_from_db()
    assert esp.status == 'em_andamento'  # bloqueado: sem conclusão

    esp.conclusao = 'Sem não conformidades relevantes nesta vistoria.'
    esp.save(update_fields=['conclusao'])
    resp = client.post(reverse('inspecoes:especialidade_finalizar', kwargs={'pk': esp.pk}))
    esp.refresh_from_db()
    assert esp.status == 'finalizada'
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py::test_finalizar_especialidade_exige_conclusao_preenchida -v`
Expected: FAIL — the second assert fails because today's `especialidade_finalizar` finalizes regardless of `conclusao` AND the first assert fails too (it finalizes immediately since nothing blocks it yet).

- [ ] **Step 8: Add the validation**

In `src/apps/inspecoes/views.py`, inside `especialidade_finalizar` (currently at line 327), add a check right after the existing achados check:

```python
    if not esp.achados.exists():
        messages.error(request, 'Não é possível finalizar sem achados registrados.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    if not esp.conclusao.strip():
        messages.error(request, 'Não é possível finalizar sem preencher a conclusão e os direcionamentos.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    esp.status = 'finalizada'
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py -v`
Expected: 2 passed

- [ ] **Step 10: Add the field to the form and template**

In `src/apps/inspecoes/forms.py`, in `class EspecialidadeForm(forms.ModelForm)`:

```python
    class Meta:
        model = InspecaoEspecialidade
        fields = ['especialidade', 'data_inspecao', 'conclusao']
        widgets = {
            'especialidade': forms.Select(attrs={'class': 'form-select'}),
            'conclusao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'especialidade': 'Especialidade',
            'conclusao': 'Conclusão e direcionamentos',
        }
```

In `src/apps/inspecoes/templates/inspecoes/especialidade_form.html`, after the `data_inspecao` field block (currently lines 56-62), add:

```html
          <div class="mb-3">
            <label for="{{ form.conclusao.id_for_label }}" class="form-label">{{ form.conclusao.label }}</label>
            {{ form.conclusao }}
            <div class="form-text">Obrigatório para finalizar esta especialidade — alimenta o Relatório Final de Inspeção.</div>
            {% if form.conclusao.errors %}
            <div class="text-danger small mt-1">{{ form.conclusao.errors }}</div>
            {% endif %}
          </div>
```

- [ ] **Step 11: Run the full inspecoes test suite to check nothing broke**

Run: `pytest src/apps/inspecoes -v`
Expected: all passing (the new `EspecialidadeForm` field is `required=False` at the HTML level since the model field is `blank=True` — finalization enforcement is the view check from Step 8, not form validation, so existing specialty-creation tests that don't set `conclusao` keep working)

- [ ] **Step 12: Commit**

```bash
git add src/apps/inspecoes/models.py src/apps/inspecoes/migrations/0016_inspecaoespecialidade_conclusao.py src/apps/inspecoes/views.py src/apps/inspecoes/forms.py src/apps/inspecoes/templates/inspecoes/especialidade_form.html src/apps/inspecoes/tests/test_relatorio_final_invariantes.py
git commit -m "feat: InspecaoEspecialidade.conclusao, exigida para finalizar (ADR-09)"
```

---

### Task 3: Novo tipo de evento `relatorio_final_gerado`

**Files:**
- Modify: `src/apps/inspecoes/models.py:441-457` (`LogAcesso.TIPO_CHOICES`)

- [ ] **Step 1: Add the choice**

In `src/apps/inspecoes/models.py`, inside `LogAcesso.TIPO_CHOICES`, after `'subvisita_criada'`:

```python
        ('subvisita_criada', 'Subvisita de acompanhamento criada'),
        ('relatorio_final_gerado', 'Relatório Final de Inspeção gerado'),
    ]
```

`CharField` choices don't require a migration for a new choice value in SQLite/Postgres (no column constraint changes), but Django still records the choices change:

- [ ] **Step 2: Generate and apply the migration**

Run: `python manage.py makemigrations inspecoes`
Expected: `Migrations for 'inspecoes': ... ~ Alter field tipo on logacesso`

Rename to `0017_logacesso_tipo_relatorio_final.py`, then:
Run: `python manage.py migrate`
Expected: `Applying inspecoes.0017_logacesso_tipo_relatorio_final... OK`

- [ ] **Step 3: Commit**

```bash
git add src/apps/inspecoes/models.py src/apps/inspecoes/migrations/0017_logacesso_tipo_relatorio_final.py
git commit -m "feat: novo tipo de LogAcesso para geracao do Relatorio Final"
```

---

### Task 4: Model `RelatorioFinalInspecao`

**Files:**
- Modify: `src/apps/inspecoes/models.py`
- Modify: `src/apps/inspecoes/admin.py`
- Test: `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py`

- [ ] **Step 1: Write the failing test**

Append to `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py`:

```python
from django.core.files.base import ContentFile
from apps.inspecoes.models import RelatorioFinalInspecao


@pytest.mark.django_db
def test_relatorio_final_e_versionado_e_unico_por_inspecao():
    U = get_user_model()
    u = U.objects.create_user(username='ana', password='1')
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)

    r1 = RelatorioFinalInspecao.objects.create(
        inspecao=insp, numero_versao=1, snapshot={'ok': True}, gerado_por=u,
    )
    r1.arquivo_pdf.save('teste.pdf', ContentFile(b'%PDF-fake'), save=True)
    r2 = RelatorioFinalInspecao.objects.create(
        inspecao=insp, numero_versao=2, snapshot={'ok': True}, gerado_por=u,
    )

    assert list(insp.relatorios_finais.all()) == [r2, r1]  # ordering = ['-numero_versao']
    assert RelatorioFinalInspecao.objects.filter(pk=r1.pk).exists()  # gerar de novo não apaga o anterior

    with pytest.raises(Exception):
        RelatorioFinalInspecao.objects.create(inspecao=insp, numero_versao=1, snapshot={}, gerado_por=u)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py::test_relatorio_final_e_versionado_e_unico_por_inspecao -v`
Expected: FAIL with `ImportError: cannot import name 'RelatorioFinalInspecao'`

- [ ] **Step 3: Add the model**

In `src/apps/inspecoes/models.py`, after the `LogAcesso` class (end of file):

```python
def relatorio_pdf_upload_path(instance, filename):
    return f'relatorios/{instance.inspecao_id}/v{instance.numero_versao}/{filename}'


class RelatorioFinalInspecao(models.Model):
    """Documento formal (PDF + snapshot) gerado ao encerrar uma inspeção
    completa, para instruir ART junto ao CREA.

    Imutável depois de gerado (ADR-03): gerar de novo cria uma nova versão,
    nunca sobrescreve. NÃO herda SoftDeleteModel — é um registro de
    auditoria/legal, mesma categoria de LogAcesso/EncaminhamentoHistorico;
    nada o exclui, nem logicamente.

    `snapshot` guarda uma cópia estruturada do conteúdo (achados, conclusões,
    descritivo) no momento da geração, incluindo os CAMINHOS das fotos
    copiadas para este relatório (não FKs para `Foto` — ver ADR-07: o
    snapshot sobrevive a uma purga futura dos originais).
    """
    inspecao = models.ForeignKey(
        Inspecao, on_delete=models.PROTECT, related_name='relatorios_finais',
        verbose_name='Inspeção',
    )
    numero_versao = models.PositiveIntegerField('Versão')
    arquivo_pdf = models.FileField('PDF gerado', upload_to=relatorio_pdf_upload_path)
    snapshot = models.JSONField('Snapshot')
    gerado_por = models.ForeignKey(
        get_user_model(), on_delete=models.PROTECT, related_name='relatorios_finais_gerados',
        verbose_name='Gerado por',
    )
    gerado_em = models.DateTimeField('Gerado em', auto_now_add=True)

    class Meta:
        ordering = ['-numero_versao']
        verbose_name = 'Relatório Final de Inspeção'
        verbose_name_plural = 'Relatórios Finais de Inspeção'
        constraints = [
            models.UniqueConstraint(
                fields=['inspecao', 'numero_versao'], name='unique_versao_por_inspecao',
            ),
        ]

    def __str__(self):
        return f'{self.inspecao.edificacao} — Relatório Final v{self.numero_versao}'
```

- [ ] **Step 4: Generate and apply the migration**

Run: `python manage.py makemigrations inspecoes`
Expected: `Migrations for 'inspecoes': ... + Create model RelatorioFinalInspecao`

Rename to `0018_relatoriofinalinspecao.py`, then:
Run: `python manage.py migrate`
Expected: `Applying inspecoes.0018_relatoriofinalinspecao... OK`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py::test_relatorio_final_e_versionado_e_unico_por_inspecao -v`
Expected: PASS

- [ ] **Step 6: Register in admin (read-only — it's an immutable audit record)**

In `src/apps/inspecoes/admin.py`, add the import and a new registration (do **not** use `SoftDeleteAdminMixin` — this model has no soft delete):

```python
from .models import (
    Inspecao, InspecaoEspecialidade, Achado, Foto, LogAcesso,
    VisitaTecnica, VisitaFoto, EncaminhamentoHistorico, RelatorioFinalInspecao,
)
```

```python
@admin.register(RelatorioFinalInspecao)
class RelatorioFinalInspecaoAdmin(admin.ModelAdmin):
    list_display = ['inspecao', 'numero_versao', 'gerado_por', 'gerado_em']
    list_filter = ['inspecao__edificacao']
    readonly_fields = ['inspecao', 'numero_versao', 'arquivo_pdf', 'snapshot', 'gerado_por', 'gerado_em']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
```

- [ ] **Step 7: Confirm the admin page loads**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 8: Commit**

```bash
git add src/apps/inspecoes/models.py src/apps/inspecoes/migrations/0018_relatoriofinalinspecao.py src/apps/inspecoes/admin.py src/apps/inspecoes/tests/test_relatorio_final_invariantes.py
git commit -m "feat: model RelatorioFinalInspecao, versionado e imutavel (ADR-03/ADR-07)"
```

---

### Task 5: Invariante `pendencias_relatorio_final` / `pode_gerar_relatorio_final`

**Files:**
- Modify: `src/apps/inspecoes/models.py` (`Inspecao`)
- Test: `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py`

This is the single method the rest of the feature relies on for ADR-04/05/08/09 — it returns a list of human-readable pendências; an empty list means the report can be generated.

- [ ] **Step 1: Write the failing tests — one per pendência, plus the happy path**

Append to `src/apps/inspecoes/tests/test_relatorio_final_invariantes.py`:

```python
from django.core.files.uploadedfile import SimpleUploadedFile


def _criar_especialidade(insp, especialidade, conclusao='Conclusão padrão.', finalizada=True):
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade=especialidade, profissional='Ana',
        data_inspecao=date.today(), conclusao=conclusao,
    )
    if finalizada:
        esp.status = 'finalizada'
        esp.save(update_fields=['status'])
    return esp


def _achado_nao_conforme(esp, n_fotos=2):
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=4, urgencia=4, tendencia=4,
    )
    for i in range(n_fotos):
        Foto.objects.create(
            achado=achado,
            arquivo=SimpleUploadedFile(f'f{i}.jpg', b'fake', content_type='image/jpeg'),
            nome_original=f'f{i}.jpg',
        )
    return achado


@pytest.mark.django_db
def test_pendencia_quando_falta_especialidade():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    _criar_especialidade(insp, 'civil')
    _criar_especialidade(insp, 'eletrica')
    # mecânica nunca cadastrada
    pendencias = insp.pendencias_relatorio_final()
    assert any('Falta cadastrar' in p and 'Mecânica' in p for p in pendencias)
    assert not insp.pode_gerar_relatorio_final


@pytest.mark.django_db
def test_pendencia_quando_especialidade_nao_finalizada():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    _criar_especialidade(insp, 'civil', finalizada=False)
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    pendencias = insp.pendencias_relatorio_final()
    assert any('não finalizada' in p for p in pendencias)
    assert not insp.pode_gerar_relatorio_final


@pytest.mark.django_db
def test_pendencia_quando_falta_descritivo_da_edificacao():
    edif = Edificacao.objects.create(nome='Sede')  # sem descritivo
    insp = Inspecao.objects.create(edificacao=edif)
    for e in ('civil', 'eletrica', 'mecanica'):
        _criar_especialidade(insp, e)
    pendencias = insp.pendencias_relatorio_final()
    assert any('descritivo' in p for p in pendencias)


@pytest.mark.django_db
def test_pendencia_quando_falta_conclusao_de_alguma_especialidade():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    _criar_especialidade(insp, 'civil', conclusao='')
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    pendencias = insp.pendencias_relatorio_final()
    assert any('conclusão' in p and 'Civil' in p for p in pendencias)


@pytest.mark.django_db
def test_pendencia_quando_achado_nao_conforme_tem_menos_de_2_fotos():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    civil = _criar_especialidade(insp, 'civil')
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    _achado_nao_conforme(civil, n_fotos=1)
    pendencias = insp.pendencias_relatorio_final()
    assert any('menos de 2 fotos' in p for p in pendencias)


@pytest.mark.django_db
def test_sem_pendencias_quando_tudo_preenchido():
    edif = Edificacao.objects.create(nome='Sede', descritivo='Prédio de 2 pavimentos.')
    insp = Inspecao.objects.create(edificacao=edif)
    civil = _criar_especialidade(insp, 'civil')
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    _achado_nao_conforme(civil, n_fotos=2)
    assert insp.pendencias_relatorio_final() == []
    assert insp.pode_gerar_relatorio_final
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py -v`
Expected: FAIL with `AttributeError: 'Inspecao' object has no attribute 'pendencias_relatorio_final'`

- [ ] **Step 3: Implement the invariant**

In `src/apps/inspecoes/models.py`, inside `class Inspecao(SoftDeleteModel):`, after `status_geral`:

```python
    ESPECIALIDADES_OBRIGATORIAS = {'civil', 'eletrica', 'mecanica'}

    def pendencias_relatorio_final(self):
        """Lista de pendências (texto legível) que impedem gerar o
        Relatório Final de Inspeção. Lista vazia = pode gerar
        (ver ADR-04, ADR-05, ADR-08, ADR-09)."""
        pendencias = []
        especialidades = list(self.especialidades.all())
        existentes = {e.especialidade: e for e in especialidades}
        faltando = self.ESPECIALIDADES_OBRIGATORIAS - set(existentes)

        if faltando:
            nomes_choices = dict(InspecaoEspecialidade.ESPECIALIDADE_CHOICES)
            nomes = ', '.join(nomes_choices[k] for k in sorted(faltando))
            pendencias.append(f'Falta cadastrar: {nomes}.')
            return pendencias  # sem as 3, nada mais faz sentido checar ainda

        obrigatorias = [e for e in especialidades if e.especialidade in self.ESPECIALIDADES_OBRIGATORIAS]
        nao_finalizadas = [e for e in obrigatorias if e.status != 'finalizada']
        if nao_finalizadas:
            nomes = ', '.join(e.get_especialidade_display() for e in nao_finalizadas)
            pendencias.append(f'Especialidade(s) não finalizada(s): {nomes}.')
            return pendencias  # idem — com especialidade em andamento, conclusão/fotos ainda podem mudar

        if not self.edificacao.descritivo.strip():
            pendencias.append('Falta o descritivo da edificação.')

        for esp in obrigatorias:
            if not esp.conclusao.strip():
                pendencias.append(f'Falta a conclusão de {esp.get_especialidade_display()}.')

        achados_insuficientes = []
        for esp in obrigatorias:
            for achado in esp.achados.filter(gut_total__gt=0):
                if achado.fotos.count() < 2:
                    achados_insuficientes.append(achado)
        if achados_insuficientes:
            primeiros = ', '.join(f'"{a.verificacao}"' for a in achados_insuficientes[:5])
            reticencias = '...' if len(achados_insuficientes) > 5 else ''
            pendencias.append(
                f'{len(achados_insuficientes)} achado(s) não conforme(s) com menos de 2 fotos: '
                f'{primeiros}{reticencias}.'
            )

        return pendencias

    @property
    def pode_gerar_relatorio_final(self):
        return not self.pendencias_relatorio_final()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_invariantes.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/apps/inspecoes/models.py src/apps/inspecoes/tests/test_relatorio_final_invariantes.py
git commit -m "feat: Inspecao.pendencias_relatorio_final / pode_gerar_relatorio_final (ADR-04/05/08/09)"
```

---

### Task 6: Permissão de geração

**Files:**
- Modify: `src/apps/inspecoes/views.py`

**Files:**
- Test: `src/apps/inspecoes/tests/test_relatorio_final_views.py` (new)

- [ ] **Step 1: Write the failing test**

Create `src/apps/inspecoes/tests/test_relatorio_final_views.py`:

```python
import pytest
from datetime import date
from django.contrib.auth import get_user_model

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.inspecoes.views import _pode_gerar_relatorio_final


@pytest.fixture
def inspecao_com_profissionais(db):
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana Civil',
        data_inspecao=date.today(), conclusao='ok',
    )
    InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='eletrica', profissional='Beto Eletrica',
        data_inspecao=date.today(), conclusao='ok',
    )
    return insp


@pytest.mark.django_db
def test_profissional_de_qualquer_uma_das_especialidades_pode_gerar(inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    eletrica = U.objects.create_user(username='beto', password='1', first_name='Beto', last_name='Eletrica')
    estranho = U.objects.create_user(username='carlos', password='1', first_name='Carlos', last_name='Estranho')
    staff = U.objects.create_user(username='staff', password='1', is_staff=True)

    assert _pode_gerar_relatorio_final(civil, inspecao_com_profissionais)
    assert _pode_gerar_relatorio_final(eletrica, inspecao_com_profissionais)
    assert not _pode_gerar_relatorio_final(estranho, inspecao_com_profissionais)
    assert _pode_gerar_relatorio_final(staff, inspecao_com_profissionais)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py -v`
Expected: FAIL with `ImportError: cannot import name '_pode_gerar_relatorio_final'`

- [ ] **Step 3: Implement the helper**

In `src/apps/inspecoes/views.py`, right after `_acesso_negado_especialidade` (currently ending at line 282), add:

```python
def _pode_gerar_relatorio_final(user, inspecao):
    """Quem pode gerar/editar o Relatório Final de Inspeção: staff, superusuário,
    ou qualquer profissional listado em QUALQUER UMA das especialidades da
    inspeção (não precisa ter participado das 3 — ver glossário, Seção 5)."""
    if user.is_staff or user.is_superuser:
        return True
    nomes_permitidos = set()
    for esp in inspecao.especialidades.all():
        nomes_permitidos.update(esp.profissionais_lista)
    return user.get_full_name() in nomes_permitidos
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: permissao de geracao do Relatorio Final (qualquer especialidade da inspecao)"
```

---

### Task 7: Painel de status do Relatório Final (view + template + URL)

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`
- Create: `src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html`
- Test: `src/apps/inspecoes/tests/test_relatorio_final_views.py`

- [ ] **Step 1: Write the failing test**

Append to `test_relatorio_final_views.py`:

```python
from django.urls import reverse


@pytest.mark.django_db
def test_painel_mostra_pendencias_para_quem_tem_acesso(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)

    resp = client.get(reverse('inspecoes:relatorio_final_painel', kwargs={'pk': inspecao_com_profissionais.pk}))

    assert resp.status_code == 200
    assert 'Falta cadastrar' in resp.content.decode()  # falta Mecânica


@pytest.mark.django_db
def test_painel_nega_acesso_a_quem_nao_participou(client, inspecao_com_profissionais):
    U = get_user_model()
    estranho = U.objects.create_user(username='carlos', password='1', first_name='Carlos', last_name='Estranho')
    client.force_login(estranho)

    resp = client.get(reverse('inspecoes:relatorio_final_painel', kwargs={'pk': inspecao_com_profissionais.pk}), follow=True)

    assert resp.status_code == 200
    assert 'Acesso negado' in resp.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py -v`
Expected: FAIL with `django.urls.exceptions.NoReverseMatch: Reverse for 'relatorio_final_painel' not found`

- [ ] **Step 3: Add the view**

In `src/apps/inspecoes/views.py`, add a new section after `especialidade_reabrir` (after line 363):

```python
# ── Relatório Final de Inspeção (ART/CREA) ──────────────────────────────────

@login_required
def relatorio_final_painel(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades', 'especialidades__achados__fotos', 'relatorios_finais',
        ),
        pk=pk,
    )
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(
            request,
            'Acesso negado. Apenas os profissionais responsáveis por esta '
            'inspeção podem acessar o Relatório Final.',
        )
        return redirect('inspecoes:detail', pk=pk)
    return render(request, 'inspecoes/relatorio_final_painel.html', {
        'inspecao': inspecao,
        'pendencias': inspecao.pendencias_relatorio_final(),
        'versoes': inspecao.relatorios_finais.all(),
        'descritivo_form': DescritivoEdificacaoForm(instance=inspecao.edificacao),
    })
```

Add the import at the top of the file (in the `.forms` import block, currently lines 25-29):

```python
from .forms import (
    InspecaoForm, EspecialidadeForm, AchadoForm, InspecaoFilterForm,
    VisitaTecnicaForm, VisitaFilterForm, SignUpForm,
    AcompanhamentoFilterForm, ReclassificarForm, AcompanhamentoAchadoForm,
)
from apps.edificacoes.forms import DescritivoEdificacaoForm
```

(`DescritivoEdificacaoForm` doesn't exist yet — that's Task 8's first step. Create it now as a minimal stub so this task's test can pass, then flesh it out in Task 8: in `src/apps/edificacoes/forms.py`, add)

```python
class DescritivoEdificacaoForm(forms.ModelForm):
    class Meta:
        model = Edificacao
        fields = ['descritivo']
        widgets = {
            'descritivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }
        labels = {'descritivo': 'Descritivo da edificação'}
```

- [ ] **Step 4: Add the URL**

In `src/apps/inspecoes/urls.py`, after the especialidades block (after line 34), add a new section:

```python
    # ── Relatório Final de Inspeção (ART/CREA) ─────────────────────────────────
    path('inspecoes/<int:pk>/relatorio-final/', views.relatorio_final_painel, name='relatorio_final_painel'),
```

- [ ] **Step 5: Create the template**

Create `src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html`:

```html
{% extends 'base.html' %}
{% block title %}Relatório Final de Inspeção — {{ inspecao.edificacao }}{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="mb-3">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{% url 'inspecoes:list' %}">Inspeções</a></li>
    <li class="breadcrumb-item"><a href="{% url 'inspecoes:detail' inspecao.pk %}">{{ inspecao.edificacao }}</a></li>
    <li class="breadcrumb-item active">Relatório Final de Inspeção</li>
  </ol>
</nav>

<div class="card mb-4">
  <div class="card-header"><h4 class="mb-0"><i class="bi bi-file-earmark-text"></i> Relatório Final de Inspeção</h4></div>
  <div class="card-body">
    {% if pendencias %}
    <div class="alert alert-warning">
      <h6 class="alert-heading">Pendências antes de gerar:</h6>
      <ul class="mb-0">
        {% for p in pendencias %}<li>{{ p }}</li>{% endfor %}
      </ul>
    </div>
    {% else %}
    <div class="alert alert-success mb-3">
      <i class="bi bi-check-circle-fill"></i> Tudo pronto — esta inspeção pode gerar o Relatório Final.
    </div>
    <form method="post" action="{% url 'inspecoes:relatorio_final_gerar' inspecao.pk %}">
      {% csrf_token %}
      <button type="submit" class="btn btn-success">
        <i class="bi bi-file-earmark-plus"></i> Gerar Relatório Final (versão {{ versoes.count|add:1 }})
      </button>
    </form>
    {% endif %}
  </div>
</div>

<div class="card mb-4">
  <div class="card-header"><h5 class="mb-0">Descritivo da edificação</h5></div>
  <div class="card-body">
    <form method="post" action="{% url 'inspecoes:relatorio_final_editar_descritivo' inspecao.pk %}">
      {% csrf_token %}
      {{ descritivo_form.descritivo }}
      <div class="form-text">Reutilizado em todo relatório desta edificação — editar aqui não cria uma nova versão sozinho.</div>
      <button type="submit" class="btn btn-outline-primary btn-sm mt-2">Salvar descritivo</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header"><h5 class="mb-0">Versões já geradas</h5></div>
  <div class="card-body">
    {% if not versoes %}
    <p class="text-muted mb-0">Nenhuma versão gerada ainda.</p>
    {% else %}
    <ul class="list-group">
      {% for v in versoes %}
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <span>Versão {{ v.numero_versao }} — gerada em {{ v.gerado_em|date:"d/m/Y H:i" }} por {{ v.gerado_por.get_full_name|default:v.gerado_por.username }}</span>
        <a href="{% url 'inspecoes:relatorio_final_download' inspecao.pk v.pk %}" class="btn btn-sm btn-outline-success">
          <i class="bi bi-download"></i> Baixar PDF
        </a>
      </li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
</div>
{% endblock %}
```

(This template references `relatorio_final_gerar`, `relatorio_final_editar_descritivo` and `relatorio_final_download` URLs, which don't exist yet — they're added in Tasks 8, 9 and 11. Until then, rendering this template raises `NoReverseMatch` for those links; that's expected and resolved task-by-task. If you want `test_painel_mostra_pendencias_para_quem_tem_acesso` to pass before those tasks, temporarily comment out the two `{% url %}` calls not yet defined, then restore them as each task lands.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py -v`
Expected: PASS (once Tasks 8/9/11 land and the commented-out URLs are restored; see note above)

- [ ] **Step 7: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html src/apps/edificacoes/forms.py src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: painel de status do Relatorio Final de Inspecao"
```

---

### Task 8: Editar descritivo a partir do painel

**Files:**
- Modify: `src/apps/edificacoes/forms.py` (flesh out `DescritivoEdificacaoForm` from Task 7's stub — already complete, no change needed here)
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`

- [ ] **Step 1: Write the failing test**

Append to `test_relatorio_final_views.py`:

```python
@pytest.mark.django_db
def test_editar_descritivo_pelo_painel(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)

    resp = client.post(
        reverse('inspecoes:relatorio_final_editar_descritivo', kwargs={'pk': inspecao_com_profissionais.pk}),
        {'descritivo': 'Prédio de 4 pavimentos, estrutura em concreto armado.'},
    )

    assert resp.status_code == 302
    inspecao_com_profissionais.edificacao.refresh_from_db()
    assert inspecao_com_profissionais.edificacao.descritivo == 'Prédio de 4 pavimentos, estrutura em concreto armado.'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_editar_descritivo_pelo_painel -v`
Expected: FAIL with `NoReverseMatch`

- [ ] **Step 3: Implement the view**

In `src/apps/inspecoes/views.py`, right after `relatorio_final_painel`:

```python
@login_required
@require_POST
def relatorio_final_editar_descritivo(request, pk):
    inspecao = get_object_or_404(Inspecao.objects.select_related('edificacao'), pk=pk)
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:relatorio_final_painel', pk=pk)
    form = DescritivoEdificacaoForm(request.POST, instance=inspecao.edificacao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Descritivo da edificação atualizado.')
    else:
        messages.error(request, 'Não foi possível salvar o descritivo.')
    return redirect('inspecoes:relatorio_final_painel', pk=pk)
```

- [ ] **Step 4: Add the URL**

In `src/apps/inspecoes/urls.py`, after the `relatorio_final_painel` route:

```python
    path('inspecoes/<int:pk>/relatorio-final/descritivo/', views.relatorio_final_editar_descritivo, name='relatorio_final_editar_descritivo'),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_editar_descritivo_pelo_painel -v`
Expected: PASS

- [ ] **Step 6: Restore the `{% url 'inspecoes:relatorio_final_editar_descritivo' %}` reference in `relatorio_final_painel.html`** if it was commented out in Task 7.

- [ ] **Step 7: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: editar descritivo da edificacao pelo painel do Relatorio Final (ADR-08)"
```

---

### Task 9: Snapshot + cópia de fotos (ADR-03/ADR-07)

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Test: `src/apps/inspecoes/tests/test_relatorio_final_views.py`

- [ ] **Step 1: Write the failing tests** (photo copy/summarizing, and the general-numbers section)

Append to `test_relatorio_final_views.py`:

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.inspecoes.models import Achado, Foto
from apps.inspecoes.views import _montar_snapshot_relatorio


@pytest.mark.django_db
def test_snapshot_copia_fotos_e_resume_conformes(inspecao_com_profissionais):
    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    nc = Achado.objects.create(
        especialidade=civil, localizacao='L1', verificacao='Rachadura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=5, urgencia=5, tendencia=5, recomendacao='Reparar',
    )
    for i in range(3):  # 3 fotos — só as 2 mais antigas devem entrar
        Foto.objects.create(
            achado=nc, arquivo=SimpleUploadedFile(f'f{i}.jpg', f'conteudo{i}'.encode(), content_type='image/jpeg'),
            nome_original=f'f{i}.jpg',
        )
    conforme = Achado.objects.create(
        especialidade=civil, localizacao='L2', verificacao='Piso ok', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True,
    )

    snapshot = _montar_snapshot_relatorio(inspecao_com_profissionais, numero_versao=1)

    civil_data = next(e for e in snapshot['especialidades'] if e['especialidade'] == 'civil')
    assert len(civil_data['achados_completos']) == 1
    assert len(civil_data['achados_completos'][0]['fotos']) == 2
    assert civil_data['achados_resumidos'] == [{'localizacao': 'L2', 'verificacao': 'Piso ok'}]

    # as fotos foram de fato copiadas para um caminho próprio do relatório
    from django.core.files.storage import default_storage
    for caminho in civil_data['achados_completos'][0]['fotos']:
        assert default_storage.exists(caminho)
        assert caminho.startswith(f'relatorios/{inspecao_com_profissionais.pk}/v1/')


@pytest.mark.django_db
def test_snapshot_inclui_dados_gerais_iguais_ao_painel_de_encerramento(inspecao_com_profissionais):
    """ADR da Seção 6 do design doc: o relatório reaproveita os mesmos
    números do painel de encerramento (análise geral) — não só a listagem
    itemizada de achados."""
    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    Achado.objects.create(
        especialidade=civil, localizacao='L1', verificacao='Rachadura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=5, urgencia=5, tendencia=5, prioridade_risco=1,
    )
    Achado.objects.create(
        especialidade=civil, localizacao='L2', verificacao='Piso ok', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True,
    )

    snapshot = _montar_snapshot_relatorio(inspecao_com_profissionais, numero_versao=1)

    gerais = snapshot['dados_gerais']
    assert gerais['total_achados'] == 2
    assert gerais['total_nao_conformes'] == 1
    assert gerais['total_conformes'] == 1
    assert gerais['p1'] == 1
    civil_gerais = next(e for e in gerais['por_especialidade'] if e['especialidade_nome'] == 'Engenharia Civil')
    assert civil_gerais == {'especialidade_nome': 'Engenharia Civil', 'total': 2, 'total_nc': 1, 'p1': 1, 'p2': 0, 'p3': 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_snapshot_copia_fotos_e_resume_conformes -v`
Expected: FAIL with `ImportError: cannot import name '_montar_snapshot_relatorio'`

- [ ] **Step 3: Implement the helpers**

In `src/apps/inspecoes/views.py`, add after `_pode_gerar_relatorio_final`:

```python
def _copiar_fotos_para_relatorio(inspecao_pk, numero_versao, achado, fotos):
    """Copia os arquivos de imagem usados para um caminho próprio do
    relatório — independente do ciclo de vida da Foto original (ADR-07).
    Retorna a lista de caminhos salvos (relativos ao storage)."""
    from django.core.files.storage import default_storage
    caminhos = []
    for i, foto in enumerate(fotos, start=1):
        ext = foto.arquivo.name.rsplit('.', 1)[-1]
        destino = f'relatorios/{inspecao_pk}/v{numero_versao}/achado_{achado.pk}_{i}.{ext}'
        with foto.arquivo.open('rb') as origem:
            caminho_salvo = default_storage.save(destino, ContentFile(origem.read()))
        caminhos.append(caminho_salvo)
    return caminhos


def _dados_gerais_snapshot(especialidades):
    """Reaproveita o mesmo recorte de números do painel de encerramento
    (análise geral — `_analise_data`/`por_especialidade` em
    `inspecao_analise_pdf`), mas como valores simples (int/str), não
    instâncias de `Achado` — o resultado precisa ser JSON-serializável
    para entrar no snapshot."""
    todos_achados = []
    for esp in especialidades:
        todos_achados.extend(list(esp.achados.all()))
    total = len(todos_achados)
    nao_conformes = [a for a in todos_achados if a.gut_total > 0]
    total_nc = len(nao_conformes)

    por_especialidade = []
    for esp in especialidades:
        ach = [a for a in todos_achados if a.especialidade_id == esp.pk]
        nc = [a for a in ach if a.gut_total > 0]
        por_especialidade.append({
            'especialidade_nome': esp.get_especialidade_display(),
            'total': len(ach),
            'total_nc': len(nc),
            'p1': len([a for a in nc if a.prioridade_risco == 1]),
            'p2': len([a for a in nc if a.prioridade_risco == 2]),
            'p3': len([a for a in nc if a.prioridade_risco == 3]),
        })

    return {
        'total_achados': total,
        'total_nao_conformes': total_nc,
        'total_conformes': total - total_nc,
        'p1': len([a for a in nao_conformes if a.prioridade_risco == 1]),
        'p2': len([a for a in nao_conformes if a.prioridade_risco == 2]),
        'p3': len([a for a in nao_conformes if a.prioridade_risco == 3]),
        'por_especialidade': por_especialidade,
    }


def _montar_snapshot_relatorio(inspecao, numero_versao):
    """Monta o conteúdo estruturado (JSON-serializável) congelado numa
    geração do Relatório Final — ver ADR-03. Inclui os dados gerais
    (mesmos números do painel de encerramento) e, por especialidade,
    achados completos (não conformes, com fotos copiadas) e resumidos
    (conformes, sem foto)."""
    edificacao = inspecao.edificacao
    especialidades = list(inspecao.especialidades.all())
    especialidades_data = []
    for esp in especialidades:
        achados_completos = []
        achados_resumidos = []
        for achado in esp.achados.all():
            if achado.gut_total > 0:
                fotos = list(achado.fotos.order_by('data_upload')[:2])
                caminhos_fotos = _copiar_fotos_para_relatorio(inspecao.pk, numero_versao, achado, fotos)
                achados_completos.append({
                    'localizacao': achado.localizacao,
                    'sub_localizacao': achado.sub_localizacao,
                    'verificacao': achado.verificacao,
                    'descricao_nao_conformidade': achado.descricao_nao_conformidade,
                    'gut_total': achado.gut_total,
                    'prioridade_risco': achado.get_prioridade_risco_display(),
                    'recomendacao': achado.recomendacao,
                    'fotos': caminhos_fotos,
                })
            else:
                achados_resumidos.append({
                    'localizacao': achado.localizacao,
                    'verificacao': achado.verificacao,
                })
        especialidades_data.append({
            'especialidade': esp.especialidade,
            'especialidade_nome': esp.get_especialidade_display(),
            'profissionais': esp.profissionais_lista,
            'conclusao': esp.conclusao,
            'achados_completos': achados_completos,
            'achados_resumidos': achados_resumidos,
        })
    return {
        'edificacao_nome': edificacao.nome,
        'edificacao_endereco': edificacao.endereco,
        'edificacao_descritivo': edificacao.descritivo,
        'inspecao_criada_em': inspecao.criado_em.isoformat(),
        'dados_gerais': _dados_gerais_snapshot(especialidades),
        'especialidades': especialidades_data,
    }
```

- [ ] **Step 4: Run both tests to verify they pass**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_snapshot_copia_fotos_e_resume_conformes src/apps/inspecoes/tests/test_relatorio_final_views.py::test_snapshot_inclui_dados_gerais_iguais_ao_painel_de_encerramento -v`
Expected: both PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: montagem do snapshot (dados gerais + achados + fotos) do Relatorio Final (ADR-03/ADR-07)"
```

---

### Task 10: Geração do PDF e da versão

**Files:**
- Modify: `src/apps/inspecoes/views.py` (imports + `_gerar_pdf_bytes` + `relatorio_final_gerar`)
- Modify: `src/apps/inspecoes/urls.py`
- Create: `src/apps/inspecoes/templates/inspecoes/relatorio_final_pdf.html` (draft — see plan header Note on scope)

- [ ] **Step 1: Write the failing test**

Append to `test_relatorio_final_views.py`:

```python
@pytest.mark.django_db
def test_gerar_relatorio_final_cria_versao_1_e_bloqueia_sem_pendencias_resolvidas(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)

    # falta mecânica — deve ser bloqueado, nenhuma versão criada
    resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    assert resp.status_code == 302
    assert inspecao_com_profissionais.relatorios_finais.count() == 0

    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')

    resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    assert resp.status_code == 302
    assert inspecao_com_profissionais.relatorios_finais.count() == 1
    relatorio = inspecao_com_profissionais.relatorios_finais.first()
    assert relatorio.numero_versao == 1
    assert relatorio.gerado_por == civil
    assert relatorio.arquivo_pdf.name
    assert relatorio.snapshot['edificacao_nome'] == 'Sede'

    # gerar de novo cria a versão 2, não sobrescreve a 1
    resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    assert inspecao_com_profissionais.relatorios_finais.count() == 2
    assert set(inspecao_com_profissionais.relatorios_finais.values_list('numero_versao', flat=True)) == {1, 2}

    from apps.inspecoes.models import LogAcesso
    assert LogAcesso.objects.filter(tipo='relatorio_final_gerado').count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_gerar_relatorio_final_cria_versao_1_e_bloqueia_sem_pendencias_resolvidas -v`
Expected: FAIL with `NoReverseMatch`

- [ ] **Step 3: Add the `Max` import**

In `src/apps/inspecoes/views.py`, line 11:

```python
from django.db.models import Count, Q, Min, Max
```

- [ ] **Step 4: Add `_gerar_pdf_bytes`**

Right after `_gerar_pdf` (currently ending at line 1335):

```python
def _gerar_pdf_bytes(html_string):
    """Como `_gerar_pdf`, mas devolve os bytes do PDF em vez de um
    HttpResponse — usado quando o PDF precisa ser salvo num FileField
    (RelatorioFinalInspecao), não só servido para download direto."""
    from xhtml2pdf import pisa
    buffer = io.BytesIO()
    result = pisa.pisaDocument(io.BytesIO(html_string.encode('utf-8')), buffer, encoding='utf-8')
    if result.err:
        return None
    return buffer.getvalue()
```

- [ ] **Step 5: Implement `relatorio_final_gerar`**

Right after `relatorio_final_editar_descritivo`:

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
    html = render_to_string('inspecoes/relatorio_final_pdf.html', {
        'inspecao': inspecao, 'snapshot': snapshot, 'numero_versao': numero_versao,
    }, request=request)
    pdf_bytes = _gerar_pdf_bytes(html)
    if pdf_bytes is None:
        messages.error(request, 'Erro ao gerar o PDF do relatório. Tente novamente.')
        return redirect('inspecoes:relatorio_final_painel', pk=pk)

    relatorio = RelatorioFinalInspecao(
        inspecao=inspecao, numero_versao=numero_versao, snapshot=snapshot, gerado_por=request.user,
    )
    nome_arquivo = f"relatorio_final_{inspecao.edificacao.nome.replace(' ', '_')}_v{numero_versao}.pdf"
    relatorio.arquivo_pdf.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
    relatorio.save()

    _log(request, 'relatorio_final_gerado',
         f'Relatório Final de Inspeção (v{numero_versao}) gerado para "{inspecao.edificacao}".')
    messages.success(request, f'Relatório Final de Inspeção (versão {numero_versao}) gerado com sucesso.')
    return redirect('inspecoes:relatorio_final_painel', pk=pk)
```

Add `RelatorioFinalInspecao` to the `.models` import block (currently lines 21-24):

```python
from .models import (
    Inspecao, InspecaoEspecialidade, Achado, Foto, OpcaoCampo, LogAcesso,
    VisitaTecnica, VisitaFoto, EncaminhamentoHistorico, RelatorioFinalInspecao,
)
```

- [ ] **Step 6: Add the URL**

In `src/apps/inspecoes/urls.py`, after the `relatorio_final_editar_descritivo` route:

```python
    path('inspecoes/<int:pk>/relatorio-final/gerar/', views.relatorio_final_gerar, name='relatorio_final_gerar'),
```

- [ ] **Step 7: Create the PDF template (draft — pending team review, per design doc Section 6)**

Create `src/apps/inspecoes/templates/inspecoes/relatorio_final_pdf.html`:

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; color: #222; }
  h1 { font-size: 16pt; }
  h2 { font-size: 13pt; margin-top: 24px; border-bottom: 1px solid #999; padding-bottom: 4px; }
  h3 { font-size: 11.5pt; margin-bottom: 2px; }
  .achado { margin-bottom: 16px; page-break-inside: avoid; }
  .achado-fotos img { width: 48%; margin-right: 2%; border: 1px solid #ccc; }
  .conforme-linha { font-size: 9.5pt; color: #444; }
  .assinatura { margin-top: 40px; page-break-inside: avoid; }
  .assinatura-linha { border-top: 1px solid #333; width: 60%; margin-top: 36px; padding-top: 4px; }
</style>
</head>
<body>

<h1>Relatório Final de Inspeção — {{ inspecao.edificacao.nome }}</h1>
<p>Versão {{ numero_versao }} — gerado em {% now "d/m/Y H:i" %}</p>

<h2>1. Descritivo da edificação</h2>
<p>{{ snapshot.edificacao_descritivo|linebreaks }}</p>
{% if snapshot.edificacao_endereco %}<p>Endereço: {{ snapshot.edificacao_endereco }}</p>{% endif %}

<h2>2. Dados gerais</h2>
<p>
  Total de itens verificados: {{ snapshot.dados_gerais.total_achados }} —
  Não conformes: {{ snapshot.dados_gerais.total_nao_conformes }} —
  Conformes: {{ snapshot.dados_gerais.total_conformes }}
</p>
<p>
  Prioridade 1 (crítico): {{ snapshot.dados_gerais.p1 }} —
  Prioridade 2 (regular): {{ snapshot.dados_gerais.p2 }} —
  Prioridade 3 (mínimo): {{ snapshot.dados_gerais.p3 }}
</p>
<table border="1" cellpadding="4" style="border-collapse: collapse; width: 100%;">
  <tr><th>Especialidade</th><th>Total</th><th>Não conformes</th><th>P1</th><th>P2</th><th>P3</th></tr>
  {% for linha in snapshot.dados_gerais.por_especialidade %}
  <tr>
    <td>{{ linha.especialidade_nome }}</td><td>{{ linha.total }}</td><td>{{ linha.total_nc }}</td>
    <td>{{ linha.p1 }}</td><td>{{ linha.p2 }}</td><td>{{ linha.p3 }}</td>
  </tr>
  {% endfor %}
</table>

{% for esp in snapshot.especialidades %}
<h2>3.{{ forloop.counter }} Achados — {{ esp.especialidade_nome }}</h2>

{% for a in esp.achados_completos %}
<div class="achado">
  <h3>{{ a.localizacao }}{% if a.sub_localizacao %} — {{ a.sub_localizacao }}{% endif %}: {{ a.verificacao }}</h3>
  <p>{{ a.descricao_nao_conformidade }}</p>
  <p><strong>GUT:</strong> {{ a.gut_total }} — <strong>Prioridade:</strong> {{ a.prioridade_risco }}</p>
  {% if a.recomendacao %}<p><strong>Recomendação:</strong> {{ a.recomendacao }}</p>{% endif %}
  <div class="achado-fotos">
    {% for caminho in a.fotos %}<img src="{{ MEDIA_URL }}{{ caminho }}">{% endfor %}
  </div>
</div>
{% endfor %}

{% for a in esp.achados_resumidos %}
<p class="conforme-linha">{{ a.localizacao }} — {{ a.verificacao }} — conforme</p>
{% endfor %}

<h3>Conclusão e direcionamentos</h3>
<p>{{ esp.conclusao|linebreaks }}</p>
{% endfor %}

<h2>4. Assinaturas</h2>
{% for esp in snapshot.especialidades %}
<h3>{{ esp.especialidade_nome }}</h3>
{% for nome in esp.profissionais %}
<div class="assinatura">
  <div class="assinatura-linha">{{ nome }}</div>
</div>
{% endfor %}
{% endfor %}

</body>
</html>
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_gerar_relatorio_final_cria_versao_1_e_bloqueia_sem_pendencias_resolvidas -v`
Expected: PASS

- [ ] **Step 9: Restore the `{% url 'inspecoes:relatorio_final_gerar' %}` form action in `relatorio_final_painel.html`** if it was commented out in Task 7.

- [ ] **Step 10: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/relatorio_final_pdf.html src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: geracao do PDF e da versao do Relatorio Final de Inspecao (ADR-03/06)"
```

---

### Task 11: Download de uma versão gerada

**Files:**
- Modify: `src/apps/inspecoes/views.py`
- Modify: `src/apps/inspecoes/urls.py`

- [ ] **Step 1: Write the failing test**

Append to `test_relatorio_final_views.py`:

```python
@pytest.mark.django_db
def test_download_relatorio_final(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)
    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')
    client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    relatorio = inspecao_com_profissionais.relatorios_finais.get()

    resp = client.get(reverse('inspecoes:relatorio_final_download', kwargs={'pk': inspecao_com_profissionais.pk, 'versao_pk': relatorio.pk}))

    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert resp.content.startswith(b'%PDF')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_download_relatorio_final -v`
Expected: FAIL with `NoReverseMatch`

- [ ] **Step 3: Implement the view**

Right after `relatorio_final_gerar`:

```python
@login_required
def relatorio_final_download(request, pk, versao_pk):
    inspecao = get_object_or_404(Inspecao, pk=pk)
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:detail', pk=pk)
    relatorio = get_object_or_404(RelatorioFinalInspecao, pk=versao_pk, inspecao=inspecao)
    resp = HttpResponse(relatorio.arquivo_pdf.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{os.path.basename(relatorio.arquivo_pdf.name)}"'
    return resp
```

- [ ] **Step 4: Add the URL**

In `src/apps/inspecoes/urls.py`, after the `relatorio_final_gerar` route:

```python
    path('inspecoes/<int:pk>/relatorio-final/<int:versao_pk>/download/', views.relatorio_final_download, name='relatorio_final_download'),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_download_relatorio_final -v`
Expected: PASS

- [ ] **Step 6: Restore the `{% url 'inspecoes:relatorio_final_download' %}` link in `relatorio_final_painel.html`** if it was commented out in Task 7.

- [ ] **Step 7: Run the whole file to confirm every test in it passes now**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py -v`
Expected: all passed

- [ ] **Step 8: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/urls.py src/apps/inspecoes/templates/inspecoes/relatorio_final_painel.html src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: download de uma versao do Relatorio Final de Inspecao"
```

---

### Task 12: Aviso ao reabrir especialidade após relatório já gerado (ADR-06)

**Files:**
- Modify: `src/apps/inspecoes/views.py:351-363` (`especialidade_reabrir`)

> Nota: `achado_update`/`achado_delete` já exigem `especialidade.pode_editar`
> (status `em_andamento`) para rodar — ou seja, a ÚNICA porta de entrada
> para voltar a editar achados de uma especialidade finalizada é reabri-la.
> Colocar o aviso em `especialidade_reabrir` já cobre o caso descrito no
> ADR-06 (edição de achado após relatório gerado) sem precisar duplicar o
> aviso em cada view de edição de achado.

- [ ] **Step 1: Write the failing test**

Append to `test_relatorio_final_views.py`:

```python
@pytest.mark.django_db
def test_reabrir_especialidade_avisa_quando_ja_ha_relatorio_gerado(client, inspecao_com_profissionais):
    U = get_user_model()
    civil_user = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil_user)
    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')
    client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))

    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    resp = client.post(reverse('inspecoes:especialidade_reabrir', kwargs={'pk': civil.pk}), follow=True)

    assert resp.status_code == 200
    mensagens = [str(m) for m in resp.context['messages']]
    assert any('Relatório Final' in m and 'v1' in m for m in mensagens)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_reabrir_especialidade_avisa_quando_ja_ha_relatorio_gerado -v`
Expected: FAIL — no such message is shown today.

- [ ] **Step 3: Add the warning**

In `src/apps/inspecoes/views.py`, inside `especialidade_reabrir` (currently lines 351-363), right before `esp.status = 'em_andamento'`:

```python
    if esp.status == 'em_andamento':
        messages.error(request, 'Esta especialidade já está em andamento.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    ultimo_relatorio = esp.inspecao.relatorios_finais.first()
    if ultimo_relatorio:
        messages.warning(
            request,
            f'Esta inspeção já tem um Relatório Final gerado (v{ultimo_relatorio.numero_versao}, '
            f'{ultimo_relatorio.gerado_em:%d/%m/%Y}). Editar agora não altera esse relatório — '
            f'gere uma nova versão se precisar refletir esta mudança.',
        )
    esp.status = 'em_andamento'
```

(`esp.inspecao.relatorios_finais.first()` returns the latest version because `RelatorioFinalInspecao.Meta.ordering = ['-numero_versao']`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest src/apps/inspecoes/tests/test_relatorio_final_views.py::test_reabrir_especialidade_avisa_quando_ja_ha_relatorio_gerado -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/apps/inspecoes/views.py src/apps/inspecoes/tests/test_relatorio_final_views.py
git commit -m "feat: aviso ao reabrir especialidade com Relatorio Final ja gerado (ADR-06)"
```

---

### Task 13: Link na tela de detalhe da inspeção

**Files:**
- Modify: `src/apps/inspecoes/templates/inspecoes/detail.html`

- [ ] **Step 1: Add the link next to "Abrir Painel de Encerramento"**

In `src/apps/inspecoes/templates/inspecoes/detail.html`, inside the conclusion banner (currently lines 15-25), add the new button next to the existing one:

```html
{% if inspecao.status_geral == 'finalizada' and inspecao.especialidades.exists %}
<div class="alert alert-success d-flex justify-content-between align-items-center flex-wrap gap-2 no-print" role="status">
  <div>
    <h5 class="alert-heading mb-1"><i class="bi bi-check-circle-fill"></i> Inspeção concluída</h5>
    <span class="mb-0">Todas as especialidades foram finalizadas. Veja o painel de insights e gere o laudo.</span>
  </div>
  <div class="d-flex gap-2">
    <a href="{% url 'inspecoes:inspecao_analise' inspecao.pk %}" class="btn btn-success">
      <i class="bi bi-clipboard2-data"></i> Abrir Painel de Encerramento
    </a>
    <a href="{% url 'inspecoes:relatorio_final_painel' inspecao.pk %}" class="btn btn-outline-success">
      <i class="bi bi-file-earmark-text"></i> Relatório Final de Inspeção
    </a>
  </div>
</div>
{% endif %}
```

- [ ] **Step 2: Manually verify in the browser**

Run: `python manage.py runserver`, open an inspection with all 3 specialties finalized, confirm the new button appears and links to the painel.

- [ ] **Step 3: Run the whole inspecoes test suite one more time**

Run: `pytest src/apps/inspecoes -v`
Expected: all passing

- [ ] **Step 4: Commit**

```bash
git add src/apps/inspecoes/templates/inspecoes/detail.html
git commit -m "feat: link para o Relatorio Final de Inspecao na tela de detalhe"
```

---

## Final Check

- [ ] Run the full test suite: `pytest -v` — expect all passing (170+ pre-existing + ~20 new).
- [ ] Run `python manage.py check` — expect no issues.
- [ ] Run `python manage.py makemigrations --check --dry-run` — expect "No changes detected".
- [ ] Manually walk through the flow once in the browser: finalize 3 specialties (with conclusões filled in), fill the descritivo, confirm the pendências list empties out, generate, download the PDF, reopen a specialty and confirm the warning appears.
