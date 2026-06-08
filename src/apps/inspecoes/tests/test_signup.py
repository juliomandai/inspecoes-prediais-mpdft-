import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

URL = '/cadastro/'
SENHA_VALIDA = 'Vistoria2026'


def _dados(**over):
    d = {
        'nome_completo': 'Joao da Silva',
        'email': 'joao.silva@mpdft.mp.br',
        'password1': SENHA_VALIDA,
        'password2': SENHA_VALIDA,
    }
    d.update(over)
    return d


@pytest.mark.django_db
def test_pagina_cadastro_publica(client):
    resp = client.get(reverse('inspecoes:signup'))
    assert resp.status_code == 200
    assert b'Criar conta' in resp.content


@pytest.mark.django_db
def test_login_tem_link_cadastro(client):
    resp = client.get(reverse('login'))
    assert reverse('inspecoes:signup').encode() in resp.content


@pytest.mark.django_db
def test_cadastro_cria_usuario_valido(client):
    resp = client.post(reverse('inspecoes:signup'), _dados())
    assert resp.status_code == 302
    U = get_user_model()
    u = U.objects.get(email='joao.silva@mpdft.mp.br')
    assert u.username == 'joao.silva@mpdft.mp.br'
    assert u.get_full_name() == 'Joao da Silva'
    assert u.check_password(SENHA_VALIDA)
    assert u.is_staff is False
    assert u.is_superuser is False
    assert u.is_active is True
    # logado automaticamente
    assert '_auth_user_id' in client.session


@pytest.mark.django_db
def test_cadastro_rejeita_email_nao_institucional(client):
    resp = client.post(reverse('inspecoes:signup'), _dados(email='joao@gmail.com'))
    assert resp.status_code == 200
    assert get_user_model().objects.count() == 0
    assert b'institucional' in resp.content


@pytest.mark.django_db
def test_cadastro_senhas_diferentes(client):
    resp = client.post(reverse('inspecoes:signup'), _dados(password2='Outra2026xyz'))
    assert resp.status_code == 200
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_cadastro_senha_fraca(client):
    resp = client.post(reverse('inspecoes:signup'), _dados(password1='123', password2='123'))
    assert resp.status_code == 200
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_cadastro_email_duplicado(client):
    U = get_user_model()
    U.objects.create_user(username='joao.silva@mpdft.mp.br', email='joao.silva@mpdft.mp.br', password='x')
    resp = client.post(reverse('inspecoes:signup'), _dados())
    assert resp.status_code == 200
    assert U.objects.filter(email='joao.silva@mpdft.mp.br').count() == 1
    assert 'Já existe'.encode() in resp.content


@pytest.mark.django_db
def test_cadastro_exige_nome_completo(client):
    resp = client.post(reverse('inspecoes:signup'), _dados(nome_completo='Joao'))
    assert resp.status_code == 200
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_usuario_logado_e_redirecionado(client):
    U = get_user_model()
    u = U.objects.create_user(username='ja@mpdft.mp.br', password='x')
    client.force_login(u)
    resp = client.get(reverse('inspecoes:signup'))
    assert resp.status_code == 302
