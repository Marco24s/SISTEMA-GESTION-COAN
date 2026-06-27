import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_add_procurement_delete_pin_system"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("licitaciones", "0005_tenderprocess_classification"),
    ]

    operations = [
        migrations.CreateModel(
            name="ForeignTenderProcess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(default=2026, verbose_name="Ejercicio / Año")),
                ("process_number", models.CharField(max_length=60, verbose_name="Licitacion")),
                ("process_type", models.CharField(choices=[("PUBLICA", "Licitacion Publica"), ("PRIVADA", "Licitacion Privada"), ("CONTRATACION_DIRECTA", "Contratacion Directa"), ("OTRO", "Otro")], default="PUBLICA", max_length=30, verbose_name="Tipo de proceso")),
                ("has_oca", models.BooleanField(blank=True, null=True, verbose_name="OCA")),
                ("status", models.CharField(choices=[("INICIADO", "Iniciado"), ("EN_EVALUACION", "En evaluacion"), ("DICTAMEN_EMITIDO", "Dictamen emitido"), ("PENDIENTE_ASIGNACION", "Pendiente de asignacion"), ("ADJUDICADO", "Adjudicado"), ("EN_RECEPCION", "En recepcion"), ("FINALIZADO", "Finalizado"), ("FRACASADO", "Fracasado"), ("DEJADO_SIN_EFECTO", "Dejado sin efecto")], default="INICIADO", max_length=30, verbose_name="Estado")),
                ("currency", models.CharField(choices=[("USD", "Dolares"), ("EUR", "Euros"), ("ARS", "Pesos"), ("OTRA", "Otra")], default="USD", max_length=10, verbose_name="Moneda unica del proceso")),
                ("custom_currency", models.CharField(blank=True, max_length=30, verbose_name="Nombre de otra moneda")),
                ("evaluation_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True, verbose_name="Monto del dictamen de evaluacion")),
                ("awarded_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True, verbose_name="Monto asignado en adjudicacion")),
                ("notes", models.TextField(blank=True, verbose_name="Observaciones generales")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_foreign_tender_processes", to=settings.AUTH_USER_MODEL, verbose_name="Creado por")),
            ],
            options={
                "verbose_name": "Licitacion en el exterior",
                "verbose_name_plural": "Licitaciones en el exterior",
                "ordering": ["-year", "process_number"],
            },
        ),
        migrations.CreateModel(
            name="ForeignTenderRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requirement_number", models.CharField(max_length=30, verbose_name="REQ")),
                ("requested_amount", models.DecimalField(decimal_places=2, max_digits=18, verbose_name="Monto del requerimiento")),
                ("workshop", models.CharField(blank=True, help_text="Utilizar solo si el taller no existe entre las unidades.", max_length=100, verbose_name="Taller alternativo")),
                ("aircraft", models.CharField(blank=True, max_length=100, verbose_name="Aeronave / sistema")),
                ("description", models.TextField(verbose_name="Descripcion")),
                ("notes", models.TextField(blank=True, verbose_name="Observaciones")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("process", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="licitaciones.foreigntenderprocess", verbose_name="Licitacion")),
                ("unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="foreign_tender_requirements", to="core.unit", verbose_name="Taller / destino")),
            ],
            options={
                "verbose_name": "Requerimiento exterior",
                "verbose_name_plural": "Requerimientos exteriores",
                "ordering": ["requirement_number"],
            },
        ),
        migrations.CreateModel(
            name="ForeignTenderUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_date", models.DateField(verbose_name="Fecha")),
                ("organization", models.CharField(blank=True, max_length=120, verbose_name="Organismo")),
                ("document_type", models.CharField(choices=[("GDE", "GDE"), ("GFH", "GFH"), ("NOTA", "Nota"), ("DISPOSICION", "Disposicion"), ("INFORME", "Informe"), ("OTRO", "Otro")], default="GFH", max_length=20, verbose_name="Tipo de documento")),
                ("document_number", models.CharField(blank=True, max_length=150, verbose_name="Numero de documento")),
                ("description", models.TextField(verbose_name="Novedad / estado informado")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_foreign_tender_updates", to=settings.AUTH_USER_MODEL)),
                ("process", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="updates", to="licitaciones.foreigntenderprocess", verbose_name="Licitacion")),
            ],
            options={
                "verbose_name": "Novedad de licitacion exterior",
                "verbose_name_plural": "Novedades de licitaciones exteriores",
                "ordering": ["-event_date", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="foreigntenderprocess",
            constraint=models.UniqueConstraint(fields=("year", "process_number"), name="unique_foreign_tender_year_number"),
        ),
        migrations.AddConstraint(
            model_name="foreigntenderrequirement",
            constraint=models.UniqueConstraint(fields=("process", "requirement_number"), name="unique_foreign_tender_requirement"),
        ),
    ]
