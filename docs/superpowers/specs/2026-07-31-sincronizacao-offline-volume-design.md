# Sincronização Offline em Alto Volume (Achados + Fotos) — Design

**Data:** 2026-07-31
**Projeto:** Inspeções Prediais MPDFT
**Status:** Aprovado para planejamento (decisões fechadas em sessão de grilling)

---

## 1. Objetivo

Tornar a sincronização offline robusta em cenários de **alto volume**: muitas
dezenas de achados, cada um com várias fotos, registrados numa única sessão de
campo em área de sinal fraco/ausente (ex.: subsolo de uma promotoria).

Gatilho: um colega relatou "diversos erros ao sincronizar" após uma inspeção de
subsolo com grande volume de registros. O relato foi **verbal e genérico** — sem
texto exato do erro capturado (print/log) — então o desenho abaixo assume
**múltiplas causas plausíveis compostas**, não uma causa única confirmada
(diferente do incidente anterior de HTTP 400, que tinha causa raiz identificada
com precisão — ver `technical_lessons.md`).

Escala de referência: **~30-60 achados por sessão, 3-5 fotos por achado**, sem
nenhuma compressão client-side hoje (apenas um teto de 10MB por arquivo
individual). Isso pode significar 1-2 GB de payload numa única sessão offline.

---

## 2. Causas plausíveis identificadas (lendo o código atual)

Lendo `pwa.js`, `achado_form.html` e `views.py` nesta sessão, três problemas
independentes coexistem e se compõem em cenários de alto volume:

1. **Acoplamento achado+fotos numa única requisição.** Hoje
   `salvarAchadoOffline`/`salvarEdicaoOffline` empacotam o texto do achado E
   todas as suas fotos (base64) num único POST/PATCH. Se essa requisição falhar
   por qualquer motivo — tamanho, timeout, queda de sinal no meio — o achado
   **inteiro** fica pendente, inclusive campos de texto que pesam bytes e
   sincronizariam sem problema algum sozinhos.

2. **Nenhuma compressão de imagem.** `fotoParaB64()` só rejeita arquivos
   individuais acima de 10MB; não há redimensionamento nem recompressão. Fotos
   de câmera de celular (3-8MB cada) + inflação base64 (+33%) já quase
   estouraram o limite de request do Django uma vez (commit `7882c87`, limite
   subido de 10MB→40MB). Em um achado com 4-5 fotos, o problema pode recorrer.

3. **Risco de estouro de cota de armazenamento local.** Fotos base64 ficam
   armazenadas no IndexedDB **sem compressão** enquanto aguardam sincronizar.
   Strings em IndexedDB costumam ser armazenadas como UTF-16 internamente
   (2 bytes/caractere mesmo para conteúdo ASCII como base64), então o custo
   efetivo de armazenamento é ~2.7x o tamanho do arquivo original (1.33x
   inflação base64 × ~2x armazenamento UTF-16). Para 45 achados × 4 fotos ×
   6MB, isso é **~2.9 GB** só de fotos pendentes no navegador — plausível de
   estourar a cota de armazenamento em tablets mais antigos/com pouco espaço
   livre, antes mesmo de tentar sincronizar.

4. **Loop de sincronização totalmente serial, sem retry automático.** Cada
   achado pendente é um `fetch` sequencial; uma falha de rede marca "erro"
   imediatamente, sem tentar de novo automaticamente. Em sinal instável, uma
   queda momentânea gera uma "avalanche" de itens marcados como erro que na
   prática só precisavam de uma nova tentativa.

---

## 3. Glossário (termos novos desta sessão)

Ver também o glossário de `2026-06-23-edicao-offline-achados-design.md`
(achado pré-preenchido, campos de identidade/diagnóstico, baseline, fila de
edições pendentes, selo "pronto offline") — não redefinido aqui.

