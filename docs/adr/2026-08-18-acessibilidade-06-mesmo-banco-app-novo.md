# ADR-06: Mesmo banco SQLite, novo app Django

## Status
Aceita (2026-08-18, sessão de grilling)

## Contexto
O módulo poderia viver em banco/serviço separado (isolamento de escala,
deploy independente) ou no mesmo SQLite do projeto (simplicidade,
integridade referencial com `Edificacao`). Uso é só online, por poucas
pessoas do SPO — não tem o padrão de escrita em rajada que motivou a
rearquitetura de sincronização offline de achados.

## Decisão
Novo app Django (`apps/acessibilidade` ou nome equivalente) no mesmo
projeto e banco SQLite. FK direta para `Edificacao`.

## Consequências
- Reaproveita backup automático (`backup_automatico.bat`), grafo único de
  migrations, mesmo processo de deploy na VM.
- Risco de contenção de escrita no SQLite (lock de arquivo inteiro) existe
  mas é considerado baixo dado o padrão de uso (poucos usuários, edição
  manual, não sync em massa).
- Se o padrão de uso mudar (muitos usuários simultâneos, escrita em
  volume), revisitar esta decisão — mesmo gatilho que motivaria migrar
  para Postgres no projeto como um todo.
