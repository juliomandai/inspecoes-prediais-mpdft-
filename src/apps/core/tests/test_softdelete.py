"""Testa o mixin `SoftDeleteModel` (apps.core.softdelete) usando os models
reais do projeto que o adotam — o app `core` não tem models próprios."""
import pytest
from datetime import date
from django.contrib.auth import get_user_model

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(username='ana', password='1')


@pytest.fixture
def cadeia(db):
    """Edificação → Inspeção → Especialidade → Achado, toda ativa."""
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='X', data_inspecao=date.today(),
    )
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=3, urgencia=3, tendencia=3,
    )
    return edif, insp, esp, achado


@pytest.mark.django_db
def test_excluir_marca_e_esconde_do_manager_padrao(cadeia, usuario):
    _, insp, _, _ = cadeia
    insp.excluir(usuario)

    assert insp.excluido
    assert insp.excluido_em is not None
    assert insp.excluido_por == usuario
    assert not Inspecao.objects.filter(pk=insp.pk).exists()
    assert Inspecao.todos_objects.filter(pk=insp.pk).exists()


@pytest.mark.django_db
def test_excluir_e_idempotente(cadeia, usuario):
    _, insp, _, _ = cadeia
    insp.excluir(usuario)
    momento_original = insp.excluido_em

    outro = get_user_model().objects.create_user(username='outra', password='1')
    insp.excluir(outro)  # não deve sobrescrever quem/quando excluiu

    insp.refresh_from_db()
    assert insp.excluido_em == momento_original
    assert insp.excluido_por == usuario


@pytest.mark.django_db
def test_restaurar_desfaz_exclusao(cadeia, usuario):
    _, insp, _, _ = cadeia
    insp.excluir(usuario)
    insp.restaurar()

    assert not insp.excluido
    assert insp.excluido_em is None
    assert insp.excluido_por is None
    assert Inspecao.objects.filter(pk=insp.pk).exists()


@pytest.mark.django_db
def test_cascata_ao_excluir_propaga_para_filhos_cascade(cadeia, usuario):
    _, insp, esp, achado = cadeia
    insp.excluir(usuario)

    esp.refresh_from_db()
    achado.refresh_from_db()
    assert esp.excluido
    assert esp.excluido_por == usuario
    assert achado.excluido
    assert achado.excluido_por == usuario
    assert not InspecaoEspecialidade.objects.filter(pk=esp.pk).exists()
    assert not Achado.objects.filter(pk=achado.pk).exists()


@pytest.mark.django_db
def test_cascata_ao_restaurar_traz_os_filhos_de_volta(cadeia, usuario):
    _, insp, esp, achado = cadeia
    insp.excluir(usuario)
    insp.restaurar()

    esp.refresh_from_db()
    achado.refresh_from_db()
    assert not esp.excluido
    assert not achado.excluido


@pytest.mark.django_db
def test_excluir_filho_isoladamente_nao_afeta_o_pai(cadeia, usuario):
    _, insp, esp, achado = cadeia
    achado.excluir(usuario)

    esp.refresh_from_db()
    insp.refresh_from_db()
    assert achado.excluido
    assert not esp.excluido
    assert not insp.excluido
    # a especialidade continua enxergando só os achados ativos
    assert list(esp.achados.all()) == []
    assert list(Achado.todos_objects.filter(especialidade=esp)) == [achado]


@pytest.mark.django_db
def test_apagar_definitivamente_remove_de_verdade(cadeia, usuario):
    _, insp, _, _ = cadeia
    pk = insp.pk
    insp.apagar_definitivamente()

    assert not Inspecao.todos_objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_delete_padrao_vira_soft_delete(cadeia):
    _, insp, _, _ = cadeia
    insp.delete()

    assert not Inspecao.objects.filter(pk=insp.pk).exists()
    assert Inspecao.todos_objects.filter(pk=insp.pk).exists()


@pytest.mark.django_db
def test_delete_hard_true_remove_de_verdade(cadeia):
    _, insp, _, _ = cadeia
    insp.delete(hard=True)

    assert not Inspecao.todos_objects.filter(pk=insp.pk).exists()


@pytest.mark.django_db
def test_nome_excluido_nao_bloqueia_recriar_edificacao_ativa(usuario):
    original = Edificacao.objects.create(nome='Promotoria X')
    original.excluir(usuario)

    nova = Edificacao.objects.create(nome='Promotoria X')  # não pode estourar UNIQUE

    assert nova.pk != original.pk
    assert Edificacao.objects.get(nome='Promotoria X') == nova


@pytest.mark.django_db
def test_todos_objects_nao_filtra_e_objects_filtra(cadeia, usuario):
    _, insp, _, _ = cadeia
    Inspecao.objects.create(edificacao=insp.edificacao)
    insp.excluir(usuario)

    assert Inspecao.objects.count() == 1
    assert Inspecao.todos_objects.count() == 2
