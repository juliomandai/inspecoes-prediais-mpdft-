"""Testes unitários diretos para `_montar_contexto_docx` e
`_dividir_em_ate_n_paragrafos` (views.py) — apontados pela revisão de
qualidade da Task 11 como cobertos só indiretamente pelo teste de integração
`test_relatorio_final_gerar_produz_docx` (que confirma apenas a ausência de
placeholders `{{ }}`/`{% %}` residuais, não que os VALORES calculados estão
corretos)."""
import pytest
from datetime import date

from apps.edificacoes.models import Edificacao, Profissional
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.inspecoes.views import _dividir_em_ate_n_paragrafos, _montar_contexto_docx


# ── _dividir_em_ate_n_paragrafos ────────────────────────────────────────────

def test_dividir_texto_vazio_retorna_n_strings_vazias():
    assert _dividir_em_ate_n_paragrafos('', 3) == ['', '', '']


def test_dividir_menos_paragrafos_que_n_preenche_resto_com_vazio():
    resultado = _dividir_em_ate_n_paragrafos('Único parágrafo.', 3)
    assert resultado == ['Único parágrafo.', '', '']


def test_dividir_exatamente_n_paragrafos_preserva_ordem():
    texto = 'Primeiro parágrafo.\n\nSegundo parágrafo.\n\nTerceiro parágrafo.'
    resultado = _dividir_em_ate_n_paragrafos(texto, 3)
    assert resultado == ['Primeiro parágrafo.', 'Segundo parágrafo.', 'Terceiro parágrafo.']


def test_dividir_mais_paragrafos_que_n_concatena_excedente_no_ultimo_slot():
    """Comportamento documentado: parágrafos excedentes (mais que `n`) são
    concatenados (com '\\n\\n') no último slot, nunca descartados."""
    texto = 'Um.\n\nDois.\n\nTrês.\n\nQuatro.'
    resultado = _dividir_em_ate_n_paragrafos(texto, 2)
    assert resultado == ['Um.', 'Dois.\n\nTrês.\n\nQuatro.']
    assert len(resultado) == 2
    # nenhum parágrafo foi descartado
    assert 'Dois.' in resultado[-1]
    assert 'Três.' in resultado[-1]
    assert 'Quatro.' in resultado[-1]


# ── _montar_contexto_docx ────────────────────────────────────────────────────

def _prof(nome, crea):
    return Profissional.objects.create(nome=nome, crea=crea)


@pytest.fixture
def inspecao_minima(db):
    """Civil e Elétrica com profissionais DIFERENTES e conhecidos — serve
    para detectar troca de especialidade em `profissional_principal`."""
    edif = Edificacao.objects.create(nome='Sede Teste', endereco='Rua X, 1', descritivo='Prédio teste')
    insp = Inspecao.objects.create(edificacao=edif)
    civil = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', data_inspecao=date.today(), conclusao='Conclusão civil.',
    )
    civil.profissionais.set([_prof('Ana Civil', 'CREA-111/D-DF')])
    eletrica = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='eletrica', data_inspecao=date.today(), conclusao='Conclusão elétrica.',
    )
    eletrica.profissionais.set([_prof('Beto Eletrica', 'CREA-222/D-DF')])
    return insp, civil, eletrica


def _textos_fake():
    """Fake estruturalmente correto do dict `textos` (saída do Gemini) —
    mesmas chaves que `_montar_contexto_docx` acessa diretamente."""
    return {
        'sumario_executivo': 'Resumo executivo.',
        'principais_constatacoes': '',
        'resultados_gerais_intro': '',
        'resultados_gerais_achados_criticos': '',
        'itens_conformidade_civil': '',
        'itens_conformidade_eletrica': '',
        'itens_conformidade_mecanica': '',
        'conclusao': '',
        'providencias_administracao': '',
        'manutencao_classificacao': '',
        'manutencao_fundamentacao': '',
        'uso_classificacao': '',
        'uso_fundamentacao': '',
    }


def _painel_fake(por_especialidade, matriz_risco_prazo):
    """Fake estruturalmente correto do dict `painel` (painel de
    encerramento) — só as chaves que `_montar_contexto_docx` lê."""
    return {
        'resumo_especialidade': {'por_especialidade': por_especialidade},
        'por_direcionamento': [],
        'matriz_risco_prazo': matriz_risco_prazo,
        'n_ganhos_rapidos': 0,
        'iqe': 70, 'iqe_faixa': 'Regular', 'total': 10,
        'pct_conformidade': 70, 'total_conformes': 7, 'total_nc': 3,
        'p1_total': 1, 'p2_total': 1, 'p3_total': 1, 'gut_media': 10.0,
    }


