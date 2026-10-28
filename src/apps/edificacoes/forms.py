from decimal import Decimal

from django import forms
from .models import Edificacao, Profissional


def formatar_decimal_br(valor):
    """Converte um Decimal (ex. 4745.52) para texto no padrão BR (4.745,52)."""
    texto = f'{valor:,.2f}'
    return texto.translate(str.maketrans({',': '.', '.': ','}))


class CampoDecimalBR(forms.DecimalField):
    """DecimalField cujo widget exibe/aceita separador de milhar "." e
    decimal "," (ex. "4.745,52"), em vez do formato "4745.52" do Django."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip()
            if value:
                value = value.replace('.', '').replace(',', '.')
        return super().to_python(value)

    def prepare_value(self, value):
        if isinstance(value, Decimal):
            return formatar_decimal_br(value)
        return value


class EdificacaoForm(forms.ModelForm):
    area_construida_m2 = CampoDecimalBR(
        label='Área construída (m²)', required=False,
        max_digits=10, decimal_places=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'inputmode': 'decimal',
            'placeholder': '0,00', 'autocomplete': 'off',
        }),
    )

    class Meta:
        model = Edificacao
        fields = [
            'nome', 'endereco', 'area_construida_m2', 'pavimentos',
            'data_inauguracao', 'ativo',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
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


class ProfissionalForm(forms.ModelForm):
    class Meta:
        model = Profissional
        fields = ['nome', 'crea']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'crea': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: 12345/D-DF'}),
        }

    def clean_crea(self):
        crea = self.cleaned_data['crea'].strip()
        qs = Profissional.objects.filter(crea__iexact=crea)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um profissional cadastrado com este CREA.')
        return crea
