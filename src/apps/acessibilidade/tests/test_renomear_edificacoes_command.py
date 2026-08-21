import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.edificacoes.models import Edificacao
from apps.acessibilidade.models import Avaliacao, CriterioAcessibilidade, LocalAcessibilidade
from apps.inspecoes.models import Inspecao, VisitaTecnica


@pytest.mark.django_db
def test_renomeia_no_lugar_quando_nao_ha_duplicata():
    Edificacao.objects.create(sigla='PJSA', nome='PJSA')

    call_command('renomear_edificacoes_acessibilidade')

    pjsa = Edificacao.objects.get(sigla='PJSA')
    assert pjsa.nome == 'Promotoria de Justiça de Samambaia'
    assert Edificacao.objects.count() == 1


@pytest.mark.django_db
def test_funde_placeholder_na_edificacao_oficial_existente():
    oficial = Edificacao.objects.create(nome='Promotoria de Justiça de Samambaia')
    placeholder = Edificacao.objects.create(sigla='PJSA', nome='PJSA')
    usuario = get_user_model().objects.create_user(username='ana', password='1')
    local = LocalAcessibilidade.objects.create(edificacao=placeholder, nome='Sanitário')
    criterio = CriterioAcessibilidade.objects.create(nome='Critério X')
    Avaliacao.objects.create(local=local, criterio=criterio, atualizado_por=usuario)
    visita = VisitaTecnica.objects.create(
        edificacao=placeholder, data_visita='2026-01-01', participantes='Fulano', motivo='Rotina',
    )
    inspecao = Inspecao.objects.create(edificacao=placeholder)

    call_command('renomear_edificacoes_acessibilidade')

    assert not Edificacao.objects.filter(pk=placeholder.pk).exists()
    oficial.refresh_from_db()
    assert oficial.sigla == 'PJSA'
    assert oficial.nome == 'Promotoria de Justiça de Samambaia'

    local.refresh_from_db()
    visita.refresh_from_db()
    inspecao.refresh_from_db()
    assert local.edificacao_id == oficial.pk
    assert visita.edificacao_id == oficial.pk
    assert inspecao.edificacao_id == oficial.pk


@pytest.mark.django_db
def test_funde_bsbi_por_correspondencia_parcial_de_bloco_a():
    oficial = Edificacao.objects.create(nome='Edifício-sede – Bloco A')
    placeholder = Edificacao.objects.create(sigla='BSBI', nome='BSBI')
    local = LocalAcessibilidade.objects.create(edificacao=placeholder, nome='Sanitário')

    call_command('renomear_edificacoes_acessibilidade')

    assert not Edificacao.objects.filter(pk=placeholder.pk).exists()
    oficial.refresh_from_db()
    assert oficial.sigla == 'BSBI'
    local.refresh_from_db()
    assert local.edificacao_id == oficial.pk


@pytest.mark.django_db
def test_e_idempotente():
    Edificacao.objects.create(nome='Promotoria de Justiça de Samambaia')
    Edificacao.objects.create(sigla='PJSA', nome='PJSA')

    call_command('renomear_edificacoes_acessibilidade')
    call_command('renomear_edificacoes_acessibilidade')

    assert Edificacao.objects.count() == 1
    assert Edificacao.objects.get().sigla == 'PJSA'


@pytest.mark.django_db
def test_dry_run_nao_grava():
    Edificacao.objects.create(sigla='PJSA', nome='PJSA')
    call_command('renomear_edificacoes_acessibilidade', '--dry-run')
    assert Edificacao.objects.get(sigla='PJSA').nome == 'PJSA'
