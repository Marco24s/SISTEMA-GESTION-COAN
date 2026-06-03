# Generated manually on 2026-06-02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_add_supervivencia_pin_system"),
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
                    ("supervivencia_admin", "Supervivencia / Administracion"),
                ],
                max_length=20,
                verbose_name="Sistema",
            ),
        ),
    ]
