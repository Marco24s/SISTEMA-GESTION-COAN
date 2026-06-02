# Generated manually on 2026-06-01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_add_supervivencia_pin_system"),
        ("supervivencia", "0005_pyrotechnicphysicalitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="PyrotechnicStorageLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True, verbose_name="Codigo")),
                ("name", models.CharField(max_length=150, verbose_name="Ubicacion")),
                (
                    "location_type",
                    models.CharField(
                        choices=[
                            ("POLVORIN", "Polvorin"),
                            ("PANOL", "Pañol"),
                            ("DEPOSITO", "Deposito"),
                            ("TALLER", "Taller"),
                            ("OTRO", "Otro"),
                        ],
                        default="DEPOSITO",
                        max_length=30,
                        verbose_name="Tipo de ubicacion",
                    ),
                ),
                ("is_restricted", models.BooleanField(default=True, verbose_name="Zona restringida")),
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
                "verbose_name": "Ubicacion pirotecnica",
                "verbose_name_plural": "Ubicaciones pirotecnicas",
                "ordering": ["code"],
            },
        ),
    ]
