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


@pytest.mark.django_db
def test_gerar_relatorio_final_cria_versao_1_e_bloqueia_sem_pendencias_resolvidas(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)

    # falta mecânica — deve ser bloqueado, nenhuma versão criada
    resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    assert resp.status_code == 302
    assert inspecao_com_profissionais.relatorios_finais.count() == 0

    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')

    resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    assert resp.status_code == 302
    assert inspecao_com_profissionais.relatorios_finais.count() == 1
    relatorio = inspecao_com_profissionais.relatorios_finais.first()
    assert relatorio.numero_versao == 1
    assert relatorio.gerado_por == civil
    assert relatorio.arquivo_pdf.name
    assert relatorio.snapshot['edificacao_nome'] == 'Sede'

    # gerar de novo cria a versão 2, não sobrescreve a 1
    resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    assert inspecao_com_profissionais.relatorios_finais.count() == 2
    assert set(inspecao_com_profissionais.relatorios_finais.values_list('numero_versao', flat=True)) == {1, 2}

    from apps.inspecoes.models import LogAcesso
    assert LogAcesso.objects.filter(tipo='relatorio_final_gerado').count() == 2


@pytest.mark.django_db
def test_foto_embutida_como_data_uri_no_pdf_mas_nao_no_snapshot_persistido(inspecao_com_profissionais):
    """Cobre a correção feita durante a execução: o xhtml2pdf não resolve
    MEDIA_URL/caminhos de arquivo, então as fotos entram no HTML do PDF como
    data URI base64 (`_montar_contexto_pdf_com_fotos`) — mas o `snapshot`
    que é de fato persistido em `RelatorioFinalInspecao.snapshot` continua
    leve, com o caminho do arquivo, não a imagem inflada em base64."""
    from apps.inspecoes.views import _montar_snapshot_relatorio, _montar_contexto_pdf_com_fotos

    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    achado = Achado.objects.create(
        especialidade=civil, localizacao='L1', verificacao='Rachadura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=5, urgencia=5, tendencia=5,
    )
    Foto.objects.create(
        achado=achado, arquivo=SimpleUploadedFile('f.jpg', b'conteudo-fake', content_type='image/jpeg'),
        nome_original='f.jpg',
    )

    snapshot = _montar_snapshot_relatorio(inspecao_com_profissionais, numero_versao=1)
    contexto_pdf = _montar_contexto_pdf_com_fotos(snapshot)

    civil_pdf = next(e for e in contexto_pdf['especialidades'] if e['especialidade'] == 'civil')
    fotos_pdf = civil_pdf['achados_completos'][0]['fotos']
    assert len(fotos_pdf) == 1
    assert fotos_pdf[0].startswith('data:image/jpeg;base64,')

    civil_original = next(e for e in snapshot['especialidades'] if e['especialidade'] == 'civil')
    assert not civil_original['achados_completos'][0]['fotos'][0].startswith('data:')


