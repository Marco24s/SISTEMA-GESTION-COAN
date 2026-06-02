from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0006_pyrotechnicstoragelocation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pyrotechnicphysicalitem",
            name="current_location",
            field=models.CharField(
                blank=True,
                help_text="Deposito, pañol, polvorin o referencia actual. No debe quedar vacio.",
                max_length=180,
                verbose_name="Ubicacion actual",
            ),
        ),
        migrations.AddField(
            model_name="pyrotechnicphysicalitem",
            name="current_storage_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="physical_items",
                to="supervivencia.pyrotechnicstoragelocation",
                verbose_name="Ubicacion controlada",
            ),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicphysicalitem",
            index=models.Index(fields=["current_storage_location"], name="superviven_current_f110c0_idx"),
        ),
    ]
