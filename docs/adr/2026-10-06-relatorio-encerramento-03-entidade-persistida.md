# ADR-03: Relatório Final de Inspeção é uma entidade persistida, não um PDF efêmero

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
O relatório lastreia uma ART protocolada no CREA. Se fosse puramente derivado
(como o laudo agregado atual — ver ADR-01), uma edição posterior num achado
tornaria qualquer PDF "regerado" divergente do que foi de fato assinado e
entregue ao CREA — sem nenhum registro de que isso ocorreu. Isso é
inaceitável para um documento com valor legal/regulatório.

## Decisão
Criar uma nova entidade com identidade própria (nome provisório
`RelatorioFinalInspecao` — a confirmar na Seção 5/Entidades) que registra
quando foi gerado e por quem, e preserva um conteúdo imutável daquele
momento. Gerar de novo não sobrescreve um relatório existente — cria uma
nova versão, cada uma com sua própria identidade e timestamp.

## Consequências
- **Resolvido (Seção 4):** fica congelado **os dois** — o arquivo PDF
  renderizado (o documento de fato impresso/assinado, igual ao padrão já
  usado por `Foto`/`VisitaFoto`) **e** um snapshot estruturado dos dados
  (JSON com achados/textos/prioridades/referências às fotos usadas naquele
  momento) — o snapshot permite auditoria/consulta sem precisar abrir o PDF.
- Precisa de uma invariante que lide com achados mudando depois que um
  relatório já foi gerado (ver Seção 5 — Agregados e Invariantes).
- Introduz a primeira entidade do app `inspecoes` com ciclo de vida de
  "documento versionado" — diferente do padrão atual (Inspecao/Especialidade/
  Achado são todos mutáveis in-place).
