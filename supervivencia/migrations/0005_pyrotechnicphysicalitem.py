# Generated manually on 2026-06-01

import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("supervivencia", "0004_new_sigera_like_base"),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PyrotechnicPhysicalItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("serial_number", models.CharField(blank=True, max_length=120, null=True, unique=True, verbose_name="Numero de serie")),
                ("lot_number", models.CharField(blank=True, max_length=120, null=True, verbose_name="Lote / partida")),
                ("manufacturer", models.CharField(blank=True, max_length=150, null=True, verbose_name="Fabricante")),
                ("manufacture_date", models.DateField(blank=True, null=True, verbose_name="Fecha de fabricacion")),
                ("expiration_date", models.DateField(verbose_name="Fecha de vencimiento")),
                (
                    "condition",
                    models.CharField(
                        choices=[
                            ("SERVICEABLE", "Operativo"),
                            ("UNSERVICEABLE", "No operativo"),
                            ("QUARANTINE", "En cuarentena"),
                            ("BLOCKED", "Bloqueado"),
                        ],
                        default="SERVICEABLE",
                        max_length=30,
                        verbose_name="Condicion",
                    ),
                ),
                (
                    "operational_status",
                    models.CharField(
                        choices=[
                            ("STOCK", "En deposito"),
                            ("RESERVED", "Reservado"),
                            ("INSTALLED", "Montado"),
                            ("REMOVED", "Removido"),
                            ("CONSUMED", "Consumido"),
                            ("DISCARDED", "Dado de baja"),
                        ],
                        default="STOCK",
                        max_length=30,
                        verbose_name="Estado operativo",
                    ),
                ),
                (
                    "current_location",
                    models.CharField(
                        help_text="Deposito, pañol, polvorin o referencia actual. No debe quedar vacio.",
                        max_length=180,
                        verbose_name="Ubicacion actual",
                    ),
                ),
                ("certificate_reference", models.CharField(blank=True, max_length=180, null=True, verbose_name="Certificado / documento")),
                ("notes", models.TextField(blank=True, null=True, verbose_name="Observaciones")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "catalog_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="physical_items",
                        to="supervivencia.pyrotechniccatalogitem",
                        verbose_name="Elemento de catalogo",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_pyrotechnic_physical_items",
                        to=django.conf.settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Material pirotecnico fisico",
                "verbose_name_plural": "Material pirotecnico fisico",
                "ordering": ["expiration_date", "catalog_item__nomenclature", "serial_number", "lot_number"],
            },
        ),
        migrations.AddIndex(
            model_name="pyrotechnicphysicalitem",
            index=models.Index(fields=["expiration_date"], name="superviven_expirat_d47f43_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicphysicalitem",
            index=models.Index(fields=["condition"], name="superviven_conditi_447c6e_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicphysicalitem",
            index=models.Index(fields=["operational_status"], name="superviven_operati_c5d24d_idx"),
        ),
        migrations.AddIndex(
            model_name="pyrotechnicphysicalitem",
            index=models.Index(fields=["is_active"], name="superviven_is_acti_24c7d1_idx"),
        ),
    ]
