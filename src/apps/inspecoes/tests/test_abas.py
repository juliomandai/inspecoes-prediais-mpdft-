import re
import pytest
from datetime import date
from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.fixture
def cenario(db, client):
    from apps.edificacoes.models import Edificacao
    from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
    U = get_user_model()
    u = U.objects.create_user(username='ze', password='1', is_staff=True)
    client.force_login(u)
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    civ = InspecaoEspecialidade.objects.create(inspecao=insp, especialidade='civil',
        profissional='X', data_inspecao=date.today())
    ele = InspecaoEspecialidade.objects.create(inspecao=insp, especialidade='eletrica',
        profissional='X', data_inspecao=date.today())
    return insp, civ, ele


def _pane_ativo(content, esp_pk):
    return bool(re.search(r'show active"\s+id="pane-%d"' % esp_pk, content))


@pytest.mark.django_db
def test_aba_param_ativa_especialidade_correta(client, cenario):
    insp, civ, ele = cenario
    resp = client.get(reverse('inspecoes:detail', args=[insp.pk]) + f'?aba={ele.pk}')
    content = resp.content.decode()
    assert _pane_ativo(content, ele.pk)
    assert not _pane_ativo(content, civ.pk)


@pytest.mark.django_db
def test_sem_aba_ativa_a_primeira(client, cenario):
    insp, civ, ele = cenario
    resp = client.get(reverse('inspecoes:detail', args=[insp.pk]))
    content = resp.content.decode()
    assert _pane_ativo(content, civ.pk)
    assert not _pane_ativo(content, ele.pk)


@pytest.mark.django_db
def test_aba_invalida_cai_na_primeira(client, cenario):
    insp, civ, ele = cenario
    resp = client.get(reverse('inspecoes:detail', args=[insp.pk]) + '?aba=99999')
    content = resp.content.decode()
    assert _pane_ativo(content, civ.pk)


@pytest.mark.django_db
def test_criar_achado_redireciona_para_aba_da_especialidade(client, cenario):
    from apps.inspecoes.models import Achado, OpcaoCampo
    insp, civ, ele = cenario
    OpcaoCampo.objects.create(campo='localizacao', label='Terreo', ativo=True)
    resp = client.post(reverse('inspecoes:achado_create', args=[ele.pk]), {
        'localizacao': 'Terreo', 'verificacao': 'Teste', 'em_conformidade': 'on',
        'grupo_tecnico': '', 'requisito_afetado': '',
        'gravidade': 1, 'urgencia': 1, 'tendencia': 1,
        'prioridade_risco': 3, 'direcionamento': 'manutencao', 'prazo_meses': 12,
    })
    assert resp.status_code == 302
    assert resp.url.endswith(f'?aba={ele.pk}')
    assert Achado.objects.filter(especialidade=ele).exists()