| Termo | Definição |
|---|---|
| **Fila de fotos pendentes** (`fotos_pendentes`) | Novo object store no IndexedDB. Cada item é uma foto já comprimida aguardando upload, referenciando o achado ao qual pertence. |
| **`achado_id_local`** | O `id` autoincrementado local (IndexedDB) de um achado criado offline, usado para vincular fotos a ele **antes** de o achado ter um `pk` de servidor. |
| **`pk_servidor`** | Campo adicionado a um item de `fotos_pendentes` assim que o achado pai sincroniza; a partir daí a foto pode ser enviada. |
| **Compressão na captura** | Redimensionar (canvas, máx. 1600px no maior lado) e recomprimir (JPEG, qualidade 0.7) uma foto **no momento em que é selecionada/tirada**, antes de qualquer gravação no IndexedDB. |
| **Erro de rede** (retryable) | Falha de `fetch` sem resposta do servidor (timeout, conexão recusada/caída). Elegível a retry automático com backoff. |
| **Erro permanente** (non-retryable) | Resposta HTTP do servidor com status de erro (4xx/5xx). Não se tenta de novo automaticamente; fica pendente com o detalhe exato para o usuário decidir. |
| **Achado com fotos pendentes** | Estado válido e esperado: achado já existe no servidor (texto sincronizado, tem `pk`), mas uma ou mais fotos ainda estão na fila local tentando subir. |

---

## 4. Decisões (ADRs)

### ADR-01 — Desacoplar sincronização de dados do achado e de fotos
O texto do achado (campos de identidade + diagnóstico) sincroniza numa
requisição pequena e própria; fotos sincronizam depois, uma requisição por
foto, numa fila independente.
*Por quê:* elimina o acoplamento de risco entre a parte mais leve/crítica
(texto) e a parte mais pesada/instável (fotos). Uma foto grande ou uma queda de
rede não deve nunca impedir que o registro textual do achado chegue ao
servidor.
*Trade-off aceito:* mais requisições HTTP no total (1 + N por achado, em vez de
1); exige uma fila de fotos separada da fila de achados no IndexedDB.

### ADR-02 — Comprimir fotos no momento da captura
Antes de gravar qualquer foto no IndexedDB (criação ou edição offline),
redimensionar via `canvas` para no máximo 1600px no maior lado e recomprimir
como JPEG qualidade 0.7 (~200-500KB por foto, ante 3-8MB originais).
*Por quê:* resolve **ao mesmo tempo** o risco de estouro de cota de
armazenamento local (fotos ficam ~10-20x menores no IndexedDB) e o payload de
rede na sincronização. 1600px/q0.7 é suficiente para exibição em tela e
inserção em relatórios PDF (fotos tipicamente exibidas em ~10×7cm na página).
*Trade-off aceito:* alguns ms/segundos de processamento por foto no momento da
captura, perceptível ao tirar várias fotos em sequência rápida. Perda de
nitidez em zoom digital extremo (aceitável para o uso em relatório).
*Nota de implementação:* o teto atual de 10MB por arquivo (`achado_form.html`)
passa a ser um filtro **pré-compressão** (rejeitar apenas originais
patologicamente grandes), não mais o controle principal de tamanho.

### ADR-03 — Vínculo foto→achado via ID local, promovido após sync do achado
Cada item da fila de fotos guarda o `achado_id_local`, não um `pk` de
servidor. O loop de sincronização só tenta enviar fotos cujo achado pai já
sincronizou (e por tanto já tem `pk` real); as demais aguardam a próxima
rodada.
*Por quê:* um achado criado offline não tem `pk` de servidor até sincronizar;
a foto precisa saber a qual achado pertence sem depender de um identificador
que ainda não existe.
*Invariante:* uma foto nunca é enviada antes de o achado pai existir no
servidor. Se o achado falhar ao sincronizar, suas fotos ficam aguardando (não
tentam, não se perdem, não se associam ao achado errado).

