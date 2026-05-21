# Research: Sistema de Registro de Achados de Inspeção Predial

**Feature**: 001-registro-achados
**Date**: 2026-05-14

---

## 1. Stack da Aplicação Web

**Decision**: Python 3.11 + Django 4.2 LTS (server-side rendering)

**Rationale**:
- Django LTS garante suporte até abril de 2026; maturidade e comunidade ampla.
- ORM integrado, sistema de autenticação nativo, painel administrativo e validação de
  formulários prontos para uso — reduz código custom e acelera entrega.
- Server-side rendering com templates Django elimina a necessidade de um
  framework JavaScript separado (React, Vue), reduzindo complexidade operacional
  para equipe de TI do MPDFT.
- Python é amplamente disponível no Windows e possui baixa curva de aprendizado
  para manutenção futura.

**Alternatives considered**:
- Node.js/Express + React: maior complexidade de deploy; dois runtimes distintos;
  não necessário para o volume de dados e número de usuários esperado.
- Flask: mais simples, mas exigiria construir autenticação, ORM e admin do zero.
- PHP/Laravel: convencional em ambiente governamental, mas sem vantagem sobre
  Django para este caso de uso.

---

## 2. Banco de Dados

**Decision**: SQLite para ambiente de desenvolvimento/pequeno deployment;
PostgreSQL para produção com múltiplos usuários simultâneos.

**Rationale**:
- SQLite: arquivo único, sem servidor, backup por cópia de arquivo — ideal para
  implantação inicial ou ambiente de testes. O Django suporta SQLite nativamente.
- PostgreSQL: suporte a múltiplas escritas simultâneas (WAL); recomendado quando
  mais de 5 usuários acessarem o sistema ao mesmo tempo.
- A troca SQLite → PostgreSQL requer apenas mudança de `DATABASE_URL` no `.env`;
  nenhuma alteração de código.
- **Nota constitucional**: a constituição exige aprovação institucional para uso
  de bancos de dados. A aprovação DEVE ser obtida junto ao servidor Júlio Mandai
  (SPO/MPDFT) antes do deploy em produção.

**Alternatives considered**:
- SQL Server: disponível no ecossistema Microsoft, mas requer licença adicional e
  driver `pyodbc`, aumentando complexidade de configuração.
- MongoDB: sem benefício para dados fortemente relacionais (inspeção → achados →
  fotos); overhead desnecessário.

---

## 3. Armazenamento de Fotos

**Decision**: Sistema de arquivos local (diretório `media/`), com possibilidade
de apontar para pasta sincronizada com OneDrive.

**Rationale**:
- Django gerencia upload e servimento de arquivos de mídia nativamente via
  `MEDIA_ROOT` e `MEDIA_URL`.
- Armazenar fotos em pasta sincronizada com OneDrive provê backup automático e
  acesso fora do servidor sem infraestrutura adicional.
- Blobs no banco de dados foram descartados: arquivos grandes em banco degradam
  performance e dificultam backup seletivo.

**Constraints**:
- Formatos aceitos: JPEG, PNG (validado no backend).
- Tamanho máximo por arquivo: 10 MB (configurável via `DATA_UPLOAD_MAX_MEMORY_SIZE`).
- Múltiplos arquivos por achado suportados.

---

## 4. Interface do Usuário

**Decision**: Bootstrap 5 + templates Django (Jinja2-style)

**Rationale**:
- Bootstrap 5 fornece grid responsivo funcional em tablets e desktops sem
  JavaScript framework adicional.
- Formulários multi-etapa (informações iniciais → achados) implementados com
  sessão Django + redirecionamento pós-POST (padrão PRG — Post/Redirect/Get).
- Cálculo automático do índice GUT implementado em JavaScript vanilla no
  formulário de achado (G × U × T), sem dependências externas.
- htmx (opcional): permite atualização parcial da página (ex.: adicionar achado
  sem recarregar a inspeção) sem SPA completo; decisão adiada para fase de
  implementação.

**Alternatives considered**:
- React/Vue SPA: complexidade de build e deploy desproporcionais ao tamanho da
  equipe; dois projetos (frontend/backend) em vez de um.

---

## 5. Autenticação

**Decision**: Autenticação nativa do Django (username + password); sessões
server-side com CSRF protection.

**Rationale**:
- Sistema de autenticação do Django inclui: hashing de senhas (PBKDF2),
  proteção CSRF, controle de sessão, decorators `@login_required`.
- Para v1 não é necessário integração com Active Directory do MPDFT; pode ser
  adicionado posteriormente via `django-auth-ldap` sem refactoring.
- Cada servidor da SPO terá login individual, permitindo rastrear quem cadastrou
  cada inspeção.

**Alternatives considered**:
- LDAP/Active Directory: adequado para v2 quando o MPDFT disponibilizar
  credenciais de rede para integração; desnecessário para v1.
- SSO/OAuth: sem infraestrutura de IdP identificada no ambiente MPDFT para v1.

---

## 6. Servidor de Aplicação (Windows Deploy)

**Decision**: Waitress (WSGI server puro-Python, compatível com Windows)

**Rationale**:
- Gunicorn não suporta Windows; Waitress é a alternativa padrão para Django em
  Windows, sem dependências de compilação.
- Pode ser registrado como serviço Windows via `NSSM` (Non-Sucking Service
  Manager) para inicialização automática.
- IIS com `wfastcgi` é alternativa se o MPDFT preferir infraestrutura IIS.

---

## 7. Retenção de Dados (6 meses)

**Decision**: Management command Django para exclusão/arquivamento de inspeções
com mais de 6 meses, agendado via Agendador de Tarefas do Windows.

**Rationale**:
- Agendador de Tarefas do Windows (Task Scheduler) dispara `python manage.py
  purge_old_inspecoes` diariamente.
- Command verifica `data_inspecao` e move registros elegíveis para tabela de
  arquivo ou os remove (comportamento configurável).
- Sem dependência de Celery ou infraestrutura de filas.

---

## 8. Referências Normativas (aplicadas ao design)

- **NBR 16747:2020**: orientou os campos de grupo técnico, localização e
  classificação de risco (Crítico/Regular/Mínimo).
- **NBR 13752/1996**: orientou campos de requisito afetado e recomendação técnica.
- **IBAPE**: boas práticas de inspeção predial como referência para listas de
  valores dos campos de verificação e grupo técnico.
- **NBR 16401-1:2024** e **NBR 16858-1/7**: referências para os itens de
  verificação nas especialidades Mecânica (climatização) e Civil (elevadores).
