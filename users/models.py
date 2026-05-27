# users/models.py
from django.db import models
from django.conf import settings
from sucursales.models import Sucursal


class Vendedor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)  # Campo agregado con valor por defecto
    sucursales_autorizadas = models.ManyToManyField(
        Sucursal,
        blank=True,
        related_name='vendedores_autorizados',
        help_text="Sucursales en las que el usuario puede abrir caja."
    )

    def __str__(self):
        return self.user.username