@pytest.mark.django_db
def test_falha_na_geracao_do_pdf_limpa_fotos_ja_copiadas(client, inspecao_com_profissionais):
    """Cobre o achado da revisão de qualidade: `_montar_snapshot_relatorio`
    (chamado antes de `_gerar_pdf_bytes`) já copiou as fotos para
    relatorios/<pk>/v<N>/... antes de sabermos se o PDF vai ser gerado com
    sucesso. Se `_gerar_pdf_bytes` falhar, essas cópias não podem ficar
    órfãs — nenhuma RelatorioFinalInspecao vai apontar pra elas.

    Captura os caminhos reais via um espião em `_montar_snapshot_relatorio`
    em vez de prever o nome do arquivo: o storage de mídia deste projeto não
    é isolado por teste, então um arquivo de uma execução anterior pode já
    ocupar o nome "óbvio" e forçar o Django a usar um sufixo diferente.
    """
    from unittest.mock import patch
    from django.core.files.storage import default_storage
    import apps.inspecoes.views as views_module

    U = get_user_model()
    civil_user = U.objects.create_user(username='ana2', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil_user)

    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')
    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    achado = Achado.objects.create(
        especialidade=civil, localizacao='L1', verificacao='Rachadura',
        grupo_tecnico='estrutura', requisito_afetado='seguranca_estrutural',
        gravidade=5, urgencia=5, tendencia=5,
    )
    Foto.objects.create(
        achado=achado, arquivo=SimpleUploadedFile('f1.jpg', b'conteudo1', content_type='image/jpeg'),
        nome_original='f1.jpg',
    )
    Foto.objects.create(
        achado=achado, arquivo=SimpleUploadedFile('f2.jpg', b'conteudo2', content_type='image/jpeg'),
        nome_original='f2.jpg',
    )

    capturado = {}
    original_montar_snapshot = views_module._montar_snapshot_relatorio

    def _snapshot_espiao(inspecao, numero_versao):
        resultado = original_montar_snapshot(inspecao, numero_versao)
        capturado['snapshot'] = resultado
        return resultado

    with patch('apps.inspecoes.views._montar_snapshot_relatorio', side_effect=_snapshot_espiao), \
         patch('apps.inspecoes.views._gerar_pdf_bytes', return_value=None):
        resp = client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))

    assert resp.status_code == 302
    assert inspecao_com_profissionais.relatorios_finais.count() == 0

    snapshot = capturado['snapshot']
    civil_data = next(e for e in snapshot['especialidades'] if e['especialidade'] == 'civil')
    caminhos_copiados = civil_data['achados_completos'][0]['fotos']
    assert len(caminhos_copiados) == 2  # sanity: as fotos foram de fato copiadas antes da falha
    for caminho in caminhos_copiados:
        assert not default_storage.exists(caminho)


@pytest.mark.django_db
def test_download_relatorio_final(client, inspecao_com_profissionais):
    U = get_user_model()
    civil = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil)
    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')
    client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))
    relatorio = inspecao_com_profissionais.relatorios_finais.get()

    resp = client.get(reverse('inspecoes:relatorio_final_download', kwargs={'pk': inspecao_com_profissionais.pk, 'versao_pk': relatorio.pk}))

    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert resp.content.startswith(b'%PDF')


@pytest.mark.django_db
def test_reabrir_especialidade_avisa_quando_ja_ha_relatorio_gerado(client, inspecao_com_profissionais):
    U = get_user_model()
    civil_user = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil_user)
    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')
    client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))

    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    resp = client.post(reverse('inspecoes:especialidade_reabrir', kwargs={'pk': civil.pk}), follow=True)

    assert resp.status_code == 200
    mensagens = [str(m) for m in resp.context['messages']]
    assert any('Relatório Final' in m and 'v1' in m for m in mensagens)


@pytest.mark.django_db
def test_editar_especialidade_finalizada_avisa_quando_ja_ha_relatorio_gerado(client, inspecao_com_profissionais):
    U = get_user_model()
    civil_user = U.objects.create_user(username='ana', password='1', first_name='Ana', last_name='Civil')
    client.force_login(civil_user)
    InspecaoEspecialidade.objects.create(
        inspecao=inspecao_com_profissionais, especialidade='mecanica', profissional='Carlos Mecanica',
        data_inspecao=date.today(), conclusao='ok', status='finalizada',
    )
    inspecao_com_profissionais.especialidades.update(status='finalizada')
    client.post(reverse('inspecoes:relatorio_final_gerar', kwargs={'pk': inspecao_com_profissionais.pk}))

    civil = inspecao_com_profissionais.especialidades.get(especialidade='civil')
    resp = client.post(
        reverse('inspecoes:especialidade_update', kwargs={'pk': civil.pk}),
        {
            'especialidade': 'civil',
            'data_inspecao': civil.data_inspecao.isoformat(),
            'conclusao': 'Conclusão revisada após gerar o relatório.',
            'profissionais': ['Ana Civil'],
        },
        follow=True,
    )

    assert resp.status_code == 200
    civil.refresh_from_db()
    assert civil.conclusao == 'Conclusão revisada após gerar o relatório.'
    mensagens = [str(m) for m in resp.context['messages']]
    assert any('Relatório Final' in m and 'v1' in m for m in mensagens)
