# Edição Offline de Achados Pré-cadastrados (PWA) — Design

**Data:** 2026-06-23
**Projeto:** Inspeções Prediais MPDFT
**Status:** Aprovado para planejamento (decisões fechadas em sessão de grilling)

---

## 1. Objetivo

Permitir que **achados já cadastrados** (pré-preenchidos no escritório) sejam
**editados em campo, offline**, para completar o **diagnóstico** e anexar/excluir
**fotos** obtidas no local. Ao reconectar, as edições sincronizam com o servidor.

Fluxo-alvo: no escritório, com conexão, o técnico pré-cadastra os achados de uma
inspeção (localização, item de verificação etc.). Em campo, sem WiFi, abre cada
achado, preenche o diagnóstico e adiciona as fotos. De volta à conexão, tudo é
enviado.

---

## 2. Estado atual e por que "só funciona para novos achados"

Já existe um andaime de offline-edição no código, porém **incompleto em dois
pontos independentes** — ambos descobertos lendo o código nesta sessão:

**Gap 1 — a página de edição não abre offline.**
- `prepararEspecialidadeParaCampo()` (`static/js/pwa.js:89`) salva os **dados** do
  achado em IndexedDB (`achados_preparados`), mas **não** adiciona
  `/achados/<pk>/editar/` ao cache de páginas do Service Worker.
- O SW é *network-first* para páginas (`static/sw.js:64`) e **ignora `/media/`**
  por completo (`static/sw.js:37`). Logo, offline: a página de edição cai no
  fallback "Sem conexão" e as fotos existentes aparecem quebradas.
- `obterAchadoPreparado()` é usado apenas como **gate** sim/não
  (`templates/inspecoes/achado_form.html:392`); o snapshot salvo **nunca hidrata**
  o formulário.

**Gap 2 — mesmo abrindo, só ~5 campos sincronizam.**
- O submit offline em modo edição coleta apenas `em_conformidade`, G/U/T,
  `prioridade_risco` e fotos novas (`templates/inspecoes/achado_form.html:401`).
- O endpoint `achado_sincronizar_edicao` (`apps/inspecoes/views.py:810`) atualiza
  somente esses campos. **Descrição da não conformidade, requisito afetado, grupo
  técnico, recomendação, direcionamento e prazo não sincronizam** — justamente as
  "informações de diagnóstico" que o fluxo de campo precisa preencher.

São, portanto, **duas frentes**: (a) tornar o formulário de edição *carregável e
renderizável* offline e (b) ampliar o que a edição offline captura.

---

## 3. Glossário

| Termo | Definição |
|---|---|
| **Achado pré-preenchido** | Qualquer `Achado` já existente em uma `InspecaoEspecialidade` **não finalizada**. Não há flag de "rascunho" no modelo — é simplesmente um achado criado antes da ida a campo. |
| **Campos de identidade** | `localizacao`, `sub_localizacao`, `verificacao`. Definidos no pré-cadastro; **não** editáveis offline (travados no formulário de campo). |
| **Campos de diagnóstico** | `em_conformidade`, `descricao_nao_conformidade`, `requisito_afetado`, `grupo_tecnico`, `gravidade`, `urgencia`, `tendencia`, `prioridade_risco`, `recomendacao`, `direcionamento`, `prazo_meses`. **Editáveis offline.** |
| **Preparar para campo** | Tornar uma especialidade utilizável offline: cachear as páginas de edição dos seus achados, baixar as fotos existentes e salvar um *baseline* de cada achado. Passa a ser **automático ao visualizar a aba**. |
| **Baseline / snapshot** | Cópia dos valores do achado no momento da preparação (`achados_preparados`). Usado para diffs de "campos tocados" e como referência de prontidão. |
| **Campos tocados (dirty)** | Campos de diagnóstico cujo valor offline difere do baseline. Apenas esses são enviados na sincronização (merge campo a campo). |
| **Fila de edições pendentes** | `achados_edicao_pendentes` (IndexedDB) — edições offline aguardando envio. |
| **Selo "pronto offline"** | Indicador por aba de especialidade confirmando que seus achados foram cacheados e podem ser editados sem rede. |

---

## 4. Decisões (ADRs)

