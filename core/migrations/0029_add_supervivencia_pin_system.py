# Generated manually on 2026-06-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_alter_greasebatch_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usersystempin",
            name="system_code",
            field=models.CharField(
                choices=[
                    ("sgmg", "Materias Grasas (SGMG)"),
                    ("sigera", "Ropa de Trabajo (SIGERA)"),
                    ("sgp", "Presupuesto (SGP)"),
                    ("licitaciones", "Licitaciones"),
                    ("supervivencia", "Supervivencia / Pirotecnia"),
                ],
                max_length=20,
                verbose_name="Sistema",
            ),
        ),
    ]
