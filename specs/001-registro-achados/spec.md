# Feature Specification: Sistema de Registro de Achados de Inspeção Predial

**Feature Branch**: `001-registro-achados`

**Created**: 2026-05-14

**Status**: Draft

**Input**: Sistema web para registrar os achados da inspeção predial de cada edificação do MPDFT, com preenchimento de informações iniciais da inspeção, cadastro de achados com dados técnicos, upload de fotos, matriz GUT, análise de risco e recomendações.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Registrar nova inspeção com achados completos (Priority: P1)

Um servidor da SPO acessa o sistema, preenche as informações iniciais da inspeção (localidade, profissional responsável, especialidade e data), em seguida adiciona os achados encontrados durante a vistoria. Para cada achado, informa localização, sub-localização, item de verificação, grupo técnico, descrição da não conformidade, requisito afetado, faz o upload das fotos, preenche a matriz GUT e define a análise de risco e a recomendação técnica com prazo.

**Why this priority**: É o fluxo central e único propósito do sistema. Sem ele, nenhum outro cenário faz sentido. Representa o 100% do valor de negócio na versão inicial.

**Independent Test**: Pode ser testado de forma independente criando uma nova inspeção do zero até a finalização de ao menos um achado completo (com foto, GUT e recomendação), e verificando que os dados são recuperáveis após o cadastro.

**Acceptance Scenarios**:

1. **Given** o servidor está autenticado no sistema, **When** ele clica em "Nova Inspeção" e preenche localidade, profissional, especialidade e data, **Then** uma nova inspeção é criada com status "Em andamento" e o sistema apresenta a tela de cadastro de achados.

2. **Given** uma inspeção está em andamento, **When** o servidor preenche todos os campos obrigatórios de um achado e clica em salvar, **Then** o achado é registrado e aparece na lista de achados da inspeção com resumo do grau de risco e índice GUT.

3. **Given** o servidor está preenchendo um achado, **When** ele informa as notas de Gravidade (G), Urgência (U) e Tendência (T) — cada uma entre 1 e 5, **Then** o sistema calcula e exibe automaticamente o índice GUT (G × U × T) sem nenhuma ação adicional do usuário.

4. **Given** o servidor tenta salvar um achado, **When** algum campo obrigatório (localização, verificação, descrição da não conformidade, GUT ou análise de risco) está vazio, **Then** o sistema impede o salvamento e destaca o(s) campo(s) pendente(s).

5. **Given** um achado foi salvo, **When** o servidor visualiza a inspeção, **Then** as fotos associadas ao achado são exibidas junto aos demais dados desse achado.

---

### User Story 2 — Retomar inspeção em andamento (Priority: P2)

Um servidor da SPO inicia o preenchimento de uma inspeção, precisa interromper (encerrar o navegador ou sessão) e retorna ao sistema posteriormente para continuar de onde parou, sem perda de dados.

**Why this priority**: Vistorias prediais ocorrem em campo, com conexão instável e interrupções frequentes. A capacidade de salvar e retomar é essencial para não perder trabalho já realizado.

**Independent Test**: Pode ser testado criando uma inspeção com ao menos um achado salvo, fechando o navegador, reabrindo o sistema e verificando que a inspeção e seus achados estão intactos e editáveis.

**Acceptance Scenarios**:

1. **Given** o servidor tem uma inspeção "Em andamento", **When** ele acessa a lista de inspeções, **Then** a inspeção aparece com status "Em andamento" e pode ser reaberta para continuar o preenchimento.

2. **Given** o servidor reabriu uma inspeção em andamento, **When** ele adiciona um novo achado, **Then** os achados já cadastrados anteriormente permanecem e o novo achado é adicionado à lista existente.

3. **Given** o servidor reabre um achado já salvo, **When** ele edita qualquer campo e salva, **Then** os novos dados substituem os anteriores e o histórico de modificação não é perdido para os demais achados.

---

### User Story 3 — Consultar inspeções registradas (Priority: P3)

Um servidor da SPO acessa a lista de inspeções já registradas, filtra por critérios básicos (localidade, data, profissional) e visualiza o detalhe de uma inspeção com todos os seus achados.

**Why this priority**: Consulta histórica é necessária para acompanhamento de recomendações e auditorias, mas não bloqueia o fluxo de registro de novas inspeções.

**Independent Test**: Pode ser testado com ao menos duas inspeções cadastradas, aplicando filtros e verificando que os resultados correspondem aos critérios aplicados, e que ao abrir uma inspeção todos os achados são exibidos corretamente.

**Acceptance Scenarios**:

1. **Given** existem inspeções registradas, **When** o servidor acessa a lista, **Then** vê ao menos: localidade, data, profissional responsável, especialidade e quantidade de achados de cada inspeção.

2. **Given** o servidor aplica um filtro por localidade ou período, **When** confirma o filtro, **Then** apenas inspeções correspondentes aos critérios são exibidas.

3. **Given** o servidor abre o detalhe de uma inspeção, **When** a tela carrega, **Then** todos os achados são listados com localização, índice GUT, grau de risco e status da recomendação visíveis sem precisar abrir cada achado individualmente.

---

### Edge Cases

- O que acontece se o servidor fechar o navegador sem salvar um achado que estava em edição?
- Como o sistema se comporta se o arquivo de foto enviado ultrapassar um tamanho máximo ou estiver em formato não suportado?
- O que ocorre quando as notas GUT resultam em um índice que sugere prioridade diferente da selecionada manualmente pelo servidor?
- Como os dados são tratados após o período de retenção de 6 meses — exclusão automática ou arquivamento?
- O que acontece se dois servidores tentarem editar o mesmo achado simultaneamente?

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir criar uma nova inspeção com os seguintes campos: localidade (selecionada a partir de uma lista predefinida de edificações/promotorias do MPDFT cadastradas no sistema), nome do profissional responsável (texto livre), especialidade (opção única: Civil, Mecânica ou Elétrica) e data da inspeção (padrão: data atual, editável).

