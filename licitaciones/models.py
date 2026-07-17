from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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


class ForeignTenderProcess(models.Model):
    PROCESS_TYPE_CHOICES = TenderProcess.PROCESS_TYPE_CHOICES
    CURRENCY_CHOICES = [
        ("USD", "Dolares"),
        ("EUR", "Euros"),
        ("ARS", "Pesos"),
        ("OTRA", "Otra"),
    ]
    STATUS_CHOICES = [
        ("INICIADO", "Iniciado"),
        ("EN_EVALUACION", "En evaluacion"),
        ("DICTAMEN_EMITIDO", "Dictamen emitido"),
        ("DISPONIBLE_PARA_ADJUDICAR", "Disponible para adjudicar"),
        ("PENDIENTE_ASIGNACION", "Pendiente de asignacion"),
        ("ADJUDICADO", "Adjudicado"),
        ("EN_RECEPCION", "En recepcion"),
        ("FINALIZADO", "Finalizado"),
        ("FRACASADO", "Fracasado"),
        ("DEJADO_SIN_EFECTO", "Dejado sin efecto"),
    ]
    DELIVERY_DAY_TYPE_CHOICES = [
        ("CORRIDOS", "Dias corridos"),
        ("HABILES", "Dias habiles (lunes a viernes)"),
    ]

    year = models.PositiveIntegerField(default=2026, verbose_name="Ejercicio / Año")
    process_number = models.CharField(max_length=60, verbose_name="Licitacion")
    expediente = models.CharField(max_length=150, blank=True, verbose_name="Expediente")
    process_type = models.CharField(
        max_length=30,
        choices=PROCESS_TYPE_CHOICES,
        default="PUBLICA",
        verbose_name="Tipo de proceso",
    )
    has_oca = models.BooleanField(blank=True, null=True, verbose_name="OCA")
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="INICIADO",
        verbose_name="Estado",
    )
    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default="USD",
        verbose_name="Moneda unica del proceso",
    )
    custom_currency = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Nombre de otra moneda",
    )
    evaluation_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Monto del dictamen de evaluacion",
    )
    awarded_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Monto asignado en adjudicacion",
    )
    allocation_gfh = models.TextField(blank=True, verbose_name="GFH de asignacion")
    incoterm = models.CharField(max_length=30, blank=True, verbose_name="Incoterm")
    oca_expiration = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Fecha de vencimiento OCA",
        help_text="Admite una fecha o una aclaracion, por ejemplo 'No aplica'.",
    )
    delivery_term_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Cantidad de dias del plazo de entrega",
    )
    delivery_term_day_type = models.CharField(
        max_length=10,
        choices=DELIVERY_DAY_TYPE_CHOICES,
        blank=True,
        verbose_name="Tipo de dias del plazo de entrega",
    )
    sp = models.CharField(max_length=30, blank=True, verbose_name="SP")
    saimb_number = models.CharField(max_length=30, blank=True, verbose_name="SAIMB Nro.")
    received = models.BooleanField(blank=True, null=True, verbose_name="Recibido")
    notes = models.TextField(blank=True, verbose_name="Observaciones generales")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_foreign_tender_processes",
        verbose_name="Creado por",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Licitacion en el exterior"
        verbose_name_plural = "Licitaciones en el exterior"
        ordering = ["-year", "process_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "process_number"],
                name="unique_foreign_tender_year_number",
            )
        ]

    def __str__(self):
        return f"{self.process_number} ({self.year})"

    def clean(self):
        errors = {}
        if self.currency == "OTRA" and not self.custom_currency.strip():
            errors["custom_currency"] = "Indique el nombre de la moneda."
        if self.currency != "OTRA":
            self.custom_currency = ""
        for field_name in ("evaluation_amount", "awarded_amount"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                errors[field_name] = "El monto no puede ser negativo."
        if self.has_oca is False:
            self.oca_expiration = ""
            self.delivery_term_days = None
            self.delivery_term_day_type = ""

        expiration_date = self.oca_expiration_date
        has_delivery_term = (
            self.delivery_term_days is not None or bool(self.delivery_term_day_type)
        )
        if expiration_date:
            if not self.delivery_term_days:
                errors["delivery_term_days"] = "Indique una cantidad de dias mayor que cero."
            if not self.delivery_term_day_type:
                errors["delivery_term_day_type"] = "Indique si son dias habiles o corridos."
        elif has_delivery_term:
            errors["oca_expiration"] = (
                "Para calcular el plazo de entrega, ingrese una fecha valida en formato DD/MM/AAAA."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.process_number:
            self.process_number = self.process_number.upper().strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("licitaciones:foreign_detail", kwargs={"pk": self.pk})

    @property
    def currency_label(self):
        if self.currency == "OTRA":
            return self.custom_currency.upper()
        return self.get_currency_display()

    @property
    def currency_symbol(self):
        return {"USD": "USD", "EUR": "EUR", "ARS": "$"}.get(
            self.currency,
            self.custom_currency.upper() or "MON",
        )

    @property
    def requested_amount(self):
        return sum(
            (requirement.requested_amount for requirement in self.requirements.all()),
            start=0,
        )

    @property
    def remaining_amount(self):
        if self.evaluation_amount is None or self.awarded_amount is None:
            return None
        return self.evaluation_amount - self.awarded_amount

    @property
    def oca_expiration_date(self):
        value = (self.oca_expiration or "").strip()
        for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        return None

    @property
    def delivery_due_date(self):
        base_date = self.oca_expiration_date
        days = self.delivery_term_days
        if not base_date or not days or not self.delivery_term_day_type:
            return None
        if self.delivery_term_day_type == "CORRIDOS":
            return base_date + timedelta(days=days)

        due_date = base_date
        elapsed = 0
        while elapsed < days:
            due_date += timedelta(days=1)
            if due_date.weekday() < 5:
                elapsed += 1
        return due_date

    @property
    def latest_update(self):
        return self.updates.order_by("-event_date", "-created_at").first()


class ForeignTenderRequirement(models.Model):
    process = models.ForeignKey(
        ForeignTenderProcess,
        on_delete=models.CASCADE,
        related_name="requirements",
        verbose_name="Licitacion",
    )
    requirement_number = models.CharField(max_length=30, verbose_name="REQ")
    requested_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Monto del requerimiento",
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="foreign_tender_requirements",
        verbose_name="Taller / destino",
        blank=True,
        null=True,
    )
    workshop = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Taller alternativo",
        help_text="Utilizar solo si el taller no existe entre las unidades.",
    )
    aircraft = models.CharField(max_length=100, blank=True, verbose_name="Aeronave / sistema")
    description = models.TextField(verbose_name="Descripcion")
    notes = models.TextField(blank=True, verbose_name="Observaciones")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Requerimiento exterior"
        verbose_name_plural = "Requerimientos exteriores"
        ordering = ["requirement_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["process", "requirement_number"],
                name="unique_foreign_tender_requirement",
            )
        ]

    def __str__(self):
        return f"REQ {self.requirement_number} - {self.process.process_number}"

    def clean(self):
        errors = {}
        if self.requested_amount is not None and self.requested_amount < 0:
            errors["requested_amount"] = "El monto no puede ser negativo."
        if not self.unit and not self.workshop.strip():
            errors["workshop"] = "Seleccione una unidad o indique el taller."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.requirement_number:
            self.requirement_number = self.requirement_number.upper().strip()
        if self.workshop:
            self.workshop = self.workshop.upper().strip()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def workshop_label(self):
        return self.unit.name if self.unit else self.workshop


