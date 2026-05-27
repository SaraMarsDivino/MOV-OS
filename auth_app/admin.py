from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


class CustomUserAdmin(BaseUserAdmin):
    # Extend the default fieldsets to include custom flags and sucursales
    fieldsets = BaseUserAdmin.fieldsets + (
        (_('Flags'), {'fields': ('is_admin', 'is_employee')}),
        (_('Permisos'), {'fields': ('can_add_products', 'can_edit_products', 'can_view_analytics')}),
        (_('Sucursales autorizadas'), {'fields': ('sucursales_autorizadas',)}),
    )

    # When creating a user via admin, allow setting the custom fields too
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'is_admin', 'is_employee', 'sucursales_autorizadas', 'groups', 'user_permissions'),
        }),
    ) + BaseUserAdmin.add_fieldsets

    # Use horizontal filters for many-to-many relations to provide a compact UI
    filter_horizontal = ('sucursales_autorizadas', 'groups', 'user_permissions')


admin.site.register(User, CustomUserAdmin)
