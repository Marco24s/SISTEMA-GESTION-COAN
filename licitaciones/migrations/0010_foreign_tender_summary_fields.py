import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licitaciones", "0009_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="allocation_gfh",
            field=models.TextField(blank=True, verbose_name="GFH de asignacion"),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="expediente",
            field=models.CharField(blank=True, max_length=150, verbose_name="Expediente"),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="incoterm",
            field=models.CharField(blank=True, max_length=30, verbose_name="Incoterm"),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="oca_expiration",
            field=models.CharField(blank=True, help_text="Admite una fecha o una aclaracion, por ejemplo 'No aplica'.", max_length=150, verbose_name="Fecha de vencimiento OCA"),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="received",
            field=models.BooleanField(blank=True, null=True, verbose_name="Recibido"),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="saimb_number",
            field=models.CharField(blank=True, max_length=30, verbose_name="SAIMB Nro."),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="sp",
            field=models.CharField(blank=True, max_length=30, verbose_name="SP"),
        ),
        migrations.AlterField(
            model_name="foreigntenderprocess",
            name="status",
            field=models.CharField(choices=[("INICIADO", "Iniciado"), ("EN_EVALUACION", "En evaluacion"), ("DICTAMEN_EMITIDO", "Dictamen emitido"), ("DISPONIBLE_PARA_ADJUDICAR", "Disponible para adjudicar"), ("PENDIENTE_ASIGNACION", "Pendiente de asignacion"), ("ADJUDICADO", "Adjudicado"), ("EN_RECEPCION", "En recepcion"), ("FINALIZADO", "Finalizado"), ("FRACASADO", "Fracasado"), ("DEJADO_SIN_EFECTO", "Dejado sin efecto")], default="INICIADO", max_length=30, verbose_name="Estado"),
        ),
        migrations.CreateModel(
            name="ForeignTenderPurchaseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_number", models.CharField(max_length=40, verbose_name="Nro. OC / OCA")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18, verbose_name="Monto OC / OCA")),
                ("issue_date", models.DateField(blank=True, null=True, verbose_name="Fecha de emision")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("process", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="purchase_orders", to="licitaciones.foreigntenderprocess", verbose_name="Licitacion")),
            ],
            options={
                "verbose_name": "Orden de compra exterior",
                "verbose_name_plural": "Ordenes de compra exteriores",
                "ordering": ["issue_date", "order_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="foreigntenderpurchaseorder",
            constraint=models.UniqueConstraint(fields=("process", "order_number"), name="unique_foreign_purchase_order"),
        ),
    ]
