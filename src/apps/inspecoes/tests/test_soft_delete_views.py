import pytest
from datetime import date
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.fixture
def cenario(db, client):
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado, Foto

    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)

    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='ze', data_inspecao=date.today(),
    )
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=3, urgencia=3, tendencia=3,
    )
    foto = Foto.objects.create(
        achado=achado,
        arquivo=SimpleUploadedFile('foto.jpg', b'conteudo-fake', content_type='image/jpeg'),
        nome_original='foto.jpg',
    )
    return {'usuario': u, 'edif': edif, 'insp': insp, 'esp': esp, 'achado': achado, 'foto': foto}


@pytest.mark.django_db
def test_achado_delete_view_e_soft(client, cenario):
    from apps.inspecoes.models import Achado

    achado = cenario['achado']
    resp = client.post(reverse('inspecoes:achado_delete', kwargs={'pk': achado.pk}))
    assert resp.status_code == 302

    achado.refresh_from_db()
    assert achado.excluido
    assert achado.excluido_por == cenario['usuario']
    assert not Achado.objects.filter(pk=achado.pk).exists()
    assert Achado.todos_objects.filter(pk=achado.pk).exists()


@pytest.mark.django_db
def test_inspecao_delete_view_cascateia_para_especialidade_achado_e_foto(client, cenario):
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado, Foto

    insp, esp, achado, foto = cenario['insp'], cenario['esp'], cenario['achado'], cenario['foto']
    resp = client.post(reverse('inspecoes:delete', kwargs={'pk': insp.pk}))
    assert resp.status_code == 302

    esp.refresh_from_db()
    achado.refresh_from_db()
    foto.refresh_from_db()
    assert esp.excluido and achado.excluido and foto.excluido
    assert not InspecaoEspecialidade.objects.filter(pk=esp.pk).exists()
    assert not Achado.objects.filter(pk=achado.pk).exists()
    assert not Foto.objects.filter(pk=foto.pk).exists()
    # o arquivo físico não é removido num soft delete — só num hard delete/purge.
    assert foto.arquivo.storage.exists(foto.arquivo.name)
    foto.arquivo.delete(save=False)  # limpeza do arquivo de teste


@pytest.mark.django_db
def test_foto_delete_view_e_soft_e_some_da_listagem_do_achado(client, cenario):
    from apps.inspecoes.models import Foto

    achado, foto = cenario['achado'], cenario['foto']
    resp = client.delete(reverse('inspecoes:foto_delete', kwargs={'pk': foto.pk}))
    assert resp.status_code == 204

    foto.refresh_from_db()
    assert foto.excluido
    assert list(achado.fotos.all()) == []
    assert Foto.todos_objects.filter(pk=foto.pk).exists()
    foto.arquivo.delete(save=False)  # limpeza do arquivo de teste


@pytest.mark.django_db
def test_visita_delete_view_e_soft(client, cenario):
    from apps.inspecoes.models import VisitaTecnica

    visita = VisitaTecnica.objects.create(
        edificacao=cenario['edif'], data_visita=date.today(),
        participantes='ze', motivo='Rotina', criado_por=cenario['usuario'],
    )
    resp = client.post(reverse('inspecoes:visita_delete', kwargs={'pk': visita.pk}))
    assert resp.status_code == 302

    visita.refresh_from_db()
    assert visita.excluido
    assert not VisitaTecnica.objects.filter(pk=visita.pk).exists()


@pytest.mark.django_db
def test_excluir_visita_principal_cascateia_para_subvisita_mas_nao_para_outra_visita(client, cenario):
    """Caso real que motivou a preocupação do usuário: excluir a visita-pai
    não pode apagar/afetar visitas técnicas de outras edificações ou blocos."""
    from apps.inspecoes.models import VisitaTecnica

    principal = VisitaTecnica.objects.create(
        edificacao=cenario['edif'], data_visita=date.today(),
        participantes='ze', motivo='Rotina', criado_por=cenario['usuario'],
    )
    sub = VisitaTecnica.objects.create(
        edificacao=cenario['edif'], visita_pai=principal, data_visita=date.today(),
        participantes='ze', motivo='Acompanhamento', criado_por=cenario['usuario'],
    )
    outra_edificacao_visita = VisitaTecnica.objects.create(
        edificacao=cenario['edif'], data_visita=date.today(),
        participantes='ze', motivo='Visita independente', criado_por=cenario['usuario'],
    )

    principal.excluir(cenario['usuario'])

    sub.refresh_from_db()
    outra_edificacao_visita.refresh_from_db()
    assert sub.excluido
    assert not outra_edificacao_visita.excluido
    assert VisitaTecnica.todos_objects.filter(pk=sub.pk, excluido_em__isnull=False).exists()
    assert VisitaTecnica.todos_objects.filter(pk=outra_edificacao_visita.pk, excluido_em__isnull=True).exists()

    # restaurar a principal também traz a subvisita de volta
    principal.restaurar()
    sub.refresh_from_db()
    assert not sub.excluido
