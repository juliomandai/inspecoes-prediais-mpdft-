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
    criterio_ok = CriterioAcessibilidade.objects.create(nome='Critério OK')
    criterio_pendente = CriterioAcessibilidade.objects.create(nome='Critério Pendente')
    Avaliacao.objects.create(local=local, criterio=criterio_ok, status=Avaliacao.Status.OK, atualizado_por=usuario)
    Avaliacao.objects.create(local=local, criterio=criterio_pendente, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)
    return {'usuario': usuario, 'edificacao': edificacao}


@pytest.mark.django_db
def test_dashboard_exige_login(client):
    resp = client.get(reverse('acessibilidade:dashboard'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_dashboard_mostra_contagem_por_edificacao(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:dashboard'))
    assert resp.status_code == 200
    assert resp.context['stats'][0]['total'] == 2
    assert resp.context['stats'][0]['ok'] == 1
    assert resp.context['stats'][0]['pendente'] == 1


@pytest.mark.django_db
def test_lista_filtra_por_status(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:lista'), {'status': 'PENDENTE'})
    itens = list(resp.context['pagina'].object_list)
    assert len(itens) == 1
    assert itens[0].criterio.nome == 'Critério Pendente'


@pytest.mark.django_db
def test_lista_busca_por_texto(client, cenario):
    client.force_login(cenario['usuario'])
    resp = client.get(reverse('acessibilidade:lista'), {'q': 'Critério OK'})
    itens = list(resp.context['pagina'].object_list)
    assert len(itens) == 1
