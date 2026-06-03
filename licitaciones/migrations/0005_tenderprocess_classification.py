# Generated manually on 2026-06-02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licitaciones", "0004_alter_tenderprocess_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenderprocess",
            name="classification",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Sin clasificar"),
                    ("REPUESTO", "Repuesto"),
                    ("SUPERVIVENCIA", "Supervivencia"),
                    ("SIN_EFECTO", "Desiertos / Sin efecto / Fracasados"),
                    ("GRASAS_LUBRICANTES", "Grasas y Lubricantes"),
                    ("REPUESTOS_FONDEF", "Repuestos / FONDEF"),
                ],
                default="",
                max_length=30,
                verbose_name="Clasificacion",
            ),
        ),
    ]
