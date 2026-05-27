from django import forms
from .models import Sucursal

class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = ['nombre', 'direccion', 'telefono', 'low_stock_threshold']