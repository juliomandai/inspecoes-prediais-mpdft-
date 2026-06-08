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
