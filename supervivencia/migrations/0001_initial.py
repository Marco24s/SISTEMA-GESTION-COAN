# Generated manually on 2026-06-01

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("licitaciones", "0003_update_year_verbose_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Aircraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30, unique=True, verbose_name="Codigo")),
                ("name", models.CharField(max_length=120, verbose_name="Aeronave")),
                ("description", models.TextField(blank=True, null=True, verbose_name="Descripcion")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
            ],
            options={
                "verbose_name": "Aeronave",
                "verbose_name_plural": "Aeronaves",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="PyrotechnicItemType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30, unique=True, verbose_name="Codigo")),
                ("name", models.CharField(max_length=150, verbose_name="Elemento")),
                ("description", models.TextField(blank=True, null=True, verbose_name="Descripcion")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
            ],
            options={
                "verbose_name": "Tipo de elemento pirotecnico",
                "verbose_name_plural": "Tipos de elementos pirotecnicos",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="AircraftVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="Variante / grupo")),
                ("description", models.TextField(blank=True, null=True, verbose_name="Descripcion")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                (
                    "aircraft",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="supervivencia.aircraft",
                        verbose_name="Aeronave",
                    ),
                ),
            ],
            options={
                "verbose_name": "Variante de aeronave",
                "verbose_name_plural": "Variantes de aeronave",
                "ordering": ["aircraft__code", "name"],
                "unique_together": {("aircraft", "name")},
            },
        ),
        migrations.CreateModel(
            name="PyrotechnicRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(default=2026, verbose_name="Año")),
                (
                    "month",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Enero"),
                            (2, "Febrero"),
                            (3, "Marzo"),
                            (4, "Abril"),
                            (5, "Mayo"),
                            (6, "Junio"),
                            (7, "Julio"),
                            (8, "Agosto"),
                            (9, "Septiembre"),
                            (10, "Octubre"),
                            (11, "Noviembre"),
                            (12, "Diciembre"),
                        ],
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(12),
                        ],
                        verbose_name="Mes",
                    ),
                ),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="Cantidad")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("SIN_ALARMA", "Sin alarma"),
                            ("INICIO_GESTION", "Inicio de gestion"),
                            ("ADQUISICION", "Adquisicion"),
                            ("SIN_GESTION", "Sin gestion de compra"),
                            ("ENTREGADO", "Entregado / cerrado"),
                            ("CANCELADO", "Cancelado"),
                        ],
                        default="SIN_ALARMA",
                        max_length=30,
                        verbose_name="Estado",
                    ),
                ),
                ("reference", models.CharField(blank=True, max_length=180, null=True, verbose_name="Referencia documental")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "aircraft",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pyrotechnic_requirements",
                        to="supervivencia.aircraft",
                        verbose_name="Aeronave",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_pyrotechnic_requirements",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "item_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requirements",
                        to="supervivencia.pyrotechnicitemtype",
                        verbose_name="Tipo de elemento",
                    ),
                ),
                (
                    "tender_process",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pyrotechnic_requirements",
                        to="licitaciones.tenderprocess",
                        verbose_name="Proceso licitatorio asociado",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pyrotechnic_requirements",
                        to="supervivencia.aircraftvariant",
                        verbose_name="Variante / grupo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Necesidad de supervivencia / pirotecnia",
                "verbose_name_plural": "Necesidades de supervivencia / pirotecnia",
                "ordering": ["year", "month", "aircraft__code", "variant__name", "item_type__code"],
            },
        ),
        migrations.CreateModel(
            name="PyrotechnicRequirementNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note_date", models.DateField(verbose_name="Fecha")),
                ("text", models.TextField(verbose_name="Novedad")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_pyrotechnic_notes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "requirement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_notes",
                        to="supervivencia.pyrotechnicrequirement",
                        verbose_name="Necesidad",
                    ),
                ),
            ],
            options={
                "verbose_name": "Novedad de supervivencia / pirotecnia",
                "verbose_name_plural": "Novedades de supervivencia / pirotecnia",
                "ordering": ["-note_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pyrotechnicrequirement",
            index=models.Index(fields=["year", "month"], name="superviven_year_48752d_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicrequirement",
            index=models.Index(fields=["status"], name="superviven_status_49b422_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicrequirement",
            index=models.Index(fields=["is_active"], name="superviven_is_acti_39246e_idx"),
        ),
    ]