### ADR-01 — Escopo: diagnóstico completo + fotos; identidade travada
Offline, o técnico edita **todos os campos de diagnóstico** e gerencia fotos
(adicionar/excluir). Os **campos de identidade** ficam travados (read-only no
formulário de campo), pois representam o que foi definido no pré-cadastro.
*Por quê:* é exatamente o trabalho de campo descrito; travar identidade evita
divergência de "qual item é este".

### ADR-02 — Preparação automática, escopo por aba, com selo de prontidão
Não haverá botão manual de "preparar". Ao **abrir/visualizar uma aba de
especialidade** no detalhe da inspeção (online), o app prepara automaticamente os
achados **daquela aba** (páginas + fotos + baseline) e exibe um **selo "pronto
offline ✓ (N)"**.
*Por quê:* "todos os achados de uma inspeção" podem ser 50–100; preparar tudo de
uma vez é pesado. Preparar por aba distribui o custo e cobre o fluxo real (o
técnico trabalha uma especialidade por vez). O selo dá confiança antes de perder
o sinal.
*Trade-off aceito:* se o técnico não abrir uma aba antes de sair, aquela
especialidade não estará disponível offline.

### ADR-03 — Sincronização por campos tocados (merge), não sobrescrita total
A edição offline envia **apenas os campos de diagnóstico alterados** em relação ao
baseline; o servidor preserva os demais.
*Por quê:* decisão revista durante o grilling. "Última escrita vence" sobre o
registro inteiro reverteria silenciosamente alterações feitas no servidor em
campos que o técnico nem tocou. O endpoint atual já aplica updates parciais
(`dados.get(campo, achado.campo)`), então o merge campo a campo encaixa
naturalmente.
*Trade-off aceito:* se **o mesmo campo** for alterado no servidor e offline, a
sincronização que chegar por último vence aquele campo (sem detecção de versão).
Aceitável dado o uso típico de 1 técnico por especialidade.

### ADR-04 — Cachear fotos existentes para visualização offline
Ao preparar, baixar os arquivos das fotos já existentes do achado para o tablet,
para que sejam visíveis offline (necessário para escolher quais excluir).
*Por quê:* sem isso, ADR-05 (excluir fotos) seria "escolher no escuro".
*Custo:* baixo na prática — o pré-cadastro **raramente ou nunca** já tem fotos
(elas são tiradas em campo). O cache de fotos existentes será quase sempre vazio.

### ADR-05 — Exclusão de fotos offline
Offline o técnico pode **adicionar novas** fotos e **marcar fotos existentes para
exclusão**. As remoções entram na fila e são aplicadas na sincronização. Excluir
uma foto adicionada offline (ainda não enviada) apenas a remove da fila local.

### ADR-06 — Falha de sincronização: manter contador + "tentar novamente"
Mantém-se o comportamento atual do banner (`N com erro — tentar novamente`), sem
painel detalhado por achado.
*Por quê:* simplicidade; o volume e a taxa de falha esperados são baixos.
*Revisitar se:* surgirem casos recorrentes de edição "presa" (ex.: especialidade
finalizada antes do sync) que confundam o usuário.

---

## 5. Arquitetura

Todo o código vive no app `apps.inspecoes` e nos assets PWA já existentes
(`static/js/pwa.js`, `static/sw.js`), seguindo os padrões atuais.

### 5.1 Preparação automática por aba (ADR-02)
- No `detail.html`, disparar a preparação quando uma aba de especialidade ficar
  visível: evento `shown.bs.tab` **e** a aba já ativa no carregamento.
- `prepararEspecialidadeParaCampo(espPk)` passa a, para cada achado da aba:
  1. `fetch` + `cache.put` da página `/achados/<pk>/editar/` em `CACHE_PAGINAS`;
  2. `fetch` + cache dos arquivos de foto existentes (via lista vinda de
     `especialidade_achados_para_campo`, que precisa passar a incluir as URLs das
     fotos);
  3. gravar o **baseline** em `achados_preparados`.
- Ao concluir, marcar o **selo "pronto offline ✓ (N)"** na aba.
- O botão manual "Preparar para campo" (nível inspeção e nível especialidade)
  torna-se redundante; avaliar remover ou rebaixar a "recachear agora".

