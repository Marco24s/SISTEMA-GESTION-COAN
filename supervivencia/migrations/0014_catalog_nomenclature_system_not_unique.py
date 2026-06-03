# Generated manually on 2026-06-03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0013_pyrotechnicphysicalitem_lot_quantity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="nomenclature",
            field=models.CharField(max_length=150, verbose_name="Nomenclatura"),
        ),
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="system",
            field=models.CharField(max_length=150, verbose_name="Sistema"),
        ),
    ]
