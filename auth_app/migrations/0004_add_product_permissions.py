from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0003_user_can_add_products_user_can_edit_products_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='can_export_products',
            field=models.BooleanField(default=False, help_text='Puede exportar el catálogo de productos a Excel'),
        ),
        migrations.AddField(
            model_name='user',
            name='can_disable_products',
            field=models.BooleanField(default=False, help_text='Puede habilitar/deshabilitar productos'),
        ),
        migrations.AddField(
            model_name='user',
            name='can_archive_products',
            field=models.BooleanField(default=False, help_text='Puede archivar/restaurar productos y ver la papelera'),
        ),
        migrations.AddField(
            model_name='user',
            name='can_transfer_stock',
            field=models.BooleanField(default=False, help_text='Puede transferir stock entre sucursales'),
        ),
        migrations.AddField(
            model_name='user',
            name='can_assign_stock',
            field=models.BooleanField(default=False, help_text='Puede asignar stock a productos en masa'),
        ),
    ]
