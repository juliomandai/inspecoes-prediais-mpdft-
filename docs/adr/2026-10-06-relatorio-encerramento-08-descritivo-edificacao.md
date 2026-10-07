# ADR-08: Descritivo da edificação — campo novo em `Edificacao`, obrigatório para o relatório, editável pelos profissionais da inspeção

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
O Relatório Final de Inspeção abre com um descritivo da edificação (idade,
tipo construtivo, uso etc.), reutilizável entre inspeções da mesma
edificação — não é reescrito do zero a cada inspeção. `Edificacao` hoje é
editável só por staff (`@staff_member_required`, `apps/edificacoes/views.py`),
o que criaria uma dependência de staff no meio do fluxo de encerramento de
uma inspeção conduzida por profissionais não-staff.

## Decisão
Novo campo `Edificacao.descritivo` (texto livre). É **obrigatório** para
liberar a geração do relatório — mais uma condição de bloqueio junto às de
[[ADR-04]] (3 especialidades finalizadas) e [[ADR-05]] (mínimo de fotos).
É editável não só por staff, mas também pelos profissionais responsáveis
pela inspeção (mesma regra de permissão de geração do relatório — Seção 5) —
editado diretamente no fluxo de encerramento/geração do relatório, sem
precisar passar pela tela de Edificação.

## Consequências
- `Edificacao` (já um shared kernel entre `inspecoes` e `acessibilidade`,
  ver ADR-01 da sessão de 2026-08-18) ganha mais um campo.
- A tela de edição de Edificação (`edificacao_update`) continua
  staff-only para os demais campos (nome, endereço, ativo) — só o
  descritivo ganha esse caminho de edição alternativo, fora dessa tela.
- Precisa de uma checagem de permissão própria para editar só este campo
  (não reaproveita `@staff_member_required`).
