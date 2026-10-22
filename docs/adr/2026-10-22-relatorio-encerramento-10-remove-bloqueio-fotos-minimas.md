# ADR-10: Remove o bloqueio de geração por achado não conforme com menos de 2 fotos

## Status
Aceita (2026-10-22)

## Contexto
[ADR-05](2026-10-06-relatorio-encerramento-05-bloqueio-fotos-minimas.md) fazia
`Inspecao.pendencias_relatorio_final()` bloquear a geração do relatório
sempre que algum achado não conforme (`gut_total > 0`) tivesse menos de 2
fotos ativas. Na prática isso travava inspeções inteiras entre "3
especialidades finalizadas" e "relatório gerável" por causa de fotos
faltantes em achados antigos, sem uma forma simples de destravar (a própria
ADR-05 já registrava essa consequência como pergunta em aberto).

O usuário pediu explicitamente que a quantidade de fotos por achado deixe de
ser considerada pendência para liberar a geração.

## Decisão
`pendencias_relatorio_final()` não verifica mais a quantidade de fotos dos
achados. As demais invariantes continuam valendo: as 3 especialidades
obrigatórias finalizadas (ADR-04), descritivo da edificação preenchido
(ADR-08) e conclusão de cada especialidade preenchida (ADR-09).

A seleção de fotos para o PDF (até 2 fotos mais antigas por achado não
conforme, `_montar_snapshot_relatorio`) não muda — se o achado tiver 0 ou 1
foto, o relatório simplesmente mostra o que houver (ou nenhuma foto) para
aquele achado.

## Consequências
- Um relatório pode ser gerado com achados não conformes sem fotos
  (ou com só 1), já que isso não é mais uma pendência.
- Simplifica `pendencias_relatorio_final()` — remove a verificação por achado
  e a mensagem agregada de "achados com menos de 2 fotos".
