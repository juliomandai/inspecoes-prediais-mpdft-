from django.urls import path
from . import views

app_name = 'acessibilidade'

urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
    path('acessibilidade/avaliacoes/<int:pk>/editar/', views.editar, name='editar'),
    path('acessibilidade/avaliacoes/editar-lote/', views.editar_lote, name='editar_lote'),
    path('acessibilidade/avaliacoes/exportar.csv', views.exportar_csv, name='exportar_csv'),
    path('acessibilidade/alertas/', views.alertas, name='alertas'),
]
