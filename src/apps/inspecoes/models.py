import uuid
from datetime import date
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model


class Inspecao(models.Model):
    """Container principal da inspeção — uma por edificação por campanha."""

    edificacao = models.ForeignKey(
        'edificacoes.Edificacao',
        on_delete=models.PROTECT,
        verbose_name='Edificação',
        related_name='inspecoes',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Inspeção'
        verbose_name_plural = 'Inspeções'

    def __str__(self):
        return f'{self.edificacao}'

    @property
    def status_geral(self):
        especialidades = list(self.especialidades.all())
        if not especialidades:
            return 'em_andamento'
        return 'finalizada' if all(e.status == 'finalizada' for e in especialidades) else 'em_andamento'


class InspecaoEspecialidade(models.Model):
    """Sub-inspeção por especialidade dentro de uma Inspeção."""

    ESPECIALIDADE_CHOICES = [
        ('civil', 'Engenharia Civil'),
        ('mecanica', 'Engenharia Mecânica'),
        ('eletrica', 'Engenharia Elétrica'),
    ]
    STATUS_CHOICES = [
        ('em_andamento', 'Em andamento'),
        ('finalizada', 'Finalizada'),
    ]

    inspecao = models.ForeignKey(
        Inspecao,
        on_delete=models.CASCADE,
        verbose_name='Inspeção',
        related_name='especialidades',
    )
    especialidade = models.CharField('Especialidade', max_length=20, choices=ESPECIALIDADE_CHOICES)
    profissional = models.TextField('Profissionais responsáveis', help_text='Um nome por linha.')
    data_inspecao = models.DateField('Data da inspeção')
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='em_andamento')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['especialidade']
        verbose_name = 'Especialidade da Inspeção'
        verbose_name_plural = 'Especialidades da Inspeção'
        constraints = [
            models.UniqueConstraint(
                fields=['inspecao', 'especialidade'],
                name='unique_inspecao_especialidade',
            )
        ]

    def __str__(self):
        return f'{self.inspecao.edificacao} — {self.get_especialidade_display()}'

    # Datas futuras são permitidas (pré-cadastro antes de ir ao local) e a
    # exigência de ao menos um profissional é validada na view, que monta o
    # campo 'profissional' a partir dos inputs dinâmicos.

    @property
    def profissionais_lista(self):
        return [p.strip() for p in self.profissional.splitlines() if p.strip()]

    @property
    def profissionais_display(self):
        return ', '.join(self.profissionais_lista)

    @property
    def pode_editar(self):
        return self.status == 'em_andamento'


