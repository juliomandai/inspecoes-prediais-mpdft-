# Glossário — Relatório de Encerramento de Inspeção (ART/CREA)

Termos confirmados durante a sessão de grilling (`/grill-with-docs`, 2026-10-06).
Cada termo: definição de uma frase + pergunta que o resolveu.

| Termo | Definição | Resolvido em |
|---|---|---|
| Laudo (agregado) | PDF já existente (`inspecao_analise_pdf`), com estatísticas agregadas (Pareto, GUT, contagens) — não lista achados individualmente, não é o documento desta sessão. | P1 — [[ADR-01]] |
| Relatório Final de Inspeção | Documento novo e distinto do laudo agregado: itemiza cada achado com fotos e termina em blocos de assinatura, para instruir a ART junto ao CREA. Nome oficial do documento (UI, arquivo gerado, código). | P1 — [[ADR-01]] |
| Engenheiro responsável (assinante) | Todo profissional listado em `InspecaoEspecialidade.profissional` daquela especialidade — não um cargo distinto. Se a especialidade tem 2 nomes, os 2 assinam o bloco daquela especialidade. Sem número de CREA no documento (fica só no protocolo da ART em si). | P1 |
| RelatorioFinalInspecao (entidade) | Registro persistido e versionado de uma geração do Relatório Final de Inspeção: quando, por quem, o PDF gerado e um snapshot estruturado (JSON) dos achados/fotos usados naquele momento. Gerar de novo cria uma nova versão, não sobrescreve. Identidade = id técnico + `numero_versao` sequencial por inspeção (exibido no documento/UI). | P4 — [[ADR-03]] |
| Entrada completa (achado não conforme) | Listagem no relatório com localização, verificação, descrição da não conformidade, GUT, prioridade, recomendação e mínimo 2 fotos. Só para achados com `gut_total > 0`. | P5 |
| Entrada resumida (achado conforme) | Linha única (localização + verificação + "conforme") para achados com `gut_total == 0` — sem exigência de foto, mantém o relatório enxuto. | P5 |
| Permissão de geração | Pode gerar o relatório de uma inspeção quem está listado em `profissional` de **pelo menos uma** das 3 especialidades daquela inspeção (ou staff/superusuário, por extensão de `_pode_editar_especialidade`) — não precisa ter participado das 3. | P5 |
| Seleção de fotos (achado com mais de 2) | Entram no relatório as 2 fotos mais antigas por `data_upload` (ordem de upload crescente) — o mínimo de 2 é um piso, extras não entram. | P5 |
| RelatorioFinalGerado (evento) | `LogAcesso` tipo novo (`relatorio_final_gerado`), registrado quando uma versão do relatório é gerada — mesmo padrão de auditoria já usado em todo o resto do sistema. Sem outro consumidor automático. | P6 |
| Descritivo da edificação | Texto livre em `Edificacao.descritivo` (idade, tipo construtivo, uso etc.) — reutilizável entre inspeções da mesma edificação, obrigatório para gerar o relatório, editável também pelos profissionais da inspeção (não só staff). | P4/5 — [[ADR-08]] |
| Conclusão (e direcionamentos) da especialidade | Texto livre narrativo em `InspecaoEspecialidade.conclusao` — um por especialidade, redigido pelo(s) profissional(is) daquela especialidade, exigido para finalizar a especialidade (não só pra gerar o relatório). Direcionamentos ficam embutidos no texto, não são um resumo computado. | P4/5 — [[ADR-09]] |
