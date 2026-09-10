from django.contrib import admin
from apps.core.admin import SoftDeleteAdminMixin
from .models import Avaliacao, AvaliacaoHistorico, CriterioAcessibilidade, LocalAcessibilidade


@admin.register(LocalAcessibilidade)
class LocalAcessibilidadeAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['edificacao', 'regiao', 'nome', 'excluido_em']
    list_filter = ['edificacao', 'regiao']
    search_fields = ['nome', 'edificacao__nome']


@admin.register(CriterioAcessibilidade)
class CriterioAcessibilidadeAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['nome', 'excluido_em']
    search_fields = ['nome']


@admin.register(Avaliacao)
class AvaliacaoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ['local', 'criterio', 'status', 'status_acao', 'atualizado_por', 'atualizado_em', 'excluido_em']
    list_filter = ['status', 'status_acao', 'local__edificacao']
    search_fields = ['local__nome', 'criterio__nome']


@admin.register(AvaliacaoHistorico)
class AvaliacaoHistoricoAdmin(admin.ModelAdmin):
    list_display = ['avaliacao', 'editado_por', 'editado_em']
    list_filter = ['editado_por']
    readonly_fields = ['avaliacao', 'snapshot_anterior', 'snapshot_novo', 'editado_por', 'editado_em']