class Achado(models.Model):
    GRUPO_TECNICO_CHOICES = [
        ('esquadrias', 'Esquadrias'),
        ('instalacoes', 'Instalações Hidrossanitárias'),
        ('acabamento', 'Acabamento'),
        ('instalacoes_mecanicas', 'Instalações Mecânicas'),
        ('instalacoes_eletricas', 'Instalações Elétricas'),
        ('estrutura', 'Estrutura'),
        ('impermeabilizacao', 'Impermeabilização'),
        ('cobertura', 'Cobertura'),
        ('equipamentos', 'Equipamentos Prediais'),
        ('acessibilidade', 'Acessibilidade'),
        ('outros', 'Outros'),
    ]
    REQUISITO_CHOICES = [
        ('seguranca_estrutural', 'Segurança Estrutural'),
        ('acessibilidade', 'Acessibilidade'),
        ('saude_qualidade_ar', 'Saúde e Qualidade do Ar'),
        ('funcionalidade', 'Funcionalidade'),
        ('estetica', 'Estética'),
        ('eficiencia_energetica', 'Eficiência Energética'),
        ('sustentabilidade', 'Sustentabilidade'),
        ('durabilidade', 'Durabilidade'),
    ]
    DIRECIONAMENTO_CHOICES = [
        ('garantia', 'Garantia de obra'),
        ('manutencao', 'Manutenção'),
        ('nova_contratacao', 'Nova contratação'),
    ]
    PRAZO_CHOICES = [
        (1, '1 mês'),
        (3, '3 meses'),
        (6, '6 meses'),
        (12, '12 meses'),
        (18, '18 meses'),
        (24, '24 meses'),
    ]
    PRIORIDADE_CHOICES = [
        (1, 'Prioridade 1 — Crítico'),
        (2, 'Prioridade 2 — Regular'),
        (3, 'Prioridade 3 — Mínimo'),
    ]

    especialidade = models.ForeignKey(
        InspecaoEspecialidade,
        on_delete=models.CASCADE,
        related_name='achados',
        verbose_name='Especialidade',
    )
    localizacao = models.CharField('Localização', max_length=200)
    sub_localizacao = models.CharField('Sub-localização', max_length=200, blank=True)
    verificacao = models.CharField('Verificação', max_length=300)
    grupo_tecnico = models.CharField('Grupo técnico', max_length=200)
    em_conformidade = models.BooleanField(
        'Em conformidade', default=False,
        help_text='Marque quando o item verificado estiver conforme. Os campos GUT ficam desabilitados.',
    )
    descricao_nao_conformidade = models.TextField('Descrição da não conformidade', blank=True)
    requisito_afetado = models.CharField('Requisito afetado', max_length=200)
    gravidade = models.IntegerField('Gravidade (G)', default=1)
    urgencia = models.IntegerField('Urgência (U)', default=1)
    tendencia = models.IntegerField('Tendência (T)', default=1)
    gut_total = models.IntegerField('Índice GUT', editable=False, default=0)
    prioridade_risco = models.IntegerField('Análise de risco', choices=PRIORIDADE_CHOICES, default=3)
    recomendacao = models.TextField('Recomendação técnica', blank=True)
    direcionamento = models.CharField('Direcionamento', max_length=30, choices=DIRECIONAMENTO_CHOICES, default='manutencao')
    ordem_servico = models.CharField(
        'Ordem de serviço (Resolve)', max_length=50, blank=True,
        help_text='Número da OS aberta no sistema Resolve. Preencher quando direcionamento for Manutenção.',
    )
    prazo_meses = models.IntegerField('Prazo para resolução', choices=PRAZO_CHOICES, default=12)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Achado'
        verbose_name_plural = 'Achados'

    def __str__(self):
        return f'{self.localizacao} — {self.verificacao}'

    def clean(self):
        if not self.em_conformidade:
            for campo, valor in [('gravidade', self.gravidade), ('urgencia', self.urgencia), ('tendencia', self.tendencia)]:
                if valor is not None and not (1 <= valor <= 5):
                    raise ValidationError({campo: 'A nota deve ser entre 1 e 5.'})

    def save(self, *args, **kwargs):
        # Defesa: as colunas GUT são NOT NULL. Nunca persiste None
        # (a coluna usa default 1) para evitar IntegrityError em qualquer caminho.
        self.gravidade = self.gravidade or 1
        self.urgencia = self.urgencia or 1
        self.tendencia = self.tendencia or 1
        if self.em_conformidade:
            self.gut_total = 0
        else:
            self.gut_total = self.gravidade * self.urgencia * self.tendencia
        super().save(*args, **kwargs)


class OpcaoCampo(models.Model):
    """Opções configuráveis para campos do formulário de Achado."""
    CAMPO_CHOICES = [
        ('localizacao', 'Localização'),
        ('grupo_tecnico', 'Grupo técnico'),
        ('requisito_afetado', 'Requisito afetado'),
    ]
    campo = models.CharField('Campo', max_length=30, choices=CAMPO_CHOICES)
    label = models.CharField('Descrição', max_length=200)
    is_padrao = models.BooleanField('Padrão do sistema', default=False)
    ativo = models.BooleanField('Ativo', default=True)
    ordem = models.PositiveIntegerField('Ordem', default=0)

    class Meta:
        ordering = ['campo', 'ordem', 'label']
        constraints = [
            models.UniqueConstraint(fields=['campo', 'label'], name='unique_campo_label'),
        ]
        verbose_name = 'Opção de campo'
        verbose_name_plural = 'Opções de campos'

    def __str__(self):
        return f'{self.get_campo_display()}: {self.label}'


def foto_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    hoje = date.today()
    return f'fotos/{hoje.year}/{hoje.month:02d}/{instance.achado_id}/{uuid.uuid4()}.{ext}'


class Foto(models.Model):
    achado = models.ForeignKey(Achado, on_delete=models.CASCADE, related_name='fotos', verbose_name='Achado')
    arquivo = models.ImageField('Foto', upload_to=foto_upload_path)
    nome_original = models.CharField(max_length=255)
    tamanho_bytes = models.IntegerField(default=0)
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_upload']
        verbose_name = 'Foto'
        verbose_name_plural = 'Fotos'

    def __str__(self):
        return self.nome_original


