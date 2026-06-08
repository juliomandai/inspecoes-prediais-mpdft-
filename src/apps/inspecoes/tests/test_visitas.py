import pytest


@pytest.mark.django_db
def test_infra_pytest_funciona():
    from apps.edificacoes.models import Edificacao
    edif = Edificacao.objects.create(nome="Predio Teste")
    assert edif.pk is not None
