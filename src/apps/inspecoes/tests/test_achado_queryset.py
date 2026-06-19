import pytest
from datetime import date
from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.fixture
def cenario(db):
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado

    sede = Edificacao.objects.create(nome='Sede')
    anexo = Edificacao.objects.create(nome='Anexo')
    insp_sede = Inspecao.objects.create(edificacao=sede)
    insp_anexo = Inspecao.objects.create(edificacao=anexo)
    civ = InspecaoEspecialidade.objects.create(inspecao=insp_sede, especialidade='civil',
        profissional='X', data_inspecao=date.today())
    ele = InspecaoEspecialidade.objects.create(inspecao=insp_anexo, especialidade='eletrica',
        profissional='Y', data_inspecao=date.today())

    def nc(esp, direc, status='pendente'):
        return Achado.objects.create(
            especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
            requisito_afetado='durabilidade', gravidade=4, urgencia=3, tendencia=2,
            prioridade_risco=1, direcionamento=direc, status=status,
        )

    a_manut = nc(civ, 'manutencao')
    a_nova = nc(civ, 'nova_contratacao')
    a_garantia = nc(ele, 'garantia', status='finalizado')
    conforme = Achado.objects.create(
        especialidade=civ, localizacao='L9', verificacao='OK', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True, direcionamento='manutencao',
    )
    return {
        'sede': sede, 'anexo': anexo, 'civ': civ, 'ele': ele,
        'a_manut': a_manut, 'a_nova': a_nova, 'a_garantia': a_garantia, 'conforme': conforme,
    }


@pytest.mark.django_db
def test_acompanhamento_exclui_conformes(cenario):
    from apps.inspecoes.models import Achado
    qs = Achado.objects.acompanhamento()
    assert cenario['conforme'] not in qs
    assert set(qs) == {cenario['a_manut'], cenario['a_nova'], cenario['a_garantia']}


@pytest.mark.django_db
def test_com_filtros_acompanhamento_combina_localidade_e_status(cenario):
    from apps.inspecoes.forms import AcompanhamentoFilterForm
    from apps.inspecoes.models import Achado
    form = AcompanhamentoFilterForm({'localidade': cenario['anexo'].pk, 'status': 'finalizado'})
    qs = Achado.objects.acompanhamento().com_filtros_acompanhamento(form)
    assert list(qs) == [cenario['a_garantia']]


@pytest.mark.django_db
def test_contagem_por_direcionamento_uma_unica_query(cenario, django_assert_num_queries):
    from apps.inspecoes.models import Achado
    qs = Achado.objects.acompanhamento()
    with django_assert_num_queries(1):
        contagens = qs.contagem_por('direcionamento', Achado.DIRECIONAMENTO_CHOICES)
    por_chave = {row['chave']: row['total'] for row in contagens}
    assert por_chave == {'garantia': 1, 'manutencao': 1, 'nova_contratacao': 1}


@pytest.mark.django_db
def test_contagem_por_localidade_ordenada_desc(cenario):
    from apps.inspecoes.models import Achado
    # cenario já tem 2 achados não conformes na Sede (a_manut, a_nova) e 1 no Anexo (a_garantia).
    qs = Achado.objects.acompanhamento()
    linhas = qs.contagem_por_localidade()
    assert linhas[0]['nome'] == 'Sede'
    assert linhas[0]['total'] == 2
    assert linhas[1]['nome'] == 'Anexo'
    assert linhas[1]['total'] == 1


@pytest.mark.django_db
def test_lista_badges_uma_unica_query_independente_do_numero_de_categorias(client, cenario, django_assert_max_num_queries):
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)
    # Antes do refatoramento eram N count() (um por categoria) + 1 total — aqui é 1 query agregada.
    with django_assert_max_num_queries(12):
        resp = client.get(reverse('inspecoes:acompanhamento_lista') + '?categoria=todas')
    assert resp.status_code == 200
