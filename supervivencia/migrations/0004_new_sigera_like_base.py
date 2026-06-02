# Generated manually on 2026-06-01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_add_supervivencia_pin_system"),
        ("supervivencia", "0003_item_type_technical_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PyrotechnicCatalogItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nomenclature", models.CharField(max_length=150, unique=True, verbose_name="Nomenclatura")),
                ("system", models.CharField(max_length=150, verbose_name="Sistema")),
                ("part_number", models.CharField(blank=True, max_length=80, null=True, verbose_name="N° / Parte")),
                ("nsn", models.CharField(blank=True, max_length=80, null=True, verbose_name="N.S.N")),
                (
                    "alternate_part_number",
                    models.CharField(blank=True, max_length=120, null=True, verbose_name="Numero de parte alternativo"),
                ),
                (
                    "theoretical_life_months",
                    models.PositiveIntegerField(blank=True, null=True, verbose_name="Vida util teorica (meses)"),
                ),
                ("description", models.TextField(blank=True, null=True, verbose_name="Descripcion")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
            ],
            options={
                "verbose_name": "Elemento de pirotecnia",
                "verbose_name_plural": "Catalogo de pirotecnia",
                "ordering": ["nomenclature"],
            },
        ),
        migrations.CreateModel(
            name="SurvivalMedium",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identifier", models.CharField(max_length=80, unique=True, verbose_name="Identificacion")),
                ("name", models.CharField(max_length=150, verbose_name="Medio")),
                (
                    "medium_type",
                    models.CharField(
                        choices=[
                            ("AERONAVE", "Aeronave"),
                            ("BALSA", "Balsa"),
                            ("CHALECO", "Chaleco"),
                            ("EQUIPO", "Equipo de supervivencia"),
                            ("CONTENEDOR", "Contenedor"),
                            ("OTRO", "Otro"),
                        ],
                        default="AERONAVE",
                        max_length=30,
                        verbose_name="Tipo de medio",
                    ),
                ),
                ("model", models.CharField(blank=True, max_length=120, null=True, verbose_name="Modelo")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.unit",
                        verbose_name="Unidad",
                    ),
                ),
            ],
            options={
                "verbose_name": "Medio de supervivencia",
                "verbose_name_plural": "Medios de supervivencia",
                "ordering": ["identifier"],
            },
        ),
    ]
