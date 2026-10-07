import pytest
from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.edificacoes.models import Edificacao
from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, Achado, Foto


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
