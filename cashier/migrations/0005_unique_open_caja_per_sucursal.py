from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0004_venta_caja'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='aperturacierrecaja',
            constraint=models.UniqueConstraint(
                fields=('sucursal',),
                condition=models.Q(('estado', 'abierta')),
                name='unique_open_caja_per_sucursal',
            ),
        ),
    ]
