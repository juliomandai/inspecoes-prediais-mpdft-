from decimal import Decimal

from django.test import TestCase
import pytest
from apps.edificacoes.forms import EdificacaoForm
from apps.edificacoes.models import Edificacao
from apps.edificacoes.models import Profissional
from apps.edificacoes.models import HistoricoIntervencao


@pytest.mark.django_db
def test_descritivo_aceita_texto_livre_e_pode_ficar_vazio():
    e1 = Edificacao.objects.create(nome='Sede com descritivo', descritivo='Prédio de 3 pavimentos, construído em 1998.')
    e2 = Edificacao.objects.create(nome='Sede sem descritivo')
    assert e1.descritivo == 'Prédio de 3 pavimentos, construído em 1998.'
    assert e2.descritivo == ''


@pytest.mark.django_db
def test_area_construida_aceita_formato_br_com_milhar_e_decimal():
    form = EdificacaoForm(data={
        'nome': 'Sede com área', 'endereco': '', 'area_construida_m2': '4.745,52',
        'pavimentos': '', 'ativo': True,
    })
    assert form.is_valid(), form.errors
    edificacao = form.save()
    assert edificacao.area_construida_m2 == Decimal('4745.52')


@pytest.mark.django_db
def test_area_construida_exibe_valor_salvo_em_formato_br():
    edificacao = Edificacao.objects.create(nome='Sede com área', area_construida_m2=Decimal('4745.52'))
    form = EdificacaoForm(instance=edificacao)
    assert form['area_construida_m2'].value() == '4.745,52'


@pytest.mark.django_db
def test_profissional_crea_e_unico_entre_ativos():
    Profissional.objects.create(nome='Ana Civil', crea='12345/D-DF')
    with pytest.raises(Exception):
        Profissional.objects.create(nome='Outra Pessoa', crea='12345/D-DF')


@pytest.mark.django_db
def test_profissional_form_exige_crea():
    from apps.edificacoes.forms import ProfissionalForm
    form = ProfissionalForm(data={'nome': 'Ana Civil', 'crea': ''})
    assert not form.is_valid()
    assert 'crea' in form.errors


@pytest.mark.django_db
def test_historico_intervencao_ordena_por_ano():
    e = Edificacao.objects.create(nome='Sede com histórico')
    HistoricoIntervencao.objects.create(edificacao=e, ano=2023, descricao='Troca de chiller')
    HistoricoIntervencao.objects.create(edificacao=e, ano=2022, descricao='Recuperação de fachada')
    anos = list(e.historico_intervencoes.values_list('ano', flat=True))
    assert anos == [2022, 2023]


@pytest.mark.django_db
def test_edificacao_update_sincroniza_historico(client, django_user_model):
    staff = django_user_model.objects.create_user(username='admin', password='x', is_staff=True)
    client.force_login(staff)
    e = Edificacao.objects.create(nome='Sede histórico view')
    resp = client.post(f'/edificacoes/{e.pk}/editar/', {
        'nome': 'Sede histórico view', 'endereco': '', 'area_construida_m2': '',
        'pavimentos': '', 'ativo': 'on',
        'historico_ano': ['2022', '2023'],
        'historico_descricao': ['Reforma de fachada', 'Troca de elevador'],
    })
    assert resp.status_code == 302
    assert list(e.historico_intervencoes.values_list('ano', 'descricao')) == [
        (2022, 'Reforma de fachada'), (2023, 'Troca de elevador'),
    ]


@pytest.mark.django_db
def test_edificacao_create_form_invalido_reexibe_historico_digitado(client, django_user_model):
    staff = django_user_model.objects.create_user(username='admin', password='x', is_staff=True)
    client.force_login(staff)
    Edificacao.objects.create(nome='Sede já existente')
    # nome duplicado torna o form inválido; o histórico digitado não deve ser perdido.
    resp = client.post('/edificacoes/nova/', {
        'nome': 'Sede já existente', 'endereco': '', 'area_construida_m2': '',
        'pavimentos': '', 'ativo': 'on',
        'historico_ano': ['2022'],
        'historico_descricao': ['Reforma de fachada'],
    })
    assert resp.status_code == 200
    assert resp.context['historico'] == [{'ano': '2022', 'descricao': 'Reforma de fachada'}]
    assert not HistoricoIntervencao.objects.exists()


@pytest.mark.django_db
def test_sincronizar_historico_ignora_ano_nao_numerico_sem_perder_os_demais():
    from django.test import RequestFactory
    from apps.edificacoes.views import _sincronizar_historico

    e = Edificacao.objects.create(nome='Sede ano inválido')
    HistoricoIntervencao.objects.create(edificacao=e, ano=2000, descricao='Antigo')
    request = RequestFactory().post('/edificacoes/0/editar/', {
        'historico_ano': ['2022', 'abc'],
        'historico_descricao': ['Reforma de fachada', 'Intervenção sem ano válido'],
    })
    _sincronizar_historico(e, request)
    assert list(e.historico_intervencoes.values_list('ano', 'descricao')) == [
        (2022, 'Reforma de fachada'),
    ]
