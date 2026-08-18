from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade
from apps.acessibilidade.services import aplicar_edicao

FIXTURE = Path(__file__).parent / 'fixtures' / 'painel_teste.json'


@pytest.fixture
def usuario_sistema(db):
    return get_user_model().objects.create_user(username='sistema', password='1')


@pytest.mark.django_db
def test_importa_edificacao_local_criterio_e_avaliacoes(usuario_sistema):
    call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='sistema')

    edificacao = Edificacao.objects.get(sigla='TEST')
    local = LocalAcessibilidade.objects.get(edificacao=edificacao, nome='Sanitário Acessível')
    assert CriterioAcessibilidade.objects.count() == 2
    assert Avaliacao.objects.count() == 2

    avaliacao_ok = Avaliacao.objects.get(local=local, criterio__nome='Altura da bacia')
    assert avaliacao_ok.status == Avaliacao.Status.OK
    assert avaliacao_ok.resolucao_diagnostico == ''

    avaliacao_pendente = Avaliacao.objects.get(local=local, criterio__nome='Barra de apoio')
    assert avaliacao_pendente.status == Avaliacao.Status.PENDENTE
    assert avaliacao_pendente.resolucao_diagnostico == 'Manutenção Predial'
    assert avaliacao_pendente.observacao == 'falta instalar barra'
    assert 'barras de apoio devem suportar' in avaliacao_pendente.criterio.base_legal


@pytest.mark.django_db
def test_importacao_e_idempotente(usuario_sistema):
    call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='sistema')
    assert Avaliacao.objects.count() == 2

    # Uma edição manual feita entre as duas cargas não pode ser sobrescrita
    # por um rerun — get_or_create só aplica `defaults` na criação.
    editada = Avaliacao.objects.get(criterio__nome='Altura da bacia')
    aplicar_edicao(editada, {'observacao': 'edição manual pós-carga'}, usuario_sistema)

    call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='sistema')
    assert Avaliacao.objects.count() == 2
    editada.refresh_from_db()
    assert editada.observacao == 'edição manual pós-carga'


@pytest.mark.django_db
def test_falha_com_mensagem_clara_se_usuario_nao_existe(db):
    from django.core.management.base import CommandError
    with pytest.raises(CommandError):
        call_command('importar_painel_acessibilidade', arquivo=str(FIXTURE), usuario='nao-existe')


@pytest.mark.django_db
def test_falha_com_mensagem_clara_se_status_desconhecido(tmp_path, usuario_sistema):
    import json
    from django.core.management.base import CommandError

    dados = json.loads(FIXTURE.read_text(encoding='utf-8'))
    dados['status'] = ['Não se aplica', 'OK', 'Status Inexistente']
    dados['rows'][0][5] = 2  # aponta para o status desconhecido
    arquivo = tmp_path / 'painel_status_invalido.json'
    arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')

    with pytest.raises(CommandError):
        call_command('importar_painel_acessibilidade', arquivo=str(arquivo), usuario='sistema')
