from django.db import migrations


def drop_legacy_part_number_unique(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    CatalogItem = apps.get_model("supervivencia", "PyrotechnicCatalogItem")
    table_name = CatalogItem._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)

    quote_name = schema_editor.connection.ops.quote_name
    for constraint_name, details in constraints.items():
        if details.get("unique") and details.get("columns") == ["part_number"]:
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} "
                f"DROP CONSTRAINT IF EXISTS {quote_name(constraint_name)}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0018_catalog_composite_identity"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_part_number_unique, migrations.RunPython.noop),
    ]
