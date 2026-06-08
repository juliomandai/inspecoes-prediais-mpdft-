import pytest


@pytest.mark.django_db
def test_infra_pytest_funciona():
    from apps.edificacoes.models import Edificacao
    edif = Edificacao.objects.create(nome="Predio Teste")
    assert edif.pk is not None


from datetime import date, timedelta
from django.core.exceptions import ValidationError
from apps.edificacoes.models import Edificacao


@pytest.fixture
def edificacao(db):
    return Edificacao.objects.create(nome="Promotoria Central")


@pytest.mark.django_db
def test_cria_visita_valida(edificacao):
    from apps.inspecoes.models import VisitaTecnica
    v = VisitaTecnica.objects.create(
        edificacao=edificacao,
        data_visita=date.today(),
        responsavel="Maria Souza",
        motivo="Vistoria de rotina",
        achados="Sem anomalias relevantes.",
        conclusoes_encaminhamentos="Nada a encaminhar.",
    )
    assert v.pk is not None
    assert str(v) == f"Promotoria Central — {date.today():%d/%m/%Y}"


@pytest.mark.django_db
def test_data_visita_futura_invalida(edificacao):
    from apps.inspecoes.models import VisitaTecnica
    v = VisitaTecnica(
        edificacao=edificacao,
        data_visita=date.today() + timedelta(days=1),
        responsavel="Maria Souza",
        motivo="x", achados="x", conclusoes_encaminhamentos="x",
    )
    with pytest.raises(ValidationError):
        v.full_clean()


@pytest.mark.django_db
def test_visita_foto_vinculada(edificacao):
    from apps.inspecoes.models import VisitaTecnica, VisitaFoto
    from django.core.files.base import ContentFile
    v = VisitaTecnica.objects.create(
        edificacao=edificacao, data_visita=date.today(),
        responsavel="X", motivo="x", achados="x", conclusoes_encaminhamentos="x",
    )
    f = VisitaFoto.objects.create(
        visita=v,
        arquivo=ContentFile(b"fake", name="foto.jpg"),
        nome_original="foto.jpg",
        tamanho_bytes=4,
    )
    assert v.fotos.count() == 1
    assert f.visita_id == v.pk


@pytest.mark.django_db
def test_logacesso_tem_tipos_de_visita():
    from apps.inspecoes.models import LogAcesso
    tipos = dict(LogAcesso.TIPO_CHOICES)
    assert "visita_criada" in tipos
    assert "visita_excluida" in tipos


@pytest.mark.django_db
def test_visita_form_valido(edificacao):
    from apps.inspecoes.forms import VisitaTecnicaForm
    form = VisitaTecnicaForm(data={
        'data_visita': date.today().isoformat(),
        'responsavel': 'João',
        'motivo': 'Vistoria',
        'achados': 'ok',
        'conclusoes_encaminhamentos': 'ok',
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_visita_form_rejeita_data_futura(edificacao):
    from apps.inspecoes.forms import VisitaTecnicaForm
    form = VisitaTecnicaForm(data={
        'data_visita': (date.today() + timedelta(days=2)).isoformat(),
        'responsavel': 'João', 'motivo': 'x',
        'achados': 'x', 'conclusoes_encaminhamentos': 'x',
    })
    assert not form.is_valid()
    assert 'data_visita' in form.errors


from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def usuario_logado(db, client):
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='123', first_name='Ze', last_name='Silva')
    client.force_login(u)
    return u


@pytest.mark.django_db
def test_home_mostra_menu(client, usuario_logado):
    resp = client.get(reverse('inspecoes:home'))
    assert resp.status_code == 200
    assert b'Inspe' in resp.content
    assert b'Visita' in resp.content


@pytest.mark.django_db
def test_lista_inspecoes_em_inspecoes_url(client, usuario_logado):
    resp = client.get(reverse('inspecoes:list'))
    assert resp.status_code == 200
    assert resp.request['PATH_INFO'] == '/inspecoes/'


@pytest.mark.django_db
def test_lista_localidades_mostra_edificacoes_ativas(client, usuario_logado):
    from apps.edificacoes.models import Edificacao
    Edificacao.objects.create(nome="Sede A")
    Edificacao.objects.create(nome="Sede Inativa", ativo=False)
    resp = client.get(reverse('inspecoes:visita_localidades'))
    assert resp.status_code == 200
    assert b'Sede A' in resp.content
    assert b'Sede Inativa' not in resp.content


@pytest.mark.django_db
def test_visita_list_filtra_por_data(client, usuario_logado, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date(2026, 1, 10),
                                 responsavel="A", motivo="m1", achados="x", conclusoes_encaminhamentos="x")
    VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date(2026, 6, 10),
                                 responsavel="A", motivo="m2", achados="x", conclusoes_encaminhamentos="x")
    url = reverse('inspecoes:visita_list', args=[edificacao.pk])
    resp = client.get(url, {'data_inicio': '2026-05-01', 'data_fim': '2026-12-31'})
    assert resp.status_code == 200
    assert b'm2' in resp.content
    assert b'm1' not in resp.content


@pytest.mark.django_db
def test_cria_visita_via_post_com_foto(client, usuario_logado, edificacao):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.inspecoes.models import VisitaTecnica, LogAcesso
    png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
           b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
           b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    foto = SimpleUploadedFile('v.png', png, content_type='image/png')
    url = reverse('inspecoes:visita_create', args=[edificacao.pk])
    resp = client.post(url, {
        'data_visita': date.today().isoformat(),
        'responsavel': 'Ze Silva',
        'motivo': 'Vistoria geral',
        'achados': 'tudo certo',
        'conclusoes_encaminhamentos': 'nada',
        'fotos': [foto],
    })
    assert resp.status_code == 302
    v = VisitaTecnica.objects.get(edificacao=edificacao)
    assert v.responsavel == 'Ze Silva'
    assert v.criado_por_id == usuario_logado.pk
    assert v.fotos.count() == 1
    assert LogAcesso.objects.filter(tipo='visita_criada').exists()


