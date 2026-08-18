# ADR-02: Acessibilidade é um bounded context separado de `Achado`

## Status
Aceita (2026-08-18, sessão de grilling)

## Contexto
`inspecoes` já tem o conceito de `Achado` (problema registrado durante uma
inspeção de campo, por especialidade, com fotos e fluxo de sincronização
offline). O painel de acessibilidade tem um conceito superficialmente
parecido — item de checklist avaliado como OK/Pendente/Não se aplica — mas
segue um ciclo de conformidade normativa (NBR 9050/15 etc.), não o ciclo de
"inspeção de campo → achado → correção" das demais especialidades.

## Decisão
Acessibilidade **não** se torna uma especialidade dentro do fluxo de
`Achado`. É um domínio/app Django separado, com seu próprio modelo de dados,
compartilhando apenas `Edificacao` (ver ADR-01).

## Consequências
- Não herda de graça a máquina de edição offline (IndexedDB, fila de sync,
  compressão de fotos) já construída para achados — mas isso é aceitável
  porque o módulo é uso online (ver ADR-03).
- UI, views e regras de permissão são construídas do zero para este domínio,
  não reaproveitando templates/JS de `achado_form.html` etc.
- Evita contaminar o modelo de `Achado` com campos que só fazem sentido para
  conformidade normativa (resolução prevista, ordem de serviço, base legal).
