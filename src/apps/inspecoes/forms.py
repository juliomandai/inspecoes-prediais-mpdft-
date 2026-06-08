from datetime import date
from django import forms
from .models import Inspecao, InspecaoEspecialidade, Achado, OpcaoCampo, VisitaTecnica
from apps.edificacoes.models import Edificacao


class InspecaoForm(forms.ModelForm):
    class Meta:
        model = Inspecao
        fields = ['edificacao']
        widgets = {
            'edificacao': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['edificacao'].queryset = Edificacao.objects.filter(ativo=True)
        self.fields['edificacao'].label = 'Edificação'


class EspecialidadeForm(forms.ModelForm):
    data_inspecao = forms.DateField(
        label='Data da inspeção',
        initial=date.today,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = InspecaoEspecialidade
        fields = ['especialidade', 'profissional', 'data_inspecao']
        widgets = {
            'especialidade': forms.Select(attrs={'class': 'form-select'}),
            'profissional': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'especialidade': 'Especialidade',
            'profissional': 'Profissional responsável',
        }

    def __init__(self, *args, inspecao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.inspecao = inspecao
        # Ao criar (sem instância), oculta especialidades já cadastradas
        if inspecao and not (kwargs.get('instance') and kwargs['instance'].pk):
            existentes = list(inspecao.especialidades.values_list('especialidade', flat=True))
            self.fields['especialidade'].choices = [
                (k, v) for k, v in InspecaoEspecialidade.ESPECIALIDADE_CHOICES
                if k not in existentes
            ]
            if not self.fields['especialidade'].choices:
                self.fields['especialidade'].choices = [('', 'Todas as especialidades já foram adicionadas')]


class AchadoForm(forms.ModelForm):
    localizacao = forms.ChoiceField(
        label='Localização',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    grupo_tecnico = forms.ChoiceField(
        label='Grupo técnico',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    requisito_afetado = forms.ChoiceField(
        label='Requisito afetado',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    em_conformidade = forms.BooleanField(
        label='Item em conformidade',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_em_conformidade'}),
    )
    gravidade = forms.IntegerField(
        label='Gravidade (G)', min_value=1, max_value=5, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
    )
    urgencia = forms.IntegerField(
        label='Urgência (U)', min_value=1, max_value=5, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
    )
    tendencia = forms.IntegerField(
        label='Tendência (T)', min_value=1, max_value=5, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
    )
    prioridade_risco = forms.TypedChoiceField(
        label='Análise de risco (prioridade)',
        choices=[(3, 'Prioridade 3 — Mínimo'), (2, 'Prioridade 2 — Regular'), (1, 'Prioridade 1 — Crítico')],
        coerce=int, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    direcionamento = forms.ChoiceField(
        label='Direcionamento',
        choices=Achado.DIRECIONAMENTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    prazo_meses = forms.TypedChoiceField(
        label='Prazo para resolução',
        choices=Achado.PRAZO_CHOICES,
        coerce=int, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Achado
        fields = [
            'localizacao', 'sub_localizacao', 'verificacao', 'grupo_tecnico',
            'em_conformidade', 'descricao_nao_conformidade', 'requisito_afetado',
            'gravidade', 'urgencia', 'tendencia',
            'prioridade_risco', 'recomendacao', 'direcionamento', 'prazo_meses',
        ]
        widgets = {
            'sub_localizacao': forms.TextInput(attrs={'class': 'form-control'}),
            'verificacao': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao_nao_conformidade': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'recomendacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'sub_localizacao': 'Sub-localização',
            'verificacao': 'Item de verificação',
            'descricao_nao_conformidade': 'Descrição da não conformidade',
            'recomendacao': 'Recomendação técnica',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        loc_labels = list(
            OpcaoCampo.objects.filter(campo='localizacao', ativo=True)
            .values_list('label', flat=True)
        )
        loc_choices = [('', '— Selecione —')] + [(v, v) for v in loc_labels]
        instance = kwargs.get('instance')
        if instance and instance.pk and instance.localizacao:
            if instance.localizacao not in loc_labels:
                loc_choices.append((instance.localizacao, instance.localizacao))
        self.fields['localizacao'].choices = loc_choices

        custom_gt = list(
            OpcaoCampo.objects.filter(campo='grupo_tecnico', ativo=True)
            .values_list('label', flat=True)
        )
        gt_choices = sorted(
            [(v, v) for _, v in Achado.GRUPO_TECNICO_CHOICES] + [(v, v) for v in custom_gt],
            key=lambda x: x[1].lower(),
        )
        self.fields['grupo_tecnico'].choices = [('', '— Selecione —')] + gt_choices

        custom_ra = list(
            OpcaoCampo.objects.filter(campo='requisito_afetado', ativo=True)
            .values_list('label', flat=True)
        )
        ra_choices = sorted(
            [(v, v) for _, v in Achado.REQUISITO_CHOICES] + [(v, v) for v in custom_ra],
            key=lambda x: x[1].lower(),
        )
        self.fields['requisito_afetado'].choices = [('', '— Selecione —')] + ra_choices

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('em_conformidade'):
            cleaned['gravidade'] = 1
            cleaned['urgencia'] = 1
            cleaned['tendencia'] = 1
            cleaned['descricao_nao_conformidade'] = ''
            cleaned['requisito_afetado'] = ''
            cleaned['recomendacao'] = ''
            cleaned['direcionamento'] = 'manutencao'
            cleaned['prazo_meses'] = 12
            cleaned['prioridade_risco'] = 3
        return cleaned


class InspecaoFilterForm(forms.Form):
    edificacao = forms.ModelChoiceField(
        queryset=Edificacao.objects.filter(ativo=True),
        required=False, label='Edificação',
        empty_label='Todas as edificações',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    especialidade = forms.ChoiceField(
        choices=[('', 'Todas')] + InspecaoEspecialidade.ESPECIALIDADE_CHOICES,
        required=False, label='Especialidade',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    profissional = forms.CharField(
        required=False, label='Profissional',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do profissional'}),
    )
    data_inicio = forms.DateField(
        required=False, label='Data de',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    data_fim = forms.DateField(
        required=False, label='Data até',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + InspecaoEspecialidade.STATUS_CHOICES,
        required=False, label='Status',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class VisitaTecnicaForm(forms.ModelForm):
    data_visita = forms.DateField(
        label='Data da visita',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
    )

    class Meta:
        model = VisitaTecnica
        fields = ['data_visita', 'responsavel', 'motivo', 'achados', 'conclusoes_encaminhamentos']
        widgets = {
            'responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'achados': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'conclusoes_encaminhamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'responsavel': 'Profissional responsável',
            'motivo': 'Motivo da visita',
            'achados': 'Achados da visita',
            'conclusoes_encaminhamentos': 'Conclusões e encaminhamentos',
        }

    def clean_data_visita(self):
        data = self.cleaned_data['data_visita']
        if data and data > date.today():
            raise forms.ValidationError('A data da visita não pode ser futura.')
        return data


class VisitaFilterForm(forms.Form):
    data_inicio = forms.DateField(
        required=False, label='Data de',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    data_fim = forms.DateField(
        required=False, label='Data até',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
