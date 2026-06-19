"""Testes unitários dos sub-cálculos de _analise_data — sem DB, sem request.

Cada função é testada isoladamente, com instâncias de Achado em memória
(nunca salvas). Isso só é possível porque nenhuma delas acessa relações de
banco (FK) — a exceção é _cobertura_fotos, que precisa de Achado salvo
com Fotos relacionadas (tem seu próprio teste com @pytest.mark.django_db).
"""
import json
import pytest
from apps.inspecoes.models import Achado, InspecaoEspecialidade
from apps.inspecoes.views import (
    _achados_por_direcionamento,
    _componentes_gut_medios,
    _estatisticas_gut,
    _iqe_score,
    _matriz_risco_prazo,
    _montar_charts,
    _plano_acao,
    _por_direcionamento,
    _por_grupo_tecnico,
    _por_localizacao,
    _por_prazo,
    _por_requisito,
    _analise_data,
)


def achado(**kwargs):
    defaults = dict(
        localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=1, tendencia=1,
        prioridade_risco=3, direcionamento='manutencao', prazo_meses=12,
        gut_total=1,
    )
    defaults.update(kwargs)
    return Achado(**defaults)


def test_achados_por_direcionamento_separa_por_categoria_e_prioridade():
    a1 = achado(direcionamento='manutencao', prioridade_risco=1)
    a2 = achado(direcionamento='manutencao', prioridade_risco=2)
    a3 = achado(direcionamento='garantia', prioridade_risco=1)
    manut, nova, garantia = _achados_por_direcionamento([a1, a2, a3])
    assert manut['p1'] == [a1]
    assert manut['p2'] == [a2]
    assert nova == {'p1': [], 'p2': [], 'p3': []}
    assert garantia['p1'] == [a3]


def test_por_grupo_tecnico_grupos_e_pareto_compartilham_acumulado():
    a1 = achado(grupo_tecnico='estrutura', prioridade_risco=1)
    a2 = achado(grupo_tecnico='estrutura', prioridade_risco=2)
    a3 = achado(grupo_tecnico='cobertura', prioridade_risco=3)
    grupos, pareto = _por_grupo_tecnico([a1, a2, a3], total_nc=3)
    assert {g['grupo_tecnico']: g['total'] for g in grupos} == {'estrutura': 2, 'cobertura': 1}
    # pareto ordena por total desc e acumula — mesmo mapa, ordens diferentes.
    assert pareto[0]['grupo_tecnico'] == 'estrutura'
    assert pareto[0]['acumulado'] == 2
    assert pareto[0]['acumulado_pct'] == round(2 / 3 * 100)
    assert pareto[1]['acumulado'] == 3
    assert pareto[1]['acumulado_pct'] == 100


def test_estatisticas_gut_media_max_min_desvio():
    achados = [achado(gut_total=10), achado(gut_total=20), achado(gut_total=30)]
    stats = _estatisticas_gut(achados)
    assert stats['media'] == 20.0
    assert stats['max'] == 30
    assert stats['min'] == 10
    assert stats['desvio'] == round((((10-20)**2 + (20-20)**2 + (30-20)**2) / 3) ** 0.5, 1)


def test_estatisticas_gut_top_inclui_gut_pct_relativo_ao_maior():
    achados = [achado(gut_total=50), achado(gut_total=25)]
    stats = _estatisticas_gut(achados)
    top = {a.gut_total: a.gut_pct for a in stats['top']}
    assert top[50] == 100
    assert top[25] == 50


def test_estatisticas_gut_lista_vazia_nao_quebra():
    stats = _estatisticas_gut([])
    assert stats == {'media': 0, 'max': 0, 'min': 0, 'desvio': 0, 'top': []}


def test_por_localizacao_contagem_e_soma_gut_compartilham_mapa():
    a1 = achado(localizacao='Sede', gut_total=10, prioridade_risco=1)
    a2 = achado(localizacao='Sede', gut_total=20, prioridade_risco=2)
    a3 = achado(localizacao='Anexo', gut_total=5, prioridade_risco=3)
    por_loc, por_loc_gut = _por_localizacao([a1, a2, a3])

    sede = next(l for l in por_loc if l['localizacao'] == 'Sede')
    assert sede['total'] == 2 and sede['p1'] == 1 and sede['p2'] == 1

    assert por_loc_gut[0]['localizacao'] == 'Sede'
    assert por_loc_gut[0]['soma_gut'] == 30
    assert por_loc_gut[0]['gut_pct'] == 100
    assert por_loc_gut[1]['gut_pct'] == round(5 / 30 * 100)
    # mesmo dict por localização nas duas visões (identidade, não só igualdade).
    assert sede is por_loc_gut[0]


def test_por_prazo_ordenado_por_prazo_crescente():
    a1 = achado(prazo_meses=12)
    a2 = achado(prazo_meses=1)
    resultado = _por_prazo([a1, a2])
    assert [p['prazo'] for p in resultado] == [1, 12]


