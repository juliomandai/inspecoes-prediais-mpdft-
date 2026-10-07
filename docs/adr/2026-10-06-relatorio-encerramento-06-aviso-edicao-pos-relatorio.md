# ADR-06: Editar/reabrir após relatório já gerado só avisa, não bloqueia

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
Uma vez gerada a versão N do Relatório Final de Inspeção (ADR-03), nada no
fluxo normal impede reabrir uma especialidade finalizada (`especialidade_reabrir`
já existe hoje) e editar achados — o que pode divergir da versão já
potencialmente assinada/protocolada no CREA.

## Decisão
Ao reabrir uma especialidade, ou editar/excluir um achado, de uma inspeção
que já tem ao menos um Relatório Final de Inspeção gerado, o sistema mostra
um aviso (ex.: "Esta inspeção já tem um Relatório Final gerado (v1,
12/03/2026). Editar agora não altera esse relatório — gere uma nova versão
se precisar refletir esta mudança."). A ação prossegue normalmente após o
aviso; nada é bloqueado.

## Consequências
- A versão já gerada nunca é alterada (imutável, por ADR-03); divergência
  entre dados ao vivo e a última versão gerada é esperada e sinalizada, não
  impedida.
- Mantém o profissional avisado sem travar correções legítimas de dados.
- Implica guardar, em algum lugar de fácil consulta pela view de
  reabertura/edição, se a inspeção tem relatório(s) gerado(s) — ex. uma
  property `Inspecao.tem_relatorio_final_gerado` ou equivalente.
