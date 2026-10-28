import pytest
from types import SimpleNamespace
from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
from apps.relatorio_final.dados import classificar_condicao_global, montar_payload_llm, plano_acao_por_horizonte


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


@pytest.mark.django_db
def test_montar_payload_llm_inclui_apenas_dados_existentes():
    edificacao = Edificacao.objects.create(nome='Sede payload')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    Achado.objects.create(
        especialidade=esp, localizacao='Subsolo', verificacao='Estrutura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=4, urgencia=3, tendencia=3, prioridade_risco=1,
        descricao_nao_conformidade='Trinca na viga.', recomendacao='Reforçar viga.',
        direcionamento='garantia', prazo_meses=1,
    )
    Achado.objects.create(
        especialidade=esp, localizacao='Térreo', verificacao='Pintura',
        grupo_tecnico='acabamento', requisito_afetado='estetica', em_conformidade=True,
    )
    especialidades = list(inspecao.especialidades.all())
    nao_conformes = [a for esp2 in especialidades for a in esp2.achados.all() if a.gut_total > 0]
    plano = plano_acao_por_horizonte(nao_conformes)
    painel = {
        'iqe': 84, 'iqe_faixa': 'Bom', 'pct_conformidade': 50,
        'total': 2, 'total_nc': 1, 'total_conformes': 1,
        'p1_total': 1, 'p2_total': 0, 'p3_total': 0,
        'gut_media': '36,0', 'gut_max': 36, 'gut_min': 36,
        'por_localizacao': [{'localizacao': 'Subsolo', 'total': 1, 'p1': 1, 'p2': 0, 'p3': 0}],
        'n_incoerencias': 0, 'n_ganhos_rapidos': 1,
    }
    payload = montar_payload_llm(especialidades, plano, painel)
    civil = payload['especialidades'][0]
    assert civil['especialidade'] == 'Engenharia Civil'
    assert civil['total_verificacoes'] == 2
    assert civil['nao_conformes'][0]['descricao_nao_conformidade'] == 'Trinca na viga.'
    assert civil['nao_conformes'][0]['grupo_tecnico'] == 'Estrutura'
    assert civil['itens_conformes'] == [{'localizacao': 'Térreo', 'verificacao': 'Pintura'}]
    assert payload['painel']['iqe'] == 84
    assert payload['plano_de_acao'][0]['nc'] == 1
    import json
    json.dumps(payload)  # precisa ser 100% JSON-serializável