def test_por_requisito_inclui_todos_os_requisitos_mesmo_zerados():
    a1 = achado(requisito_afetado='durabilidade')
    resultado = _por_requisito([a1])
    chaves = {r['requisito'] for r in resultado}
    assert chaves == set(dict(Achado.REQUISITO_CHOICES))
    assert next(r for r in resultado if r['requisito'] == 'durabilidade')['total'] == 1
    assert next(r for r in resultado if r['requisito'] == 'estetica')['total'] == 0


@pytest.mark.parametrize('total, total_conformes, n_p1, n_p2, n_p3, iqe_esperado, faixa', [
    (10, 10, 0, 0, 0, 100, 'Bom'),     # tudo conforme
    (10, 0, 10, 0, 0, 0, 'Crítico'),   # tudo P1
    (0, 0, 0, 0, 0, 100, 'Bom'),       # sem achados
])
def test_iqe_score_extremos(total, total_conformes, n_p1, n_p2, n_p3, iqe_esperado, faixa):
    info = _iqe_score(total, total_conformes, [0] * n_p1, [0] * n_p2, [0] * n_p3)
    assert info['iqe'] == iqe_esperado
    assert info['faixa'] == faixa


def test_componentes_gut_medios():
    achados = [achado(gravidade=1, urgencia=2, tendencia=3), achado(gravidade=5, urgencia=4, tendencia=3)]
    g, u, t = _componentes_gut_medios(achados, total_nc=2)
    assert (g, u, t) == (3.0, 3.0, 3.0)


def test_componentes_gut_medios_sem_achados():
    assert _componentes_gut_medios([], total_nc=0) == (0, 0, 0)


def test_matriz_risco_prazo_marca_incoerencia_e_ganho_rapido():
    p1_prazo_longo = achado(prioridade_risco=1, prazo_meses=24)   # incoerência
    p1_prazo_curto = achado(prioridade_risco=1, prazo_meses=1)    # ganho rápido
    matriz, labels, n_incoerencias, n_ganhos = _matriz_risco_prazo([p1_prazo_longo, p1_prazo_curto])
    assert n_incoerencias == 1
    assert n_ganhos == 1
    celula_p1_24 = next(c for c in matriz[0]['celulas'] if c['prazo'] == 24)
    assert celula_p1_24['tipo'] == 'incoerencia'


def test_por_direcionamento_calcula_percentual():
    a1 = achado(direcionamento='manutencao')
    a2 = achado(direcionamento='manutencao')
    a3 = achado(direcionamento='garantia')
    resultado = _por_direcionamento([a1, a2, a3], total_nc=3)
    manut = next(d for d in resultado if d['key'] == 'manutencao')
    assert manut['total'] == 2
    assert manut['pct'] == round(2 / 3 * 100)


def test_plano_acao_ordena_por_prioridade_depois_gut_desc():
    baixa_prio_alto_gut = achado(prioridade_risco=3, gut_total=100)
    alta_prio_baixo_gut = achado(prioridade_risco=1, gut_total=5)
    resultado = _plano_acao([baixa_prio_alto_gut, alta_prio_baixo_gut])
    assert resultado == [alta_prio_baixo_gut, baixa_prio_alto_gut]


def test_montar_charts_serializa_json_consistente_com_as_metricas():
    por_direcionamento = [{'label': 'Manutenção', 'total': 2}]
    pareto = [{'nome': 'Estrutura', 'total': 2, 'acumulado_pct': 100}]
    por_prazo = [{'label': '12 meses', 'total': 2}]
    por_requisito = [{'label': 'Durabilidade', 'total': 2, 'color': '#7B2D00'}]
    charts = _montar_charts([1], [2, 2], [], por_direcionamento, pareto, por_prazo, por_requisito)
    assert json.loads(charts['risco'])['data'] == [1, 2, 0]
    assert json.loads(charts['direcionamento'])['labels'] == ['Manutenção']
    assert json.loads(charts['pareto'])['acumulado'] == [100]


@pytest.mark.django_db
def test_analise_data_integra_tudo_e_mantem_as_chaves_do_dict():
    insp_esp_fields = dict(profissional='X', data_inspecao='2026-01-01', especialidade='civil')
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao
    edif = Edificacao.objects.create(nome='Sede X')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(inspecao=insp, **insp_esp_fields)
    a1 = Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=5, urgencia=5, tendencia=5, prioridade_risco=1,
    )
    conforme = Achado.objects.create(
        especialidade=esp, localizacao='L2', verificacao='OK', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True,
    )
    dados = _analise_data([a1, conforme])
    assert dados['total'] == 2
    assert dados['total_nc'] == 1
    assert dados['total_conformes'] == 1
    assert dados['iqe'] == 50  # penalidade 5 (1×P1) sobre total=2: 100*(1 - 5/(5*2))
    assert dados['plano_acao'] == [a1]
    assert json.loads(dados['chart_risco'])['data'] == [1, 0, 0]
