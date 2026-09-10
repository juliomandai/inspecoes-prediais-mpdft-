"""Exclusão lógica (soft delete) reutilizável entre apps.

Todo model "de negócio" (criado/editado/excluído por um usuário) deve herdar
de `SoftDeleteModel` em vez de `models.Model`. Isso dá a ele:

- `excluido_em` / `excluido_por`: quando e quem excluiu (None enquanto ativo).
- `objects` (manager padrão): só enxerga registros NÃO excluídos — todo o
  código existente (views, relatórios, dashboards, `related_name` reverso)
  continua funcionando sem alteração, pois já fica filtrado por trás.
- `todos_objects`: enxerga tudo, inclusive excluídos — use em admin,
  auditoria, ou para checar duplicidade antes de recriar um registro.
- `.excluir(usuario=None)`: exclusão lógica desta instância. Idempotente.
  Propaga automaticamente para relações filhas `on_delete=CASCADE` que também
  sejam `SoftDeleteModel` (espelha o CASCADE que o banco já faria num delete
  de verdade).
- `.restaurar()`: desfaz a exclusão lógica (e dos filhos excluídos junto).
- `.delete()`: sobrescrito para virar exclusão lógica por padrão (mantém os
  call-sites existentes funcionando sem mudança). Passe `hard=True` para
  remover a linha de verdade (usado só por comandos de manutenção/purga).
- `.apagar_definitivamente()`: atalho para a remoção real (`delete(hard=True)`).

Relações `on_delete=PROTECT` nunca são tocadas automaticamente — nem
cascateadas, nem bloqueadas — pois `.excluir()` não passa pelo `Collector` do
Django (só marca a linha). Não há hoje nenhuma view que exclua uma
Edificacao/LocalAcessibilidade/CriterioAcessibilidade, então essa proteção não
faz falta ainda; se um dia isso for exposto, reavalie.

Campos com `unique=True`/`unique_together` nos models que adotam este mixin
devem virar `UniqueConstraint(..., condition=Q(excluido_em__isnull=True))` —
senão um registro excluído continua "ocupando" o nome/sigla e impede recriar
um ativo com o mesmo valor.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet base — misture com querysets customizados no lugar de
    `models.QuerySet` para ganhar `.ativos()`/`.excluidos()` sem perder os
    métodos próprios do model (ver `apps.inspecoes.models.AchadoQuerySet`)."""

    def ativos(self):
        return self.filter(excluido_em__isnull=True)

    def excluidos(self):
        return self.filter(excluido_em__isnull=False)

    def delete(self):
        """Exclusão lógica em massa. NÃO cascateia para filhos (bulk `.update()`
        não instancia cada objeto) — para isso, itere chamando `.excluir()` em
        cada instância. Use `.apagar_definitivamente()` para remover de fato."""
        return self.update(excluido_em=timezone.now(), excluido_por=None)

    def apagar_definitivamente(self):
        return super().delete()


def manager_ativos(queryset_class):
    """Manager cujo `get_queryset()` já vem filtrado para só registros ativos.

    Use isto (em vez de `SoftDeleteModel.objects` herdado) quando o model tem
    um QuerySet customizado próprio (ex.: `AchadoQuerySet`) — faça o
    queryset customizado herdar de `SoftDeleteQuerySet` e monte o manager
    padrão do model com `objects = manager_ativos(MeuQuerySet)()`."""
    class _AtivosManager(models.Manager.from_queryset(queryset_class)):
        def get_queryset(self):
            return super().get_queryset().filter(excluido_em__isnull=True)
    return _AtivosManager


def manager_todos(queryset_class):
    """Manager sem filtro — inclui excluídos. Equivalente ao `todos_objects`
    herdado, mas parametrizado por um QuerySet customizado."""
    return models.Manager.from_queryset(queryset_class)


class SoftDeleteModel(models.Model):
    excluido_em = models.DateTimeField('Excluído em', null=True, blank=True, editable=False)
    excluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name='+', verbose_name='Excluído por',
    )

    objects = manager_ativos(SoftDeleteQuerySet)()
    todos_objects = manager_todos(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    @property
    def excluido(self):
        return self.excluido_em is not None

    def excluir(self, usuario=None):
        """Exclusão lógica desta instância. Idempotente: chamar de novo num
        registro já excluído não faz nada (não sobrescreve quem/quando)."""
        if self.excluido:
            return
        self.excluido_em = timezone.now()
        self.excluido_por = usuario
        self.save(update_fields=['excluido_em', 'excluido_por'])
        for modelo_filho, campo in self._relacoes_cascade():
            for filho in modelo_filho.objects.filter(**{campo: self.pk}):
                filho.excluir(usuario)

    def restaurar(self):
        """Desfaz a exclusão lógica desta instância e dos filhos que tiverem
        sido excluídos em cascata junto com ela."""
        if not self.excluido:
            return
        self.excluido_em = None
        self.excluido_por = None
        self.save(update_fields=['excluido_em', 'excluido_por'])
        for modelo_filho, campo in self._relacoes_cascade():
            qs = modelo_filho.todos_objects.filter(**{campo: self.pk, 'excluido_em__isnull': False})
            for filho in qs:
                filho.restaurar()

    def delete(self, using=None, keep_parents=False, *, usuario=None, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.excluir(usuario=usuario)
        return (1, {self._meta.label: 1})

    def apagar_definitivamente(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def _relacoes_cascade(self):
        """[(modelo_filho, nome_do_campo_fk), ...] para toda relação reversa
        `on_delete=CASCADE` cujo modelo também seja SoftDeleteModel."""
        relacoes = []
        for related in self._meta.related_objects:
            if related.on_delete is not models.CASCADE:
                continue
            modelo_filho = related.related_model
            if not (isinstance(modelo_filho, type) and issubclass(modelo_filho, SoftDeleteModel)):
                continue
            relacoes.append((modelo_filho, related.field.name))
        return relacoes
