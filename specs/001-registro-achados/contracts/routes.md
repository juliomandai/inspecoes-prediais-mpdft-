# Interface Contracts: Rotas e Comportamento das Views

**Feature**: 001-registro-achados
**Date**: 2026-05-14
**Type**: Server-side rendered Django web application

Cada rota descreve: método HTTP, URL, proteção de acesso, dados esperados
na requisição e comportamento esperado na resposta. Todas as rotas (exceto
login) exigem autenticação (`@login_required`).

---

## Autenticação

### `GET /login/`
**Acesso**: público
**Resposta**: formulário de login (username + password)

### `POST /login/`
**Acesso**: público
**Body (form)**: `username`, `password`, `next` (opcional)
**Comportamento**:
- Credenciais válidas → redireciona para `next` ou `/` (lista de inspeções)
- Credenciais inválidas → reexibe formulário com mensagem de erro

### `GET /logout/`
**Acesso**: autenticado
**Comportamento**: encerra sessão e redireciona para `/login/`

---

## Edificações (administração)

### `GET /edificacoes/`
**Acesso**: staff apenas
**Resposta**: lista de edificações (nome, endereço, status ativo)

### `GET /edificacoes/nova/`
**Acesso**: staff apenas
**Resposta**: formulário de cadastro de edificação

### `POST /edificacoes/nova/`
**Acesso**: staff apenas
**Body (form)**: `nome`, `endereco`
**Comportamento**:
- Dados válidos → cria edificação, redireciona para `/edificacoes/`
- Dados inválidos → reexibe formulário com erros (ex.: nome duplicado)

### `GET /edificacoes/<id>/editar/`
**Acesso**: staff apenas
**Resposta**: formulário preenchido com dados da edificação

### `POST /edificacoes/<id>/editar/`
**Acesso**: staff apenas
**Body (form)**: `nome`, `endereco`, `ativo`
**Comportamento**:
- Dados válidos → atualiza, redireciona para `/edificacoes/`
- Dados inválidos → reexibe formulário com erros

---

## Inspeções

### `GET /`  ≡  `GET /inspecoes/`
**Acesso**: autenticado
**Query params** (opcionais): `edificacao_id`, `data_inicio`, `data_fim`, `especialidade`, `profissional`
**Resposta**: lista paginada de inspeções; colunas: edificação, data, profissional, especialidade, status, nº de achados
**Ordenação padrão**: data_inspecao decrescente

### `GET /inspecoes/nova/`
**Acesso**: autenticado
**Resposta**: formulário com campos: edificação (dropdown de ativas), profissional, especialidade, data_inspecao

### `POST /inspecoes/nova/`
**Acesso**: autenticado
**Body (form)**: `edificacao`, `profissional`, `especialidade`, `data_inspecao`
**Comportamento**:
- Dados válidos → cria inspeção com `status=em_andamento`, redireciona para `/inspecoes/<id>/`
- Dados inválidos → reexibe formulário com erros

### `GET /inspecoes/<id>/`
**Acesso**: autenticado
**Resposta**: detalhe da inspeção (metadados) + lista de achados (localização, GUT, risco, direcionamento); botão "Adicionar achado" visível somente se `status=em_andamento`

### `POST /inspecoes/<id>/finalizar/`
**Acesso**: autenticado
**Comportamento**:
- Inspeção `em_andamento` com ao menos 1 achado → muda status para `finalizada`, redireciona para `/inspecoes/<id>/`
- Inspeção sem achados → erro: "Não é possível finalizar uma inspeção sem achados registrados"
- Inspeção já `finalizada` → resposta 400

---

## Achados

### `GET /inspecoes/<id>/achados/novo/`
**Acesso**: autenticado
**Pré-condição**: inspeção com `status=em_andamento`; caso contrário → 403
**Resposta**: formulário de achado com todos os campos (localização, sub-localização, verificação, grupo técnico, descrição, requisito afetado, G/U/T, prioridade, recomendação, direcionamento, prazo); campo `gut_total` é somente leitura, calculado em tempo real via JavaScript

### `POST /inspecoes/<id>/achados/novo/`
**Acesso**: autenticado
**Pré-condição**: inspeção com `status=em_andamento`
**Body (form)**: todos os campos obrigatórios do Achado
**Comportamento**:
- Dados válidos → cria achado, `gut_total` calculado no servidor (G×U×T), redireciona para `/inspecoes/<id>/`
- Dados inválidos → reexibe formulário com erros destacados por campo
- Campo obrigatório vazio → impede salvamento, destaca campo

### `GET /achados/<id>/editar/`
**Acesso**: autenticado
**Pré-condição**: achado em inspeção `em_andamento`; caso contrário → 403
**Resposta**: formulário preenchido com dados do achado + galeria de fotos já enviadas

### `POST /achados/<id>/editar/`
**Acesso**: autenticado
**Pré-condição**: inspeção `em_andamento`
**Body (form)**: campos do achado (todos editáveis exceto `gut_total` e `inspecao`)
**Comportamento**:
- Dados válidos → atualiza achado, recalcula `gut_total`, redireciona para `/inspecoes/<inspecao_id>/`
- Dados inválidos → reexibe formulário com erros

---

## Fotos

### `POST /achados/<id>/fotos/`
**Acesso**: autenticado
**Pré-condição**: achado em inspeção `em_andamento`
**Body (multipart/form-data)**: `arquivo` (um ou múltiplos arquivos)
**Comportamento**:
- Arquivo válido (JPEG/PNG, ≤ 10 MB) → cria registro `Foto`, salva arquivo em `media/fotos/<ano>/<mes>/<achado_id>/`, responde com JSON `{id, url, nome_original}` (compatível com upload assíncrono via fetch)
- Arquivo inválido → resposta 400 com mensagem de erro
- Inspeção finalizada → resposta 403

### `DELETE /fotos/<id>/`
**Acesso**: autenticado
**Pré-condição**: inspeção `em_andamento`
**Comportamento**: remove registro do banco e arquivo físico; responde com 204 No Content

---

## Regras Gerais de Comportamento

| Situação | Comportamento |
|----------|---------------|
| Usuário não autenticado tenta acessar qualquer rota protegida | Redireciona para `/login/?next=<url>` |
| Usuário staff tenta editar inspeção de outro usuário | Permitido (sem ownership nesta versão) |
| Requisição GET a URL inválida (ID inexistente) | Resposta 404 com página de erro amigável |
| Inspeção finalizada e usuário tenta editar achado | Resposta 403 com mensagem "Inspeção finalizada não pode ser editada" |
| Foto com formato inválido | Resposta 400 com mensagem indicando formatos aceitos |

---

## Cálculo do GUT (contrato de negócio)

O índice GUT é calculado **sempre no servidor** durante o save do Achado,
garantindo consistência independente do cliente:

```
gut_total = gravidade × urgencia × tendencia
```

O frontend exibe o cálculo em tempo real apenas como conveniência visual;
o valor persistido é sempre o calculado pelo servidor.

**Faixas de referência** (informativas, não aplicadas automaticamente):

| Faixa GUT | Sugestão de Prioridade |
|-----------|------------------------|
| 75 – 125 | Crítico (1) |
| 20 – 74 | Regular (2) |
| 1 – 19 | Mínimo (3) |

A prioridade de risco final é sempre definida manualmente pelo servidor da SPO.
