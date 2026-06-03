from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("supervivencia", "0010_storage_location_destino_label"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupervivenciaDeletionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_type", models.CharField(max_length=80, verbose_name="Tipo de objeto")),
                ("object_id", models.CharField(max_length=80, verbose_name="ID eliminado")),
                ("object_repr", models.CharField(max_length=300, verbose_name="Registro eliminado")),
                ("deleted_at", models.DateTimeField(auto_now_add=True, verbose_name="Fecha de eliminacion")),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="supervivencia_deletion_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Eliminado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Registro de borrado",
                "verbose_name_plural": "Registros de borrado",
                "ordering": ["-deleted_at"],
            },
        ),
    ]
