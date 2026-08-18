import pytest
from django.contrib.auth import get_user_model

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao
from apps.acessibilidade.services import aplicar_edicao, aplicar_edicao_lote


@pytest.fixture
def avaliacao(db):
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    return Avaliacao.objects.create(
        local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario,
    )


@pytest.mark.django_db
def test_aplicar_edicao_atualiza_campos_e_autor(avaliacao):
    novo_usuario = get_user_model().objects.create_user(username='joao', password='1')
    aplicar_edicao(avaliacao, {'status': Avaliacao.Status.OK, 'responsavel': 'João'}, novo_usuario)
    avaliacao.refresh_from_db()
    assert avaliacao.status == Avaliacao.Status.OK
    assert avaliacao.responsavel == 'João'
    assert avaliacao.atualizado_por == novo_usuario


@pytest.mark.django_db
def test_aplicar_edicao_cria_historico_com_snapshots(avaliacao):
    usuario = avaliacao.atualizado_por
    aplicar_edicao(avaliacao, {'status': Avaliacao.Status.OK}, usuario)
    historico = avaliacao.historico.get()
    assert historico.snapshot_anterior['status'] == 'PENDENTE'
    assert historico.snapshot_novo['status'] == 'OK'
    assert historico.editado_por == usuario


@pytest.mark.django_db
def test_aplicar_edicao_ignora_campos_nao_editaveis(avaliacao):
    aplicar_edicao(avaliacao, {'local_id': 999999}, avaliacao.atualizado_por)
    avaliacao.refresh_from_db()
    assert avaliacao.local_id != 999999


@pytest.mark.django_db
def test_aplicar_edicao_lote_cria_um_historico_por_avaliacao(avaliacao, db):
    edificacao = avaliacao.local.edificacao
    criterio2 = CriterioAcessibilidade.objects.create(nome='Outro critério')
    avaliacao2 = Avaliacao.objects.create(
        local=avaliacao.local, criterio=criterio2, status=Avaliacao.Status.PENDENTE,
        atualizado_por=avaliacao.atualizado_por,
    )
    aplicar_edicao_lote([avaliacao, avaliacao2], {'status_acao': Avaliacao.StatusAcao.EM_ANDAMENTO}, avaliacao.atualizado_por)
    avaliacao.refresh_from_db()
    avaliacao2.refresh_from_db()
    assert avaliacao.status_acao == Avaliacao.StatusAcao.EM_ANDAMENTO
    assert avaliacao2.status_acao == Avaliacao.StatusAcao.EM_ANDAMENTO
    assert avaliacao.historico.count() == 1
    assert avaliacao2.historico.count() == 1
