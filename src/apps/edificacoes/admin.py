from django.contrib import admin
from apps.core.admin import SoftDeleteAdminMixin
from .models import Edificacao, Profissional, HistoricoIntervencao


@admin.register(Edificacao)
class EdificacaoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['nome', 'sigla', 'ativo', 'criado_em', 'excluido_em']
    list_filter = ['ativo']
    search_fields = ['nome', 'sigla']
    list_editable = ['ativo']
    ordering = ['nome']


@admin.register(Profissional)
class ProfissionalAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['nome', 'crea', 'criado_em', 'excluido_em']
    search_fields = ['nome', 'crea']
    ordering = ['nome']


@admin.register(HistoricoIntervencao)
class HistoricoIntervencaoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['edificacao', 'ano', 'descricao']
    list_filter = ['edificacao']
    ordering = ['edificacao', 'ano']
