import pytest
from datetime import date
from django.contrib.auth import get_user_model

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.inspecoes.views import _pode_gerar_relatorio_final


@pytest.fixture
def inspecao_com_profissionais(db):
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana Civil',
        data_inspecao=date.today(), conclusao='ok',
    )
    InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='eletrica', profissional='Beto Eletrica',
        data_inspecao=date.today(), conclusao='ok',
    )
    return insp


@pytest.mark.django_db
def test_profissional_de_qualquer_uma_das_especialidades_pode_gerar(inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    eletrica = U.objects.create_user(username='beto', password='1', first_name='Beto', last_name='Eletrica')
    estranho = U.objects.create_user(username='carlos', password='1', first_name='Carlos', last_name='Estranho')
    staff = U.objects.create_user(username='staff', password='1', is_staff=True)

    assert _pode_gerar_relatorio_final(civil, inspecao_com_profissionais)
    assert _pode_gerar_relatorio_final(eletrica, inspecao_com_profissionais)
    assert not _pode_gerar_relatorio_final(estranho, inspecao_com_profissionais)
    assert _pode_gerar_relatorio_final(staff, inspecao_com_profissionais)
