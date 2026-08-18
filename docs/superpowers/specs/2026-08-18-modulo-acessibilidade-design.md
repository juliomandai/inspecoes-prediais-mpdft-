# Design: Módulo de Acessibilidade na plataforma de inspeções

**Status:** Design aprovado via sessão de grilling (`/grill-with-docs`, 2026-08-18). Não implementado — próximo passo é `/writing-plans`.

## 1. Contexto

O SPO/MPDFT mantém hoje um painel de diagnóstico de acessibilidade como um
HTML autônomo — na prática um **Artifact do Claude.ai**, que usa
`window.storage` (persistência client-side ligada àquele artifact
específico) para guardar edições. Não há banco real, não há multiusuário
consistente, e a edição só sobrevive enquanto o artifact existir.

O arquivo-fonte (`painel-acessibilidade-mpdft.html`) contém:
- **5.137 avaliações** cruzando 13 edificações × regiões (subsolo, térreo,
  pavimentos...) × locais específicos × 217 critérios normativos (NBR
  9050/15, NBR 16537/16, Lei nº 13.146/2015, Decreto Distrital nº
  39.272/2018).
- Para cada avaliação: status (OK/Pendente/Não se aplica), resolução
  diagnosticada, observação, e uma camada de acompanhamento de plano de
  ação (status da ação, responsável, prazo, ordem de serviço, notas).
- Base legal (`details.legal`) só preenchida para uma das 13 edificações
  (PJPL) nesta versão — as demais não têm o detalhamento ainda.

Pergunta original: é viável transformar isso num módulo real dentro da
plataforma Django de inspeções, com banco de dados persistente e edição
multiusuário?

**Resposta: sim.** O domínio é bem definido, o volume de dados é trivial
para SQLite, e a plataforma já tem toda a infraestrutura necessária
(autenticação, `Edificacao`, deploy, backup). As decisões abaixo definem
como.

## 2. Glossário

Ver [`docs/grilling/acessibilidade-glossary.md`](../../grilling/acessibilidade-glossary.md)
para os termos completos com a pergunta que resolveu cada um.

Resumo:
- **Edificação** — reaproveita o model `Edificacao` já existente.
- **Local** — ponto físico específico dentro de uma edificação (entidade catálogo própria).
- **Região** — subdivisão (subsolo, térreo...) — campo de escolha fixa, não entidade.
- **Critério** — item normativo avaliável (entidade catálogo própria, com base legal opcional).
- **Avaliação** — a associação local+critério com status, resolução, plano de ação e histórico. É o agregado raiz do domínio.

## 3. Decisões de arquitetura (ADRs)

| ADR | Decisão |
|---|---|
| [ADR-01](../../adr/2026-08-18-acessibilidade-01-shared-edificacao.md) | Reaproveitar `Edificacao` existente (shared kernel) — adicionar campo de sigla, cadastrar as 11 edificações que faltam |
| [ADR-02](../../adr/2026-08-18-acessibilidade-02-bounded-context-separado.md) | Bounded context separado de `Achado`/`inspecoes` — não é uma especialidade |
| [ADR-03](../../adr/2026-08-18-acessibilidade-03-sem-offline.md) | Uso online-only — sem PWA/IndexedDB/sync |
| [ADR-04](../../adr/2026-08-18-acessibilidade-04-modelo-edicao-unico.md) | Modelo de edição único (sem separar diagnóstico de plano de ação) |
| [ADR-05](../../adr/2026-08-18-acessibilidade-05-historico-completo.md) | Histórico completo e imutável de cada edição |
| [ADR-06](../../adr/2026-08-18-acessibilidade-06-mesmo-banco-app-novo.md) | Mesmo banco SQLite, novo app Django |

## 4. Modelo de dados proposto

Novo app Django, ex. `apps/acessibilidade/models.py`:

