from django.contrib import admin


class ExcluidoListFilter(admin.SimpleListFilter):
    """Por padrão o admin mostra só os ativos — os excluídos ficam disponíveis
    via este filtro, em vez de aparecerem misturados na listagem."""
    title = 'excluído'
    parameter_name = 'excluido'

    def lookups(self, request, model_admin):
        return [('nao', 'Não'), ('sim', 'Sim')]

    def queryset(self, request, queryset):
        if self.value() == 'sim':
            return queryset.filter(excluido_em__isnull=False)
        if self.value() == 'nao':
            return queryset.filter(excluido_em__isnull=True)
        return queryset


class SoftDeleteAdminMixin:
    """Aplique a um ModelAdmin de um model que herda `SoftDeleteModel` para:

    - enxergar excluídos no admin (filtrados por padrão via `ExcluidoListFilter`,
      não pelo manager `objects` do model);
    - ganhar as ações "Restaurar" e "Excluir definitivamente";
    - o botão de exclusão padrão do admin continua funcionando — vira
      exclusão lógica automaticamente, pois `Model.delete()`/`QuerySet.delete()`
      já estão sobrescritos no model.
    """
    actions = ['restaurar_selecionados', 'apagar_definitivamente_selecionados']

    def get_queryset(self, request):
        # ModelAdmin.get_queryset() normalmente usa `self.model._default_manager`
        # (= `objects`, só ativos). Trocamos para `todos_objects` para que
        # excluídos apareçam no admin (via ExcluidoListFilter).
        qs = self.model.todos_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_list_filter(self, request):
        return [*super().get_list_filter(request), ExcluidoListFilter]

    @admin.action(description='Restaurar selecionados')
    def restaurar_selecionados(self, request, queryset):
        total = 0
        for obj in queryset.filter(excluido_em__isnull=False):
            obj.restaurar()
            total += 1
        self.message_user(request, f'{total} registro(s) restaurado(s).')

    @admin.action(description='Excluir definitivamente (não pode ser desfeito)')
    def apagar_definitivamente_selecionados(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, 'Só um superusuário pode excluir definitivamente.', level='error')
            return
        total = queryset.count()
        for obj in queryset:
            obj.apagar_definitivamente()
        self.message_user(request, f'{total} registro(s) removido(s) definitivamente.')
