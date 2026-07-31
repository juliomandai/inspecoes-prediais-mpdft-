import json
import pytest
from datetime import date
from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model


@pytest.fixture
def cenario(db, client):
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
        especialidade=esp, localizacao='Subsolo', verificacao='Infiltração',
        grupo_tecnico='estrutura', requisito_afetado='durabilidade',
        gravidade=2, urgencia=2, tendencia=2, prioridade_risco=3,
    )
    return {'u': u, 'esp': esp, 'achado': achado}


def _png_minimo():
    return (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')


@pytest.mark.django_db
def test_sincronizar_foto_cria_foto_no_achado(client, cenario):
    from apps.inspecoes.models import Foto
    achado = cenario['achado']
    arquivo = SimpleUploadedFile('subsolo.png', _png_minimo(), content_type='image/png')
    resp = client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[achado.pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 201
    assert json.loads(resp.content)['ok'] is True
    assert Foto.objects.filter(achado=achado).count() == 1


@pytest.mark.django_db
def test_sincronizar_foto_rejeita_sem_arquivo(client, cenario):
    resp = client.post(reverse('inspecoes:achado_sincronizar_foto', args=[cenario['achado'].pk]))
    assert resp.status_code == 400
    assert json.loads(resp.content)['erro'] == 'Nenhum arquivo enviado.'


@pytest.mark.django_db
def test_sincronizar_foto_rejeita_formato_invalido(client, cenario):
    arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
    resp = client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[cenario['achado'].pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 400
    assert json.loads(resp.content)['erro'] == 'Formato inválido. Use JPEG ou PNG.'


@pytest.mark.django_db
def test_sincronizar_foto_funciona_com_especialidade_finalizada(client, cenario):
    """ADR-10 do design: uma foto pendente deve poder subir mesmo que a
    especialidade já tenha sido finalizada nesse meio-tempo."""
    from apps.inspecoes.models import Foto
    esp = cenario['esp']
    esp.status = 'finalizada'
    esp.save()
    arquivo = SimpleUploadedFile('subsolo.png', _png_minimo(), content_type='image/png')
    resp = client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[cenario['achado'].pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 201
    assert Foto.objects.filter(achado=cenario['achado']).count() == 1


@pytest.mark.django_db
def test_sincronizar_foto_nao_exige_csrf_token():
    """O endpoint é usado pela fila de sincronização offline (pwa.js), que não
    tem acesso a um token CSRF renderizado em página — precisa ser csrf_exempt,
    igual aos demais endpoints de sync (achado_sincronizar,
    achado_sincronizar_edicao)."""
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
    U = get_user_model()
    u = U.objects.create_user(username='maria', password='1', is_staff=True)
    edif = Edificacao.objects.create(nome='Sede 2')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='X', data_inspecao=date.today(),
    )
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=1, tendencia=1, prioridade_risco=3,
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(u)
    arquivo = SimpleUploadedFile('subsolo.png', _png_minimo(), content_type='image/png')
    resp = csrf_client.post(
        reverse('inspecoes:achado_sincronizar_foto', args=[achado.pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_foto_upload_continua_funcionando_apos_refatoracao(client, cenario):
    """Garante que extrair _criar_foto_do_upload não quebrou o endpoint online
    existente (usado pelo upload AJAX na edição, com conexão)."""
    from apps.inspecoes.models import Foto
    arquivo = SimpleUploadedFile('online.png', _png_minimo(), content_type='image/png')
    resp = client.post(
        reverse('inspecoes:foto_upload', args=[cenario['achado'].pk]),
        {'arquivo': arquivo},
    )
    assert resp.status_code == 200
    body = json.loads(resp.content)
    assert 'id' in body and 'url' in body
    assert Foto.objects.filter(achado=cenario['achado']).count() == 1
