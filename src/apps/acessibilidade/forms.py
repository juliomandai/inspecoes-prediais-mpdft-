from django import forms
from .models import Avaliacao


class AvaliacaoEditForm(forms.Form):
    status = forms.ChoiceField(choices=Avaliacao.Status.choices, label='Status')
    resolucao_diagnostico = forms.CharField(max_length=40, required=False, label='Resolução (diagnóstico)')
    observacao = forms.CharField(widget=forms.Textarea, required=False, label='Observação')
    status_acao = forms.ChoiceField(choices=Avaliacao.StatusAcao.choices, label='Status da ação')
    responsavel = forms.CharField(max_length=200, required=False, label='Responsável')
    prazo = forms.DateField(required=False, label='Prazo', widget=forms.DateInput(attrs={'type': 'date'}))
    resolucao_prevista = forms.CharField(max_length=40, required=False, label='Resolução prevista')
    ordem_servico = forms.CharField(max_length=100, required=False, label='Ordem de serviço')
    data_os = forms.DateField(required=False, label='Data da OS', widget=forms.DateInput(attrs={'type': 'date'}))
    notas = forms.CharField(widget=forms.Textarea, required=False, label='Notas')


class AvaliacaoEdicaoLoteForm(forms.Form):
    ids_selecionados = forms.CharField()
    status = forms.ChoiceField(choices=Avaliacao.Status.choices, required=False, label='Status')
    resolucao_diagnostico = forms.CharField(max_length=40, required=False, label='Resolução (diagnóstico)')
    status_acao = forms.ChoiceField(choices=Avaliacao.StatusAcao.choices, required=False, label='Status da ação')
    responsavel = forms.CharField(max_length=200, required=False, label='Responsável')
    prazo = forms.DateField(required=False, label='Prazo')
    resolucao_prevista = forms.CharField(max_length=40, required=False, label='Resolução prevista')
    ordem_servico = forms.CharField(max_length=100, required=False, label='Ordem de serviço')

    def clean_ids_selecionados(self):
        valor = self.cleaned_data['ids_selecionados']
        ids = []
        for token in valor.split(','):
            token = token.strip()
            if not token:
                continue
            if not token.isdigit():
                raise forms.ValidationError('ids_selecionados contém um valor inválido.')
            ids.append(int(token))
        if not ids:
            raise forms.ValidationError('Nenhuma avaliação selecionada.')
        return valor

    def ids_list(self):
        return [int(x) for x in self.cleaned_data['ids_selecionados'].split(',') if x.strip()]

    def patch(self):
        # Usa checagem de "truthy" (não `is not None`) de propósito: os únicos
        # campos hoje expostos na UI de edição em lote (status_acao) são
        # ChoiceFields onde "" significa "não alterar". Isso tem uma limitação
        # conhecida: não é possível usar a edição em lote para *limpar* um
        # CharField opcional (setar para string vazia) — se um campo assim for
        # exposto na UI de lote no futuro, essa limitação precisa ser revisitada.
        campos = [
            'status', 'resolucao_diagnostico', 'status_acao',
            'responsavel', 'prazo', 'resolucao_prevista', 'ordem_servico',
        ]
        return {c: self.cleaned_data[c] for c in campos if self.cleaned_data.get(c)}