### 5.2 Servir fotos existentes offline (Gap 1 / ADR-04)
- Hoje o SW dá `return` em `/media/` (não intercepta) — `static/sw.js:37`.
- Mudança: interceptar `/media/` com **cache-first que NÃO popula
  automaticamente** — responde apenas o que a preparação colocou no cache; se não
  houver e estiver offline, retorna um placeholder. Assim não se cacheia toda a
  mídia do app, só as fotos preparadas.
- Incrementar a versão dos caches (`CACHE_PAGINAS`/`CACHE_ESTATICO` → v4).

### 5.3 Formulário de edição offline (Gap 2 / ADR-01, ADR-03)
- Ampliar a coleta no bloco "modo editar" de `achado_form.html` para **todos os
  campos de diagnóstico** (hoje só 5).
- Registrar **baseline** (do `achados_preparados`) e, no submit offline, enviar
  apenas os campos cujo valor mudou (`campos tocados`) + listas de fotos a
  adicionar e a excluir.
- Travar os **campos de identidade** (read-only) no contexto de edição de campo.
- `deletarFoto()` passa a ser *offline-aware*: offline, marca a foto para exclusão
  (enfileira) em vez de fazer `DELETE` imediato.

### 5.4 Endpoint de sincronização (ADR-03, ADR-05)
- `achado_sincronizar_edicao` (`views.py:810`) passa a aceitar e aplicar, **apenas
  quando presentes**, todos os campos de diagnóstico (preservando os ausentes —
  semântica que o `dados.get(campo, achado.campo)` já oferece), respeitando a
  cascata de `em_conformidade`.
- Aceitar `fotos_excluir: [pk, ...]` e remover as `Foto` correspondentes do achado
  (idempotente: ignorar pk inexistente).

### 5.5 Limpeza pós-sync
- Após sincronizar com sucesso, **excluir** os itens da fila (`achados_pendentes` /
  `achados_edicao_pendentes`) em vez de apenas marcar `sincronizado=1`, evitando
  crescimento indefinido do IndexedDB.

---

## 6. Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `static/sw.js` | interceptar `/media/` (cache-first sem popular); bump de versão dos caches |
| `static/js/pwa.js` | preparação automática por aba (páginas + fotos + baseline); selo; ampliar payload de edição (campos tocados + `fotos_excluir`); limpeza pós-sync |
| `templates/inspecoes/detail.html` | disparo automático no `shown.bs.tab` + selo por aba; ajustar/remover botões manuais "Preparar para campo" |
| `templates/inspecoes/achado_form.html` | edição offline: coletar todos os campos de diagnóstico, baseline/dirty, travar identidade, `deletarFoto` offline-aware |
| `apps/inspecoes/views.py` | `achado_sincronizar_edicao`: campos de diagnóstico parciais + `fotos_excluir`; `especialidade_achados_para_campo`: incluir URLs das fotos existentes |
| testes | cobertura de sync parcial e exclusão de foto via sync |

---

## 7. Testes

- **pytest-django** (servidor):
  - `achado_sincronizar_edicao` aplica apenas os campos enviados e preserva os demais;
  - cascata de `em_conformidade` no sync;
  - `fotos_excluir` remove as fotos certas e é idempotente;
  - rejeição quando a especialidade está finalizada (comportamento atual mantido).
- **Verificação no navegador** (Playwright, como na T051), simulando offline:
  abrir aba → confirmar selo "pronto offline" → `navigator.onLine=false` → editar
  diagnóstico + adicionar/excluir foto → voltar online → sincronizar → conferir no
  servidor que só os campos tocados mudaram e as fotos refletem add/del.

---

## 8. Fora de escopo (YAGNI)

- Edição offline dos **campos de identidade** (localização/verificação).
- Detecção de conflito por versão / resolução de merge no mesmo campo (ADR-03
  aceita "último sync vence" no nível do campo).
- Painel detalhado de falhas de sincronização (ADR-06 mantém contador + retry).
- Preparação automática de **toda a inspeção** de uma vez (ADR-02 é por aba).
- Criação de achados offline já existe e não é alterada aqui.

---

## 9. Próximo passo

Gerar o plano de implementação fásico (`/writing-plans`) em
`docs/superpowers/plans/2026-06-23-edicao-offline-achados.md`, derivado destas
decisões.
