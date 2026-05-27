from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_merge_0011_and_0015'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='activo',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Activo'),
        ),
    ]
