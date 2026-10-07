# ADR-09: Conclusão e direcionamentos — campo novo em `InspecaoEspecialidade`, texto livre, exigido para finalizar

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
O Relatório Final de Inspeção precisa, por especialidade, de uma conclusão
redigida à mão (texto livre, incluindo os direcionamentos narrados pelo
profissional — não um resumo computado a partir de `Achado.direcionamento`).

## Decisão
Novo campo `InspecaoEspecialidade.conclusao` (texto livre). Editável pela
mesma regra de hoje (`_pode_editar_especialidade` — staff ou os
profissionais **daquela** especialidade especificamente, não qualquer uma
das 3 como na permissão de gerar o relatório inteiro). Passa a ser
**exigido para finalizar**: `especialidade_finalizar` (`apps/inspecoes/views.py`)
bloqueia a finalização se o campo estiver vazio.

## Consequências
- `especialidade_finalizar` ganha uma nova validação além da existente
  ("tem achados registrados") — passa a exigir também a conclusão escrita.
- A obrigatoriedade é imposta mais cedo no fluxo (na finalização de cada
  especialidade), não só na hora de gerar o relatório — diferente do
  descritivo da edificação ([[ADR-08]]), que só é cobrado na geração.
- Como a conclusão passa a existir antes/independente do relatório, ela
  também entra no snapshot estruturado (ver [[ADR-03]]) junto com os
  achados daquela especialidade.
