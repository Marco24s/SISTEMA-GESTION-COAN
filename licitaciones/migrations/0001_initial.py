from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_destinations(apps, schema_editor):
    ProcurementDestination = apps.get_model("licitaciones", "ProcurementDestination")
    destinations = [
        ("ARCE", "ARCE"),
        ("BACE", "BACE"),
        ("BAPI", "BAPI"),
        ("FAE3", "FAE3"),
        ("BARD", "BARD"),
        ("JEOB", "JEOB"),
    ]
    for code, name in destinations:
        ProcurementDestination.objects.get_or_create(code=code, defaults={"name": name})


def unseed_destinations(apps, schema_editor):
    ProcurementDestination = apps.get_model("licitaciones", "ProcurementDestination")
    ProcurementDestination.objects.filter(code__in=["ARCE", "BACE", "BAPI", "FAE3", "BARD", "JEOB"]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcurementDestination",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True, verbose_name="Codigo")),
                ("name", models.CharField(max_length=150, verbose_name="Nombre")),
                ("description", models.TextField(blank=True, null=True, verbose_name="Descripcion")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
            ],
            options={
                "verbose_name": "Destino requirente",
                "verbose_name_plural": "Destinos requirentes",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="TenderProcess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(default=2026, verbose_name="Ejercicio / Anio")),
                ("process_number", models.CharField(max_length=60, verbose_name="Numero de proceso")),
                ("expediente", models.CharField(blank=True, max_length=120, null=True, verbose_name="Expediente")),
                ("name", models.CharField(max_length=300, verbose_name="Nombre del proceso")),
                (
                    "process_type",
                    models.CharField(
                        choices=[
                            ("PUBLICA", "Licitacion Publica"),
                            ("PRIVADA", "Licitacion Privada"),
                            ("CONTRATACION_DIRECTA", "Contratacion Directa"),
                            ("OTRO", "Otro"),
                        ],
                        default="PRIVADA",
                        max_length=30,
                        verbose_name="Tipo de proceso",
                    ),
                ),
                ("opening_date", models.DateTimeField(blank=True, null=True, verbose_name="Fecha de apertura")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PUBLICADO", "Publicado"),
                            ("EN_APERTURA", "En apertura"),
                            ("EN_EVALUACION", "En evaluacion"),
                            ("PREADJUDICADO", "Preadjudicado"),
                            ("DISPONIBLE_ADJUDICAR", "Disponible para adjudicar"),
                            ("ADJUDICADO", "Adjudicado"),
                            ("FRACASADO", "Fracasado"),
                            ("DESIERTO", "Desierto"),
                            ("DEJADO_SIN_EFECTO", "Dejado sin efecto"),
                        ],
                        default="PUBLICADO",
                        max_length=30,
                        verbose_name="Estado",
                    ),
                ),
                ("amount_ars", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True, verbose_name="Monto en pesos")),
                (
                    "currency",
                    models.CharField(
                        choices=[("ARS", "Pesos"), ("USD", "Dolares"), ("EUR", "Euros"), ("OTRA", "Otra")],
                        default="ARS",
                        max_length=10,
                        verbose_name="Moneda original",
                    ),
                ),
                (
                    "foreign_amount",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True, verbose_name="Monto en moneda extranjera"),
                ),
                (
                    "exchange_rate",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True, verbose_name="Tipo de cambio usado"),
                ),
                ("exchange_rate_date", models.DateField(blank=True, null=True, verbose_name="Fecha del tipo de cambio")),
                ("has_oca", models.BooleanField(blank=True, null=True, verbose_name="OCA")),
                ("source", models.CharField(default="COMPRAR.GOB.AR", max_length=150, verbose_name="Fuente")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_tender_processes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "destination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tender_processes",
                        to="licitaciones.procurementdestination",
                        verbose_name="Destino requirente",
                    ),
                ),
            ],
            options={
                "verbose_name": "Proceso licitatorio",
                "verbose_name_plural": "Procesos licitatorios",
                "ordering": ["-year", "destination__code", "-opening_date", "process_number"],
                "unique_together": {("year", "process_number")},
            },
        ),
        migrations.RunPython(seed_destinations, unseed_destinations),
    ]
