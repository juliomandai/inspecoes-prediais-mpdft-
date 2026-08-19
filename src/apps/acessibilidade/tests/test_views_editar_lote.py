import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def duas_avaliacoes(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    c1 = CriterioAcessibilidade.objects.create(nome='Critério 1')
    c2 = CriterioAcessibilidade.objects.create(nome='Critério 2')
    a1 = Avaliacao.objects.create(local=local, criterio=c1, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)
    a2 = Avaliacao.objects.create(local=local, criterio=c2, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)
    return {'usuario': usuario, 'a1': a1, 'a2': a2}


@pytest.mark.django_db
def test_editar_lote_aplica_a_todos_os_selecionados(client, duas_avaliacoes):
    client.force_login(duas_avaliacoes['usuario'])
    resp = client.post(reverse('acessibilidade:editar_lote'), {
        'ids_selecionados': f"{duas_avaliacoes['a1'].pk},{duas_avaliacoes['a2'].pk}",
        'status_acao': 'EM_ANDAMENTO',
    })
    assert resp.status_code == 302
    duas_avaliacoes['a1'].refresh_from_db()
    duas_avaliacoes['a2'].refresh_from_db()
    assert duas_avaliacoes['a1'].status_acao == 'EM_ANDAMENTO'
    assert duas_avaliacoes['a2'].status_acao == 'EM_ANDAMENTO'
    assert duas_avaliacoes['a1'].historico.count() == 1
    assert duas_avaliacoes['a2'].historico.count() == 1


@pytest.mark.django_db
def test_editar_lote_sem_campos_preenchidos_nao_altera_nada(client, duas_avaliacoes):
    client.force_login(duas_avaliacoes['usuario'])
    resp = client.post(reverse('acessibilidade:editar_lote'), {
        'ids_selecionados': f"{duas_avaliacoes['a1'].pk}",
    })
    assert resp.status_code == 302
    assert duas_avaliacoes['a1'].historico.count() == 0


@pytest.mark.django_db
def test_editar_lote_exige_login(client, duas_avaliacoes):
    resp = client.post(reverse('acessibilidade:editar_lote'), {
        'ids_selecionados': f"{duas_avaliacoes['a1'].pk}",
        'status_acao': 'EM_ANDAMENTO',
    })
    assert resp.status_code == 302
    duas_avaliacoes['a1'].refresh_from_db()
    assert duas_avaliacoes['a1'].historico.count() == 0


@pytest.mark.django_db
def test_editar_lote_get_redireciona_sem_alterar(client, duas_avaliacoes):
    client.force_login(duas_avaliacoes['usuario'])
    resp = client.get(reverse('acessibilidade:editar_lote'))
    assert resp.status_code == 302
    assert resp.url == reverse('acessibilidade:lista')


@pytest.mark.django_db
def test_editar_lote_ids_malformados_nao_derruba_a_view(client, duas_avaliacoes):
    client.force_login(duas_avaliacoes['usuario'])
    resp = client.post(reverse('acessibilidade:editar_lote'), {
        'ids_selecionados': f"{duas_avaliacoes['a1'].pk},abc",
        'status_acao': 'EM_ANDAMENTO',
    })
    assert resp.status_code == 302
    duas_avaliacoes['a1'].refresh_from_db()
    assert duas_avaliacoes['a1'].historico.count() == 0
    assert duas_avaliacoes['a1'].status_acao != 'EM_ANDAMENTO'
