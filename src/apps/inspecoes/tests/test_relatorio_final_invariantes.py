import pytest
from datetime import date
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import IntegrityError
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado, Foto
from apps.inspecoes.models import RelatorioFinalInspecao


@pytest.mark.django_db
def test_conclusao_aceita_texto_livre_e_pode_ficar_vazia():
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana', data_inspecao=date.today(),
    )
    assert esp.conclusao == ''
    esp.conclusao = 'Estrutura em bom estado geral; recomenda-se manutenção preventiva nos itens 3 e 7.'
    esp.save(update_fields=['conclusao'])
    esp.refresh_from_db()
    assert 'manutenção preventiva' in esp.conclusao


@pytest.mark.django_db
def test_finalizar_especialidade_exige_conclusao_preenchida():
    U = get_user_model()
    u = U.objects.create_user(username='ana', password='1', is_staff=True)
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade='civil', profissional='Ana', data_inspecao=date.today(),
    )
    Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=1, urgencia=1, tendencia=1, em_conformidade=True,
    )
    client = pytest.importorskip('django.test').Client()
    client.force_login(u)

    resp = client.post(reverse('inspecoes:especialidade_finalizar', kwargs={'pk': esp.pk}))
    esp.refresh_from_db()
    assert esp.status == 'em_andamento'  # bloqueado: sem conclusão

    esp.conclusao = 'Sem não conformidades relevantes nesta vistoria.'
    esp.save(update_fields=['conclusao'])
    resp = client.post(reverse('inspecoes:especialidade_finalizar', kwargs={'pk': esp.pk}))
    esp.refresh_from_db()
    assert esp.status == 'finalizada'


@pytest.mark.django_db
def test_relatorio_final_e_versionado_e_unico_por_inspecao():
    U = get_user_model()
    u = U.objects.create_user(username='ana', password='1')
    edif = Edificacao.objects.create(nome='Sede')
    insp = Inspecao.objects.create(edificacao=edif)

    r1 = RelatorioFinalInspecao.objects.create(
        inspecao=insp, numero_versao=1, snapshot={'ok': True}, gerado_por=u,
    )
    r1.arquivo_pdf.save('teste.pdf', ContentFile(b'%PDF-fake'), save=True)
    r2 = RelatorioFinalInspecao.objects.create(
        inspecao=insp, numero_versao=2, snapshot={'ok': True}, gerado_por=u,
    )

    assert list(insp.relatorios_finais.all()) == [r2, r1]  # ordering = ['-numero_versao']
    assert RelatorioFinalInspecao.objects.filter(pk=r1.pk).exists()  # gerar de novo não apaga o anterior

    with pytest.raises(IntegrityError):
        RelatorioFinalInspecao.objects.create(inspecao=insp, numero_versao=1, snapshot={}, gerado_por=u)


def _criar_especialidade(insp, especialidade, conclusao='Conclusão padrão.', finalizada=True):
    esp = InspecaoEspecialidade.objects.create(
        inspecao=insp, especialidade=especialidade, profissional='Ana',
        data_inspecao=date.today(), conclusao=conclusao,
    )
    if finalizada:
        esp.status = 'finalizada'
        esp.save(update_fields=['status'])
    return esp


def _achado_nao_conforme(esp, n_fotos=2):
    achado = Achado.objects.create(
        especialidade=esp, localizacao='L1', verificacao='V', grupo_tecnico='estrutura',
        requisito_afetado='durabilidade', gravidade=4, urgencia=4, tendencia=4,
    )
    for i in range(n_fotos):
        Foto.objects.create(
            achado=achado,
            arquivo=SimpleUploadedFile(f'f{i}.jpg', b'fake', content_type='image/jpeg'),
            nome_original=f'f{i}.jpg',
        )
    return achado


@pytest.mark.django_db
def test_pendencia_quando_falta_especialidade():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    _criar_especialidade(insp, 'civil')
    _criar_especialidade(insp, 'eletrica')
    # mecânica nunca cadastrada
    pendencias = insp.pendencias_relatorio_final()
    assert any('Falta cadastrar' in p and 'Mecânica' in p for p in pendencias)
    assert not insp.pode_gerar_relatorio_final


@pytest.mark.django_db
def test_pendencia_quando_especialidade_nao_finalizada():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    _criar_especialidade(insp, 'civil', finalizada=False)
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    pendencias = insp.pendencias_relatorio_final()
    assert any('não finalizada' in p for p in pendencias)
    assert not insp.pode_gerar_relatorio_final


@pytest.mark.django_db
def test_pendencia_quando_falta_descritivo_da_edificacao():
    edif = Edificacao.objects.create(nome='Sede')  # sem descritivo
    insp = Inspecao.objects.create(edificacao=edif)
    for e in ('civil', 'eletrica', 'mecanica'):
        _criar_especialidade(insp, e)
    pendencias = insp.pendencias_relatorio_final()
    assert any('descritivo' in p for p in pendencias)


@pytest.mark.django_db
def test_pendencia_quando_falta_conclusao_de_alguma_especialidade():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    _criar_especialidade(insp, 'civil', conclusao='')
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    pendencias = insp.pendencias_relatorio_final()
    assert any('conclusão' in p and 'Civil' in p for p in pendencias)


@pytest.mark.django_db
def test_pendencia_quando_achado_nao_conforme_tem_menos_de_2_fotos():
    edif = Edificacao.objects.create(nome='Sede', descritivo='x')
    insp = Inspecao.objects.create(edificacao=edif)
    civil = _criar_especialidade(insp, 'civil')
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    _achado_nao_conforme(civil, n_fotos=1)
    pendencias = insp.pendencias_relatorio_final()
    assert any('menos de 2 fotos' in p for p in pendencias)


@pytest.mark.django_db
def test_sem_pendencias_quando_tudo_preenchido():
    edif = Edificacao.objects.create(nome='Sede', descritivo='Prédio de 2 pavimentos.')
    insp = Inspecao.objects.create(edificacao=edif)
    civil = _criar_especialidade(insp, 'civil')
    _criar_especialidade(insp, 'eletrica')
    _criar_especialidade(insp, 'mecanica')
    _achado_nao_conforme(civil, n_fotos=2)
    assert insp.pendencias_relatorio_final() == []
    assert insp.pode_gerar_relatorio_final
