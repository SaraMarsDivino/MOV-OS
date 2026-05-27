from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_remove_proveedor_and_migrate_cod2_to_barcode'),
        ('products', '0015_ajustestock_transferenciastock_stocksucursal'),
    ]

    operations = [
        # Merge migration: no-op. This resolves multiple leaf nodes.
    ]
