# users/forms.py

from django import forms
from django.contrib.auth import get_user_model
from reports.models import Sucursal

User = get_user_model()

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_superuser', 'sucursales_autorizadas', 'can_add_products', 'can_edit_products', 'can_view_analytics']
        widgets = {
            'password': forms.PasswordInput(render_value=True),
            'sucursales_autorizadas': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sucursales_autorizadas'].queryset = Sucursal.objects.all()
        # En edición, hacemos que la contraseña no sea obligatoria.
        if self.instance and self.instance.pk:
            self.fields['password'].required = False

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise forms.ValidationError("Este campo es obligatorio.")
        normalized = username.lower()
        # Si estamos editando, comparamos con la instancia actual
        if self.instance and self.instance.pk:
            current = self.instance.username.strip().lower()
            # Si no cambió, retorno
            if normalized == current:
                return self.instance.username
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un usuario con ese nombre.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        is_superuser = cleaned_data.get('is_superuser')
        sucursales = cleaned_data.get('sucursales_autorizadas')
        # Para usuarios que no son superuser es obligatorio seleccionar sucursales
        if not is_superuser and (not sucursales or len(sucursales) == 0):
            self.add_error('sucursales_autorizadas', "Debe seleccionar al menos una sucursal para usuarios no administradores.")
        return cleaned_data
