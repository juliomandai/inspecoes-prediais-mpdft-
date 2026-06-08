from django.contrib import admin
from .models import Inspecao, InspecaoEspecialidade, Achado, Foto, LogAcesso, VisitaTecnica, VisitaFoto


class FotoInline(admin.TabularInline):
    model = Foto
    extra = 0
    readonly_fields = ['nome_original', 'tamanho_bytes', 'data_upload']


class AchadoInline(admin.TabularInline):
    model = Achado
    extra = 0
    fields = ['localizacao', 'verificacao', 'gut_total', 'prioridade_risco']
    readonly_fields = ['gut_total']
    show_change_link = True


class InspecaoEspecialidadeInline(admin.TabularInline):
    model = InspecaoEspecialidade
    extra = 0
    fields = ['especialidade', 'profissional', 'data_inspecao', 'status']
    show_change_link = True


@admin.register(Inspecao)
class InspecaoAdmin(admin.ModelAdmin):
    list_display = ['edificacao', 'status_geral', 'criado_em']
    list_filter = ['edificacao']
    search_fields = ['edificacao__nome']
    date_hierarchy = 'criado_em'
    inlines = [InspecaoEspecialidadeInline]


@admin.register(InspecaoEspecialidade)
class InspecaoEspecialidadeAdmin(admin.ModelAdmin):
    list_display = ['inspecao', 'especialidade', 'profissional', 'data_inspecao', 'status']
    list_filter = ['status', 'especialidade']
    search_fields = ['profissional', 'inspecao__edificacao__nome']
    date_hierarchy = 'data_inspecao'
    inlines = [AchadoInline]


@admin.register(Achado)
class AchadoAdmin(admin.ModelAdmin):
    list_display = ['especialidade', 'localizacao', 'verificacao', 'gut_total', 'prioridade_risco']
    list_filter = ['prioridade_risco', 'grupo_tecnico', 'direcionamento']
    readonly_fields = ['gut_total']
    inlines = [FotoInline]


class VisitaFotoInline(admin.TabularInline):
    model = VisitaFoto
    extra = 0
    readonly_fields = ['nome_original', 'tamanho_bytes', 'data_upload']


@admin.register(VisitaTecnica)
class VisitaTecnicaAdmin(admin.ModelAdmin):
    list_display = ['edificacao', 'data_visita', 'responsavel', 'criado_em']
    list_filter = ['edificacao']
    search_fields = ['responsavel', 'edificacao__nome', 'motivo']
    date_hierarchy = 'data_visita'
    inlines = [VisitaFotoInline]


@admin.register(LogAcesso)
class LogAcessoAdmin(admin.ModelAdmin):
    list_display = ['criado_em', 'usuario', 'tipo', 'descricao', 'ip']
    list_filter = ['tipo']
    search_fields = ['usuario__username', 'usuario__first_name', 'descricao']
    date_hierarchy = 'criado_em'
    readonly_fields = ['usuario', 'tipo', 'descricao', 'ip', 'criado_em']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
