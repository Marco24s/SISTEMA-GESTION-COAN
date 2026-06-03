# Generated manually on 2026-06-02

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0012_pyrotechniccatalogliferule"),
    ]

    operations = [
        migrations.AddField(
            model_name="pyrotechnicphysicalitem",
            name="lot_quantity",
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
                verbose_name="Cantidad del lote",
            ),
        ),
    ]
