import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def cenario(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    ontem = datetime.date.today() - datetime.timedelta(days=1)
    amanha = datetime.date.today() + datetime.timedelta(days=1)

    vencida_pendente = Avaliacao.objects.create(
        local=local, criterio=CriterioAcessibilidade.objects.create(nome='Vencida e pendente'),
        status=Avaliacao.Status.PENDENTE, prazo=ontem,
        status_acao=Avaliacao.StatusAcao.EM_ANDAMENTO, atualizado_por=usuario,
    )
    vencida_concluida = Avaliacao.objects.create(
        local=local, criterio=CriterioAcessibilidade.objects.create(nome='Vencida mas concluida'),
        status=Avaliacao.Status.OK, prazo=ontem,
        status_acao=Avaliacao.StatusAcao.CONCLUIDA, atualizado_por=usuario,
    )
    nao_vencida = Avaliacao.objects.create(
        local=local, criterio=CriterioAcessibilidade.objects.create(nome='No prazo'),
        status=Avaliacao.Status.PENDENTE, prazo=amanha,
        status_acao=Avaliacao.StatusAcao.EM_ANDAMENTO, atualizado_por=usuario,
    )
    return {
        'usuario': usuario, 'vencida_pendente': vencida_pendente,
        'vencida_concluida': vencida_concluida, 'nao_vencida': nao_vencida,
    }


@pytest.mark.django_db
def test_alertas_mostra_so_vencidas_e_nao_concluidas(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:alertas'))
    ids = [a.pk for a in resp.context['avaliacoes']]
    assert ids == [cenario['vencida_pendente'].pk]
