# Design: Relatório Final de Inspeção (para ART/CREA)

**Status:** Design fechado via sessão de grilling (`/grill-with-docs`, 2026-10-06).
Será apresentado à equipe para apreciação e aprovação do **modelo/conteúdo do
relatório** antes de implementar — a estrutura de domínio abaixo (entidades,
invariantes) é considerada estável; o layout/seções exatas do PDF podem
mudar após a revisão da equipe. Não implementado — próximo passo é
`/writing-plans`.

## 1. Contexto

Ao concluir as 3 especialidades (civil, elétrica, mecânica) de uma inspeção
predial, o SPO/MPDFT precisa de um documento formal — itemizando cada
achado com fotos e terminando em blocos de assinatura — para instruir uma
ART junto ao CREA. O sistema já gera um PDF ("laudo", `inspecao_analise_pdf`)
com estatísticas agregadas (Pareto, GUT, contagens), mas sem listar achados
individualmente, sem fotos por achado, e sem assinatura — não serve para
esse propósito.

## 2. Glossário

Ver [`docs/grilling/relatorio-encerramento-glossary.md`](../../grilling/relatorio-encerramento-glossary.md)
para os termos completos com a pergunta que resolveu cada um.

Resumo:
- **Relatório Final de Inspeção** — documento novo e distinto do laudo agregado.
- **RelatorioFinalInspecao** — entidade persistida e versionada que registra cada geração (PDF + snapshot).
- **Descritivo da edificação** — texto sobre a edificação em si, reutilizável entre inspeções.
- **Conclusão (e direcionamentos) da especialidade** — texto narrativo por especialidade, exigido para finalizar.
- **Entrada completa / resumida** — achado não conforme (completo + 2 fotos) vs. conforme (linha única).

## 3. Decisões de arquitetura (ADRs)

| ADR | Decisão |
|---|---|
| [ADR-01](../../adr/2026-10-06-relatorio-encerramento-01-documento-novo.md) | Documento novo e distinto do laudo agregado existente |
| [ADR-02](../../adr/2026-10-06-relatorio-encerramento-02-mesmo-app-inspecoes.md) | Vive dentro de `apps.inspecoes`, sem app novo |
| [ADR-03](../../adr/2026-10-06-relatorio-encerramento-03-entidade-persistida.md) | Entidade persistida e versionada, não um PDF efêmero |
| [ADR-04](../../adr/2026-10-06-relatorio-encerramento-04-exige-3-especialidades.md) | Geração exige as 3 especialidades finalizadas |
| [ADR-05](../../adr/2026-10-06-relatorio-encerramento-05-bloqueio-fotos-minimas.md) | Bloqueia geração se achado não conforme tiver <2 fotos |
| [ADR-06](../../adr/2026-10-06-relatorio-encerramento-06-aviso-edicao-pos-relatorio.md) | Editar/reabrir após relatório gerado só avisa, não bloqueia |
| [ADR-07](../../adr/2026-10-06-relatorio-encerramento-07-snapshot-duplica-fotos.md) | Snapshot duplica os arquivos de foto usados |
| [ADR-08](../../adr/2026-10-06-relatorio-encerramento-08-descritivo-edificacao.md) | Descritivo da edificação: campo novo, obrigatório, editável pelos profissionais |
| [ADR-09](../../adr/2026-10-06-relatorio-encerramento-09-conclusao-especialidade.md) | Conclusão/direcionamentos: campo novo, obrigatório para finalizar |

## 4. Modelo de dados proposto

Alterações em `apps/edificacoes/models.py`:

```python
class Edificacao(SoftDeleteModel):
    ...
    descritivo = models.TextField('Descritivo', blank=True)
    # Obrigatório apenas para gerar o Relatório Final de Inspeção (ADR-08) —
    # não é NOT NULL no banco, a validação é de aplicação (ver Seção 5).
```

Alterações em `apps/inspecoes/models.py`:

```python
class InspecaoEspecialidade(SoftDeleteModel):
    ...
    conclusao = models.TextField('Conclusão e direcionamentos', blank=True)
    # Obrigatório para finalizar (ADR-09) — validado em especialidade_finalizar,
    # não NOT NULL no banco (especialidades já finalizadas antes desta feature
    # existir ficam com o campo vazio até serem reabertas — ver Riscos).
```

Nova entidade, mesmo app (`apps/inspecoes/models.py`):

