from django.contrib import admin
from .models import Edificacao


@admin.register(Edificacao)
class EdificacaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'criado_em']
    list_filter = ['ativo']
    search_fields = ['nome']
    list_editable = ['ativo']
    ordering = ['nome']