### ADR-04 — Retry automático com backoff, só para erros de rede
Falha de rede (sem resposta do servidor): tenta novamente automaticamente até
3 vezes, com espera crescente (2s, 5s) antes de desistir e marcar como
pendente. Erro permanente do servidor (4xx): não insiste, marca pendente
imediatamente com o detalhe exato retornado.
*Por quê:* evita que uma instabilidade momentânea de sinal (esperada em
subsolo) gere uma fila inteira de "erros" que na prática desapareceriam
sozinhos numa nova tentativa.
*Trade-off aceito:* uma sessão de sincronização com muitas falhas de rede reais
pode demorar mais (esperas entre tentativas).

**Trade-off adicional aceito (identificado na revisão final da implementação,
2026-07-31): duplicata em caso de "ack perdido".** `fetchComRetry` re-tenta
sempre que `fetch()` lança exceção — inclusive no caso em que o servidor
processou a requisição com sucesso (criou o `Achado` ou a `Foto`) mas a
resposta nunca chegou ao cliente (conexão caiu depois do envio, exatamente a
condição de sinal fraco que esta funcionalidade existe para tolerar). Não há
chave de idempotência nem deduplicação em nenhum dos três endpoints de
sincronização (`achado_sincronizar`, `achado_sincronizar_edicao`,
`achado_sincronizar_foto`), então um "ack perdido" pode gerar um `Achado` ou
uma `Foto` duplicados, não apenas uma foto duplicada. O guard de reentrância
(`syncEmAndamento`) não cobre esse caso — ele só impede que duas chamadas
concorrentes de `pwaSync` disputem a mesma leitura da fila; não afeta o retry
interno de uma única chamada.
*Por quê aceito, e não corrigido nesta rodada:* implementar deduplicação
exigiria uma chave de idempotência gerada no cliente e um mecanismo de
dedup no servidor — mudança de escopo maior que as 8 tasks originais desta
sessão de grilling, sem ter sido levantada na interrogação original.
*Mitigação prática:* duplicatas são visíveis e corrigíveis manualmente (um
achado ou foto repetidos aparecem no relatório e podem ser excluídos), ao
contrário de perda silenciosa de dado, que é o risco que este ADR já mitiga.
*Revisitar se:* duplicatas se mostrarem frequentes no uso real de campo — a
correção seria um id gerado no cliente por item de fila (achado ou foto),
enviado no payload, com o servidor rejeitando/ignorando um id já processado
dentro de uma janela curta.

### ADR-05 — Banner separa progresso de achados e de fotos
O banner de status deixa de reportar um número agregado único
("N sincronizado(s), M com erro"). Passa a mostrar achados e fotos
separadamente, ex.: *"45/45 achados sincronizados. Fotos: 172/180 enviadas, 8
pendentes (tentando novamente em rede instável)."*
*Por quê:* comunica que o dado textual do achado já está seguro no servidor
mesmo quando fotos ainda estão subindo/tentando — reduz a ansiedade de "perdi o
achado" quando, na real, é só uma foto demorando.

### ADR-06 — Compatibilidade retroativa com o formato antigo de fila
O novo código de sincronização continua aceitando o formato antigo de item de
fila (achado + fotos acopladas no mesmo objeto, sem compressão), além do
formato novo.
*Por quê:* pode haver, no momento do deploy, achados presos na fila offline de
algum tablet em campo (de sessões anteriores que falharam) no formato antigo.
O fallback garante que nenhum desses itens se perca.
*Trade-off aceito:* mais um caminho de código a manter — **temporário**;
remover após confirmar que todos os tablets em uso sincronizaram e reabriram o
app pelo menos uma vez com o novo código.

### ADR-07 — Upload de fotos serial, não paralelo
Fotos da fila sobem uma de cada vez (aguarda completar antes de iniciar a
próxima), não em lote paralelo.
*Por quê:* em sinal fraco/instável (cenário do subsolo), requisições paralelas
tendem a disputar a mesma banda escassa e falhar juntas por timeout, em vez de
uma completar com sucesso por vez. Serial é mais lento no total, mas cada
tentativa individual tem mais chance de sucesso.

