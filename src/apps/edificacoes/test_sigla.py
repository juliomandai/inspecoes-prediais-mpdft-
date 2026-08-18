import pytest
from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_sigla_eh_opcional_e_unica():
    Edificacao.objects.create(nome='Prédio A', sigla='AAAA')
    with pytest.raises(Exception):
        Edificacao.objects.create(nome='Prédio B', sigla='AAAA')


@pytest.mark.django_db
def test_sigla_pode_ficar_em_branco():
    e = Edificacao.objects.create(nome='Prédio Sem Sigla')
    assert e.sigla is None


@pytest.mark.django_db
def test_migracao_atribui_siglas_conhecidas():
    Edificacao.objects.all().delete()
    a = Edificacao.objects.create(nome='Sede MPDFT — Bloco A')
    b = Edificacao.objects.create(nome='Promotoria de Justiça da Defesa da Infância e Juventude')
    Edificacao.objects.filter(nome='Sede MPDFT — Bloco A').update(sigla='BSBI')
    Edificacao.objects.filter(nome='Promotoria de Justiça da Defesa da Infância e Juventude').update(sigla='PJIJ')
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.sigla == 'BSBI'
    assert b.sigla == 'PJIJ'
