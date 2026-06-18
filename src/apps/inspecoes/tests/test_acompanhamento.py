import pytest
from datetime import date
from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.fixture
def cenario(db, client):
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True,
                              first_name='Ze', last_name='Silva')
    client.force_login(u)

    sede = Edificacao.objects.create(nome='Sede')
    anexo = Edificacao.objects.create(nome='Anexo')

    insp_sede = Inspecao.objects.create(edificacao=sede)
    insp_anexo = Inspecao.objects.create(edificacao=anexo)

    civ = InspecaoEspecialidade.objects.create(inspecao=insp_sede, especialidade='civil',
        profissional='X', data_inspecao=date.today())
    ele = InspecaoEspecialidade.objects.create(inspecao=insp_anexo, especialidade='eletrica',
        profissional='Y', data_inspecao=date.today())

    def nc(esp, direc, loc='L1', status='pendente'):
        return Achado.objects.create(
            especialidade=esp, localizacao=loc, verificacao='V', grupo_tecnico='estrutura',
            requisito_afetado='durabilidade', gravidade=4, urgencia=3, tendencia=2,
            prioridade_risco=1, direcionamento=direc, status=status,
        )

    # Não conformes
    a_manut = nc(civ, 'manutencao')
    a_nova = nc(civ, 'nova_contratacao')
    a_garantia = nc(ele, 'garantia', status='finalizado')
    # Conforme (não deve aparecer no acompanhamento)
    conforme = Achado.objects.create(
        especialidade=civ, localizacao='L9', verificacao='OK', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True, direcionamento='manutencao',
    )
    return {
        'u': u, 'sede': sede, 'anexo': anexo, 'civ': civ, 'ele': ele,
        'a_manut': a_manut, 'a_nova': a_nova, 'a_garantia': a_garantia, 'conforme': conforme,
    }


@pytest.mark.django_db
def test_painel_carrega_com_kpis(client, cenario):
    resp = client.get(reverse('inspecoes:acompanhamento_painel'))
    assert resp.status_code == 200
    # 3 não conformes, conforme fora
    assert resp.context['total'] == 3
    assert resp.context['finalizados'] == 1
    assert resp.context['pct_conclusao'] == 33


@pytest.mark.django_db
def test_lista_filtra_por_categoria(client, cenario):
    resp = client.get(reverse('inspecoes:acompanhamento_lista') + '?categoria=manutencao')
    achados = list(resp.context['achados'])
    assert cenario['a_manut'] in achados
    assert cenario['a_nova'] not in achados
    assert cenario['conforme'] not in achados


@pytest.mark.django_db
def test_lista_todas_categorias_mostra_tudo(client, cenario):
    resp = client.get(reverse('inspecoes:acompanhamento_lista') + '?categoria=todas')
    achados = list(resp.context['achados'])
    assert cenario['a_manut'] in achados
    assert cenario['a_nova'] in achados
    assert cenario['a_garantia'] in achados
    assert cenario['conforme'] not in achados
    assert resp.context['mostra_categoria_coluna'] is True


@pytest.mark.django_db
def test_lista_todas_filtro_status_cross_categoria(client, cenario):
    # status=finalizado deve trazer o achado de garantia, independentemente da categoria
    resp = client.get(reverse('inspecoes:acompanhamento_lista') + '?categoria=todas&status=finalizado')
    achados = list(resp.context['achados'])
    assert achados == [cenario['a_garantia']]


@pytest.mark.django_db
def test_lista_filtros_combinados(client, cenario):
    # garantia + localidade Anexo + especialidade elétrica + status finalizado
    url = (reverse('inspecoes:acompanhamento_lista') +
           f'?categoria=garantia&localidade={cenario["anexo"].pk}'
           f'&especialidade=eletrica&status=finalizado')
    resp = client.get(url)
    achados = list(resp.context['achados'])
    assert achados == [cenario['a_garantia']]


@pytest.mark.django_db
def test_lista_filtro_localidade_exclui_outra(client, cenario):
    url = (reverse('inspecoes:acompanhamento_lista') +
           f'?categoria=manutencao&localidade={cenario["anexo"].pk}')
    resp = client.get(url)
    assert list(resp.context['achados']) == []


@pytest.mark.django_db
def test_reclassificar_grava_historico_e_altera(client, cenario):
    from apps.inspecoes.models import Achado, EncaminhamentoHistorico
    a = cenario['a_manut']
    resp = client.post(reverse('inspecoes:achado_reclassificar', args=[a.pk]), {
        'para_direcionamento': 'nova_contratacao',
        'justificativa': 'Exige contratação especializada.',
    })
    assert resp.status_code == 302
    a.refresh_from_db()
    assert a.direcionamento == 'nova_contratacao'
    h = EncaminhamentoHistorico.objects.get(achado=a)
    assert h.de_direcionamento == 'manutencao'
    assert h.para_direcionamento == 'nova_contratacao'
    assert h.usuario == cenario['u']
    assert 'especializada' in h.justificativa


@pytest.mark.django_db
def test_reclassificar_mesma_categoria_barrada(client, cenario):
    from apps.inspecoes.models import EncaminhamentoHistorico
    a = cenario['a_manut']
    resp = client.post(reverse('inspecoes:achado_reclassificar', args=[a.pk]), {
        'para_direcionamento': 'manutencao',
        'justificativa': 'qualquer',
    })
    assert resp.status_code == 302
    a.refresh_from_db()
    assert a.direcionamento == 'manutencao'
    assert not EncaminhamentoHistorico.objects.filter(achado=a).exists()


@pytest.mark.django_db
def test_reclassificar_sem_justificativa_nao_grava(client, cenario):
    from apps.inspecoes.models import EncaminhamentoHistorico
    a = cenario['a_manut']
    client.post(reverse('inspecoes:achado_reclassificar', args=[a.pk]), {
        'para_direcionamento': 'garantia',
        'justificativa': '',
    })
    a.refresh_from_db()
    assert a.direcionamento == 'manutencao'
    assert not EncaminhamentoHistorico.objects.filter(achado=a).exists()


@pytest.mark.django_db
def test_acompanhamento_salva_status_e_os(client, cenario):
    a = cenario['a_manut']
    resp = client.post(reverse('inspecoes:acompanhamento_achado', args=[a.pk]), {
        'status': 'em_andamento',
        'ordem_servico': 'OS-555',
        'os_data_abertura': '2026-06-10',
        'os_observacoes': 'Equipe acionada.',
    })
    assert resp.status_code == 302
    a.refresh_from_db()
    assert a.status == 'em_andamento'
    assert a.ordem_servico == 'OS-555'
    assert a.os_data_abertura.isoformat() == '2026-06-10'
    assert a.os_observacoes == 'Equipe acionada.'


@pytest.mark.django_db
def test_achado_conforme_nao_acessivel_no_acompanhamento(client, cenario):
    resp = client.get(reverse('inspecoes:acompanhamento_achado', args=[cenario['conforme'].pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_gestao_achado_renderiza_com_historico(client, cenario):
    from apps.inspecoes.models import EncaminhamentoHistorico
    a = cenario['a_manut']
    EncaminhamentoHistorico.objects.create(
        achado=a, usuario=cenario['u'], de_direcionamento='garantia',
        para_direcionamento='manutencao', justificativa='Tratável pela manutenção.',
    )
    resp = client.get(reverse('inspecoes:acompanhamento_achado', args=[a.pk]))
    assert resp.status_code == 200
    assert resp.context['is_manutencao'] is True
    assert 'Tratável pela manutenção' in resp.content.decode()
    # campos de OS presentes por ser manutenção
    assert b'os_data_abertura' in resp.content
