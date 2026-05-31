from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0018_stocksucursal_permitir_venta_sin_stock'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='stock_minimo',
            field=models.PositiveIntegerField(
                default=5,
                help_text='Cantidad por sucursal por debajo de la cual se genera alerta de stock bajo',
                verbose_name='Stock mínimo (alerta)',
            ),
        ),
    ]
