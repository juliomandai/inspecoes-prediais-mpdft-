import pytest
from datetime import date
from django.urls import reverse
from django.contrib.auth import get_user_model


def test_rosca_vazia_retorna_none():
    from apps.inspecoes.views import _grafico_rosca_risco
    assert _grafico_rosca_risco(0, 0, 0) is None


def test_rosca_gera_imagem():
    from apps.inspecoes.views import _grafico_rosca_risco
    uri = _grafico_rosca_risco(2, 1, 3)
    assert uri.startswith('data:image/png;base64,')


def test_barras_vazia_retorna_none():
    from apps.inspecoes.views import _grafico_barras_prazo
    assert _grafico_barras_prazo([]) is None
    assert _grafico_barras_prazo([{'label': '1 mês', 'total': 0}]) is None


def test_barras_gera_imagem():
    from apps.inspecoes.views import _grafico_barras_prazo
    uri = _grafico_barras_prazo([{'label': '1 mês', 'total': 3}, {'label': '12 meses', 'total': 1}])
    assert uri.startswith('data:image/png;base64,')


@pytest.mark.django_db
def test_pdf_especialidade_retorna_pdf_com_imagens(client):
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Fulano', data_inspecao=date.today())
    Achado.objects.create(
        especialidade=esp, localizacao='Térreo', verificacao='Fissura',
        grupo_tecnico='Estrutura', requisito_afetado='Segurança Estrutural',
        gravidade=5, urgencia=5, tendencia=5, prioridade_risco=1,
        direcionamento='manutencao', prazo_meses=1,
    )
    resp = client.get(reverse('inspecoes:analise_pdf', args=[esp.pk]))
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert b'%PDF' in resp.content[:10]
    assert b'/Image' in resp.content  # gráficos embutidos
