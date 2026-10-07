import uuid
from datetime import date
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.core.softdelete import SoftDeleteModel, SoftDeleteQuerySet, manager_ativos, manager_todos


class Inspecao(SoftDeleteModel):
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

    ESPECIALIDADES_OBRIGATORIAS = {'civil', 'eletrica', 'mecanica'}

    def pendencias_relatorio_final(self):
        """Lista de pendências (texto legível) que impedem gerar o
        Relatório Final de Inspeção. Lista vazia = pode gerar
        (ver ADR-04, ADR-05, ADR-08, ADR-09)."""
        pendencias = []
        especialidades = list(self.especialidades.all())
        existentes = {e.especialidade: e for e in especialidades}
        faltando = self.ESPECIALIDADES_OBRIGATORIAS - set(existentes)

        if faltando:
            nomes_choices = dict(InspecaoEspecialidade.ESPECIALIDADE_CHOICES)
            nomes = ', '.join(nomes_choices[k] for k in sorted(faltando))
            pendencias.append(f'Falta cadastrar: {nomes}.')
            return pendencias  # sem as 3, nada mais faz sentido checar ainda

        obrigatorias = [e for e in especialidades if e.especialidade in self.ESPECIALIDADES_OBRIGATORIAS]
        nao_finalizadas = [e for e in obrigatorias if e.status != 'finalizada']
        if nao_finalizadas:
            nomes = ', '.join(e.get_especialidade_display() for e in nao_finalizadas)
            pendencias.append(f'Especialidade(s) não finalizada(s): {nomes}.')
            return pendencias  # idem — com especialidade em andamento, conclusão/fotos ainda podem mudar

        if not self.edificacao.descritivo.strip():
            pendencias.append('Falta o descritivo da edificação.')

        for esp in obrigatorias:
            if not esp.conclusao.strip():
                pendencias.append(f'Falta a conclusão de {esp.get_especialidade_display()}.')

        achados_insuficientes = []
        for esp in obrigatorias:
            for achado in esp.achados.filter(gut_total__gt=0):
                if achado.fotos.count() < 2:
                    achados_insuficientes.append(achado)
        if achados_insuficientes:
            primeiros = ', '.join(f'"{a.verificacao}"' for a in achados_insuficientes[:5])
            reticencias = '...' if len(achados_insuficientes) > 5 else ''
            pendencias.append(
                f'{len(achados_insuficientes)} achado(s) não conforme(s) com menos de 2 fotos: '
                f'{primeiros}{reticencias}.'
            )

        return pendencias

    @property
    def pode_gerar_relatorio_final(self):
        return not self.pendencias_relatorio_final()