- **FR-002**: O sistema DEVE permitir adicionar múltiplos achados a uma inspeção. Cada achado DEVE conter: localização na edificação, sub-localização, item de verificação, grupo técnico, descrição da não conformidade (texto livre) e requisito afetado.

- **FR-003**: O sistema DEVE permitir o upload de uma ou mais fotos por achado, vinculando-as ao achado correspondente.

- **FR-004**: O sistema DEVE oferecer campos de entrada para Gravidade (G), Urgência (U) e Tendência (T) — notas inteiras de 1 a 5 — e calcular e exibir automaticamente o índice GUT (G × U × T) sem ação adicional do usuário.

- **FR-005**: O sistema DEVE permitir definir a análise de risco de cada achado com as opções: Prioridade 1 (Crítico), Prioridade 2 (Regular) ou Prioridade 3 (Mínimo).

- **FR-006**: O sistema DEVE permitir registrar, para cada achado: recomendação técnica (texto livre), direcionamento (opção única: garantia de obra, manutenção ou nova contratação) e prazo para resolução (opção entre: 1, 3, 6, 12, 18 ou 24 meses).

- **FR-007**: O sistema DEVE reter todos os dados de inspeção por no mínimo 6 meses a partir da data da inspeção.

- **FR-008**: O sistema DEVE salvar automaticamente o progresso de uma inspeção e permitir que o usuário retome o preenchimento em outro momento sem perda de dados.

- **FR-009**: O sistema DEVE exibir, na tela de uma inspeção, a lista de todos os achados cadastrados com ao menos: localização, índice GUT, grau de risco e direcionamento da recomendação.

- **FR-010**: O sistema DEVE exibir uma lista de todas as inspeções cadastradas, mostrando: localidade, data, profissional, especialidade e quantidade de achados; e permitir filtrar por localidade e por período.

- **FR-011**: Cada inspeção DEVE ser restrita a uma única especialidade (Civil, Mecânica ou Elétrica). Para cobrir múltiplas especialidades em uma mesma edificação, o servidor DEVE criar inspeções separadas.

- **FR-012**: O sistema DEVE impedir o salvamento de um achado se qualquer campo obrigatório estiver vazio: localização, item de verificação, descrição da não conformidade, G/U/T e análise de risco.

- **FR-013**: O sistema DEVE exigir autenticação do usuário para acesso a qualquer funcionalidade.

### Key Entities

- **Inspeção**: localidade, profissional responsável, especialidade, data da inspeção, data de criação, status (em andamento / finalizada).
- **Achado**: localização na edificação, sub-localização, item de verificação, grupo técnico, descrição da não conformidade, requisito afetado, notas G/U/T (1–5 cada), índice GUT calculado, prioridade de risco (1/2/3), texto de recomendação, direcionamento, prazo; pertence a uma Inspeção.
- **Foto**: arquivo de imagem, data de upload; pertence a um Achado.

---

## Success Criteria *(mandatory)*

- **SC-001**: O servidor consegue registrar todos os dados de um achado completo (sem contar o upload de fotos) em menos de 3 minutos.
- **SC-002**: O índice GUT é exibido automaticamente, sem nenhum cálculo manual pelo servidor.
- **SC-003**: Todos os dados inseridos permanecem acessíveis por pelo menos 6 meses a partir da data da inspeção.
- **SC-004**: O servidor pode fechar o navegador e retornar ao sistema encontrando a inspeção em andamento com todos os achados já salvos intactos.
- **SC-005**: O sistema é utilizável em navegadores de desktops e tablets utilizados pelos servidores da SPO em campo.
- **SC-006**: As fotos de cada achado são exibidas junto aos demais dados desse achado ao visualizar a inspeção.
- **SC-007**: A lista de inspeções exibe resultados filtrados em menos de 5 segundos para qualquer combinação de filtros.

---

## Assumptions

- **Profissional responsável** é um campo de texto livre (nome); não é necessária uma lista de profissionais cadastrados.
- **Especialidade** é de seleção única por inspeção (Civil, Mecânica ou Elétrica). Para cobrir múltiplas especialidades, o servidor cria inspeções separadas.
- **Múltiplas fotos** podem ser enviadas por achado; formatos e tamanho máximo serão definidos na fase de planejamento técnico.
- **Prazo para resolução** é selecionado entre opções predefinidas: 1, 3, 6, 12, 18 ou 24 meses.
- **Direcionamento da recomendação** é escolha única entre três opções fixas: "garantia de obra", "manutenção" e "nova contratação".
- **Data da inspeção** tem como padrão a data atual, mas pode ser alterada pelo servidor.
- **Retenção de dados** de 6 meses é contada a partir da data da inspeção. O comportamento após esse prazo (exclusão automática ou arquivamento) será definido no planejamento.
- **Autenticação** é obrigatória; o mecanismo específico (credenciais MPDFT, SSO, login local) será definido no planejamento.
- **Índice GUT** é calculado automaticamente; a análise de risco (prioridade 1–3) pode ser sugerida pelo sistema com base no índice, mas a seleção final cabe ao servidor.
- Os campos de localização, sub-localização, item de verificação, grupo técnico e requisito afetado podem ser listas predefinidas com opção de texto livre para novos valores; isso será definido no planejamento.
