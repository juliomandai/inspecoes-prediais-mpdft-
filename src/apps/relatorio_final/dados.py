"""Dados determinísticos do Relatório Final — calculados a partir de
números/campos já existentes, SEM depender do LLM. Ver grill de
2026-10-27/28: 'Forma de execução' deixou de ser uma inferência do LLM
porque `Achado.direcionamento` já tem exatamente a informação necessária."""

from apps.inspecoes.models import Achado

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


def montar_payload_llm(especialidades, plano_por_horizonte, painel):
    """Monta o payload JSON-serializável enviado ao Gemini — SOMENTE dados
    já existentes no cadastro ou já calculados deterministicamente (regra
    de grounding do grill de 2026-10-27: o LLM nunca recebe permissão para
    inventar nada fora deste payload)."""
    grupo_labels = dict(Achado.GRUPO_TECNICO_CHOICES)
    requisito_labels = dict(Achado.REQUISITO_CHOICES)

    def achado_resumo(a):
        return {
            'localizacao': a.localizacao,
            'sub_localizacao': a.sub_localizacao,
            'verificacao': a.verificacao,
            'grupo_tecnico': grupo_labels.get(a.grupo_tecnico, a.grupo_tecnico),
            'requisito_afetado': requisito_labels.get(a.requisito_afetado, a.requisito_afetado),
            'descricao_nao_conformidade': a.descricao_nao_conformidade,
            'recomendacao': a.recomendacao,
            'prioridade_risco': a.get_prioridade_risco_display(),
            'gut_total': a.gut_total,
            'direcionamento': a.get_direcionamento_display(),
            'prazo_meses': a.prazo_meses,
        }

    payload = {'especialidades': []}
    for esp in especialidades:
        achados = list(esp.achados.all())
        nao_conformes = [a for a in achados if a.gut_total > 0]
        conformes = [a for a in achados if a.gut_total == 0]
        payload['especialidades'].append({
            'especialidade': esp.get_especialidade_display(),
            'total_verificacoes': len(achados),
            'total_nao_conformes': len(nao_conformes),
            'nao_conformes': [achado_resumo(a) for a in nao_conformes],
            'itens_conformes': [{'localizacao': a.localizacao, 'verificacao': a.verificacao} for a in conformes],
        })

    payload['painel'] = {
        'iqe': painel['iqe'], 'iqe_faixa': painel['iqe_faixa'],
        'pct_conformidade': painel['pct_conformidade'],
        'total': painel['total'], 'total_nc': painel['total_nc'], 'total_conformes': painel['total_conformes'],
        'p1_total': painel['p1_total'], 'p2_total': painel['p2_total'], 'p3_total': painel['p3_total'],
        'gut_media': painel['gut_media'], 'gut_max': painel['gut_max'], 'gut_min': painel['gut_min'],
        'por_localizacao': [
            {'localizacao': l['localizacao'], 'total': l['total'], 'p1': l['p1'], 'p2': l['p2'], 'p3': l['p3']}
            for l in painel['por_localizacao']
        ],
        'n_incoerencias': painel['n_incoerencias'], 'n_ganhos_rapidos': painel['n_ganhos_rapidos'],
    }
    payload['plano_de_acao'] = [
        {'horizonte': linha['horizonte'], 'nc': linha['nc'], 'recomendacoes': linha['recomendacoes']}
        for linha in plano_por_horizonte
    ]
    return payload
