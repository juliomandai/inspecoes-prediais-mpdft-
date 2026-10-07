from django.db import models
from django.db.models import Q

from apps.core.softdelete import SoftDeleteModel


class Edificacao(SoftDeleteModel):
    # `nome`/`sigla` não são mais `unique=True` no campo: a unicidade é
    # imposta pelas constraints abaixo, restrita aos registros ativos — senão
    # uma edificação excluída continuaria "travando" o nome/sigla para sempre.
    nome = models.CharField('Nome', max_length=200)
    sigla = models.CharField('Sigla', max_length=10, null=True, blank=True)
    endereco = models.TextField('Endereço', max_length=500, blank=True)
    descritivo = models.TextField(
        'Descritivo', blank=True,
        help_text='Idade, tipo construtivo, uso etc. — reutilizado em todo '
                   'Relatório Final de Inspeção desta edificação.',
    )
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Edificação'
        verbose_name_plural = 'Edificações'
        constraints = [
            models.UniqueConstraint(
                fields=['nome'], condition=Q(excluido_em__isnull=True),
                name='unique_edificacao_nome_ativa',
            ),
            models.UniqueConstraint(
                fields=['sigla'], condition=Q(excluido_em__isnull=True),
                name='unique_edificacao_sigla_ativa',
            ),
        ]

    def __str__(self):
        return self.nome
