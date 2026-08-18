import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import (
    Avaliacao, AvaliacaoHistorico, CriterioAcessibilidade, LocalAcessibilidade, Regiao,
)


@pytest.fixture
def edificacao(db):
    return Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(username='ana', password='1')


@pytest.mark.django_db
def test_local_acessibilidade_str(edificacao):
    local = LocalAcessibilidade.objects.create(
        edificacao=edificacao, regiao=Regiao.SUBSOLO, nome='Rampa 01',
    )
    assert str(local) == 'Prédio Teste — Subsolo — Rampa 01'


@pytest.mark.django_db
def test_local_acessibilidade_e_unico_por_edificacao_regiao_nome(edificacao):
    LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.SUBSOLO, nome='Rampa 01')
    with pytest.raises(IntegrityError):
        LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.SUBSOLO, nome='Rampa 01')


@pytest.mark.django_db
def test_criterio_acessibilidade_nome_unico():
    CriterioAcessibilidade.objects.create(nome='Altura da bacia')
    with pytest.raises(IntegrityError):
        CriterioAcessibilidade.objects.create(nome='Altura da bacia')


@pytest.mark.django_db
def test_avaliacao_agrupa_local_e_criterio(edificacao, usuario):
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    avaliacao = Avaliacao.objects.create(
        local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario,
    )
    assert avaliacao.status_acao == Avaliacao.StatusAcao.NAO_INICIADA
    assert 'Pendente' in str(avaliacao)


@pytest.mark.django_db
def test_avaliacao_e_unica_por_local_e_criterio(edificacao, usuario):
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.OK, atualizado_por=usuario)
    with pytest.raises(IntegrityError):
        Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.OK, atualizado_por=usuario)


@pytest.mark.django_db
def test_avaliacao_historico_guarda_snapshots(edificacao, usuario):
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    avaliacao = Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.OK, atualizado_por=usuario)
    historico = AvaliacaoHistorico.objects.create(
        avaliacao=avaliacao, snapshot_anterior={'status': 'PENDENTE'}, snapshot_novo={'status': 'OK'},
        editado_por=usuario,
    )
    assert avaliacao.historico.count() == 1
    assert historico.snapshot_novo['status'] == 'OK'
