# ADR-05: Histórico completo de edições (não apenas estado atual)

## Status
Aceita (2026-08-18, sessão de grilling)

## Contexto
O HTML original já registra `editadoPor`/`editadoEm` por edição, mas
sobrescreve o valor anterior (sem trilha completa). Dado que este módulo
lida com conformidade normativa e prestação de contas de um órgão público,
o usuário confirmou que é necessário histórico completo, não só o último
valor.

## Decisão
Cada edição de item gera um registro de histórico imutável (quem, quando,
o que mudou — de/para), além de atualizar o estado atual do item. O
"agregado" item de checklist inclui, portanto, o estado atual + sua lista
de edições históricas.

## Consequências
- Precisa de uma tabela de histórico (ex. `ItemAcessibilidadeHistorico` ou
  `django-simple-history`), com uma linha por edição.
- Nenhuma edição pode sobrescrever sem deixar rastro — isso é um invariante
  do agregado, não um detalhe de implementação opcional.
- Custo de armazenamento é irrelevante no volume atual (5.137 itens), mas
  cresce linearmente com o número de edições ao longo dos anos.
