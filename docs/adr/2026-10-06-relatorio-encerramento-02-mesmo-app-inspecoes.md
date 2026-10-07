# ADR-02: Relatório Final de Inspeção vive dentro de `apps.inspecoes`, sem app novo

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
O relatório depende só de entidades que já pertencem ao bounded context
`inspecoes` (Inspeção, Especialidade, Achado, Foto) — não introduz um
sub-domínio próprio, diferente do que ocorreu com `acessibilidade`
(ver ADR-02 da sessão de 2026-08-18, que separou aquele módulo por trazer um
domínio de conformidade normativa distinto).

## Decisão
Implementar como mais uma view/rota/template dentro de `apps/inspecoes/`, ao
lado de `inspecao_analise`/`inspecao_analise_pdf` — sem criar um app
`apps.relatorios` separado.

## Consequências
- Menor custo de wiring: sem settings/INSTALLED_APPS/urls cross-app, sem
  necessidade de FK entre apps.
- Em compensação, o app `inspecoes` acumula mais uma responsabilidade
  (geração de relatório formal para ART) além de registro e análise —
  aceitável dado que o relatório não tem identidade/ciclo de vida próprio
  além da inspeção que o originou (ver Seção 5 — Agregados).
