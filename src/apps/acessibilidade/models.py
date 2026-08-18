from django.conf import settings
from django.db import models


class Regiao(models.TextChoices):
    AREA_PUBLICA = 'AREA PÚBLICA', 'Área pública'
    AREA_PUBLICA_ALT = 'ÁREA PÚBLICA', 'Área pública (grafia alternativa)'
    AUDITORIO_RESTAURANTE = 'AUDITORIO E RESTAURANTE', 'Auditório e restaurante'
    INTERIOR_LOTE_DESCOBERTO = 'INTERIOR DO LOTE - DESCOBERTO', 'Interior do lote - descoberto'
    MEZANINO = 'MEZANINO', 'Mezanino'
    PAVIMENTO_01 = 'PAVIMENTO 01', 'Pavimento 01'
    PAVIMENTO_02 = 'PAVIMENTO 02', 'Pavimento 02'
    PAVIMENTO_TIPO = 'PAVIMENTO TIPO', 'Pavimento tipo'
    SUBSOLO = 'SUBSOLO', 'Subsolo'
    SUBSOLO_01 = 'SUBSOLO 01', 'Subsolo 01'
    SUBSOLO_02 = 'SUBSOLO 02', 'Subsolo 02'
    SUBSOLO_1 = 'SUBSOLO 1', 'Subsolo 1'
    SUBSOLO_2 = 'SUBSOLO 2', 'Subsolo 2'
    SUBSOLO_3 = 'SUBSOLO 3', 'Subsolo 3'
    TODOS_OS_PAVIMENTOS = 'TODOS OS PAVIMENTOS', 'Todos os pavimentos'
    TODOS_PAVIMENTOS = 'TODOS PAVIMENTOS', 'Todos pavimentos'
    TERREO = 'TÉRREO', 'Térreo'
    VARIOS_PAVIMENTOS = 'VÁRIOS PAVIMENTOS', 'Vários pavimentos'
    # Nota: alguns valores acima são variações de grafia do mesmo conceito
    # físico (ex. AREA_PUBLICA vs AREA_PUBLICA_ALT, SUBSOLO_1 vs SUBSOLO_01).
    # Preservados como estão no painel original — ver "Riscos em aberto" no
    # design doc. Consolidar é um follow-up de qualidade de dados, não um
    # bloqueio para este módulo entrar em produção.


class LocalAcessibilidade(models.Model):
    edificacao = models.ForeignKey(
        'edificacoes.Edificacao', on_delete=models.PROTECT, related_name='locais_acessibilidade',
        verbose_name='Edificação',
    )
    regiao = models.CharField('Região', max_length=40, choices=Regiao.choices)
    nome = models.CharField('Local', max_length=200)

    class Meta:
        verbose_name = 'Local de acessibilidade'
        verbose_name_plural = 'Locais de acessibilidade'
        ordering = ['edificacao__nome', 'regiao', 'nome']
        unique_together = [('edificacao', 'regiao', 'nome')]

    def __str__(self):
        return f'{self.edificacao.nome} — {self.get_regiao_display()} — {self.nome}'


class CriterioAcessibilidade(models.Model):
    nome = models.CharField('Critério', max_length=300, unique=True)
    base_legal = models.TextField('Base legal', blank=True)

    class Meta:
        verbose_name = 'Critério de acessibilidade'
        verbose_name_plural = 'Critérios de acessibilidade'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Avaliacao(models.Model):
    class Status(models.TextChoices):
        OK = 'OK', 'OK'
        PENDENTE = 'PENDENTE', 'Pendente'
        NAO_SE_APLICA = 'NAO_SE_APLICA', 'Não se aplica'

    class StatusAcao(models.TextChoices):
        NAO_INICIADA = 'NAO_INICIADA', 'Não iniciada'
        EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em andamento'
        CONCLUIDA = 'CONCLUIDA', 'Concluída'

    local = models.ForeignKey(LocalAcessibilidade, on_delete=models.PROTECT, related_name='avaliacoes')
    criterio = models.ForeignKey(CriterioAcessibilidade, on_delete=models.PROTECT, related_name='avaliacoes')

    status = models.CharField('Status', max_length=20, choices=Status.choices)
    resolucao_diagnostico = models.CharField('Resolução (diagnóstico)', max_length=40, blank=True)
    observacao = models.TextField('Observação', blank=True)

    status_acao = models.CharField(
        'Status da ação', max_length=20, choices=StatusAcao.choices, default=StatusAcao.NAO_INICIADA,
    )
    responsavel = models.CharField('Responsável', max_length=200, blank=True)
    prazo = models.DateField('Prazo', null=True, blank=True)
    resolucao_prevista = models.CharField('Resolução prevista', max_length=40, blank=True)
    ordem_servico = models.CharField('Ordem de serviço', max_length=100, blank=True)
    data_os = models.DateField('Data da OS', null=True, blank=True)
    notas = models.TextField('Notas', blank=True)

    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Atualizado por',
    )
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        unique_together = [('local', 'criterio')]

    def __str__(self):
        return f'{self.local} — {self.criterio} — {self.get_status_display()}'


class AvaliacaoHistorico(models.Model):
    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name='historico')
    snapshot_anterior = models.JSONField('Estado anterior')
    snapshot_novo = models.JSONField('Estado novo')
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Editado por',
    )
    editado_em = models.DateTimeField('Editado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de avaliação'
        verbose_name_plural = 'Histórico de avaliações'
        ordering = ['-editado_em']

    def __str__(self):
        return f'{self.avaliacao} em {self.editado_em:%d/%m/%Y %H:%M}'
