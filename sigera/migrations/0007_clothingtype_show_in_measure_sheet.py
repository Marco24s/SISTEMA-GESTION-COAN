from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sigera", "0006_personnelclothingmeasure"),
    ]

    operations = [
        migrations.AddField(
            model_name="clothingtype",
            name="show_in_measure_sheet",
            field=models.BooleanField(
                default=True,
                help_text="Indica si esta prenda debe aparecer al cargar talles del personal.",
                verbose_name="Mostrar en planilla de medidas",
            ),
        ),
    ]