class ForeignTenderPurchaseOrder(models.Model):
    process = models.ForeignKey(
        ForeignTenderProcess,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
        verbose_name="Licitacion",
    )
    order_number = models.CharField(max_length=40, verbose_name="Nro. OC / OCA")
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Monto OC / OCA",
    )
    issue_date = models.DateField(blank=True, null=True, verbose_name="Fecha de emision")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orden de compra exterior"
        verbose_name_plural = "Ordenes de compra exteriores"
        ordering = ["issue_date", "order_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["process", "order_number"],
                name="unique_foreign_purchase_order",
            )
        ]

    def __str__(self):
        return f"{self.order_number} - {self.process.process_number}"

    def clean(self):
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": "El monto no puede ser negativo."})

    def save(self, *args, **kwargs):
        if self.order_number:
            self.order_number = self.order_number.upper().strip()
        self.full_clean()
        super().save(*args, **kwargs)


class ForeignTenderUpdate(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("GDE", "GDE"),
        ("GFH", "GFH"),
        ("NOTA", "Nota"),
        ("DISPOSICION", "Disposicion"),
        ("INFORME", "Informe"),
        ("OTRO", "Otro"),
    ]

    process = models.ForeignKey(
        ForeignTenderProcess,
        on_delete=models.CASCADE,
        related_name="updates",
        verbose_name="Licitacion",
    )
    event_date = models.DateField(verbose_name="Fecha")
    organization = models.CharField(max_length=120, blank=True, verbose_name="Organismo")
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        default="GFH",
        verbose_name="Tipo de documento",
    )
    document_number = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Numero de documento",
    )
    description = models.TextField(verbose_name="Novedad / estado informado")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_foreign_tender_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Novedad de licitacion exterior"
        verbose_name_plural = "Novedades de licitaciones exteriores"
        ordering = ["-event_date", "-created_at"]

    def __str__(self):
        return f"{self.event_date} - {self.process.process_number}"

    def save(self, *args, **kwargs):
        if self.organization:
            self.organization = self.organization.upper().strip()
        if self.document_number:
            self.document_number = self.document_number.upper().strip()
        super().save(*args, **kwargs)


