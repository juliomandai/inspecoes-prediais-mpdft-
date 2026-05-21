# Implementation Plan: Sistema de Registro de Achados de Inspeção Predial

**Branch**: `001-registro-achados` | **Date**: 2026-05-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-registro-achados/spec.md`

---

## Summary

Aplicação web Django para que servidores da SPO/MPDFT registrem achados de
inspeções prediais em edificações do MPDFT. O fluxo central é: abertura de
inspeção (edificação + profissional + especialidade) → cadastro de achados
(dados técnicos + fotos + matriz GUT + análise de risco + recomendação) →
consulta e retomada de inspeções em andamento. Stack: Python 3.11 + Django 4.2
LTS, banco SQLite/PostgreSQL, interface server-side com Bootstrap 5.

---

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**:
- Django 4.2 LTS (framework web, ORM, autenticação, admin)
- Pillow (processamento e validação de imagens)
- Bootstrap 5 (interface responsiva para desktop e tablet)
- Waitress (servidor WSGI para Windows em produção)
- python-decouple (gerenciamento de variáveis de ambiente)

**Storage**:
- Banco de dados: SQLite (desenvolvimento); PostgreSQL (produção recomendada)
- Fotos: sistema de arquivos local em `media/fotos/` (pode apontar para OneDrive)

**Testing**: pytest + pytest-django

**Target Platform**: Navegador web em desktops e tablets Windows (rede MPDFT)

**Project Type**: Aplicação web server-side rendered (Django templates + Bootstrap 5)

**Performance Goals**:
- Carregamento de página em até 3 segundos
- Upload de foto concluído em até 30 segundos
- Lista de inspeções filtrada em até 5 segundos

**Constraints**:
- Acessível em tablets e desktops usados pela SPO em campo
- Dados retidos por mínimo de 6 meses (purga via management command agendado)
- Deployável em servidor Windows sem infraestrutura além de Python
- Fotos: máx. 10 MB por arquivo; formatos JPEG e PNG

**Scale/Scope**:
- ~10–20 usuários (servidores SPO)
- ~50–100 inspeções/ano; ~500–2.000 achados/ano
- ~10–50 GB de fotos/ano (estimativa)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Observação |
|-----------|--------|------------|
| I. Integridade dos Dados | ✅ PASS | Sistema captura todos os dados; fotos em sistema de arquivos; geração de laudo e planilha é feature futura separada |
| II. Rastreabilidade e Classificação de Risco | ✅ PASS | Todos os campos obrigatórios de rastreabilidade presentes (edificação, data, profissional, sistema predial, GUT, prioridade); FR-012 impede salvamento incompleto |
| III. Conformidade com a Engenharia Diagnóstica | ✅ PASS | Matriz GUT (G×U×T, 1–5) e classificação Crítico/Regular/Mínimo são features centrais; grupos técnicos e requisitos afetados alinhados com NBR 16747:2020 |
| IV. Operabilidade para a SPO | ⚠️ VIOLAÇÃO JUSTIFICADA | Constituição lista aplicações web e bancos de dados como fora de escopo v1; usuário explicitamente requisitou ambos — justificativa em Complexity Tracking |
| V. Reprodutibilidade dos Produtos | ✅ PASS | Dados estruturados no banco permitem geração futura de laudo e planilha a partir dos mesmos registros |

**Re-check pós-design (Phase 1)**: ✅ Nenhum novo conflito. O modelo de dados
cobre todos os campos exigidos pelos princípios II e III. A abordagem
server-side rendering maximiza a simplicidade operacional (Princípio IV).

---

## Project Structure

### Documentation (this feature)

```text
specs/001-registro-achados/
├── plan.md              # Este arquivo
├── research.md          # Decisões de stack e tecnologia (Phase 0)
├── data-model.md        # Entidades, campos e relacionamentos (Phase 1)
├── quickstart.md        # Guia de instalação e uso (Phase 1)
├── contracts/
│   └── routes.md        # Rotas, views e contratos de comportamento (Phase 1)
└── tasks.md             # Gerado por /speckit-tasks (não criado aqui)
```

### Source Code (repository root)

```text
src/
├── manage.py
├── requirements.txt
├── .env.example
├── mpdft_inspecoes/           # Configuração Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── edificacoes/           # Cadastro de edificações/promotorias (staff)
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── templates/
│   │       └── edificacoes/
│   ├── inspecoes/             # Inspeções, achados e fotos (servidores SPO)
│   │   ├── models.py          # Inspecao, Achado, Foto
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── templates/
│   │       └── inspecoes/
│   └── management/
│       └── commands/
│           └── purge_old_inspecoes.py  # Retenção 6 meses (agendado via Task Scheduler)
├── templates/
│   ├── base.html              # Layout compartilhado (navbar, Bootstrap 5)
│   └── registration/
│       └── login.html
├── static/
│   ├── css/
│   └── js/
│       └── gut_calculator.js  # Cálculo GUT em tempo real no formulário
└── media/                     # Fotos enviadas (gitignored; pode ser OneDrive)

tests/
├── test_edificacoes.py
├── test_inspecoes.py
├── test_achados.py
└── test_fotos.py
```

**Structure Decision**: Projeto único Django com dois apps de domínio
(`edificacoes` e `inspecoes`). A separação reflete papéis de acesso distintos
(staff para edificações; servidores SPO para inspeções) e mantém os domínios
independentes para facilitar manutenção futura.

---

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada por |
|----------|---------------------|---------------------------------------|
| Aplicação web (fora de escopo v1 na constituição) | Usuário explicitamente requisitou; habilita acesso por tablet em campo; suporta múltiplos usuários simultâneos; viabiliza upload de fotos com interface amigável | Excel/Word: não suporta upload de fotos, cálculo automático GUT, acesso multi-usuário simultâneo ou retenção estruturada de 6 meses com filtragem |
| Banco de dados (requer aprovação institucional) | Retenção de 6 meses com busca filtrada exige armazenamento estruturado (FR-007, FR-010); SQLite é arquivo único sem servidor, com mínima complexidade operacional | Planilha Excel compartilhada: sem suporte a escrita simultânea, sem integridade referencial, sem vínculo foto-achado |

**Ação requerida**: Júlio Mandai (SPO/MPDFT) deve formalizar aprovação
institucional para uso de banco de dados antes do deploy em produção,
conforme Princípio IV da constituição.
