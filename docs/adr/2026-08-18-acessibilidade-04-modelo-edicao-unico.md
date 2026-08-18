# ADR-04: Modelo de edição único (sem separação diagnóstico/plano de ação)

## Status
Aceita (2026-08-18, sessão de grilling)

## Contexto
O HTML original mantém duas estruturas de edição separadas por item:
`OVERRIDES` (corrige o diagnóstico original — status/resolução/obs) e
`ACTION_META` (acompanha o plano de ação de remediação — responsável, prazo,
ordem de serviço). O usuário confirmou que essa separação foi um acidente
de implementação, não uma necessidade de domínio (não há dois times
distintos mexendo em cada camada).

## Decisão
O item de checklist no novo módulo tem um único conjunto de campos
editáveis (status, resolução, observação, status da ação, responsável,
prazo, ordem de serviço, notas) — uma única operação de "editar item",
não duas estruturas sobrepostas.

## Consequências
- Modelo de dados mais simples: um agregado por item, não dois.
- Se no futuro emergir a necessidade real de segregar quem pode corrigir
  diagnóstico vs. quem pode gerenciar plano de ação, isso vira uma questão
  de permissão por campo, não de estrutura de dados separada.
