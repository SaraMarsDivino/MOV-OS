from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0005_unique_open_caja_per_sucursal'),
    ]

    operations = [
        migrations.AddField(
            model_name='aperturacierrecaja',
            name='efectivo_contado',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='aperturacierrecaja',
            name='descuadre',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
