# Quickstart: Sistema de Registro de Achados de Inspeção Predial

**Feature**: 001-registro-achados
**Date**: 2026-05-14

---

## Pré-requisitos

- Python 3.11 ou superior instalado no Windows
- pip disponível no PATH
- Acesso a pasta de rede ou OneDrive para armazenamento de fotos (opcional)

Verifique a instalação:
```powershell
python --version   # deve retornar Python 3.11.x ou superior
pip --version
```

---

## Instalação

```powershell
# Clone ou copie o projeto para a pasta desejada
cd C:\MPDFT\inspecoes-prediais

# Crie o ambiente virtual (recomendado)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instale as dependências
pip install -r requirements.txt
```

---

## Configuração

Copie o arquivo de exemplo e ajuste as variáveis:

```powershell
copy .env.example .env
notepad .env
```

Variáveis obrigatórias no `.env`:

```env
SECRET_KEY=<chave-secreta-longa-e-aleatória>
DEBUG=True                        # False em produção
DATABASE_URL=sqlite:///db.sqlite3 # ou postgres://user:pass@host/db
MEDIA_ROOT=C:\MPDFT\fotos        # pasta para armazenar fotos (pode ser OneDrive)
ALLOWED_HOSTS=localhost,127.0.0.1 # adicionar IP do servidor em produção
```

Gerar uma SECRET_KEY:
```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Inicialização do Banco de Dados

```powershell
# Aplicar migrações
python manage.py migrate

# Criar superusuário (administrador)
python manage.py createsuperuser
# Informe: username, e-mail (opcional), senha
```

---

## Cadastro das Edificações

As edificações devem ser cadastradas antes de criar inspeções.
Opção 1 — via painel administrativo (recomendado para v1):

```powershell
python manage.py runserver
# Acesse http://localhost:8000/admin/ com as credenciais do superusuário
# Navegue para Edificacoes → Adicionar
```

Opção 2 — via management command (carga inicial em lote):

```powershell
python manage.py carregar_edificacoes edificacoes.csv
# O arquivo CSV deve ter colunas: nome, endereco
```

---

## Criar Usuários dos Servidores da SPO

No painel administrativo (`/admin/`), em "Usuários":
- Criar novo usuário com username e senha
- Manter `is_staff = false` para servidores comuns
- Definir `is_staff = true` apenas para administradores (gestão de edificações)

---

## Executar em Desenvolvimento

```powershell
python manage.py runserver
# Acesse http://localhost:8000/
```

---

## Executar em Produção (Windows)

```powershell
pip install waitress

# Iniciar o servidor (porta 8000)
waitress-serve --port=8000 mpdft_inspecoes.wsgi:application
```

Para inicialização automática como serviço Windows, use o NSSM:
```powershell
# Baixe o NSSM em nssm.cc/download
nssm install InspecoesPrediais "C:\MPDFT\.venv\Scripts\waitress-serve.exe"
nssm set InspecoesPrediais AppParameters "--port=8000 mpdft_inspecoes.wsgi:application"
nssm set InspecoesPrediais AppDirectory "C:\MPDFT\inspecoes-prediais"
nssm start InspecoesPrediais
```

---

## Configurar Retenção de Dados (6 meses)

No Agendador de Tarefas do Windows, crie uma tarefa diária:

```
Programa: C:\MPDFT\.venv\Scripts\python.exe
Argumentos: manage.py purge_old_inspecoes
Diretório inicial: C:\MPDFT\inspecoes-prediais
Gatilho: diariamente às 02:00
```

---

## Fluxo de Uso Resumido

1. Acesse `http://<servidor>:8000/` e faça login
2. Clique em **Nova Inspeção**
3. Preencha: edificação (seleção da lista), profissional, especialidade, data
4. Clique em **Salvar** — a inspeção é criada com status "Em andamento"
5. Clique em **Adicionar Achado** e preencha todos os campos
6. Faça upload das fotos do achado
7. Salve o achado — o índice GUT é calculado automaticamente
8. Repita os passos 5–7 para todos os achados
9. Quando concluído, clique em **Finalizar Inspeção**

---

## Validação

Para confirmar que a instalação está correta:

```powershell
# Executar testes automatizados
python manage.py test

# Criar inspeção de exemplo (fixture de teste)
python manage.py carregar_fixture_demo
# Acesse http://localhost:8000/ e verifique a inspeção "DEMO - Edificação Teste"
```
