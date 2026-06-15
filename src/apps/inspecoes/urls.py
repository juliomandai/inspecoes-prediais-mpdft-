from django.urls import path
from . import views

app_name = 'inspecoes'

urlpatterns = [
    # ── Página inicial (menu) ──────────────────────────────────────────────────
    path('', views.home, name='home'),

    # ── Cadastro de novo usuário (público) ─────────────────────────────────────
    path('cadastro/', views.signup, name='signup'),

    # ── Listagem e configurações ───────────────────────────────────────────────
    path('inspecoes/', views.inspecao_list, name='list'),
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('logs/', views.log_acesso, name='log_acesso'),

    # ── Inspeções (container por edificação) ──────────────────────────────────
    path('inspecoes/nova/', views.inspecao_create, name='create'),
    path('inspecoes/<int:pk>/', views.inspecao_detail, name='detail'),
    path('inspecoes/<int:pk>/editar/', views.inspecao_update, name='update'),
    path('inspecoes/<int:pk>/excluir/', views.inspecao_delete, name='delete'),
    path('inspecoes/<int:pk>/analise/', views.inspecao_analise, name='inspecao_analise'),
    path('inspecoes/<int:pk>/analise/pdf/', views.inspecao_analise_pdf, name='inspecao_analise_pdf'),
    path('inspecoes/<int:pk>/backup/salvo/', views.inspecao_backup_download, name='backup_download'),

    # ── Especialidades ─────────────────────────────────────────────────────────
    path('inspecoes/<int:inspecao_pk>/especialidades/nova/', views.especialidade_create, name='especialidade_create'),
    path('especialidades/<int:pk>/editar/', views.especialidade_update, name='especialidade_update'),
    path('especialidades/<int:pk>/excluir/', views.especialidade_delete, name='especialidade_delete'),
    path('especialidades/<int:pk>/finalizar/', views.especialidade_finalizar, name='especialidade_finalizar'),
    path('especialidades/<int:pk>/reabrir/', views.especialidade_reabrir, name='especialidade_reabrir'),
    path('especialidades/<int:pk>/analise/', views.especialidade_analise, name='analise'),
    path('especialidades/<int:pk>/analise/pdf/', views.especialidade_analise_pdf, name='analise_pdf'),

    # ── Achados ────────────────────────────────────────────────────────────────
    path('especialidades/<int:esp_pk>/achados/novo/', views.achado_create, name='achado_create'),
    path('achados/<int:pk>/editar/', views.achado_update, name='achado_update'),
    path('achados/<int:pk>/excluir/', views.achado_delete, name='achado_delete'),

    # ── Fotos ──────────────────────────────────────────────────────────────────
    path('achados/<int:achado_pk>/fotos/', views.foto_upload, name='foto_upload'),
    path('fotos/<int:pk>/', views.foto_delete, name='foto_delete'),

    # ── Backup — restaurar ────────────────────────────────────────────────────
    path('inspecoes/restaurar/', views.inspecao_restaurar_backup, name='restaurar_backup'),

    # ── Visitas técnicas ───────────────────────────────────────────────────────
    path('visitas/', views.visita_localidades, name='visita_localidades'),
    path('visitas/localidade/<int:edif_pk>/', views.visita_list, name='visita_list'),
    path('visitas/localidade/<int:edif_pk>/nova/', views.visita_create, name='visita_create'),
    path('visitas/<int:pk>/', views.visita_detail, name='visita_detail'),
    path('visitas/<int:pk>/editar/', views.visita_update, name='visita_update'),
    path('visitas/<int:pk>/excluir/', views.visita_delete, name='visita_delete'),
    path('visitas/<int:visita_pk>/fotos/', views.visita_foto_upload, name='visita_foto_upload'),
    path('visitas/fotos/<int:pk>/', views.visita_foto_delete, name='visita_foto_delete'),

    # ── PWA ────────────────────────────────────────────────────────────────────
    path('offline/', views.offline_page, name='offline'),
    path('api/achados/sincronizar/', views.achado_sincronizar, name='achado_sincronizar'),
]
