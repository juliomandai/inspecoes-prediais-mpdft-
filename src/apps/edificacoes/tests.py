from decimal import Decimal

from django.test import TestCase
import pytest
from apps.edificacoes.forms import EdificacaoForm
from apps.edificacoes.models import Edificacao
from apps.edificacoes.models import Profissional


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