```python
class RelatorioFinalInspecao(models.Model):
    """Documento formal (PDF + snapshot) gerado ao encerrar uma inspeção
    completa, para instruir ART junto ao CREA. Imutável após gerado — ver
    ADR-03/ADR-06. NÃO herda SoftDeleteModel: é um registro de auditoria/
    legal, mesma categoria de LogAcesso/EncaminhamentoHistorico — nada o
    exclui, nem logicamente."""

    inspecao = models.ForeignKey(
        Inspecao, on_delete=models.PROTECT, related_name='relatorios_finais',
    )
    numero_versao = models.PositiveIntegerField('Versão')
    arquivo_pdf = models.FileField('PDF gerado', upload_to=relatorio_pdf_upload_path)
    snapshot = models.JSONField('Snapshot')
    # snapshot inclui: descritivo da edificação, dados agregados (iguais ao
    # painel de encerramento), achados (completos/resumidos conforme
    # Seção 5), conclusão de cada especialidade, e os caminhos das fotos
    # copiadas (ver relatorio_foto_upload_path / ADR-07) — não FKs para
    # Foto, para sobreviver a uma purga futura dos originais.
    gerado_por = models.ForeignKey(
        get_user_model(), on_delete=models.PROTECT, related_name='relatorios_finais_gerados',
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
```

Novo `LogAcesso.TIPO_CHOICES`:
```python
('relatorio_final_gerado', 'Relatório Final de Inspeção gerado'),
```

## 5. Invariantes de geração

`Inspecao` ganha um método/property (nome provisório `pode_gerar_relatorio_final`)
que só retorna `True` quando **todas** as condições abaixo são verdadeiras:

1. As 3 especialidades (civil, elétrica, mecânica) existem e `status == 'finalizada'` (ADR-04).
2. `edificacao.descritivo` não está vazio (ADR-08).
3. Cada uma das 3 especialidades tem `conclusao` não vazia (ADR-09 — na
   prática já garantido por `especialidade_finalizar`, mas revalidado aqui
   para cobrir especialidades finalizadas antes desta feature existir).
4. Todo achado com `gut_total > 0` de qualquer uma das 3 especialidades tem
   ≥ 2 `Foto` ativas (ADR-05).

A view de geração mostra, de forma acionável, qual(is) condição(ões) ainda
falta(m) — não um erro genérico.

**Permissões:**
- Gerar o relatório / editar `descritivo`: staff, superusuário, ou qualquer
  profissional listado em **qualquer uma** das 3 especialidades da inspeção.
- Editar `conclusao` de uma especialidade: staff, superusuário, ou
  profissional **daquela** especialidade especificamente (mesma regra de
  `_pode_editar_especialidade`).

**Versionamento:** `numero_versao` = `(max existente para a inspeção) + 1`.
Gerar nunca sobrescreve uma versão anterior.

**Pós-geração (ADR-06):** reabrir uma especialidade ou editar/excluir um
achado de uma inspeção com `relatorios_finais.exists()` mostra um aviso não
bloqueante, citando a versão/data do último relatório gerado.

## 6. Estrutura do documento (PDF) — sujeita a revisão da equipe

1. **Descritivo da edificação** (`Edificacao.descritivo`) + dados gerais da
   edificação/inspeção.
2. **Dados gerais** — mesmas informações do painel de encerramento/análise
   geral hoje (`_analise_data` + `por_especialidade`): contagens por
   prioridade, breakdown por especialidade.
3. **Achados por especialidade**:
   - Não conformes (`gut_total > 0`): entrada completa (localização,
     verificação, descrição, GUT, prioridade, recomendação) + as 2 fotos
     mais antigas (`data_upload` crescente).
   - Conformes: linha única resumida, sem foto.
4. **Conclusão e direcionamentos** de cada especialidade (`InspecaoEspecialidade.conclusao`).
5. **Blocos de assinatura** — um por profissional listado em cada
   especialidade (todos os nomes de `profissional`, agrupados por
   especialidade).

> Esta seção é o que vai para apreciação da equipe — o conteúdo/dados por
> trás (Seções 4-5 deste documento) não muda com o resultado dessa revisão,
> só a disposição/redação exata do PDF.

## 7. Riscos em aberto

- **Especialidades já finalizadas antes desta feature existir** ficam sem
  `conclusao` preenchida — para gerar o relatório de uma inspeção antiga
  "completa" segundo o critério atual, será preciso reabrir cada
  especialidade, preencher a conclusão, e finalizar de novo. Fricção
  esperada de rollout, não um bug.
- **Custo de armazenamento**: ADR-07 duplica fotos a cada versão gerada —
  se uma inspeção gerar muitas versões (ex. relatório corrigido repetidas
  vezes), o volume de imagens duplicadas cresce. Sem limite/expurgo
  definido nesta sessão.
- **Layout do PDF sujeito a mudança**: a equipe ainda vai revisar o modelo
  antes da aprovação final — o plano de implementação deve isolar o
  template de apresentação (HTML do PDF) da lógica de domínio (Seção 5),
  para uma mudança de layout não exigir retrabalho do back-end.

## 8. Próximo passo

`/writing-plans` para gerar o plano de implementação (migrations, model
`RelatorioFinalInspecao`, views/rotas, template do PDF, testes) — recomendo
aguardar a aprovação da equipe sobre o modelo (Seção 6) antes de implementar
o template de apresentação, mas o modelo de dados e as invariantes (Seções
4-5) já podem seguir para implementação.
