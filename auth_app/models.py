from django.contrib.auth.models import AbstractUser
from django.db import models
from reports.models import Sucursal

class User(AbstractUser):
    """
    Modelo de usuario personalizado.
    Los usuarios no administradores deben tener asignadas las sucursales en las que pueden abrir caja.
    Los administradores (is_staff o is_superuser) no necesitan esta asignación.
    """
    is_admin = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=True)
    sucursales_autorizadas = models.ManyToManyField(
        Sucursal,
        blank=True,
        related_name='usuarios_autorizados',
        help_text="Sucursales en las que el usuario puede abrir cajas (solo para usuarios no administradores)."
    )

    # Permisos granulares controlados desde la interfaz de gestión de usuarios
    can_add_products = models.BooleanField(default=False, help_text="Puede agregar productos a sucursales seleccionadas")
    can_edit_products = models.BooleanField(default=False, help_text="Puede editar valores y atributos de productos")
    can_export_products = models.BooleanField(default=False, help_text="Puede exportar el catálogo de productos a Excel")
    can_disable_products = models.BooleanField(default=False, help_text="Puede habilitar/deshabilitar productos")
    can_archive_products = models.BooleanField(default=False, help_text="Puede archivar/restaurar productos y ver la papelera")
    can_transfer_stock = models.BooleanField(default=False, help_text="Puede transferir stock entre sucursales")
    can_assign_stock = models.BooleanField(default=False, help_text="Puede asignar stock a productos en masa")
    can_view_analytics = models.BooleanField(default=False, help_text="Puede ver los reportes y analíticas del sistema")

    def __str__(self):
        return f"{self.username} ({'Admin' if self.is_admin else 'Empleado'})"

    def puede_abrir_caja_en(self, sucursal):
        """
        Devuelve True si el usuario puede abrir caja en la sucursal dada.
        Los administradores pueden abrir caja en cualquier sucursal.
        Los demás deben estar autorizados explícitamente.
        """
        if self.is_staff or self.is_superuser:
            return True
        return self.sucursales_autorizadas.filter(id=sucursal.id).exists()
