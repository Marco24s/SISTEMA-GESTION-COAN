from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sigera", "0007_clothingtype_show_in_measure_sheet"),
    ]

    operations = [
        migrations.AddField(
            model_name="clothingassignment",
            name="reception_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pendiente de recepción"),
                    ("CONFIRMED", "Recepcionado"),
                ],
                default="CONFIRMED",
                max_length=20,
                verbose_name="Estado de recepción",
            ),
        ),
        migrations.AddField(
            model_name="clothingassignment",
            name="received_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Fecha de recepción"),
        ),
        migrations.AddField(
            model_name="clothingassignment",
            name="received_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="received_clothing_assignments",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Recepcionado por",
            ),
        ),
    ]