```python
class LocalAcessibilidade(models.Model):
    edificacao = models.ForeignKey('edificacoes.Edificacao', on_delete=models.PROTECT, related_name='locais_acessibilidade')
    regiao = models.CharField(max_length=40, choices=Regiao.choices)
    nome = models.CharField(max_length=200)  # ex. "Rampa 01", "Sanitário Acessível Feminino"

    class Meta:
        unique_together = [('edificacao', 'regiao', 'nome')]


class CriterioAcessibilidade(models.Model):
    nome = models.CharField(max_length=300, unique=True)  # ex. "Altura da bacia"
    base_legal = models.TextField(blank=True)  # referência normativa, opcional — só preenchida para parte do catálogo hoje


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

    status = models.CharField(max_length=20, choices=Status.choices)
    resolucao_diagnostico = models.CharField(max_length=40, blank=True)  # Contratação / Manutenção Predial / Outro
    observacao = models.TextField(blank=True)

    status_acao = models.CharField(max_length=20, choices=StatusAcao.choices, default=StatusAcao.NAO_INICIADA)
    responsavel = models.CharField(max_length=200, blank=True)
    prazo = models.DateField(null=True, blank=True)
    resolucao_prevista = models.CharField(max_length=40, blank=True)
    ordem_servico = models.CharField(max_length=100, blank=True)
    data_os = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)

    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('local', 'criterio')]


class AvaliacaoHistorico(models.Model):
    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name='historico')
    snapshot_anterior = models.JSONField()   # estado completo antes da edição
    snapshot_novo = models.JSONField()       # estado completo depois da edição
    editado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    editado_em = models.DateTimeField(auto_now_add=True)
```

Notas de implementação (a detalhar no plano, não decisões de domínio):
- `AvaliacaoHistorico` guarda snapshot completo antes/depois em vez de
  diffs campo a campo — mais simples de implementar e suficiente para
  auditoria, sem exigir uma tabela de "campos alterados".
- `Edificacao` precisa de um campo `sigla` (novo, unique) para bater com
  os 13 códigos do painel (BSBI, BSBII, PJBZ...) — migração de dados
  cadastra os que faltam.

## 5. Escopo funcional (herdado do HTML original)

- Dashboard por edificação (% conformidade, distribuição de status).
- Listagem filtrável (edificação, região, local, status, resolução, busca textual).
- Edição individual de avaliação (todos os campos do modelo único).
- Edição em lote (aplicar a mesma mudança a várias avaliações selecionadas, cada uma gerando seu próprio registro de histórico).
- Exportação CSV (mesmas colunas do HTML original).
- Painel de alertas de prazo vencido — **calculado sob demanda** (query de avaliações com `prazo < hoje` e `status_acao != CONCLUIDA`), sem tabela de notificação persistente.
- Autenticação via login já existente da plataforma; `atualizado_por`/`editado_por` = usuário autenticado, sem campo de nome livre.

## 6. Migração dos dados existentes

Trabalho único, não recorrente: importar as 5.137 linhas do
`data-holder` JSON do HTML para o schema novo. Pontos de atenção:
- Deduplicar/normalizar a lista de `locals` (variações de grafia/acentuação
  do mesmo local físico) antes de criar `LocalAcessibilidade` — decisão
  manual, não pode ser automática com segurança.
- Mapear os 13 códigos-sigla para `Edificacao` (2 já existem, 11 precisam
  ser cadastradas).
- `details.legal` só existe para PJPL — as demais edificações ficam com
  `base_legal` vazio no `CriterioAcessibilidade` até serem preenchidas
  manualmente ou em levantamentos futuros.

## 7. Riscos em aberto

- **Contenção de escrita no SQLite** (ADR-06): aceito como risco baixo
  dado o padrão de uso (poucos usuários, edição manual). Revisitar se o
  padrão de uso mudar para volume alto de escrita simultânea.
- **Qualidade dos dados de origem**: nomes de locais inconsistentes no
  HTML original exigem limpeza manual na migração — pode haver perda ou
  fusão incorreta de locais que na verdade eram diferentes.
- **Cobertura parcial de base legal**: só uma das 13 edificações tem
  `details.legal` preenchido hoje; o módulo precisa funcionar bem mesmo
  com esse campo vazio na maioria dos critérios.

## 8. Próximo passo

`/writing-plans` para gerar o plano de implementação (tasks com TDD,
migrations, views, templates, comando de importação dos dados
existentes).
