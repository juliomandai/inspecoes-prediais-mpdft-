import pytest
from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade
from apps.inspecoes.views import _pode_gerar_relatorio_final

from django.core.files.uploadedfile import SimpleUploadedFile
from apps.inspecoes.models import Achado, Foto
from apps.inspecoes.views import _montar_snapshot_relatorio


@pytest.fixture
def inspecao_com_profissionais(db):
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana Civil',
        data_inspecao=date.today(), conclusao='ok',
    )
    InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='eletrica', profissional='Beto Eletrica',
        data_inspecao=date.today(), conclusao='ok',
    )
    return insp


@pytest.mark.django_db
def test_profissional_de_qualquer_uma_das_especialidades_pode_gerar(inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    eletrica = U.objects.create_user(username='beto', password='1', first_name='Beto', last_name='Eletrica')
    estranho = U.objects.create_user(username='carlos', password='1', first_name='Carlos', last_name='Estranho')
    staff = U.objects.create_user(username='staff', password='1', is_staff=True)

    assert _pode_gerar_relatorio_final(civil, inspecao_com_profissionais)
    assert _pode_gerar_relatorio_final(eletrica, inspecao_com_profissionais)
    assert not _pode_gerar_relatorio_final(estranho, inspecao_com_profissionais)
    assert _pode_gerar_relatorio_final(staff, inspecao_com_profissionais)


@pytest.mark.django_db
def test_painel_mostra_pendencias_para_quem_tem_acesso(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)

    resp = client.get(reverse('inspecoes:relatorio_final_painel', kwargs={'pk': inspecao_com_profissionais.pk}))

    assert resp.status_code == 200
    assert 'Falta cadastrar' in resp.content.decode()  # falta Mecânica


@pytest.mark.django_db
def test_painel_nega_acesso_a_quem_nao_participou(client, inspecao_com_profissionais):
    U = get_user_model()
    estranho = U.objects.create_user(username='carlos', password='1', first_name='Carlos', last_name='Estranho')
    client.force_login(estranho)

    resp = client.get(reverse('inspecoes:relatorio_final_painel', kwargs={'pk': inspecao_com_profissionais.pk}), follow=True)

    assert resp.status_code == 200
    assert 'Acesso negado' in resp.content.decode()


@pytest.mark.django_db
def test_editar_descritivo_pelo_painel(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)

    resp = client.post(
        reverse('inspecoes:relatorio_final_editar_descritivo', kwargs={'pk': inspecao_com_profissionais.pk}),
        {'descritivo': 'Prédio de 4 pavimentos, estrutura em concreto armado.'},
    )

    assert resp.status_code == 302
    inspecao_com_profissionais.edificacao.refresh_from_db()
    assert inspecao_com_profissionais.edificacao.descritivo == 'Prédio de 4 pavimentos, estrutura em concreto armado.'


@pytest.mark.django_db
def test_snapshot_copia_fotos_e_resume_conformes(inspecao_com_profissionais):
    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    nc = Achado.objects.create(
        especialidade=civil, localizacao='L1', verificacao='Rachadura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=5, urgencia=5, tendencia=5, recomendacao='Reparar',
    )
    for i in range(3):  # 3 fotos — só as 2 mais antigas devem entrar
        Foto.objects.create(
            achado=nc, arquivo=SimpleUploadedFile(f'f{i}.jpg', f'conteudo{i}'.encode(), content_type='image/jpeg'),
            nome_original=f'f{i}.jpg',
        )
    conforme = Achado.objects.create(
        especialidade=civil, localizacao='L2', verificacao='Piso ok', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True,
    )

    snapshot = _montar_snapshot_relatorio(inspecao_com_profissionais, numero_versao=1)

    civil_data = next(e for e in snapshot['especialidades'] if e['especialidade'] == 'civil')
    assert len(civil_data['achados_completos']) == 1
    assert len(civil_data['achados_completos'][0]['fotos']) == 2
    assert civil_data['achados_resumidos'] == [{'localizacao': 'L2', 'verificacao': 'Piso ok'}]

    # as fotos foram de fato copiadas para um caminho próprio do relatório
    from django.core.files.storage import default_storage
    for caminho in civil_data['achados_completos'][0]['fotos']:
        assert default_storage.exists(caminho)
        assert caminho.startswith(f'relatorios/{inspecao_com_profissionais.pk}/v1/')


@pytest.mark.django_db
def test_snapshot_inclui_dados_gerais_iguais_ao_painel_de_encerramento(inspecao_com_profissionais):
    """ADR da Seção 6 do design doc: o relatório reaproveita os mesmos
    números do painel de encerramento (análise geral) — não só a listagem
    itemizada de achados."""
    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    Achado.objects.create(
        especialidade=civil, localizacao='L1', verificacao='Rachadura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=5, urgencia=5, tendencia=5, prioridade_risco=1,
    )
    Achado.objects.create(
        especialidade=civil, localizacao='L2', verificacao='Piso ok', grupo_tecnico='',
        requisito_afetado='', em_conformidade=True,
    )

    snapshot = _montar_snapshot_relatorio(inspecao_com_profissionais, numero_versao=1)

    gerais = snapshot['dados_gerais']
    assert gerais['total_achados'] == 2
    assert gerais['total_nao_conformes'] == 1
    assert gerais['total_conformes'] == 1
    assert gerais['p1'] == 1
    civil_gerais = next(e for e in gerais['por_especialidade'] if e['especialidade_nome'] == 'Engenharia Civil')
    assert civil_gerais == {'especialidade_nome': 'Engenharia Civil', 'total': 2, 'total_nc': 1, 'p1': 1, 'p2': 0, 'p3': 0}
