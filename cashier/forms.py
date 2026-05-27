# cashier/forms.py
from django import forms
from .models import AperturaCierreCaja
from MOVOS.money import parse_clp_pesos

class AperturaCajaForm(forms.ModelForm):
    class Meta:
        model = AperturaCierreCaja
        fields = ['efectivo_inicial']  # Cambiamos al nombre correcto del campo
        widgets = {
            'efectivo_inicial': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 10.000',
            }),
        }
        labels = {
            'efectivo_inicial': 'Efectivo Inicial (Caja Chica)',
        }

    def clean_efectivo_inicial(self):
        raw = self.cleaned_data.get('efectivo_inicial')
        try:
            val = parse_clp_pesos(raw)
        except Exception:
            raise forms.ValidationError('El monto de efectivo inicial no es válido.')
        if val < 0:
            raise forms.ValidationError('El efectivo inicial no puede ser negativo.')
        return val
