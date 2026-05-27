from django.db import migrations, models


def migrate_codigo2_to_barcode(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    # If codigo_barras is empty and codigo_alternativo has value, move it to codigo_barras
    for p in Product.objects.all().only('id', 'codigo_alternativo', 'codigo_barras'):
        if (not p.codigo_barras) and p.codigo_alternativo:
            p.codigo_barras = p.codigo_alternativo
            p.save(update_fields=['codigo_barras'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_remove_product_iva_porcentaje_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_codigo2_to_barcode, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='product',
            name='proveedor',
        ),
    ]
