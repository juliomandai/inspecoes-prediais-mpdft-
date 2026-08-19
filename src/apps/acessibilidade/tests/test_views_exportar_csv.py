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


@pytest.mark.django_db
def test_exportar_csv_exige_login(client, avaliacao):
    resp = client.get(reverse('acessibilidade:exportar_csv'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_exportar_csv_neutraliza_injecao_de_formula(client, avaliacao):
    avaliacao.notas = '=cmd|\'/c calc\'!A1'
    avaliacao.responsavel = '+SUM(A1:A2)'
    avaliacao.save(update_fields=['notas', 'responsavel'])

    client.force_login(avaliacao.atualizado_por)
    resp = client.get(reverse('acessibilidade:exportar_csv'))
    linhas = list(csv.reader(io.StringIO(resp.content.decode('utf-8')), delimiter=';'))
    responsavel_col = linhas[1][7]
    notas_col = linhas[1][12]
    assert responsavel_col.startswith("'+")
    assert notas_col.startswith("'=")
