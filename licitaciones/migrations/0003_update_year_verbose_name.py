# Generated manually on 2026-05-30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licitaciones", "0002_tenderprocess_unit_and_destination_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenderprocess",
            name="year",
            field=models.PositiveIntegerField(default=2026, verbose_name="Ejercicio / Año"),
        ),
    ]
