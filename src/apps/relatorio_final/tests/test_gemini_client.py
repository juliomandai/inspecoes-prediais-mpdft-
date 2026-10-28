import pytest
from apps.relatorio_final import gemini_client


def test_sem_api_key_retorna_campos_vazios(settings):
    settings.GEMINI_API_KEY = ''
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos == dict(gemini_client.CAMPOS_VAZIOS)
    assert textos['sumario_executivo'] == ''


def test_falha_na_chamada_retorna_campos_vazios_sem_lancar(settings, monkeypatch):
    settings.GEMINI_API_KEY = 'fake-key'

    class ClienteQuebrado:
        def __init__(self, *a, **kw):
            raise RuntimeError('API fora do ar')

    monkeypatch.setattr(gemini_client.genai, 'Client', ClienteQuebrado)
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos == dict(gemini_client.CAMPOS_VAZIOS)


def test_chamada_bem_sucedida_retorna_textos_do_schema(settings, monkeypatch):
    settings.GEMINI_API_KEY = 'fake-key'
    valores = {campo: f'Texto de {campo}.' for campo in gemini_client.TextosRelatorioFinal.model_fields}
    valores['manutencao_classificacao'] = 'Atende integralmente'
    valores['uso_classificacao'] = 'Regular, com ressalvas'
    resposta_json = gemini_client.TextosRelatorioFinal(**valores).model_dump_json()

    class InteractionFake:
        output_text = resposta_json

    class InteractionsFake:
        def create(self, **kwargs):
            return InteractionFake()

    class ClienteFake:
        def __init__(self, *a, **kw):
            self.interactions = InteractionsFake()

    monkeypatch.setattr(gemini_client.genai, 'Client', ClienteFake)
    textos = gemini_client.gerar_textos_relatorio({'qualquer': 'coisa'})
    assert textos['sumario_executivo'] == 'Texto de sumario_executivo.'
    assert textos['manutencao_classificacao'] == 'Atende integralmente'
