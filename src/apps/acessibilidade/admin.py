from django.contrib import admin
from .models import Avaliacao, AvaliacaoHistorico, CriterioAcessibilidade, LocalAcessibilidade


@admin.register(LocalAcessibilidade)
class LocalAcessibilidadeAdmin(admin.ModelAdmin):
    list_display = ['edificacao', 'regiao', 'nome']
    list_filter = ['edificacao', 'regiao']
    search_fields = ['nome', 'edificacao__nome']


@admin.register(CriterioAcessibilidade)
class CriterioAcessibilidadeAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ['local', 'criterio', 'status', 'status_acao', 'atualizado_por', 'atualizado_em']
    list_filter = ['status', 'status_acao', 'local__edificacao']
    search_fields = ['local__nome', 'criterio__nome']


@admin.register(AvaliacaoHistorico)
class AvaliacaoHistoricoAdmin(admin.ModelAdmin):
    list_display = ['avaliacao', 'editado_por', 'editado_em']
    list_filter = ['editado_por']
    readonly_fields = ['avaliacao', 'snapshot_anterior', 'snapshot_novo', 'editado_por', 'editado_em']
