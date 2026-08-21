import pytest
from django.core.management import call_command

from apps.edificacoes.models import Edificacao


@pytest.mark.django_db
def test_renomeia_apenas_edificacoes_com_nome_placeholder():
    Edificacao.objects.create(sigla='PJSA', nome='PJSA')
    Edificacao.objects.create(sigla='BSBI', nome='Edifício-sede - Bloco A')

    call_command('renomear_edificacoes_acessibilidade')

    pjsa = Edificacao.objects.get(sigla='PJSA')
    bsbi = Edificacao.objects.get(sigla='BSBI')
    assert pjsa.nome == 'Promotoria de Justiça de Samambaia'
    # BSBI já tem nome próprio (definido pelo módulo de Visitas) — não é
    # tocado por este comando, mesmo não constando no mapa.
    assert bsbi.nome == 'Edifício-sede - Bloco A'


@pytest.mark.django_db
def test_e_idempotente():
    Edificacao.objects.create(sigla='PJSA', nome='PJSA')
    call_command('renomear_edificacoes_acessibilidade')
    call_command('renomear_edificacoes_acessibilidade')
    assert Edificacao.objects.get(sigla='PJSA').nome == 'Promotoria de Justiça de Samambaia'


@pytest.mark.django_db
def test_nao_sobrescreve_nome_ja_personalizado():
    Edificacao.objects.create(sigla='PJSA', nome='Nome customizado pelo usuário')
    call_command('renomear_edificacoes_acessibilidade')
    assert Edificacao.objects.get(sigla='PJSA').nome == 'Nome customizado pelo usuário'


@pytest.mark.django_db
def test_dry_run_nao_grava(capsys):
    Edificacao.objects.create(sigla='PJSA', nome='PJSA')
    call_command('renomear_edificacoes_acessibilidade', '--dry-run')
    assert Edificacao.objects.get(sigla='PJSA').nome == 'PJSA'
