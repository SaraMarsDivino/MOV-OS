from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cashier', '0003_alter_aperturacierrecaja_apertura_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='caja',
            field=models.ForeignKey(
                related_name='ventas',
                on_delete=django.db.models.deletion.SET_NULL,
                blank=True,
                null=True,
                to='cashier.aperturacierrecaja'
            ),
        ),
    ]
