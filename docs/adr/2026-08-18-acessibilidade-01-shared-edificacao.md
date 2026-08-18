# ADR-01: Reaproveitar `Edificacao` existente como entidade compartilhada

## Status
Aceita (2026-08-18, sessão de grilling)

## Contexto
O painel de acessibilidade (HTML/Artifact) trata 13 "localidades" (BSBI, BSBII, PJBZ...)
como universo de edificações. A plataforma de inspeções já tem um model `Edificacao`
(`apps/edificacoes/models.py`), hoje com apenas 2 registros cadastrados e sem campo
de sigla/código.

## Decisão
As 13 localidades do painel **são as mesmas edificações** já rastreadas pela
plataforma. O novo módulo de acessibilidade referencia `Edificacao` via FK — não
cria um cadastro de edificações paralelo. Isso implica: (1) adicionar um campo
de sigla/código a `Edificacao` (ou tabela de mapeamento) para bater com os
códigos do painel, e (2) cadastrar as 11 edificações que faltam.

## Consequências
- `Edificacao` vira um "shared kernel" entre os bounded contexts `inspecoes` e
  `acessibilidade` — qualquer mudança de schema nela afeta os dois.
- Ganha integridade referencial real e a possibilidade de cruzar dados entre
  os dois domínios no futuro (ex. relatório único por edificação).
- Custo: precisa de uma migração de dados para mapear os 13 códigos-sigla do
  painel para registros de `Edificacao` (existentes + novos).
