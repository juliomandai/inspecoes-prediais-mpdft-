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
    area_construida_m2 = models.DecimalField(
        'Área construída (m²)', max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    pavimentos = models.CharField(
        'Quantidade de pavimentos', max_length=300, blank=True,
        help_text='Ex.: três pavimentos (subsolo, térreo e 1º pavimento), '
                   'além de cobertura técnica.',
    )
    data_inauguracao = models.DateField('Data de inauguração', null=True, blank=True)
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


class HistoricoIntervencao(SoftDeleteModel):
    """Uma linha do quadro 'Ano / Intervenção' do laudo-modelo (seção
    Caracterização da Edificação) — intervenções relevantes já realizadas
    na edificação (reforma, troca de equipamento etc.)."""
    edificacao = models.ForeignKey(
        Edificacao, on_delete=models.CASCADE, related_name='historico_intervencoes',
        verbose_name='Edificação',
    )
    ano = models.PositiveIntegerField('Ano')
    descricao = models.CharField('Intervenção', max_length=300)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ano', 'id']
        verbose_name = 'Histórico de intervenção'
        verbose_name_plural = 'Histórico de intervenções'

    def __str__(self):
        return f'{self.ano} — {self.descricao}'


class Profissional(SoftDeleteModel):
    """Engenheiro(a)/profissional responsável técnico, reaproveitável entre
    inspeções (como Edificacao) — ver ADR do grill de 2026-10-27: antes era
    só texto livre em InspecaoEspecialidade.profissional."""
    nome = models.CharField('Nome', max_length=200)
    crea = models.CharField(
        'CREA', max_length=30,
        help_text='Número do registro no CREA (ex.: "12345/D-DF"). '
                   'Profissionais migrados do cadastro antigo recebem um '
                   'placeholder "PENDENTE-N" a completar manualmente.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Profissional'
        verbose_name_plural = 'Profissionais'
        constraints = [
            models.UniqueConstraint(
                fields=['crea'], condition=Q(excluido_em__isnull=True),
                name='unique_profissional_crea_ativo',
            ),
        ]

    def __str__(self):
        return self.nome
