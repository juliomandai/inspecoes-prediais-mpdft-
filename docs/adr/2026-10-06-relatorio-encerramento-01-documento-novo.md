# ADR-01: Relatório Final de Inspeção é um documento novo, distinto do laudo agregado existente

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
`inspecao_analise_pdf` (`apps/inspecoes/views.py`) já gera um PDF informalmente
chamado "laudo" (nome de arquivo `laudo_{edificação}_{data}.pdf`), com conteúdo
agregado/estatístico: contagens por prioridade, Pareto por grupo técnico,
estatísticas GUT. Não lista achados individualmente, não inclui fotos por
achado, e não tem blocos de assinatura.

## Decisão
O relatório que vai instruir a ART junto ao CREA é um **documento novo e
independente** — rota, view e template próprios — que não substitui nem
altera o laudo agregado atual. Os dois convivem, cada um com um propósito
diferente:
- **Laudo agregado** (existente): análise gerencial/estatística.
- **Relatório Final de Inspeção** (novo): documento formal, itemizado, assinável,
  para instruir a ART.

## Consequências
- Nenhuma mudança no fluxo, código ou template do laudo agregado atual.
- O novo relatório reaproveita os mesmos dados-fonte (`Inspecao` →
  `InspecaoEspecialidade` → `Achado` → `Foto`), mas monta seu próprio contexto
  e template — não é uma extensão de `_analise_data`/`analise_geral_pdf.html`.
- Duas rotas/botões de exportação distintos na UI da inspeção concluída.
