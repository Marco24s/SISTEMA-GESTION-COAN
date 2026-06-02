from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0009_pyrotechnicmovement"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pyrotechnicstoragelocation",
            name="code",
            field=models.CharField(max_length=50, unique=True, verbose_name="Destino"),
        ),
    ]