### ADR-08 — Escopo: aplica a criação E edição offline
O desacoplamento e a fila de fotos valem tanto para achados novos
(`achado_sincronizar`) quanto para edição offline de achados existentes
(`achado_sincronizar_edicao`).
*Por quê:* a edição offline hoje tem o mesmo padrão problemático (fotos novas
em base64 acopladas ao PATCH). Como o achado editado já tem `pk` de servidor
(existe desde o pré-cadastro), o desacoplamento aqui é mais simples: não
precisa do mapeamento `achado_id_local`→`pk`. `fotos_excluir` (só uma lista de
pks, sem bytes) continua no payload leve de texto, sem mudança.

### ADR-09 — Aviso proativo de armazenamento quase cheio
Verificar `navigator.storage.estimate()` periodicamente (ao abrir o app, ou a
cada N achados salvos offline) e mostrar um aviso no banner se o uso estiver
acima de ~80% da cota, orientando a sincronizar assim que houver sinal.
*Por quê:* mesmo com a compressão (ADR-02) reduzindo o risco em ~10-20x, ele
não desaparece por completo em tablets antigos com pouco espaço livre — um
aviso barato evita falha silenciosa por cota esgotada.
*Revisitar se:* o aviso se mostrar ruidoso demais na prática (falsos
positivos) ou se o problema de armazenamento não recorrer após o fix
principal (então pode ser YAGNI).

### ADR-10 — Finalização de especialidade não bloqueia por fotos pendentes
Uma especialidade pode ser finalizada mesmo com fotos de seus achados ainda
pendentes na fila local. O endpoint de upload de fotos continua aceitando
envios mesmo após a especialidade finalizada (só a edição de **texto** é
bloqueada por `pode_editar`, como já é hoje).
*Por quê:* simplicidade — não introduz um novo bloqueio no fluxo de
finalização existente, e evita cenários de "não consigo finalizar porque uma
foto não sobe".
*Trade-off aceito:* um relatório gerado antes de as últimas fotos chegarem
pode sair sem elas; será necessário gerar novamente depois que todas as fotos
tiverem sincronizado.

---

## 5. Arquitetura

### 5.1 IndexedDB — novo object store `fotos_pendentes`
```
fotos_pendentes: {
  id: <autoincrement>,
  achado_id_local: <id do achados_pendentes, se ainda não sincronizado>,
  pk_servidor: <pk do Achado no servidor, preenchido após sync do achado>,
  achado_pk_existente: <pk, se for edição de achado já existente — não precisa
                         de promoção>,
  blob: <Blob JPEG já comprimido>,
  nome: <string>,
  tipo: 'image/jpeg',
  criado_em: <ISO string>,
}
```
Bump da versão do banco (`inspecoes-offline`, v2 → v3) para adicionar o novo
store, mantendo os stores existentes intactos (compatibilidade com ADR-06).

### 5.2 Compressão na captura (ADR-02)
Nova função `comprimirFoto(file)` em `pwa.js` ou `achado_form.html`:
`canvas.drawImage` com redimensionamento proporcional (máx. 1600px no maior
lado) + `canvas.toBlob('image/jpeg', 0.7)`. Substitui `fotoParaB64` como
primeiro passo antes de gravar no IndexedDB — a foto já é salva comprimida,
nunca em base64 bruto do arquivo original.

### 5.3 Fluxo de criação (ADR-01, ADR-03)
1. `salvarAchadoOffline(dados)` grava **só o texto** em `achados_pendentes`,
   sem campo `fotos`.
2. Cada foto comprimida vai para `fotos_pendentes` com `achado_id_local`
   apontando para o `id` retornado no passo 1.
3. Na sincronização: primeiro sincroniza todos os itens de `achados_pendentes`
   (texto). Ao ter sucesso, grava o `pk_servidor` retornado nos itens de
   `fotos_pendentes` correspondentes (via `achado_id_local`) e remove o item de
   `achados_pendentes`.
