from django.conf import settings
from django.db import models
from django.urls import reverse

from core.models import Unit


class ProcurementDestination(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Codigo")
    name = models.CharField(max_length=150, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Destino requirente"
        verbose_name_plural = "Destinos requirentes"
        ordering = ["code"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper().strip()
        if self.name:
            self.name = self.name.upper().strip()
        super().save(*args, **kwargs)


class TenderProcess(models.Model):
    PROCESS_TYPE_CHOICES = [
        ("PUBLICA", "Licitacion Publica"),
        ("PRIVADA", "Licitacion Privada"),
        ("CONTRATACION_DIRECTA", "Contratacion Directa"),
        ("OTRO", "Otro"),
    ]

    STATUS_CHOICES = [
        ("PUBLICADO", "Publicado"),
        ("EN_APERTURA", "En apertura"),
        ("EN_EVALUACION", "En evaluacion"),
        ("PREADJUDICADO", "Preadjudicado"),
        ("DISPONIBLE_ADJUDICAR", "Disponible para adjudicar"),
        ("ADJUDICADO", "Adjudicado"),
        ("FRACASADO", "Fracasado"),
        ("DESIERTO", "Desierto"),
        ("DEJADO_SIN_EFECTO", "Dejado sin efecto"),
    ]

    CURRENCY_CHOICES = [
        ("ARS", "Pesos"),
        ("USD", "Dolares"),
        ("EUR", "Euros"),
        ("OTRA", "Otra"),
    ]

    CLASSIFICATION_CHOICES = [
        ("", "Sin clasificar"),
        ("REPUESTO", "Repuesto"),
        ("SUPERVIVENCIA", "Supervivencia"),
        ("SIN_EFECTO", "Desiertos / Sin efecto / Fracasados"),
        ("GRASAS_LUBRICANTES", "Grasas y Lubricantes"),
        ("REPUESTOS_FONDEF", "Repuestos / FONDEF"),
    ]

    CLASSIFICATION_COLORS = {
        "REPUESTO": "#bdd7ee",
        "SUPERVIVENCIA": "#f8cbad",
        "SIN_EFECTO": "#ff0000",
        "GRASAS_LUBRICANTES": "#7030a0",
        "REPUESTOS_FONDEF": "#ffc000",
    }

    CLASSIFICATION_TEXT_COLORS = {
        "SIN_EFECTO": "#ffffff",
        "GRASAS_LUBRICANTES": "#ffffff",
    }

    year = models.PositiveIntegerField(default=2026, verbose_name="Ejercicio / Año")
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="tender_processes",
        verbose_name="Destino requirente",
        blank=True,
        null=True,
    )
    destination = models.ForeignKey(
        ProcurementDestination,
        on_delete=models.PROTECT,
        related_name="tender_processes",
        verbose_name="Destino legado",
        blank=True,
        null=True,
    )
    process_number = models.CharField(max_length=60, verbose_name="Numero de proceso")
    expediente = models.CharField(max_length=120, blank=True, null=True, verbose_name="Expediente")
    name = models.CharField(max_length=300, verbose_name="Nombre del proceso")
    process_type = models.CharField(
        max_length=30,
        choices=PROCESS_TYPE_CHOICES,
        default="PRIVADA",
        verbose_name="Tipo de proceso",
    )
    classification = models.CharField(
        max_length=30,
        choices=CLASSIFICATION_CHOICES,
        blank=True,
        default="",
        verbose_name="Clasificacion",
    )
    opening_date = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de apertura")
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PUBLICADO",
        verbose_name="Estado",
    )
    amount_ars = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Monto en pesos",
    )
    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default="ARS",
        verbose_name="Moneda original",
    )
    foreign_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Monto en moneda extranjera",
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name="Tipo de cambio usado",
    )
    exchange_rate_date = models.DateField(blank=True, null=True, verbose_name="Fecha del tipo de cambio")
    has_oca = models.BooleanField(blank=True, null=True, verbose_name="OCA")
    source = models.CharField(max_length=150, default="COMPRAR.GOB.AR", verbose_name="Fuente")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_tender_processes",
        verbose_name="Creado por",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Proceso licitatorio"
        verbose_name_plural = "Procesos licitatorios"
        ordering = ["-year", "unit__name", "-opening_date", "process_number"]
        unique_together = ("year", "process_number")

    def __str__(self):
        destination_name = self.unit.name if self.unit else (self.destination.code if self.destination else "SIN_UNIDAD")
        return f"{self.process_number} - {destination_name}"

    def save(self, *args, **kwargs):
        if self.process_number:
            self.process_number = self.process_number.upper().strip()
        if self.expediente:
            self.expediente = self.expediente.upper().strip()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("licitaciones:process_list")

    @property
    def operational_group(self):
        if self.status == "ADJUDICADO":
            return "ADJUDICADO"
        if self.status in ["PREADJUDICADO", "DISPONIBLE_ADJUDICAR"]:
            return "DISPONIBLE"
        if self.status in ["FRACASADO", "DESIERTO", "DEJADO_SIN_EFECTO"]:
            return "SIN_EFECTO"
        return "EN_PROCESO"

    @property
    def classification_color(self):
        return self.CLASSIFICATION_COLORS.get(self.classification, "#e5e7eb")

    @property
    def classification_text_color(self):
        return self.CLASSIFICATION_TEXT_COLORS.get(self.classification, "#111827")
