# Data Model: Sistema de Registro de Achados de Inspeção Predial

**Feature**: 001-registro-achados
**Date**: 2026-05-14

---

## Entidades

### Edificacao (Edificação)

Representa um imóvel ou promotoria do MPDFT elegível para inspeção predial.
Mantida como lista predefinida; administrada por usuários com permissão de staff.

| Campo | Tipo | Restrições | Descrição |
|-------|------|------------|-----------|
| `id` | inteiro | PK, auto | Identificador único |
| `nome` | texto (200) | obrigatório, único | Nome oficial da edificação/promotoria |
| `endereco` | texto (500) | opcional | Endereço completo |
| `ativo` | booleano | padrão: true | Permite desativar sem excluir |
| `criado_em` | datetime | auto | Data de cadastro |

**Regras de validação**:
- `nome` não pode ser duplicado (case-insensitive).
- Edificações inativas NÃO aparecem no seletor de nova inspeção.

---

### Inspecao (Inspeção)

Representa uma vistoria realizada em uma edificação por um profissional da SPO.
Cada inspeção pertence a uma edificação e a uma única especialidade.

| Campo | Tipo | Restrições | Descrição |
|-------|------|------------|-----------|
| `id` | inteiro | PK, auto | Identificador único |
| `edificacao` | FK → Edificacao | obrigatório, CASCADE | Edificação inspecionada |
| `profissional` | texto (200) | obrigatório | Nome do fiscal responsável |
| `especialidade` | choice | obrigatório | `civil` / `mecanica` / `eletrica` |
| `data_inspecao` | data | obrigatório, padrão: hoje | Data da vistoria |
| `status` | choice | padrão: `em_andamento` | `em_andamento` / `finalizada` |
| `criado_em` | datetime | auto | Data de criação do registro |
| `atualizado_em` | datetime | auto_now | Data da última modificação |

**Especialidade — valores:**
| Valor interno | Exibição |
|---------------|---------|
| `civil` | Civil |
| `mecanica` | Mecânica |
| `eletrica` | Elétrica |

**Status — transições:**
```
em_andamento ──► finalizada   (irreversível)
```

**Regras de validação**:
- `data_inspecao` não pode ser data futura.
- Uma inspeção `finalizada` NÃO permite adição ou edição de achados.

---

### Achado

Representa um item verificado durante a inspeção (conforme / não conforme / em
conformidade). Pertence a uma inspeção.

| Campo | Tipo | Restrições | Descrição |
|-------|------|------------|-----------|
| `id` | inteiro | PK, auto | Identificador único |
| `inspecao` | FK → Inspecao | obrigatório, CASCADE | Inspeção à qual pertence |
| `localizacao` | texto (200) | obrigatório | Localização na edificação (ex.: Térreo, Subsolo) |
| `sub_localizacao` | texto (200) | opcional | Sub-localização (ex.: Guarita, CPD, Chiller) |
| `verificacao` | texto (300) | obrigatório | Item verificado (ex.: Elevador, Drenagem) |
| `grupo_tecnico` | choice | obrigatório | Grupo técnico do item (ver valores abaixo) |
| `descricao_nao_conformidade` | texto longo | obrigatório | Descrição da não conformidade observada |
| `requisito_afetado` | choice | obrigatório | Requisito de desempenho afetado |
| `gravidade` | inteiro (1–5) | obrigatório | Nota G da matriz GUT |
| `urgencia` | inteiro (1–5) | obrigatório | Nota U da matriz GUT |
| `tendencia` | inteiro (1–5) | obrigatório | Nota T da matriz GUT |
| `gut_total` | inteiro (1–125) | calculado | G × U × T (calculado automaticamente) |
| `prioridade_risco` | choice (1/2/3) | obrigatório | 1 = Crítico, 2 = Regular, 3 = Mínimo |
| `recomendacao` | texto longo | obrigatório | Recomendação técnica descritiva |
| `direcionamento` | choice | obrigatório | Tipo de ação recomendada |
| `prazo_meses` | choice | obrigatório | Prazo para resolução em meses |
| `criado_em` | datetime | auto | Data de criação do registro |
| `atualizado_em` | datetime | auto_now | Data da última modificação |

**Grupo técnico — valores:**
| Valor interno | Exibição |
|---------------|---------|
| `esquadrias` | Esquadrias |
| `instalacoes` | Instalações Hidrossanitárias |
| `acabamento` | Acabamento |
| `instalacoes_mecanicas` | Instalações Mecânicas |
| `instalacoes_eletricas` | Instalações Elétricas |
| `estrutura` | Estrutura |
| `impermeabilizacao` | Impermeabilização |
| `cobertura` | Cobertura |
| `equipamentos` | Equipamentos Prediais |
| `acessibilidade` | Acessibilidade |
| `outros` | Outros |

