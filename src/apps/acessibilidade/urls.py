from django.urls import path
from . import views

app_name = 'acessibilidade'

urlpatterns = [
    path('acessibilidade/', views.dashboard, name='dashboard'),
    path('acessibilidade/avaliacoes/', views.lista, name='lista'),
]
