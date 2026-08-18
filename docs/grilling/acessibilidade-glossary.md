# Glossário — Módulo de Acessibilidade

Termos confirmados durante a sessão de grilling (`/grill-with-docs`, 2026-08-18).
Cada termo: definição de uma frase + pergunta que o resolveu.

| Termo | Definição | Resolvido em |
|---|---|---|
| Localidade | Uma das 13 edificações cobertas pelo diagnóstico (BSBI, BSBII, PJBZ...). É a mesma entidade `Edificacao` já cadastrada na plataforma de inspeções, identificada por um código-sigla. | P1 — [[ADR-01]] |
| Região | Subdivisão física de uma edificação (ex. SUBSOLO, TÉRREO, PAVIMENTO 01). | leitura do HTML |
| Local | Ponto específico de instalação dentro de uma região (ex. "Rampa 01", "Sanitário Acessível Feminino"). | leitura do HTML |
| Item (de checklist) | Um critério normativo avaliado num local específico (ex. "Altura da bacia"), com status OK/Pendente/Não se aplica. NÃO é um `Achado` — é um domínio de conformidade normativa separado. | P2 — [[ADR-02]] |
| Status (do item) | Resultado da avaliação: OK, Pendente, ou Não se aplica. | leitura do HTML |
| Resolução (diagnosticada) | Quando o item está Pendente, a forma de correção diagnosticada: Contratação, Manutenção Predial, ou Outro. | leitura do HTML |
| Plano de ação | Acompanhamento da remediação de um item Pendente: status da ação (não iniciada/em andamento/concluída), responsável, prazo, ordem de serviço, notas. Fundido num único "editar item" junto com a correção de diagnóstico (não são mais camadas separadas). | P4 — [[ADR-04]] |
| Histórico de edição | Registro imutável de cada alteração feita num item (quem, quando, de/para) — obrigatório, não apenas o último estado. | P5 — [[ADR-05]] |
