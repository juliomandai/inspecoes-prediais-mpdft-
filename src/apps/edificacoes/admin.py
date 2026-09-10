from django.contrib import admin
from apps.core.admin import SoftDeleteAdminMixin
from .models import Edificacao


@admin.register(Edificacao)
class EdificacaoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['nome', 'sigla', 'ativo', 'criado_em', 'excluido_em']
    list_filter = ['ativo']
    search_fields = ['nome', 'sigla']
    list_editable = ['ativo']
    ordering = ['nome']
