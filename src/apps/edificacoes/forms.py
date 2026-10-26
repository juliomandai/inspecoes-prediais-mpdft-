from django import forms
from .models import Edificacao


class EdificacaoForm(forms.ModelForm):
    class Meta:
        model = Edificacao
        fields = [
            'nome', 'endereco', 'area_construida_m2', 'pavimentos',
            'data_inauguracao', 'ativo',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'area_construida_m2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'pavimentos': forms.TextInput(attrs={'class': 'form-control'}),
            'data_inauguracao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nome(self):
        nome = self.cleaned_data['nome'].strip()
        qs = Edificacao.objects.filter(nome__iexact=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe uma edificação com este nome.')
        return nome


class DescritivoEdificacaoForm(forms.ModelForm):
    class Meta:
        model = Edificacao
        fields = ['descritivo']
        widgets = {
            'descritivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }
        labels = {'descritivo': 'Descritivo da edificação'}
