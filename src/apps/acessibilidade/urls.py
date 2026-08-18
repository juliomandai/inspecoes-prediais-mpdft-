from django.urls import path
from . import views

app_name = 'acessibilidade'

urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
    path('acessibilidade/avaliacoes/<int:pk>/editar/', views.editar, name='editar'),
]