def visita_foto_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    hoje = date.today()
    return f'visitas/{hoje.year}/{hoje.month:02d}/{instance.visita_id}/{uuid.uuid4()}.{ext}'


class VisitaTecnica(models.Model):
    DISCIPLINA_CHOICES = [
        ('arquitetura', 'Arquitetura'),
        ('civil', 'Engenharia Civil'),
        ('eletrica', 'Engenharia Elétrica'),
        ('mecanica', 'Engenharia Mecânica'),
        ('multidisciplinar', 'Multidisciplinar'),
    ]

    edificacao = models.ForeignKey(
        'edificacoes.Edificacao',
        on_delete=models.PROTECT,
        verbose_name='Localidade',
        related_name='visitas',
    )
    visita_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='subvisitas',
        verbose_name='Visita de origem',
        help_text='Preenchido quando esta é uma subvisita de acompanhamento.',
    )
    data_visita = models.DateField('Data da visita')
    disciplina = models.CharField('Disciplina', max_length=20, choices=DISCIPLINA_CHOICES, blank=True)
    participantes = models.TextField('Profissionais participantes', help_text='Um nome por linha.')
    motivo = models.TextField('Motivo da visita')
    achados = models.TextField('Achados da visita', blank=True)
    conclusoes_encaminhamentos = models.TextField('Conclusões e encaminhamentos', blank=True)
    concluida = models.BooleanField('Concluída', default=False)
    concluida_em = models.DateTimeField('Concluída em', null=True, blank=True)
    criado_por = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='visitas_criadas',
        verbose_name='Criado por',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_visita', '-criado_em']
        verbose_name = 'Visita técnica'
        verbose_name_plural = 'Visitas técnicas'

    def __str__(self):
        return f'{self.edificacao} — {self.data_visita:%d/%m/%Y}'

    def clean(self):
        if self.data_visita and self.data_visita > date.today():
            raise ValidationError({'data_visita': 'A data da visita não pode ser futura.'})

    @property
    def participantes_lista(self):
        return [p.strip() for p in self.participantes.splitlines() if p.strip()]

    @property
    def participantes_display(self):
        return ', '.join(self.participantes_lista)

    @property
    def is_subvisita(self):
        return self.visita_pai_id is not None

    @property
    def pode_receber_subvisita(self):
        """Só visitas principais (não subvisitas) e ainda não concluídas
        aceitam novas subvisitas de acompanhamento."""
        return not self.is_subvisita and not self.concluida


class VisitaFoto(models.Model):
    visita = models.ForeignKey(VisitaTecnica, on_delete=models.CASCADE, related_name='fotos', verbose_name='Visita')
    arquivo = models.ImageField('Foto', upload_to=visita_foto_upload_path)
    nome_original = models.CharField(max_length=255)
    tamanho_bytes = models.IntegerField(default=0)
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_upload']
        verbose_name = 'Foto de visita'
        verbose_name_plural = 'Fotos de visita'

    def __str__(self):
        return self.nome_original


class LogAcesso(models.Model):
    TIPO_CHOICES = [
        ('login', 'Login'),
        ('inspecao_criada', 'Inspeção criada'),
        ('inspecao_excluida', 'Inspeção excluída'),
        ('especialidade_criada', 'Especialidade criada'),
        ('especialidade_excluida', 'Especialidade excluída'),
        ('achado_criado', 'Achado criado'),
        ('achado_excluido', 'Achado excluído'),
        ('visita_criada', 'Visita técnica criada'),
        ('visita_excluida', 'Visita técnica excluída'),
        ('visita_concluida', 'Visita técnica concluída'),
        ('visita_reaberta', 'Visita técnica reaberta'),
        ('subvisita_criada', 'Subvisita de acompanhamento criada'),
    ]

    usuario = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Usuário',
        related_name='logs_acesso',
    )
    tipo = models.CharField('Evento', max_length=30, choices=TIPO_CHOICES)
    descricao = models.TextField('Descrição', blank=True)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    criado_em = models.DateTimeField('Data/hora', auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Log de acesso'
        verbose_name_plural = 'Logs de acesso'

    def __str__(self):
        usuario = self.usuario.get_full_name() or self.usuario.username if self.usuario else 'Desconhecido'
        return f'{self.get_tipo_display()} — {usuario} — {self.criado_em:%d/%m/%Y %H:%M}'
