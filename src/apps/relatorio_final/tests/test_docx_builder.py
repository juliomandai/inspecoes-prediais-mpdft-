import io
import pytest
from docx import Document
from apps.relatorio_final.docx_builder import gerar_docx_relatorio


def _contexto_minimo():
    return {
        'edificacao_nome': 'Sede Teste', 'edificacao_endereco': 'Rua Teste, 123',
        'datas_vistorias': '01/01/2026', 'mes_geracao': 'janeiro', 'ano_atual': '2026',
        'area_construida': '1.000,00 m²', 'pavimentos': 'Dois pavimentos',
        'data_inauguracao_extenso': '1 de janeiro de 2020',
        'equipe_tecnica': 'Fulano, engenheiro civil',
        'responsabilidade_tecnica': 'ART civil nº 123',
        'caracterizacao_edificacao': 'Texto de caracterização de teste.',
        'sumario_executivo': 'Resumo de teste.',
        'principais_constatacoes_1': 'C1.', 'principais_constatacoes_2': 'C2.', 'principais_constatacoes_3': 'C3.',
        'providencias_administracao_1': 'P1.', 'providencias_administracao_2': 'P2.',
        'resultados_gerais_intro_1': 'R1.', 'resultados_gerais_intro_2': 'R2.',
        'resultados_gerais_achados_criticos': 'Achados críticos de teste.',
        'n_ganhos_rapidos': 0,
        'itens_conformidade_civil': 'Conforme civil.', 'itens_conformidade_eletrica': 'Conforme elétrica.',
        'itens_conformidade_mecanica': 'Conforme mecânica.',
        'conclusao_civil': 'Conclusão civil de teste.', 'conclusao_eletrica': 'Conclusão elétrica de teste.',
        'conclusao_mecanica': 'Conclusão mecânica de teste.',
        'conclusao_1': 'Conclusão 1.', 'conclusao_2': 'Conclusão 2.',
        'iqe': 90, 'iqe_faixa': 'Bom', 'total': 10, 'pct_conformidade': 80,
        'total_conformes': 8, 'total_nc': 2, 'p1_total': 1, 'p2_total': 1, 'p3_total': 0,
        'gut_media': '20,0',
        'direcionamento_manutencao_total': 1, 'direcionamento_manutencao_pct': 50,
        'direcionamento_nova_contratacao_total': 1, 'direcionamento_nova_contratacao_pct': 50,
        'direcionamento_garantia_total': 0, 'direcionamento_garantia_pct': 0,
        'manutencao_classificacao': 'Atende integralmente', 'manutencao_fundamentacao': 'Fundamentação manutenção.',
        'uso_classificacao': 'Regular', 'uso_fundamentacao': 'Fundamentação uso.',
        'condicao_global': 'Boa',
        'civil_total': 5, 'civil_nc': 1, 'civil_pct_conf': 80, 'civil_p1': 1, 'civil_p2': 0, 'civil_p3': 0,
        'eletrica_total': 3, 'eletrica_nc': 1, 'eletrica_pct_conf': 67, 'eletrica_p1': 0, 'eletrica_p2': 1, 'eletrica_p3': 0,
        'mecanica_total': 2, 'mecanica_nc': 0, 'mecanica_pct_conf': 100, 'mecanica_p1': 0, 'mecanica_p2': 0, 'mecanica_p3': 0,
        'matriz_risco_prazo': [
            {'rotulo': 'P1 – Crítico', 'celulas': ['1', '—', '—', '—', '—'], 'total': 1},
            {'rotulo': 'P2 – Regular', 'celulas': ['—', '1', '—', '—', '—'], 'total': 1},
        ],
        'top_gut': [
            {'numero': 1, 'local': 'Subsolo', 'nao_conformidade': 'Teste', 'recomendacao': 'Corrigir', 'gut': 60, 'prazo': '1 mês'},
        ],
        'historico_intervencoes': [{'ano': 2022, 'descricao': 'Troca de teste'}],
        'plano_de_acao': [
            {'horizonte': 'Imediato (até 1 mês)', 'nc': 1, 'principais_acoes': 'Corrigir X.', 'forma_execucao': 'Manutenção'},
            {'horizonte': 'Curto prazo (3 meses)', 'nc': 0, 'principais_acoes': '—', 'forma_execucao': '—'},
            {'horizonte': 'Médio prazo (6 meses)', 'nc': 0, 'principais_acoes': '—', 'forma_execucao': '—'},
            {'horizonte': 'Longo prazo (12 a 24 meses)', 'nc': 1, 'principais_acoes': 'Corrigir Y.', 'forma_execucao': 'Nova contratação'},
        ],
        'nome_civil': 'Fulano', 'titulo_civil': 'Engenheiro civil', 'crea_civil': '111/D-DF',
        'nome_eletrica': 'Cicrano', 'titulo_eletrica': 'Engenheiro eletricista', 'crea_eletrica': '222/D-DF',
        'nome_mecanica': 'Beltrano', 'titulo_mecanica': 'Engenheiro mecânico', 'crea_mecanica': '333/D-DF',
        'nome_secretaria_spo': 'Nome de Teste',
        'anexo01': [
            {'numero': 1, 'local': 'Subsolo', 'sistema_elemento': 'Estrutura', 'situacao': 'Conforme',
             'nao_conformidade': '—', 'recomendacao': '—', 'grau_risco': '—', 'gut': '—', 'prazo': '—'},
        ],
    }


def _texto_completo(doc):
    """Extrai todo o texto do documento, incluindo o que está dentro de
    tabelas (ex.: a capa do laudo é montada como tabela de layout) —
    doc.paragraphs por si só só enxerga parágrafos de nível superior."""
    textos = [p.text for p in doc.paragraphs]

    def _percorrer_tabela(tabela):
        for linha in tabela.rows:
            for celula in linha.cells:
                textos.extend(p.text for p in celula.paragraphs)
                for subtabela in celula.tables:
                    _percorrer_tabela(subtabela)

    for tabela in doc.tables:
        _percorrer_tabela(tabela)
    return '\n'.join(textos)


def test_gerar_docx_relatorio_produz_docx_valido():
    conteudo = gerar_docx_relatorio(_contexto_minimo())
    assert isinstance(conteudo, bytes)
    doc = Document(io.BytesIO(conteudo))
    texto_completo = _texto_completo(doc)
    assert 'Sede Teste' in texto_completo
    assert '{{' not in texto_completo  # nenhum marcador sobrou sem substituir
    tabela_anexo = doc.tables[15]
    assert tabela_anexo.rows[1].cells[1].text == 'Subsolo'
