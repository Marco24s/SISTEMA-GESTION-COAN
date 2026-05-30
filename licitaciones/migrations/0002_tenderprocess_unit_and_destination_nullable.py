from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("licitaciones", "0001_initial"),
        ("core", "0026_remove_customuser_security_pin_usersystempin"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenderprocess",
            name="unit",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tender_processes",
                to="core.unit",
                verbose_name="Destino requirente",
            ),
        ),
        migrations.AlterField(
            model_name="tenderprocess",
            name="destination",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tender_processes",
                to="licitaciones.procurementdestination",
                verbose_name="Destino legado",
            ),
        ),
    ]
