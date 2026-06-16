import pytest
from datetime import date, timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.fixture
def edificacao(db):
    from apps.edificacoes.models import Edificacao
    return Edificacao.objects.create(nome='Sede Teste')


@pytest.fixture
def usuario_logado(db, client):
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)
    return u


@pytest.mark.django_db
def test_criar_inspecao_com_data_escolhida(client, usuario_logado, edificacao):
    from apps.inspecoes.models import Inspecao
    resp = client.post(reverse('inspecoes:create'), {
        'edificacao': edificacao.pk,
        'data_criacao': '2025-01-15',
    })
    assert resp.status_code == 302
    insp = Inspecao.objects.get(edificacao=edificacao)
    assert insp.criado_em.date().isoformat() == '2025-01-15'


@pytest.mark.django_db
def test_editar_data_criacao_preserva_hora(client, usuario_logado, edificacao):
    from apps.inspecoes.models import Inspecao
    from django.utils import timezone
    insp = Inspecao.objects.create(edificacao=edificacao)
    local_antes = timezone.localtime(insp.criado_em)
    hora_original = (local_antes.hour, local_antes.minute)
    resp = client.post(reverse('inspecoes:update', args=[insp.pk]), {
        'edificacao': edificacao.pk,
        'data_criacao': '2024-03-10',
    })
    assert resp.status_code == 302
    insp.refresh_from_db()
    local = timezone.localtime(insp.criado_em)
    assert local.date().isoformat() == '2024-03-10'
    assert (local.hour, local.minute) == hora_original


@pytest.mark.django_db
def test_form_edicao_mostra_data_em_iso(client, usuario_logado, edificacao):
    from apps.inspecoes.models import Inspecao
    insp = Inspecao.objects.create(edificacao=edificacao)
    resp = client.get(reverse('inspecoes:update', args=[insp.pk]))
    assert resp.status_code == 200
    assert b'name="data_criacao"' in resp.content
    assert b'value="' + insp.criado_em.strftime('%Y-%m-%d').encode() in resp.content


@pytest.mark.django_db
def test_especialidade_aceita_data_futura(client, usuario_logado, edificacao):
    """Especialidade pode ter data de inspeção futura (pré-cadastro)."""
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
    insp = Inspecao.objects.create(edificacao=edificacao)
    futura = date.today() + timedelta(days=10)
    url = reverse('inspecoes:especialidade_create', args=[insp.pk])
    resp = client.post(url, {
        'especialidade': 'civil',
        'profissionais': 'Fulano de Tal',
        'data_inspecao': futura.isoformat(),
    })
    assert resp.status_code == 302
    esp = InspecaoEspecialidade.objects.get(inspecao=insp)
    assert esp.data_inspecao == futura


@pytest.mark.django_db
def test_data_criacao_futura_permitida(client, usuario_logado, edificacao):
    """Datas futuras são permitidas para pré-cadastrar uma inspeção."""
    from apps.inspecoes.models import Inspecao
    futura = (date.today() + timedelta(days=3)).isoformat()
    resp = client.post(reverse('inspecoes:create'), {
        'edificacao': edificacao.pk,
        'data_criacao': futura,
    })
    assert resp.status_code == 302
    insp = Inspecao.objects.get(edificacao=edificacao)
    assert insp.criado_em.date().isoformat() == futura
