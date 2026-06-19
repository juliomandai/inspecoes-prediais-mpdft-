import pytest
from datetime import date
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model


@pytest.mark.parametrize('gut, em_conformidade, esperado', [
    (0, True, 3),       # conforme: sempre P3, GUT é zerado em save()
    (100, True, 3),     # conforme anula qualquer GUT residual
    (75, False, 1),     # limite exato P1
    (74, False, 2),     # um abaixo do limite P1
    (20, False, 2),     # limite exato P2
    (19, False, 3),     # um abaixo do limite P2
    (1, False, 3),
])
def test_calcular_prioridade_segue_limiares_da_tela(gut, em_conformidade, esperado):
    from apps.inspecoes.models import Achado
    assert Achado.calcular_prioridade(gut, em_conformidade) == esperado


@pytest.fixture
def cenario_backup(db, client):
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
    # GUT baixo (4) mas o profissional escolheu P1 deliberadamente — o backup
    # precisa preservar essa escolha humana, não recalculá-la a partir do GUT.
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=2, tendencia=2,
        prioridade_risco=1,
    )
    return {'u': u, 'edif': edif, 'insp': insp, 'esp': esp, 'achado': achado}


@pytest.mark.django_db
def test_backup_preserva_prioridade_escolhida_pelo_profissional(client, cenario_backup):
    from apps.inspecoes.views import _gerar_zip_backup

    insp = cenario_backup['insp']
    achado = cenario_backup['achado']
    assert achado.gut_total == 4  # baixo — sugestão automática seria P3, não P1

    zip_bytes, nome = _gerar_zip_backup(insp)
    upload = SimpleUploadedFile(nome, zip_bytes, content_type='application/zip')

    resp = client.post(reverse('inspecoes:restaurar_backup'), {'backup_zip': upload})
    assert resp.status_code == 302

    from apps.inspecoes.models import Achado
    restaurado = Achado.objects.exclude(pk=achado.pk).get()
    # Prioridade do profissional (P1) preservada, mesmo com GUT baixo.
    assert restaurado.prioridade_risco == 1
    assert restaurado.gut_total == 4


@pytest.mark.django_db
def test_backup_sem_prioridade_cai_para_sugestao_do_gut(client, cenario_backup):
    """Backups gerados antes deste campo existir não têm 'prioridade_risco' no JSON."""
    import io
    import json
    import zipfile
    from apps.inspecoes.views import _gerar_zip_backup

    insp = cenario_backup['insp']
    zip_bytes, nome = _gerar_zip_backup(insp)

    # Remove o campo do JSON para simular um backup antigo.
    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf_in:
        dados = json.loads(zf_in.read('dados.json').decode('utf-8'))
        outros_nomes = [n for n in zf_in.namelist() if n != 'dados.json']
        outros_bytes = {n: zf_in.read(n) for n in outros_nomes}
    for esp_data in dados['especialidades']:
        for achado_data in esp_data['achados']:
            achado_data.pop('prioridade_risco', None)
            achado_data['gravidade'], achado_data['urgencia'], achado_data['tendencia'] = 5, 5, 5  # GUT 125 -> P1

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf_out:
        zf_out.writestr('dados.json', json.dumps(dados, ensure_ascii=False))
        for n, b in outros_bytes.items():
            zf_out.writestr(n, b)

    upload = SimpleUploadedFile(nome, buffer.getvalue(), content_type='application/zip')
    resp = client.post(reverse('inspecoes:restaurar_backup'), {'backup_zip': upload})
    assert resp.status_code == 302

    from apps.inspecoes.models import Achado
    restaurado = Achado.objects.exclude(pk=cenario_backup['achado'].pk).get()
    assert restaurado.gut_total == 125
    assert restaurado.prioridade_risco == 1  # GUT 125 >= LIMITE_GUT_P1 (75)
