# Generated manually on 2026-05-30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_remove_customuser_security_pin_usersystempin"),
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
                ],
                max_length=20,
                verbose_name="Sistema",
            ),
        ),
    ]