4. Depois, itera `fotos_pendentes` que já têm `pk_servidor` (ou
   `achado_pk_existente`, no caso de edição) e envia cada uma para
   `POST /api/achados/<pk>/fotos/` (novo endpoint), serialmente (ADR-07), com
   retry+backoff para erros de rede (ADR-04).

### 5.4 Fluxo de edição (ADR-08)
`salvarEdicaoOffline(dados)` grava só os campos de diagnóstico tocados +
`fotos_excluir` (pks) em `achados_edicao_pendentes`, sem fotos novas
embutidas. Fotos novas vão direto para `fotos_pendentes` com
`achado_pk_existente` já preenchido (o achado editado já existe no servidor) —
não precisam esperar nenhuma sincronização prévia.

### 5.5 Novo endpoint: upload de foto individual
`POST /api/achados/<pk>/fotos/` — aceita uma foto por requisição (multipart ou
base64 pequeno, já comprimida a ~200-500KB). Não verifica `pode_editar` da
especialidade (ADR-10) — só verifica que o achado existe.

### 5.6 Compatibilidade retroativa (ADR-06)
No loop de sincronização de `achados_pendentes`/`achados_edicao_pendentes`: se
o item tiver o campo `dados.fotos` preenchido (formato antigo), envia como
hoje (achado + fotos acopladas, base64, no mesmo POST/PATCH) — caminho de
código temporário, mantido até confirmar migração completa dos tablets em
campo.

### 5.7 Retry com backoff (ADR-04)
Função utilitária `fetchComRetry(url, opts, tentativas=3, esperas=[2000,
5000])`: tenta `fetch`; se lançar erro (rede) e ainda houver tentativas,
aguarda o próximo intervalo e tenta de novo; se a resposta chegar mas não for
`ok` (status HTTP), não repete — trata como erro permanente imediatamente.

### 5.8 Banner de progresso (ADR-05)
`atualizarBannerOffline()` e `pwaSync()` passam a contar achados e fotos
pendentes separadamente (`contarPendentes()` já soma criação+edição; adicionar
`contarFotosPendentes()`) e montar a mensagem com as duas contagens.

### 5.9 Alerta de armazenamento (ADR-09)
Nova função `verificarArmazenamento()`, chamada no `DOMContentLoaded` e após
salvar cada achado offline: `navigator.storage.estimate()`, se
`usage/quota > 0.8`, mostra aviso no banner (não bloqueia nada).

---

## 6. Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `static/js/pwa.js` | novo object store `fotos_pendentes` (bump IndexedDB v2→v3); `comprimirFoto()`; fila de fotos com promoção de `achado_id_local`→`pk_servidor`; `fetchComRetry()`; `pwaSync()` reescrito para 2 fases (achados depois fotos) + fallback formato antigo; banner separado (achados/fotos); `verificarArmazenamento()` |
| `templates/inspecoes/achado_form.html` | usar `comprimirFoto()` em vez de `fotoParaB64()`/inclusão direta em `dados.fotos`; salvar fotos novas em `fotos_pendentes` (criação: com `achado_id_local`; edição: com `achado_pk_existente`) |
| `apps/inspecoes/views.py` | novo endpoint `achado_foto_upload` (`POST /api/achados/<pk>/fotos/`), sem checar `pode_editar`; `achado_sincronizar`/`achado_sincronizar_edicao` deixam de esperar `fotos` no payload principal (mas mantêm suporte a receber, para o fallback do formato antigo) |
| `mpdft_inspecoes/urls.py` | rota do novo endpoint de upload de foto |
| `static/sw.js` | nenhuma mudança esperada (fora de escopo — cache de páginas/fotos existentes não é afetado) |
| testes | cobertura: sync de achado sem fotos; upload de foto individual; foto associada ao achado certo após promoção de pk; retry de rede vs erro permanente; fallback do formato antigo; upload de foto aceito após especialidade finalizada |

---

## 7. Testes

