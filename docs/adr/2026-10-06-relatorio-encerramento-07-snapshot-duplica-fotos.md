# ADR-07: Snapshot do relatório duplica os arquivos de foto usados, não só referencia

## Status
Aceita (2026-10-06, sessão de grilling)

## Contexto
O snapshot estruturado (JSON) do `RelatorioFinalInspecao` existe para
auditoria/consulta duradoura (ADR-03), mas se só referenciar `Foto` por
id/caminho, uma purga de retenção futura (`purge_old_inspecoes`, hoje
hard-delete após 180 dias) pode quebrar essas referências — mesmo com o PDF
renderizado (que embute as imagens, como o laudo já faz hoje) continuando
íntegro por conta própria.

## Decisão
Ao gerar uma versão do relatório, as fotos usadas (as 2 selecionadas por
achado não conforme — ver ADR da Seção 5, "primeiras por `data_upload`") são
duplicadas/copiadas para um armazenamento próprio do snapshot, independente
do ciclo de vida da `Foto` original. A integridade do snapshot não depende
de achados/fotos originais continuarem existindo no banco/disco.

## Consequências
- Custo adicional de armazenamento: cada geração de relatório duplica as
  imagens usadas (não é free — número de achados não conformes × 2 fotos).
- Precisa de uma rotina de cópia de arquivo na geração do relatório
  (ex. copiar para `media/relatorios/<inspecao_id>/v<numero_versao>/`), não
  apenas uma referência por FK a `Foto`.
- Soft delete e purga de retenção (`purge_old_inspecoes`) de `Foto`/`Inspecao`
  originais passam a ser irrelevantes para a integridade de um relatório já
  gerado — reforça a independência do documento legal em relação aos dados
  operacionais vivos.
