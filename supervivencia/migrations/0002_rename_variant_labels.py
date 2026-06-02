# Generated manually on 2026-06-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="aircraftvariant",
            options={
                "ordering": ["aircraft__code", "name"],
                "verbose_name": "Modelo de aeronave",
                "verbose_name_plural": "Modelos de aeronave",
            },
        ),
        migrations.AlterField(
            model_name="aircraftvariant",
            name="name",
            field=models.CharField(max_length=120, verbose_name="Modelo"),
        ),
        migrations.AlterField(
            model_name="pyrotechnicrequirement",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="pyrotechnic_requirements",
                to="supervivencia.aircraftvariant",
                verbose_name="Modelo",
            ),
        ),
    ]
