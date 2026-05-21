from django.urls import path
from . import views

app_name = 'edificacoes'

urlpatterns = [
    path('edificacoes/', views.edificacao_list, name='list'),
    path('edificacoes/nova/', views.edificacao_create, name='create'),
    path('edificacoes/<int:pk>/editar/', views.edificacao_update, name='update'),
]
