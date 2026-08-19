import csv
import io

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
    return Avaliacao.objects.create(
        local=local, criterio=criterio, status=Avaliacao.Status.PENDENTE,
        responsavel='João', atualizado_por=usuario,
    )


@pytest.mark.django_db
def test_exportar_csv_retorna_conteudo_correto(client, avaliacao):
    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:exportar_csv'))
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('text/csv')
    linhas = list(csv.reader(io.StringIO(resp.content.decode('utf-8')), delimiter=';'))
    assert linhas[0][0] == 'Edificação'
    assert linhas[1][0] == 'Prédio Teste'
    assert linhas[1][7] == 'João'


@pytest.mark.django_db
def test_exportar_csv_respeita_filtro_de_status(client, avaliacao):
    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:exportar_csv'), {'status': 'OK'})
    linhas = list(csv.reader(io.StringIO(resp.content.decode('utf-8')), delimiter=';'))
    assert len(linhas) == 1  # só o cabeçalho, nenhuma avaliação OK
