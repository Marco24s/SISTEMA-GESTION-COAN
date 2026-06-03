# Generated manually on 2026-06-02

from django.db import migrations, models
import django.db.models.deletion


def copy_legacy_life_months(apps, schema_editor):
    PyrotechnicCatalogItem = apps.get_model("supervivencia", "PyrotechnicCatalogItem")
    PyrotechnicCatalogLifeRule = apps.get_model("supervivencia", "PyrotechnicCatalogLifeRule")
    for item in PyrotechnicCatalogItem.objects.exclude(theoretical_life_months__isnull=True):
        PyrotechnicCatalogLifeRule.objects.get_or_create(
            catalog_item=item,
            situation="GENERAL",
            defaults={
                "duration_value": item.theoretical_life_months,
                "duration_unit": "MONTHS",
                "notes": "Migrado desde vida util teorica",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0011_supervivenciadeletionlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="PyrotechnicCatalogLifeRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "situation",
                    models.CharField(
                        choices=[
                            ("GENERAL", "General / unica"),
                            ("ORIGINAL_PACKAGING", "Envase original"),
                            ("STORAGE", "En deposito"),
                            ("INSTALLED", "Instalado"),
                        ],
                        max_length=30,
                        verbose_name="Situacion",
                    ),
                ),
                ("duration_value", models.PositiveIntegerField(verbose_name="Vida util")),
                (
                    "duration_unit",
                    models.CharField(
                        choices=[("MONTHS", "Meses"), ("YEARS", "Años")],
                        default="YEARS",
                        max_length=10,
                        verbose_name="Unidad",
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=180, null=True, verbose_name="Observaciones")),
                (
                    "catalog_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="life_rules",
                        to="supervivencia.pyrotechniccatalogitem",
                        verbose_name="Elemento de catalogo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Regla de vida util",
                "verbose_name_plural": "Reglas de vida util",
                "ordering": ["catalog_item__nomenclature", "situation"],
                "unique_together": {("catalog_item", "situation")},
            },
        ),
        migrations.RunPython(copy_legacy_life_months, migrations.RunPython.noop),
    ]
