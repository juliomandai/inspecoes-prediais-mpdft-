import base64
import json
import pytest
from datetime import date
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model


@pytest.fixture
def cenario(db, client):
    """Achado não conforme já preenchido (pré-cadastro), pronto para edição."""
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='X', data_inspecao=date.today(),
    )
    achado = Achado.objects.create(
        especialidade=esp,
        localizacao='Fachada', sub_localizacao='Sul', verificacao='Fissuras',
        grupo_tecnico='estrutura', requisito_afetado='durabilidade',
        descricao_nao_conformidade='Descrição original',
        recomendacao='Recomendação original',
        gravidade=2, urgencia=2, tendencia=2, prioridade_risco=3,
        direcionamento='manutencao', prazo_meses=12,
    )
    return {'u': u, 'esp': esp, 'achado': achado}


def _patch(client, achado_pk, payload):
    return client.patch(
        reverse('inspecoes:achado_sincronizar_edicao', args=[achado_pk]),
        data=json.dumps(payload), content_type='application/json',
    )


@pytest.mark.django_db
def test_sync_edicao_aplica_so_campos_enviados_e_preserva_o_resto(client, cenario):
    achado = cenario['achado']
    resp = _patch(client, achado.pk, {'recomendacao': 'Recomendação NOVA'})
    assert resp.status_code == 200
    achado.refresh_from_db()
    assert achado.recomendacao == 'Recomendação NOVA'
    # Campos não enviados permanecem como estavam.
    assert achado.descricao_nao_conformidade == 'Descrição original'
    assert achado.gravidade == 2 and achado.urgencia == 2 and achado.tendencia == 2
    assert achado.gut_total == 8


@pytest.mark.django_db
def test_sync_edicao_recalcula_gut_ao_mudar_notas(client, cenario):
    achado = cenario['achado']
    resp = _patch(client, achado.pk, {'gravidade': 5, 'urgencia': 4, 'tendencia': 3})
    assert resp.status_code == 200
    achado.refresh_from_db()
    assert achado.gut_total == 60
    assert achado.descricao_nao_conformidade == 'Descrição original'  # preservado


@pytest.mark.django_db
def test_sync_edicao_em_conformidade_limpa_diagnostico(client, cenario):
    achado = cenario['achado']
    resp = _patch(client, achado.pk, {'em_conformidade': True})
    assert resp.status_code == 200
    achado.refresh_from_db()
    assert achado.em_conformidade is True
    assert achado.gut_total == 0
    assert achado.gravidade == 1 and achado.urgencia == 1 and achado.tendencia == 1
    assert achado.prioridade_risco == 3
    assert achado.descricao_nao_conformidade == ''
    assert achado.requisito_afetado == ''
    assert achado.recomendacao == ''


@pytest.mark.django_db
def test_sync_edicao_exclui_fotos_marcadas_e_e_idempotente(client, cenario):
    from apps.inspecoes.models import Foto
    achado = cenario['achado']
    f1 = Foto.objects.create(
        achado=achado, arquivo=SimpleUploadedFile('a.jpg', b'aaaa', content_type='image/jpeg'),
        nome_original='a.jpg', tamanho_bytes=4,
    )
    f2 = Foto.objects.create(
        achado=achado, arquivo=SimpleUploadedFile('b.jpg', b'bbbb', content_type='image/jpeg'),
        nome_original='b.jpg', tamanho_bytes=4,
    )

    resp = _patch(client, achado.pk, {'fotos_excluir': [f1.pk]})
    assert resp.status_code == 200
    assert json.loads(resp.content)['fotos_excluidas'] == 1
    assert not Foto.objects.filter(pk=f1.pk).exists()
    assert Foto.objects.filter(pk=f2.pk).exists()

    # Repetir com o mesmo pk (já removido) é no-op.
    resp2 = _patch(client, achado.pk, {'fotos_excluir': [f1.pk]})
    assert resp2.status_code == 200
    assert json.loads(resp2.content)['fotos_excluidas'] == 0
    assert Foto.objects.filter(pk=f2.pk).exists()


@pytest.mark.django_db
def test_sync_edicao_rejeita_especialidade_finalizada(client, cenario):
    esp = cenario['esp']
    esp.status = 'finalizada'
    esp.save()
    resp = _patch(client, cenario['achado'].pk, {'recomendacao': 'X'})
    assert resp.status_code == 400
    assert 'finalizada' in json.loads(resp.content)['erro'].lower()


@pytest.mark.django_db
def test_achados_para_campo_inclui_editar_url_e_fotos(client, cenario):
    from apps.inspecoes.models import Foto
    achado = cenario['achado']
    Foto.objects.create(
        achado=achado, arquivo=SimpleUploadedFile('a.jpg', b'aaaa', content_type='image/jpeg'),
        nome_original='a.jpg', tamanho_bytes=4,
    )
    resp = client.get(reverse('inspecoes:achados_para_campo', args=[cenario['esp'].pk]))
    assert resp.status_code == 200
    dados = json.loads(resp.content)
    assert len(dados) == 1
    item = dados[0]
    assert item['editar_url'] == reverse('inspecoes:achado_update', args=[achado.pk])
    assert len(item['fotos']) == 1
    assert item['fotos'][0]['nome'] == 'a.jpg'
    assert item['fotos'][0]['url']
