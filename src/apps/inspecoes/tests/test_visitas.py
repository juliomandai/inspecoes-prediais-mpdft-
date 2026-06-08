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
