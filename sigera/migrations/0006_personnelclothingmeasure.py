# Generated manually on 2026-06-01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sigera", "0005_stockthreshold"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonnelClothingMeasure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "custom_measure",
                    models.CharField(
                        blank=True,
                        help_text="Usar solo si la medida no existe aun como talle del catalogo.",
                        max_length=120,
                        null=True,
                        verbose_name="Medida manual",
                    ),
                ),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "clothing_size",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="personnel_measures",
                        to="sigera.clothingsize",
                        verbose_name="Talle / Medida",
                    ),
                ),
                (
                    "clothing_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personnel_measures",
                        to="sigera.clothingtype",
                        verbose_name="Prenda",
                    ),
                ),
                (
                    "personnel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clothing_measures",
                        to="sigera.personnel",
                        verbose_name="Personal",
                    ),
                ),
            ],
            options={
                "verbose_name": "Medida de ropa del personal",
                "verbose_name_plural": "Medidas de ropa del personal",
                "ordering": ["clothing_type__name"],
                "unique_together": {("personnel", "clothing_type")},
            },
        ),
    ]
