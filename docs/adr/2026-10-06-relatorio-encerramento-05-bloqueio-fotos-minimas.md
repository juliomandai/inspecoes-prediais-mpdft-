# ADR-05: Geração do relatório é bloqueada se algum achado não conforme tiver menos de 2 fotos

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
O relatório exige, por achado não conforme, no mínimo 2 fotos (ver glossário
— "Entrada completa"). Hoje nada no sistema impede registrar/finalizar um
achado não conforme com 0 ou 1 foto.

## Decisão
A invariante de geração do relatório (em conjunto com ADR-04 — as 3
especialidades finalizadas) passa a checar também: todo achado com
`gut_total > 0` tem ≥ 2 fotos ativas (`Foto` não excluída logicamente — ver
soft delete). Se algum achado não conforme não tiver, a geração é bloqueada
e a tela lista os achados com fotos insuficientes, para completar antes de
tentar de novo.

## Consequências
- Uma inspeção pode ficar "presa" entre "3 especialidades finalizadas" e
  "relatório gerável", até as fotos faltantes serem completadas.
- Isso só é destravável se for possível reabrir/editar um achado (ou pelo
  menos anexar foto) mesmo com a especialidade já finalizada — pergunta em
  aberto, a ser resolvida na invariante seguinte sobre edição pós-finalização.