- **pytest-django** (servidor):
  - `achado_sincronizar` cria o achado corretamente sem exigir `fotos` no
    payload;
  - novo endpoint de upload de foto associa a foto ao achado certo, aceita
    mesmo com especialidade finalizada, rejeita achado inexistente;
  - `achado_sincronizar_edicao` continua funcionando com `fotos_excluir` e sem
    fotos novas no payload principal;
  - fallback do formato antigo (`achado_sincronizar` com `dados.fotos`
    preenchido) continua funcionando como hoje.
- **JS/manual (Playwright ou navegador)**, simulando offline com muitos
  achados e fotos:
  - criar 5+ achados offline com 3+ fotos cada, confirmar que os textos
    sincronizam mesmo simulando falha de rede nas fotos;
  - confirmar que fotos comprimidas ficam na faixa de 200-500KB;
  - confirmar que o banner mostra contagens separadas de achados e fotos;
  - confirmar que uma foto de um achado que falhou ao sincronizar não é
    enviada (fica aguardando o achado sincronizar primeiro);
  - simular erro de rede (offline no meio do fetch) vs erro HTTP 400, e
    confirmar que só o primeiro tenta de novo automaticamente.

---

## 8. Fora de escopo (YAGNI)

- Upload paralelo de fotos (ADR-07 mantém serial).
- Bloqueio de finalização de especialidade por fotos pendentes (ADR-10).
- Painel detalhado por achado/foto individual no banner (ADR-05 é só uma
  contagem separada, não uma lista item a item).
- Remoção do fallback de formato antigo (ADR-06) — fica até confirmar migração
  completa dos tablets, não nesta entrega.
- Compressão configurável (qualidade/resolução fixas no código, não expostas
  como configuração de usuário).
- Reprocessar/gerar novamente relatórios automaticamente quando fotos
  pendentes chegarem após a finalização (ADR-10 aceita que seja manual).

---

## 9. Riscos em aberto

- **Causa raiz não confirmada por evidência direta.** O relato original foi
  verbal, sem texto exato do erro. Se o problema persistir após este fix, será
  necessário capturar o erro exato na próxima ocorrência (idealmente via a
  página `/diagnostico-offline/` já existente) para descartar causas.
- **Aviso de armazenamento (ADR-09) pode gerar ruído** se o limiar de 80% se
  mostrar cedo demais na prática — ajustar o limiar se necessário após uso
  real.
- **Duplicata de achado/foto em caso de "ack perdido" no retry** — ver
  trade-off aceito registrado no ADR-04. Não corrigido nesta rodada; revisitar
  se duplicatas aparecerem com frequência em campo.
- **Falha ao comprimir/enfileirar uma foto offline ainda é silenciosa para o
  usuário** (só loga `console.warn`, adicionado na revisão final da
  implementação) — o achado salva e a página redireciona normalmente mesmo
  que uma foto específica tenha falhado ao processar localmente. Se isso se
  mostrar um problema real em campo (fotos "sumindo" sem explicação), a
  correção seria surfacear um aviso agregado no banner (ex.: "N fotos não
  puderam ser processadas"), não apenas o log de console.

---

## 10. Status

Implementação completa (2026-07-31): as 8 tasks do plano em
`docs/superpowers/plans/2026-07-31-sincronizacao-offline-volume.md` foram
implementadas, revisadas (conformidade + qualidade, com correções aplicadas
onde apontado) e validadas em teste manual fim-a-fim (13 achados + 41 fotos
offline, incluindo simulação de rede instável, sem perda ou duplicação de
dados). Uma revisão final de todo o conjunto de mudanças encontrou e corrigiu
três problemas de integração (página `/diagnostico-offline/` quebrada pelo
bump de versão do IndexedDB, `sw.js` sem o mesmo guard contra sessão expirada
que o `pwaSync` principal já tinha, e falha silenciosa de foto sem log) — ver
commit `c91d7ca`. Pronto para validação em campo real.