class TenderStage(models.Model):
    STATUS_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("EN_CURSO", "En curso"),
        ("COMPLETADA", "Completada"),
        ("OMITIDA", "Omitida"),
    ]

    tender = models.ForeignKey(
        TenderProcess,
        on_delete=models.CASCADE,
        related_name="stages",
        verbose_name="Licitacion",
    )
    stage_number = models.PositiveIntegerField(verbose_name="Numero de etapa")
    name = models.CharField(max_length=150, verbose_name="Nombre de etapa")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDIENTE", verbose_name="Estado")
    estimated_date = models.DateField(blank=True, null=True, verbose_name="Fecha estimada")
    start_date = models.DateField(blank=True, null=True, verbose_name="Fecha de inicio real")
    end_date = models.DateField(blank=True, null=True, verbose_name="Fecha de fin real")
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="managed_tender_stages",
        verbose_name="Usuario responsable",
    )
    notes = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Etapa de licitacion"
        verbose_name_plural = "Etapas de licitacion"
        ordering = ["stage_number"]
        unique_together = ("tender", "stage_number")

    def __str__(self):
        return f"Etapa {self.stage_number}: {self.name} - {self.tender.process_number}"


@receiver(post_save, sender=TenderProcess)
def create_tender_stages(sender, instance, created, **kwargs):
    if created:
        default_stages = [
            "Solicitud de Contratacion",
            "Afectacion Preventiva",
            "Elaboracion de Pliego",
            "Aprobacion de Pliego",
            "Llamado y Publicacion",
            "Consultas y Circulares",
            "Acto de Apertura",
            "Analisis de Ofertas",
            "Dictamen de Evaluacion",
            "Impugnaciones",
            "Adjudicacion",
            "Notificacion a Oferentes",
            "Firma de Contrato / Orden de Compra",
        ]
        stages_to_create = [
            TenderStage(
                tender=instance,
                stage_number=idx,
                name=name,
                status="PENDIENTE"
            )
            for idx, name in enumerate(default_stages, start=1)
        ]
        TenderStage.objects.bulk_create(stages_to_create)

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"
