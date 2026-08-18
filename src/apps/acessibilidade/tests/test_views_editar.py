import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade, Regiao


@pytest.fixture
def avaliacao(db):
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    edificacao = Edificacao.objects.create(nome='Prédio Teste', sigla='TEST')
    local = LocalAcessibilidade.objects.create(edificacao=edificacao, regiao=Regiao.TERREO, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Barra de apoio')
    return Avaliacao.objects.create(local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE, atualizado_por=usuario)


@pytest.mark.django_db
def test_get_editar_mostra_formulario_preenchido(client, avaliacao):
    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:editar', args=[avaliacao.pk]))
    assert resp.status_code == 200
    assert resp.context['form'].initial['status'] == 'PENDENTE'


@pytest.mark.django_db
def test_post_editar_atualiza_e_registra_historico(client, avaliacao):
    outro_usuario = get_user_model().objects.create_user(username='joao', password='1')
    client.force_login(outro_usuario)
    resp = client.post(reverse('acessibilidade:editar', args=[avaliacao.pk]), {
        'status': 'OK',
        'status_acao': 'CONCLUIDA',
        'resolucao_diagnostico': '',
        'observacao': '',
        'responsavel': '',
        'resolucao_prevista': '',
        'ordem_servico': '',
        'notas': '',
    })
    assert resp.status_code == 302
    avaliacao.refresh_from_db()
    assert avaliacao.status == 'OK'
    assert avaliacao.atualizado_por == outro_usuario
    assert avaliacao.historico.count() == 1
