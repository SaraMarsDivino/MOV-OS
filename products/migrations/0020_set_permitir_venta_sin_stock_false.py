from django.db import migrations, models


def set_stock_enforcement(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(permitir_venta_sin_stock=True).update(permitir_venta_sin_stock=False)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0019_product_stock_minimo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='permitir_venta_sin_stock',
            field=models.BooleanField(default=False, verbose_name='Permitir Venta sin Stock'),
        ),
        migrations.RunPython(set_stock_enforcement, migrations.RunPython.noop),
    ]