def _snapshot_fake():
    return {'datas_vistorias': ['01/01'], 'anexo01': []}


@pytest.mark.django_db
def test_montar_contexto_calcula_pct_conformidade_por_especialidade(inspecao_minima):
    insp, civil, eletrica = inspecao_minima
    por_especialidade = [
        {'especialidade_nome': 'Engenharia Civil', 'total': 10, 'total_nc': 3, 'p1': 1, 'p2': 1, 'p3': 1},
        {'especialidade_nome': 'Engenharia Elétrica', 'total': 5, 'total_nc': 5, 'p1': 5, 'p2': 0, 'p3': 0},
    ]
    painel = _painel_fake(por_especialidade, matriz_risco_prazo=[])

    contexto = _montar_contexto_docx(
        insp, _snapshot_fake(), painel, [civil, eletrica], [], _textos_fake(), [],
    )

    assert contexto['civil_total'] == 10
    assert contexto['civil_nc'] == 3
    assert contexto['civil_pct_conf'] == 70  # round((10-3)/10*100)
    assert contexto['civil_p1'] == 1 and contexto['civil_p2'] == 1 and contexto['civil_p3'] == 1

    assert contexto['eletrica_total'] == 5
    assert contexto['eletrica_nc'] == 5
    assert contexto['eletrica_pct_conf'] == 0  # round((5-5)/5*100)

    # Mecânica não aparece no painel nem tem especialidade cadastrada —
    # deve cair no default seguro (tudo zero), não quebrar nem herdar
    # números de outra especialidade.
    assert contexto['mecanica_total'] == 0
    assert contexto['mecanica_nc'] == 0
    assert contexto['mecanica_pct_conf'] == 0


@pytest.mark.django_db
def test_montar_contexto_matriz_risco_prazo_mantem_linha_e_coluna(inspecao_minima):
    insp, civil, eletrica = inspecao_minima
    matriz_fake = [
        {'prioridade': 1, 'celulas': [{'prazo': 1, 'qtd': 2, 'tipo': ''}, {'prazo': 3, 'qtd': 0, 'tipo': ''}]},
        {'prioridade': 2, 'celulas': [{'prazo': 1, 'qtd': 0, 'tipo': ''}, {'prazo': 3, 'qtd': 5, 'tipo': ''}]},
        {'prioridade': 3, 'celulas': [{'prazo': 1, 'qtd': 1, 'tipo': ''}, {'prazo': 3, 'qtd': 1, 'tipo': ''}]},
    ]
    painel = _painel_fake([], matriz_fake)

    contexto = _montar_contexto_docx(
        insp, _snapshot_fake(), painel, [civil, eletrica], [], _textos_fake(), [],
    )

    linhas = contexto['matriz_risco_prazo']
    assert len(linhas) == 3

    # Linha P1: qtd=2 no 1º prazo, 0 (exibido como '—') no 2º — total 2.
    assert linhas[0]['rotulo'].startswith('P1')
    assert 'Crítico' in linhas[0]['rotulo']
    assert linhas[0]['celulas'] == [2, '—']
    assert linhas[0]['total'] == 2

    # Linha P2: 0 (—) no 1º prazo, 5 no 2º — total 5. Confirma que a
    # coluna/linha de P1 não "vazou" para P2.
    assert linhas[1]['rotulo'].startswith('P2')
    assert 'Regular' in linhas[1]['rotulo']
    assert linhas[1]['celulas'] == ['—', 5]
    assert linhas[1]['total'] == 5

    # Linha P3: 1 e 1 — total 2.
    assert linhas[2]['rotulo'].startswith('P3')
    assert 'Mínimo' in linhas[2]['rotulo']
    assert linhas[2]['celulas'] == [1, 1]
    assert linhas[2]['total'] == 2


@pytest.mark.django_db
def test_montar_contexto_profissional_principal_nao_troca_especialidade(inspecao_minima):
    insp, civil, eletrica = inspecao_minima
    painel = _painel_fake([], [])

    contexto = _montar_contexto_docx(
        insp, _snapshot_fake(), painel, [civil, eletrica], [], _textos_fake(), [],
    )

    assert contexto['nome_civil'] == 'Ana Civil'
    assert contexto['crea_civil'] == 'CREA-111/D-DF'
    assert contexto['nome_eletrica'] == 'Beto Eletrica'
    assert contexto['crea_eletrica'] == 'CREA-222/D-DF'

    # Mecânica não foi cadastrada nesta inspeção — placeholder, nunca os
    # dados de civil/elétrica.
    assert contexto['nome_mecanica'] == '[nome]'
    assert contexto['crea_mecanica'] == '[CREA]'
