from django.db import migrations, models


def normalize_catalog_identity(apps, schema_editor):
    CatalogItem = apps.get_model("supervivencia", "PyrotechnicCatalogItem")

    for item in CatalogItem.objects.all().iterator():
        item.nomenclature = (item.nomenclature or "").upper().strip()
        item.system = (item.system or "").upper().strip()
        item.part_number = (item.part_number or "").upper().strip()
        item.nsn = (item.nsn or "").upper().strip()
        item.alternate_part_number = (item.alternate_part_number or "").upper().strip()
        item.save(
            update_fields=(
                "nomenclature",
                "system",
                "part_number",
                "nsn",
                "alternate_part_number",
            )
        )


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0017_alter_pyrotechnicstoragelocation_code_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="part_number",
            field=models.CharField(blank=True, max_length=80, null=True, verbose_name="N° / Parte"),
        ),
        migrations.RunPython(normalize_catalog_identity, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="part_number",
            field=models.CharField(blank=True, default="", max_length=80, verbose_name="N° / Parte"),
        ),
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="nsn",
            field=models.CharField(blank=True, default="", max_length=80, verbose_name="N.S.N"),
        ),
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="alternate_part_number",
            field=models.CharField(
                blank=True,
                default="",
                max_length=120,
                verbose_name="Numero de parte alternativo",
            ),
        ),
        migrations.AddConstraint(
            model_name="pyrotechniccatalogitem",
            constraint=models.UniqueConstraint(
                fields=("nomenclature", "system", "part_number", "nsn", "alternate_part_number"),
                name="unique_pyrotechnic_catalog_identity",
            ),
        ),
    ]
