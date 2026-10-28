import pytest
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_numero_art_fica_em_branco_por_padrao():
    edificacao = Edificacao.objects.create(nome='Sede ART')
    inspecao = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=inspecao, especialidade='civil', data_inspecao='2026-01-01',
    )
    assert esp.numero_art == ''