class InspecaoEspecialidade(SoftDeleteModel):
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
    conclusao = models.TextField(
        'Conclusão e direcionamentos', blank=True,
        help_text='Texto livre, redigido pelo profissional responsável — exigido '
                   'para finalizar esta especialidade.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['especialidade']
        verbose_name = 'Especialidade da Inspeção'
        verbose_name_plural = 'Especialidades da Inspeção'
        constraints = [
            models.UniqueConstraint(
                fields=['inspecao', 'especialidade'], condition=Q(excluido_em__isnull=True),
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


class AchadoQuerySet(SoftDeleteQuerySet):
    """Consultas do módulo Acompanhamento — ficam com o model, não espalhadas pelas views."""

    def acompanhamento(self):
        """Achados de todas as inspeções que demandam ação (não conformes)."""
        return self.filter(gut_total__gt=0).select_related('especialidade__inspecao__edificacao')

    def com_filtros_acompanhamento(self, form):
        """Aplica os filtros combináveis do AcompanhamentoFilterForm (localidade, especialidade, status)."""
        qs = self
        if form.is_valid():
            if form.cleaned_data.get('localidade'):
                qs = qs.filter(especialidade__inspecao__edificacao=form.cleaned_data['localidade'])
            if form.cleaned_data.get('especialidade'):
                qs = qs.filter(especialidade__especialidade=form.cleaned_data['especialidade'])
            if form.cleaned_data.get('status'):
                qs = qs.filter(status=form.cleaned_data['status'])
        return qs

    def contagem_por(self, campo, choices):
        """[{'chave', 'nome', 'total'}, ...] a partir de uma única query agregada."""
        totais = dict(self.values_list(campo).annotate(total=models.Count('id')))
        return [{'chave': chave, 'nome': nome, 'total': totais.get(chave, 0)} for chave, nome in choices]

    def contagem_por_localidade(self):
        """[{'pk', 'nome', 'total'}, ...] por edificação, da maior para a menor."""
        return list(
            self.values(
                pk=models.F('especialidade__inspecao__edificacao'),
                nome=models.F('especialidade__inspecao__edificacao__nome'),
            )
            .annotate(total=models.Count('id'))
            .order_by('-total')
        )


class Achado(SoftDeleteModel):
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
    # Limiares da sugestão de prioridade a partir do índice GUT. Mesmos valores
    # usados em static/js/gut_calculator.js — se mudar um lado, mude o outro.
    LIMITE_GUT_P1 = 75
    LIMITE_GUT_P2 = 20
    STATUS_ACOMPANHAMENTO_CHOICES = [
        ('pendente', 'Pendente'),
        ('em_andamento', 'Em andamento'),
        ('finalizado', 'Finalizado'),
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
    prazo_meses = models.IntegerField('Prazo para resolução', choices=PRAZO_CHOICES, default=12)

    # ── Acompanhamento (gestão do ciclo de vida — módulo "Acompanhamento") ──────
    # Estes campos são preenchidos no módulo Acompanhamento, não no registro do
    # achado durante a inspeção.
    status = models.CharField(
        'Status do acompanhamento', max_length=20,
        choices=STATUS_ACOMPANHAMENTO_CHOICES, default='pendente',
    )
    ordem_servico = models.CharField('Número da OS (Resolve)', max_length=50, blank=True)
    os_data_abertura = models.DateField('Data de abertura da OS', null=True, blank=True)
    os_observacoes = models.TextField('Observações complementares', blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = manager_ativos(AchadoQuerySet)()
    todos_objects = manager_todos(AchadoQuerySet)()

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

    @classmethod
    def calcular_prioridade(cls, gut_total, em_conformidade=False):
        """Sugere a prioridade (1/2/3) a partir do índice GUT.

        Única fonte da regra de limiares — usada como fallback ao restaurar
        backups antigos que não guardaram a prioridade escolhida pelo
        profissional. Não é chamada em save(): a prioridade no fluxo normal é
        uma escolha humana, o GUT só sugere.
        """
        if em_conformidade:
            return 3
        if gut_total >= cls.LIMITE_GUT_P1:
            return 1
        if gut_total >= cls.LIMITE_GUT_P2:
            return 2
        return 3

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


class EncaminhamentoHistorico(models.Model):
    """Registro de cada alteração de encaminhamento (direcionamento) de um achado.

    Garante rastreabilidade: quem alterou, quando, de qual categoria para qual e
    a justificativa da mudança.
    """
    achado = models.ForeignKey(
        Achado, on_delete=models.CASCADE,
        related_name='historico_encaminhamento', verbose_name='Achado',
    )
    usuario = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reclassificacoes',
        verbose_name='Responsável',
    )
    de_direcionamento = models.CharField('Categoria anterior', max_length=30, choices=Achado.DIRECIONAMENTO_CHOICES)
    para_direcionamento = models.CharField('Nova categoria', max_length=30, choices=Achado.DIRECIONAMENTO_CHOICES)
    justificativa = models.TextField('Justificativa')
    criado_em = models.DateTimeField('Data/hora', auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Histórico de encaminhamento'
        verbose_name_plural = 'Históricos de encaminhamento'

    def __str__(self):
        return f'{self.achado} — {self.get_de_direcionamento_display()} → {self.get_para_direcionamento_display()}'


class OpcaoCampo(SoftDeleteModel):
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
            models.UniqueConstraint(
                fields=['campo', 'label'], condition=Q(excluido_em__isnull=True),
                name='unique_campo_label',
            ),
        ]
        verbose_name = 'Opção de campo'
        verbose_name_plural = 'Opções de campos'

    def __str__(self):
        return f'{self.get_campo_display()}: {self.label}'


def foto_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    hoje = date.today()
    return f'fotos/{hoje.year}/{hoje.month:02d}/{instance.achado_id}/{uuid.uuid4()}.{ext}'


class Foto(SoftDeleteModel):
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


class VisitaTecnica(SoftDeleteModel):
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


class VisitaFoto(SoftDeleteModel):
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
        ('achado_reclassificado', 'Achado reclassificado'),
        ('achado_acompanhamento', 'Acompanhamento de achado atualizado'),
        ('visita_criada', 'Visita técnica criada'),
        ('visita_excluida', 'Visita técnica excluída'),
        ('visita_concluida', 'Visita técnica concluída'),
        ('visita_reaberta', 'Visita técnica reaberta'),
        ('subvisita_criada', 'Subvisita de acompanhamento criada'),
        ('relatorio_final_gerado', 'Relatório Final de Inspeção gerado'),
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


def relatorio_pdf_upload_path(instance, filename):
    return f'relatorios/{instance.inspecao_id}/v{instance.numero_versao}/{filename}'


class RelatorioFinalInspecao(models.Model):
    """Documento formal (PDF + snapshot) gerado ao encerrar uma inspeção
    completa, para instruir ART junto ao CREA.

    Imutável depois de gerado (ADR-03): gerar de novo cria uma nova versão,
    nunca sobrescreve. NÃO herda SoftDeleteModel — é um registro de
    auditoria/legal, mesma categoria de LogAcesso/EncaminhamentoHistorico;
    nada o exclui, nem logicamente.

    `snapshot` guarda uma cópia estruturada do conteúdo (achados, conclusões,
    descritivo) no momento da geração, incluindo os CAMINHOS das fotos
    copiadas para este relatório (não FKs para `Foto` — ver ADR-07: o
    snapshot sobrevive a uma purga futura dos originais).
    """
    inspecao = models.ForeignKey(
        Inspecao, on_delete=models.PROTECT, related_name='relatorios_finais',
        verbose_name='Inspeção',
    )
    numero_versao = models.PositiveIntegerField('Versão')
    arquivo_pdf = models.FileField('PDF gerado', upload_to=relatorio_pdf_upload_path)
    snapshot = models.JSONField('Snapshot')
    gerado_por = models.ForeignKey(
        get_user_model(), on_delete=models.PROTECT, related_name='relatorios_finais_gerados',
        verbose_name='Gerado por',
    )
    gerado_em = models.DateTimeField('Gerado em', auto_now_add=True)

    class Meta:
        ordering = ['-numero_versao']
        verbose_name = 'Relatório Final de Inspeção'
        verbose_name_plural = 'Relatórios Finais de Inspeção'
        constraints = [
            models.UniqueConstraint(
                fields=['inspecao', 'numero_versao'], name='unique_versao_por_inspecao',
            ),
        ]

    def __str__(self):
        return f'{self.inspecao.edificacao} — Relatório Final v{self.numero_versao}'
