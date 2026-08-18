# ADR-03: Módulo é uso online-only, sem suporte offline

## Status
Aceita (2026-08-18, sessão de grilling)

## Contexto
A plataforma de inspeções investiu pesado em sincronização offline (PWA,
IndexedDB, fila de fotos) para o fluxo de campo de achados, porque
inspetores capturam dados sem conectividade em subsolos etc. O painel de
acessibilidade é editado por pessoal do SPO a partir de um diagnóstico já
levantado — não é captura de campo em tempo real.

## Decisão
O módulo de acessibilidade não implementa PWA/offline. É uma aplicação
Django convencional (views autenticadas, formulários, submissão síncrona).

## Consequências
- Simplifica drasticamente o escopo de implementação — sem Service Worker,
  sem IndexedDB, sem fila de sincronização, sem compressão client-side.
- Se essa premissa mudar no futuro (alguém precisar editar em campo sem
  internet), é um retrabalho equivalente ao que foi feito para achados —
  não um ajuste incremental.