**Requisito afetado — valores:**
| Valor interno | Exibição |
|---------------|---------|
| `seguranca_estrutural` | Segurança Estrutural |
| `acessibilidade` | Acessibilidade |
| `saude_qualidade_ar` | Saúde e Qualidade do Ar |
| `funcionalidade` | Funcionalidade |
| `estetica` | Estética |
| `eficiencia_energetica` | Eficiência Energética |
| `sustentabilidade` | Sustentabilidade |
| `durabilidade` | Durabilidade |

**Direcionamento — valores:**
| Valor interno | Exibição |
|---------------|---------|
| `garantia` | Garantia de obra |
| `manutencao` | Manutenção |
| `nova_contratacao` | Nova contratação |

**Prazo — valores (meses):** `1`, `3`, `6`, `12`, `18`, `24`

**Regras de validação**:
- `gravidade`, `urgencia`, `tendencia`: inteiros entre 1 e 5 (inclusive).
- `gut_total` é SEMPRE calculado como G × U × T; não é editável pelo usuário.
- Achado NÃO pode ser salvo com qualquer campo obrigatório vazio.
- Achado NÃO pode ser criado ou editado em inspeção com status `finalizada`.

---

### Foto

Representa uma fotografia de evidência vinculada a um achado.

| Campo | Tipo | Restrições | Descrição |
|-------|------|------------|-----------|
| `id` | inteiro | PK, auto | Identificador único |
| `achado` | FK → Achado | obrigatório, CASCADE | Achado ao qual pertence |
| `arquivo` | arquivo | obrigatório | Caminho relativo em `media/fotos/` |
| `nome_original` | texto (255) | auto | Nome original do arquivo enviado |
| `tamanho_bytes` | inteiro | auto | Tamanho do arquivo em bytes |
| `data_upload` | datetime | auto | Momento do upload |

**Regras de validação**:
- Formatos aceitos: `image/jpeg`, `image/png`.
- Tamanho máximo: 10 MB por arquivo.
- Caminho de armazenamento: `media/fotos/<ano>/<mes>/<achado_id>/<uuid>.<ext>`.

---

## Relacionamentos

```
Edificacao (1) ──────── (N) Inspecao
Inspecao   (1) ──────── (N) Achado
Achado     (1) ──────── (N) Foto
```

- Exclusão de `Edificacao` não é permitida se existirem inspeções vinculadas
  (protegida por `PROTECT`); somente desativação (`ativo = false`).
- Exclusão de `Inspecao` propaga para `Achado` e `Foto` (`CASCADE`).
- Exclusão de `Achado` propaga para `Foto` (`CASCADE`) e remove arquivos físicos.

---

## Modelo de Usuário

Utiliza o modelo `User` padrão do Django (`django.contrib.auth`), com os
seguintes papéis de acesso:

| Papel | Django flag | Permissões |
|-------|-------------|------------|
| Servidor SPO | `is_staff = false` | Criar/editar inspeções e achados; fazer upload de fotos |
| Administrador | `is_staff = true` | Acima + gerenciar edificações, usuários e purga de dados |

Nenhuma extensão customizada do modelo `User` é necessária para v1.

---

## Diagrama ER (simplificado)

```
┌─────────────────┐         ┌──────────────────────────┐
│   Edificacao    │         │        Inspecao           │
│─────────────────│         │──────────────────────────│
│ id (PK)         │◄────────│ edificacao (FK)           │
│ nome            │         │ profissional              │
│ endereco        │         │ especialidade             │
│ ativo           │         │ data_inspecao             │
│ criado_em       │         │ status                    │
└─────────────────┘         │ criado_em / atualizado_em │
                            └──────────────┬───────────┘
                                           │ 1
                                           │
                                           ▼ N
                            ┌──────────────────────────┐
                            │          Achado           │
                            │──────────────────────────│
                            │ id (PK)                   │
                            │ inspecao (FK)             │
                            │ localizacao               │
                            │ sub_localizacao           │
                            │ verificacao               │
                            │ grupo_tecnico             │
                            │ descricao_nao_conformidade│
                            │ requisito_afetado         │
                            │ gravidade / urgencia      │
                            │ tendencia / gut_total     │
                            │ prioridade_risco          │
                            │ recomendacao              │
                            │ direcionamento            │
                            │ prazo_meses               │
                            └──────────────┬────────────┘
                                           │ 1
                                           │
                                           ▼ N
                            ┌──────────────────────────┐
                            │           Foto            │
                            │──────────────────────────│
                            │ id (PK)                   │
                            │ achado (FK)               │
                            │ arquivo                   │
                            │ nome_original             │
                            │ tamanho_bytes             │
                            │ data_upload               │
                            └──────────────────────────┘
```
