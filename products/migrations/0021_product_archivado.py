from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0020_set_permitir_venta_sin_stock_false'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='archivado',
            field=models.BooleanField(default=False, db_index=True, verbose_name='Archivado'),
        ),
    ]
