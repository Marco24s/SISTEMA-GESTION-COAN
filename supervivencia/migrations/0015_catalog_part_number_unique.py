# Generated manually on 2026-06-03

from django.db import migrations, models


def normalize_catalog_part_numbers(apps, schema_editor):
    PyrotechnicCatalogItem = apps.get_model("supervivencia", "PyrotechnicCatalogItem")
    used_part_numbers = set()

    for item in PyrotechnicCatalogItem.objects.order_by("part_number", "id"):
        part_number = (item.part_number or "").strip().upper()
        if not part_number:
            if item.part_number is not None:
                item.part_number = None
                item.save(update_fields=["part_number"])
            continue

        new_part_number = part_number
        if new_part_number in used_part_numbers:
            suffix = f" ID {item.pk}"
            new_part_number = f"{part_number[:80 - len(suffix)]}{suffix}"

        while new_part_number in used_part_numbers:
            suffix = f" ID {item.pk}"
            new_part_number = f"{new_part_number[:80 - len(suffix)]}{suffix}"

        if item.part_number != new_part_number:
            item.part_number = new_part_number
            item.save(update_fields=["part_number"])

        used_part_numbers.add(new_part_number)


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0014_catalog_nomenclature_system_not_unique"),
    ]

    operations = [
        migrations.RunPython(normalize_catalog_part_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pyrotechniccatalogitem",
            name="part_number",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True, verbose_name="N° / Parte"),
        ),
    ]
