from django.test import TestCase
import pytest
from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_descritivo_aceita_texto_livre_e_pode_ficar_vazio():
    e1 = Edificacao.objects.create(nome='Sede com descritivo', descritivo='Prédio de 3 pavimentos, construído em 1998.')
    e2 = Edificacao.objects.create(nome='Sede sem descritivo')
    assert e1.descritivo == 'Prédio de 3 pavimentos, construído em 1998.'
    assert e2.descritivo == ''
