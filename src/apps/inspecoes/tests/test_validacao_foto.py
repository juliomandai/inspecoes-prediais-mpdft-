import base64
import json
import pytest
from datetime import date
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from apps.inspecoes.views import erro_validacao_foto, foto_valida


@pytest.mark.parametrize('content_type, tamanho, valido', [
    ('image/jpeg', 1024, True),
    ('image/png', 10 * 1024 * 1024, True),          # exatamente no limite
    ('image/png', 10 * 1024 * 1024 + 1, False),     # 1 byte acima do limite
    ('application/pdf', 1024, False),
    ('image/gif', 1024, False),
])
def test_foto_valida_tipo_e_tamanho(content_type, tamanho, valido):
    assert foto_valida(content_type, tamanho) is valido


def test_erro_validacao_foto_mensagem_distingue_formato_de_tamanho():
    assert erro_validacao_foto('application/pdf', 1024) == 'Formato inválido. Use JPEG ou PNG.'
    assert erro_validacao_foto('image/jpeg', 99 * 1024 * 1024) == 'Arquivo muito grande. Máximo: 10 MB.'
    assert erro_validacao_foto('image/jpeg', 1024) is None


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
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=1, tendencia=1, prioridade_risco=3,
    )
    return {'u': u, 'esp': esp, 'achado': achado}


@pytest.mark.django_db
def test_foto_upload_rejeita_formato_invalido_com_mensagem_especifica(client, cenario):
    arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
    resp = client.post(reverse('inspecoes:foto_upload', args=[cenario['achado'].pk]), {'arquivo': arquivo})
    assert resp.status_code == 400
    assert json.loads(resp.content)['erro'] == 'Formato inválido. Use JPEG ou PNG.'


@pytest.mark.django_db
def test_foto_upload_rejeita_arquivo_grande_com_mensagem_especifica(client, cenario, monkeypatch):
    from apps.inspecoes import views
    monkeypatch.setattr(views, 'MAX_UPLOAD_SIZE', 10)  # baixa o limite só para este teste
    arquivo = SimpleUploadedFile('foto.jpg', b'x' * 100, content_type='image/jpeg')
    resp = client.post(reverse('inspecoes:foto_upload', args=[cenario['achado'].pk]), {'arquivo': arquivo})
    assert resp.status_code == 400
    assert json.loads(resp.content)['erro'] == 'Arquivo muito grande. Máximo: 10 MB.'


@pytest.mark.django_db
def test_sincronizar_ignora_foto_invalida_mas_salva_achado(client, cenario):
    from apps.inspecoes.models import Achado, Foto
    payload = {
        'esp_pk': cenario['esp'].pk,
        'localizacao': 'L2', 'verificacao': 'V2', 'grupo_tecnico': 'estrutura',
        'gravidade': 3, 'urgencia': 3, 'tendencia': 3,
        'fotos': [
            {'nome': 'malware.exe', 'tipo': 'application/x-msdownload',
             'dados_b64': base64.b64encode(b'qualquer coisa').decode()},
        ],
    }
    resp = client.post(
        reverse('inspecoes:achado_sincronizar'),
        data=json.dumps(payload), content_type='application/json',
    )
    assert resp.status_code == 201
    body = json.loads(resp.content)
    assert body['fotos_salvas'] == 0
    novo = Achado.objects.get(pk=body['achado_pk'])
    assert not Foto.objects.filter(achado=novo).exists()
