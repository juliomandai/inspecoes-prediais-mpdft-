from django.db import models


class Edificacao(models.Model):
    nome = models.CharField('Nome', max_length=200, unique=True)
    sigla = models.CharField('Sigla', max_length=10, unique=True, null=True, blank=True)
    endereco = models.TextField('Endereço', max_length=500, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Edificação'
        verbose_name_plural = 'Edificações'

    def __str__(self):
        return self.nome