@pytest.mark.django_db
def test_visita_detail_exibe_dados(client, usuario_logado, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel="Carla", motivo="Inspecao eletrica", achados="achado X",
        conclusoes_encaminhamentos="encaminhar Y")
    resp = client.get(reverse('inspecoes:visita_detail', args=[v.pk]))
    assert resp.status_code == 200
    assert b'Carla' in resp.content
    assert b'achado X' in resp.content
    assert b'encaminhar Y' in resp.content


@pytest.mark.django_db
def test_outro_usuario_nao_exclui_visita(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    U = get_user_model()
    dono = U.objects.create_user(username='dona', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    outro = U.objects.create_user(username='outro', password='1', first_name='Beto', last_name='Reis')
    client.force_login(outro)
    resp = client.post(reverse('inspecoes:visita_delete', args=[v.pk]))
    assert resp.status_code == 302
    assert VisitaTecnica.objects.filter(pk=v.pk).exists()


@pytest.mark.django_db
def test_responsavel_exclui_visita(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica, LogAcesso
    U = get_user_model()
    dono = U.objects.create_user(username='dona2', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    client.force_login(dono)
    resp = client.post(reverse('inspecoes:visita_delete', args=[v.pk]))
    assert resp.status_code == 302
    assert not VisitaTecnica.objects.filter(pk=v.pk).exists()
    assert LogAcesso.objects.filter(tipo='visita_excluida').exists()


@pytest.mark.django_db
def test_responsavel_edita_visita(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    U = get_user_model()
    dono = U.objects.create_user(username='dona3', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='antigo', achados='x', conclusoes_encaminhamentos='x')
    client.force_login(dono)
    resp = client.post(reverse('inspecoes:visita_update', args=[v.pk]), {
        'data_visita': date.today().isoformat(), 'responsavel': 'Ana Lima',
        'motivo': 'novo motivo', 'achados': 'x', 'conclusoes_encaminhamentos': 'x',
    })
    assert resp.status_code == 302
    v.refresh_from_db()
    assert v.motivo == 'novo motivo'


@pytest.mark.django_db
def test_upload_foto_visita_ajax(client, usuario_logado, edificacao):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.inspecoes.models import VisitaTecnica
    png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
           b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
           b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='X', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    foto = SimpleUploadedFile('a.png', png, content_type='image/png')
    resp = client.post(reverse('inspecoes:visita_foto_upload', args=[v.pk]), {'arquivo': foto})
    assert resp.status_code == 200
    assert resp.json()['id']
    assert v.fotos.count() == 1


@pytest.mark.django_db
def test_delete_foto_visita(client, usuario_logado, edificacao):
    from django.core.files.base import ContentFile
    from apps.inspecoes.models import VisitaTecnica, VisitaFoto
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='X', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    f = VisitaFoto.objects.create(visita=v, arquivo=ContentFile(b'x', name='a.jpg'),
                                  nome_original='a.jpg', tamanho_bytes=1)
    resp = client.delete(reverse('inspecoes:visita_foto_delete', args=[f.pk]))
    assert resp.status_code == 204
    assert v.fotos.count() == 0


@pytest.mark.django_db
def test_form_criacao_renderiza(client, usuario_logado, edificacao):
    resp = client.get(reverse('inspecoes:visita_create', args=[edificacao.pk]))
    assert resp.status_code == 200
    assert b'Nova Visita' in resp.content
    # responsavel pré-preenchido com o nome do usuário logado
    assert b'Ze Silva' in resp.content


@pytest.mark.django_db
def test_form_edicao_renderiza(client, edificacao):
    from apps.inspecoes.models import VisitaTecnica
    U = get_user_model()
    dono = U.objects.create_user(username='donaf', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date.today(),
        responsavel='Ana Lima', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    client.force_login(dono)
    resp = client.get(reverse('inspecoes:visita_update', args=[v.pk]))
    assert resp.status_code == 200
    assert b'Editar Visita' in resp.content


@pytest.mark.django_db
def test_form_edicao_renderiza_data_em_iso(client, edificacao):
    """O input type=date precisa do valor em AAAA-MM-DD, senão some na edição."""
    from apps.inspecoes.models import VisitaTecnica
    U = get_user_model()
    dono = U.objects.create_user(username='donag', password='1', first_name='Ana', last_name='Lima')
    v = VisitaTecnica.objects.create(edificacao=edificacao, data_visita=date(2026, 6, 5),
        responsavel='Ana Lima', motivo='m', achados='x', conclusoes_encaminhamentos='x')
    client.force_login(dono)
    resp = client.get(reverse('inspecoes:visita_update', args=[v.pk]))
    assert b'value="2026-06-05"' in resp.content


@pytest.mark.django_db
def test_especialidade_edicao_renderiza_data_em_iso(client, edificacao):
    """Mesmo bug de data ISO no formulário de especialidade (inspeções)."""
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
    U = get_user_model()
    u = U.objects.create_user(username='espuser', password='1', is_staff=True)
    client.force_login(u)
    insp = Inspecao.objects.create(edificacao=edificacao)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil',
        profissional='Fulano', data_inspecao=date(2026, 6, 5),
    )
    resp = client.get(reverse('inspecoes:especialidade_update', args=[esp.pk]))
    assert resp.status_code == 200
    assert b'value="2026-06-05"' in resp.content
