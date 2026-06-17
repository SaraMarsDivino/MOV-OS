from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0009_alter_venta_forma_pago_ventapago_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='offline_idempotency_key',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
