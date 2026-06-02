# Generated manually on 2026-06-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0002_rename_variant_labels"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pyrotechnicitemtype",
            name="code",
            field=models.CharField(max_length=150, unique=True, verbose_name="NOMENCLATURA"),
        ),
        migrations.AlterField(
            model_name="pyrotechnicitemtype",
            name="name",
            field=models.CharField(max_length=150, verbose_name="SISTEMA"),
        ),
        migrations.AddField(
            model_name="pyrotechnicitemtype",
            name="part_number",
            field=models.CharField(blank=True, max_length=80, null=True, verbose_name="N° / PARTE"),
        ),
        migrations.AddField(
            model_name="pyrotechnicitemtype",
            name="nsn",
            field=models.CharField(blank=True, max_length=80, null=True, verbose_name="N.S.N"),
        ),
        migrations.AddField(
            model_name="pyrotechnicitemtype",
            name="alternate_part_number",
            field=models.CharField(
                blank=True,
                max_length=120,
                null=True,
                verbose_name="NUMERO DE PARTE ALTERNATIVO",
            ),
        ),
    ]
