from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("supervivencia", "0007_physical_item_controlled_location"),
    ]

    operations = [
        migrations.CreateModel(
            name="PyrotechnicAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("installed_at", models.DateField(default=django.utils.timezone.localdate, verbose_name="Fecha de montaje / asignacion")),
                ("position", models.CharField(blank=True, max_length=120, null=True, verbose_name="Posicion / ubicacion en el medio")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo / montado")),
                ("removed_at", models.DateField(blank=True, null=True, verbose_name="Fecha de retiro")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_pyrotechnic_assignments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "medium",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pyrotechnic_assignments",
                        to="supervivencia.survivalmedium",
                        verbose_name="Medio",
                    ),
                ),
                (
                    "physical_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="supervivencia.pyrotechnicphysicalitem",
                        verbose_name="Material fisico",
                    ),
                ),
            ],
            options={
                "verbose_name": "Asignacion de pirotecnia",
                "verbose_name_plural": "Asignaciones de pirotecnia",
                "ordering": ["medium__identifier", "-is_active", "physical_item__expiration_date"],
            },
        ),
        migrations.AddConstraint(
            model_name="pyrotechnicassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=("physical_item",),
                name="unique_active_pyrotechnic_assignment",
            ),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicassignment",
            index=models.Index(fields=["is_active"], name="superviven_is_acti_8d35e6_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicassignment",
            index=models.Index(fields=["installed_at"], name="superviven_install_1e6cb9_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicassignment",
            index=models.Index(fields=["removed_at"], name="superviven_removed_7d6804_idx"),
        ),
    ]
