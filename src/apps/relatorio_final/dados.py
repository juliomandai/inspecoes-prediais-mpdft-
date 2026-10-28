"""Dados determinísticos do Relatório Final — calculados a partir de
números/campos já existentes, SEM depender do LLM. Ver grill de
2026-10-27/28: 'Forma de execução' deixou de ser uma inferência do LLM
porque `Achado.direcionamento` já tem exatamente a informação necessária."""

HORIZONTES_PRAZO = [
    (1, 'Imediato (até 1 mês)'),
    (3, 'Curto prazo (3 meses)'),
    (6, 'Médio prazo (6 meses)'),
    (None, 'Longo prazo (12 a 24 meses)'),  # agrupa 12, 18 e 24 meses
]

_ORDEM_DIRECIONAMENTO = ['garantia', 'manutencao', 'nova_contratacao']


def classificar_condicao_global(iqe):
    """Mesmos limiares de `_iqe_score` em apps/inspecoes/views.py — mapeia
    o índice já calculado para o rótulo do quadro 'Avaliação da Manutenção
    e do Uso' do laudo-modelo."""
    if iqe >= 80:
        return 'Boa'
    if iqe >= 50:
        return 'Regular'
    return 'Ruim'


def plano_acao_por_horizonte(nao_conformes):
    """Agrupa achados não conformes por horizonte de prazo (quadro 'Plano
    de Ação' do laudo-modelo). `forma_execucao` vem do campo
    `direcionamento` já existente em cada achado — nunca do LLM."""
    linhas = []
    for limite, rotulo in HORIZONTES_PRAZO:
        if limite is None:
            achados = [a for a in nao_conformes if a.prazo_meses >= 12]
        else:
            achados = [a for a in nao_conformes if a.prazo_meses == limite]
        chaves_presentes = sorted({a.direcionamento for a in achados}, key=_ORDEM_DIRECIONAMENTO.index)
        rotulos_presentes = []
        for chave in chaves_presentes:
            rotulos_presentes.append(next(a.get_direcionamento_display() for a in achados if a.direcionamento == chave))
        forma_execucao = ' e '.join(rotulos_presentes) if rotulos_presentes else '—'
        linhas.append({
            'horizonte': rotulo,
            'nc': len(achados),
            'recomendacoes': [a.recomendacao for a in achados if a.recomendacao.strip()],
            'forma_execucao': forma_execucao,
        })
    return linhas
