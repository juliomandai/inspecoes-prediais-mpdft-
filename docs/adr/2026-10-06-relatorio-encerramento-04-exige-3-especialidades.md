# ADR-04: Geração do relatório exige as 3 especialidades (civil, elétrica, mecânica) finalizadas

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
`Inspecao.status_geral` (`apps/inspecoes/models.py`) hoje considera
"finalizada" quando todas as especialidades *existentes* estão finalizadas —
mesmo que falte alguma das 3 disciplinas (ex.: só civil foi cadastrada e
finalizada). Isso é adequado para o badge geral de status da inspeção, mas
não representa "inspeção completa" no sentido exigido pela ART, que cobre
as 3 disciplinas (civil, elétrica, mecânica).

## Decisão
A liberação do botão/rota de geração do Relatório Final de Inspeção usa uma
invariante própria e mais estrita, independente de `status_geral`: as 3
especialidades (civil, elétrica, mecânica) precisam **existir** e estar com
`status == 'finalizada'`. `status_geral` não muda de comportamento — ganha
uma segunda checagem específica (ex. `Inspecao.pode_gerar_relatorio_final`)
usada só por este fluxo.

## Consequências
- Uma inspeção que só registrou civil + elétrica (sem mecânica) nunca libera
  o relatório, mesmo que as duas existentes estejam finalizadas e
  `status_geral` diga "finalizada".
- Duas noções de "completo" coexistem no mesmo model: `status_geral`
  (UI geral/badge) e a checagem específica do relatório (ART) — documentado
  aqui para não serem confundidas/unificadas por engano no futuro.
