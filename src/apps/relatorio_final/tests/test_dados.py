import pytest
from types import SimpleNamespace
from apps.relatorio_final.dados import classificar_condicao_global, plano_acao_por_horizonte


def test_classificar_condicao_global():
    assert classificar_condicao_global(84) == 'Boa'
    assert classificar_condicao_global(80) == 'Boa'
    assert classificar_condicao_global(65) == 'Regular'
    assert classificar_condicao_global(50) == 'Regular'
    assert classificar_condicao_global(30) == 'Ruim'


def _achado(prazo_meses, direcionamento, recomendacao='Corrigir X.'):
    return SimpleNamespace(prazo_meses=prazo_meses, direcionamento=direcionamento, recomendacao=recomendacao,
                            get_direcionamento_display=lambda: {
                                'garantia': 'Garantia de obra', 'manutencao': 'Manutenção', 'nova_contratacao': 'Nova contratação',
                            }[direcionamento])


def test_plano_acao_por_horizonte_agrupa_e_deriva_forma_execucao():
    achados = [
        _achado(1, 'manutencao'),
        _achado(1, 'garantia'),
        _achado(3, 'nova_contratacao'),
        _achado(12, 'manutencao'),
        _achado(24, 'nova_contratacao'),
    ]
    linhas = plano_acao_por_horizonte(achados)
    assert [l['horizonte'] for l in linhas] == [
        'Imediato (até 1 mês)', 'Curto prazo (3 meses)', 'Médio prazo (6 meses)', 'Longo prazo (12 a 24 meses)',
    ]
    imediato = linhas[0]
    assert imediato['nc'] == 2
    assert 'Garantia de obra' in imediato['forma_execucao']
    assert 'Manutenção' in imediato['forma_execucao']
    medio = linhas[2]
    assert medio['nc'] == 0
    assert medio['forma_execucao'] == '—'
    longo = linhas[3]
    assert longo['nc'] == 2
