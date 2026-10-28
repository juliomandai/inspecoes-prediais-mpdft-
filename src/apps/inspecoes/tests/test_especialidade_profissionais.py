import pytest
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.edificacoes.models import Edificacao
from apps.edificacoes.models import Profissional


@pytest.mark.django_db
def test_numero_art_fica_em_branco_por_padrao():
    edificacao = Edificacao.objects.create(nome='Sede ART')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    assert esp.numero_art == ''


@pytest.mark.django_db
def test_profissionais_lista_reflete_m2m():
    edificacao = Edificacao.objects.create(nome='Sede M2M')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    ana = Profissional.objects.create(nome='Ana Civil', crea='111/D-DF')
    bia = Profissional.objects.create(nome='Bia Civil', crea='222/D-DF')
    esp.profissionais.set([ana, bia])
    assert esp.profissionais_lista == ['Ana Civil', 'Bia Civil']
    assert esp.profissionais_display == 'Ana Civil, Bia Civil'


@pytest.mark.django_db
def test_especialidade_create_usa_profissionais_por_id(client, django_user_model):
    from django.urls import reverse

    user = django_user_model.objects.create_user(username='eng', password='x', first_name='Eng', last_name='Teste')
    client.force_login(user)
    edificacao = Edificacao.objects.create(nome='Sede view M2M')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    prof = Profissional.objects.create(nome='Ana Civil', crea='333/D-DF')
    url = reverse('inspecoes:especialidade_create', args=[inspecao.pk])
    resp = client.post(url, {
        'especialidade': 'civil', 'data_inspecao': '2026-01-01', 'numero_art': '',
        'profissionais': [str(prof.pk)],
    })
    assert resp.status_code == 302
    esp = InspecaoEspecialidade.objects.get(inspecao=inspecao)
    assert esp.profissionais_lista == ['Ana Civil']
