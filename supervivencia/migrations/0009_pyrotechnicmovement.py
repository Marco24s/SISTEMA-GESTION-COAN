from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("supervivencia", "0008_pyrotechnicassignment"),
    ]

    operations = [
        migrations.CreateModel(
            name="PyrotechnicMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "movement_type",
                    models.CharField(
                        choices=[
                            ("REGISTERED", "Alta de material"),
                            ("INSTALLED", "Montado / asignado"),
                            ("REMOVED", "Retirado"),
                            ("LOCATION_CHANGE", "Cambio de ubicacion"),
                            ("STATUS_CHANGE", "Cambio de estado"),
                            ("DISCARDED", "Baja"),
                            ("NOTE", "Nota"),
                        ],
                        max_length=30,
                        verbose_name="Movimiento",
                    ),
                ),
                ("movement_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="Fecha")),
                ("from_reference", models.CharField(blank=True, max_length=180, null=True, verbose_name="Desde")),
                ("to_reference", models.CharField(blank=True, max_length=180, null=True, verbose_name="Hacia")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                (
                    "assignment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="movements",
                        to="supervivencia.pyrotechnicassignment",
                        verbose_name="Asignacion",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_pyrotechnic_movements",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "medium",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pyrotechnic_movements",
                        to="supervivencia.survivalmedium",
                        verbose_name="Medio",
                    ),
                ),
                (
                    "physical_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="movements",
                        to="supervivencia.pyrotechnicphysicalitem",
                        verbose_name="Material fisico",
                    ),
                ),
            ],
            options={
                "verbose_name": "Movimiento de pirotecnia",
                "verbose_name_plural": "Movimientos de pirotecnia",
                "ordering": ["-movement_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="pyrotechnicmovement",
            index=models.Index(fields=["movement_type"], name="superviven_movemen_b54b1a_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicmovement",
            index=models.Index(fields=["movement_date"], name="superviven_movemen_0e476d_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicmovement",
            index=models.Index(fields=["physical_item"], name="superviven_physica_90e3d7_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicmovement",
            index=models.Index(fields=["medium"], name="superviven_medium__5f02e7_idx"),
        ),
    ]
