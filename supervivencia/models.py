from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import Unit


class SurvivalMedium(models.Model):
    MEDIUM_TYPE_CHOICES = [
        ("AERONAVE", "Aeronave"),
        ("BALSA", "Balsa"),
        ("CHALECO", "Chaleco"),
        ("EQUIPO", "Equipo de supervivencia"),
        ("CONTENEDOR", "Contenedor"),
        ("OTRO", "Otro"),
    ]

    identifier = models.CharField(max_length=80, unique=True, verbose_name="Identificacion")
    name = models.CharField(max_length=150, verbose_name="Medio")
    medium_type = models.CharField(
        max_length=30,
        choices=MEDIUM_TYPE_CHOICES,
        default="AERONAVE",
        verbose_name="Tipo de medio",
    )
    model = models.CharField(max_length=120, blank=True, null=True, verbose_name="Modelo")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Unidad")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Medio de supervivencia"
        verbose_name_plural = "Medios de supervivencia"
        ordering = ["identifier"]

    def __str__(self):
        return f"{self.identifier} - {self.name}"

    def save(self, *args, **kwargs):
        if self.identifier:
            self.identifier = self.identifier.upper().strip()
        if self.name:
            self.name = self.name.upper().strip()
        if self.model:
            self.model = self.model.upper().strip()
        if self.notes:
            self.notes = self.notes.upper().strip()
        super().save(*args, **kwargs)


class PyrotechnicCatalogItem(models.Model):
    nomenclature = models.CharField(max_length=150, verbose_name="Nomenclatura")
    system = models.CharField(max_length=150, verbose_name="Sistema")
    part_number = models.CharField(max_length=80, unique=True, blank=True, null=True, verbose_name="N° / Parte")
    nsn = models.CharField(max_length=80, blank=True, null=True, verbose_name="N.S.N")
    alternate_part_number = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name="Numero de parte alternativo",
    )
    theoretical_life_months = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Vida util teorica (meses)",
    )
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Elemento de pirotecnia"
        verbose_name_plural = "Catalogo de pirotecnia"
        ordering = ["nomenclature"]

    def __str__(self):
        return f"{self.nomenclature} - {self.system}"

    def clean(self):
        super().clean()
        if self.part_number:
            self.part_number = self.part_number.upper().strip()
        else:
            self.part_number = None

    def save(self, *args, **kwargs):
        if self.nomenclature:
            self.nomenclature = self.nomenclature.upper().strip()
        if self.system:
            self.system = self.system.upper().strip()
        if self.part_number:
            self.part_number = self.part_number.upper().strip()
        else:
            self.part_number = None
        if self.nsn:
            self.nsn = self.nsn.upper().strip()
        if self.alternate_part_number:
            self.alternate_part_number = self.alternate_part_number.upper().strip()
        if self.description:
            self.description = self.description.upper().strip()
        super().save(*args, **kwargs)

    @property
    def life_rules_summary(self):
        rules = list(self.life_rules.all())
        if rules:
            return " / ".join(
                f"{rule.get_situation_display()}: {rule.duration_value} {rule.get_duration_unit_display().lower()}"
                for rule in rules
            )
        if self.theoretical_life_months:
            return f"General: {self.theoretical_life_months} meses"
        return "-"


class PyrotechnicCatalogLifeRule(models.Model):
    SITUATION_CHOICES = [
        ("GENERAL", "General / unica"),
        ("ORIGINAL_PACKAGING", "Envase original"),
        ("STORAGE", "En deposito"),
        ("INSTALLED", "Instalado"),
    ]

    UNIT_CHOICES = [
        ("MONTHS", "Meses"),
        ("YEARS", "Años"),
    ]

    catalog_item = models.ForeignKey(
        PyrotechnicCatalogItem,
        on_delete=models.CASCADE,
        related_name="life_rules",
        verbose_name="Elemento de catalogo",
    )
    situation = models.CharField(max_length=30, choices=SITUATION_CHOICES, verbose_name="Situacion")
    duration_value = models.PositiveIntegerField(verbose_name="Vida util")
    duration_unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="YEARS", verbose_name="Unidad")
    notes = models.CharField(max_length=180, blank=True, null=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Regla de vida util"
        verbose_name_plural = "Reglas de vida util"
        ordering = ["catalog_item__nomenclature", "situation"]
        unique_together = ("catalog_item", "situation")

    def __str__(self):
        return f"{self.catalog_item.nomenclature} - {self.get_situation_display()}: {self.duration_value} {self.get_duration_unit_display()}"

    @property
    def duration_months(self):
        if self.duration_unit == "YEARS":
            return self.duration_value * 12
        return self.duration_value

    def save(self, *args, **kwargs):
        if self.notes:
            self.notes = self.notes.upper().strip()
        super().save(*args, **kwargs)


class PyrotechnicStorageLocation(models.Model):
    LOCATION_TYPE_CHOICES = [
        ("POLVORIN", "Polvorin"),
        ("PANOL", "Pañol"),
        ("DEPOSITO", "Deposito"),
        ("TALLER", "Taller"),
        ("OTRO", "Otro"),
    ]

    code = models.CharField(max_length=50, verbose_name="Destino")
    name = models.CharField(max_length=150, verbose_name="Ubicacion")
    location_type = models.CharField(
        max_length=30,
        choices=LOCATION_TYPE_CHOICES,
        default="DEPOSITO",
        verbose_name="Tipo de ubicacion",
    )
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Unidad")
    is_restricted = models.BooleanField(default=True, verbose_name="Zona restringida")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Ubicacion pirotecnica"
        verbose_name_plural = "Ubicaciones pirotecnicas"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "name", "location_type", "unit"],
                name="unique_storage_location_combination"
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper().strip()
        if self.name:
            self.name = self.name.upper().strip()
        if self.notes:
            self.notes = self.notes.upper().strip()
        super().save(*args, **kwargs)


class PyrotechnicPhysicalItem(models.Model):
    CONDITION_CHOICES = [
        ("SERVICEABLE", "Operativo"),
        ("UNSERVICEABLE", "No operativo"),
        ("QUARANTINE", "En cuarentena"),
        ("BLOCKED", "Bloqueado"),
    ]
    STATUS_CHOICES = [
        ("STOCK", "En deposito"),
        ("RESERVED", "Reservado"),
        ("INSTALLED", "Montado"),
        ("REMOVED", "Removido"),
        ("CONSUMED", "Consumido"),
        ("DISCARDED", "Dado de baja"),
    ]

    catalog_item = models.ForeignKey(
        PyrotechnicCatalogItem,
        on_delete=models.PROTECT,
        related_name="physical_items",
        verbose_name="Elemento de catalogo",
    )
    serial_number = models.CharField(
        max_length=120,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Numero de serie",
    )
    lot_number = models.CharField(max_length=120, blank=True, null=True, verbose_name="Lote / partida")
    lot_quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad del lote",
    )
    manufacturer = models.CharField(max_length=150, blank=True, null=True, verbose_name="Fabricante")
    manufacture_date = models.DateField(blank=True, null=True, verbose_name="Fecha de fabricacion")
    expiration_date = models.DateField(verbose_name="Fecha de vencimiento")
    condition = models.CharField(
        max_length=30,
        choices=CONDITION_CHOICES,
        default="SERVICEABLE",
        verbose_name="Condicion",
    )
    operational_status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="STOCK",
        verbose_name="Estado operativo",
    )
    current_location = models.CharField(
        max_length=180,
        verbose_name="Ubicacion actual",
        blank=True,
        help_text="Deposito, pañol, polvorin o referencia actual. No debe quedar vacio.",
    )
    current_storage_location = models.ForeignKey(
        PyrotechnicStorageLocation,
        on_delete=models.SET_NULL,
        related_name="physical_items",
        verbose_name="Ubicacion controlada",
        blank=True,
        null=True,
    )
    certificate_reference = models.CharField(
        max_length=180,
        blank=True,
        null=True,
        verbose_name="Certificado / documento",
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_pyrotechnic_physical_items",
        verbose_name="Creado por",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Material pirotecnico fisico"
        verbose_name_plural = "Material pirotecnico fisico"
        ordering = ["expiration_date", "catalog_item__nomenclature", "serial_number", "lot_number"]
        indexes = [
            models.Index(fields=["expiration_date"]),
            models.Index(fields=["condition"]),
            models.Index(fields=["operational_status"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["current_storage_location"]),
        ]

    def __str__(self):
        identity = self.serial_number or self.lot_number or f"ID {self.pk}"
        return f"{self.catalog_item.nomenclature} - {identity}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return self.expiration_date <= timezone.localdate()

    def save(self, *args, **kwargs):
        if self.serial_number:
            self.serial_number = self.serial_number.upper().strip()
        else:
            self.serial_number = None
        if self.lot_number:
            self.lot_number = self.lot_number.upper().strip()
        if self.manufacturer:
            self.manufacturer = self.manufacturer.upper().strip()
        if self.current_storage_location:
            self.current_location = str(self.current_storage_location)
        if self.current_location:
            self.current_location = self.current_location.upper().strip()
        if self.certificate_reference:
            self.certificate_reference = self.certificate_reference.upper().strip()
        if self.notes:
            self.notes = self.notes.upper().strip()
        super().save(*args, **kwargs)


class PyrotechnicAssignment(models.Model):
    medium = models.ForeignKey(
        SurvivalMedium,
        on_delete=models.PROTECT,
        related_name="pyrotechnic_assignments",
        verbose_name="Medio",
    )
    physical_item = models.ForeignKey(
        PyrotechnicPhysicalItem,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="Material fisico",
    )
    installed_at = models.DateField(default=timezone.localdate, verbose_name="Fecha de montaje / asignacion")
    position = models.CharField(max_length=120, blank=True, null=True, verbose_name="Posicion / ubicacion en el medio")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    is_active = models.BooleanField(default=True, verbose_name="Activo / montado")
    removed_at = models.DateField(blank=True, null=True, verbose_name="Fecha de retiro")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_pyrotechnic_assignments",
        verbose_name="Creado por",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Asignacion de pirotecnia"
        verbose_name_plural = "Asignaciones de pirotecnia"
        ordering = ["medium__identifier", "-is_active", "physical_item__expiration_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["physical_item"],
                condition=models.Q(is_active=True),
                name="unique_active_pyrotechnic_assignment",
            )
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["installed_at"]),
            models.Index(fields=["removed_at"]),
        ]

    def __str__(self):
        return f"{self.medium} - {self.physical_item}"

    def save(self, *args, **kwargs):
        if self.position:
            self.position = self.position.upper().strip()
        if self.notes:
            self.notes = self.notes.upper().strip()
        if not self.is_active and not self.removed_at:
            self.removed_at = timezone.localdate()
        super().save(*args, **kwargs)


class PyrotechnicMovement(models.Model):
    MOVEMENT_TYPE_CHOICES = [
        ("REGISTERED", "Alta de material"),
        ("INSTALLED", "Montado / asignado"),
        ("REMOVED", "Retirado"),
        ("LOCATION_CHANGE", "Cambio de ubicacion"),
        ("STATUS_CHANGE", "Cambio de estado"),
        ("DISCARDED", "Baja"),
        ("NOTE", "Nota"),
    ]

    physical_item = models.ForeignKey(
        PyrotechnicPhysicalItem,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="Material fisico",
    )
    medium = models.ForeignKey(
        SurvivalMedium,
        on_delete=models.SET_NULL,
        related_name="pyrotechnic_movements",
        verbose_name="Medio",
        blank=True,
        null=True,
    )
    assignment = models.ForeignKey(
        PyrotechnicAssignment,
        on_delete=models.SET_NULL,
        related_name="movements",
        verbose_name="Asignacion",
        blank=True,
        null=True,
    )
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPE_CHOICES, verbose_name="Movimiento")
    movement_date = models.DateField(default=timezone.localdate, verbose_name="Fecha")
    from_reference = models.CharField(max_length=180, blank=True, null=True, verbose_name="Desde")
    to_reference = models.CharField(max_length=180, blank=True, null=True, verbose_name="Hacia")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_pyrotechnic_movements",
        verbose_name="Creado por",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")

    class Meta:
        verbose_name = "Movimiento de pirotecnia"
        verbose_name_plural = "Movimientos de pirotecnia"
        ordering = ["-movement_date", "-created_at"]
        indexes = [
            models.Index(fields=["movement_type"]),
            models.Index(fields=["movement_date"]),
            models.Index(fields=["physical_item"]),
            models.Index(fields=["medium"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.physical_item}"

    def save(self, *args, **kwargs):
        if self.from_reference:
            self.from_reference = self.from_reference.upper().strip()
        if self.to_reference:
            self.to_reference = self.to_reference.upper().strip()
        if self.notes:
            self.notes = self.notes.upper().strip()
        super().save(*args, **kwargs)


class SupervivenciaDeletionLog(models.Model):
    object_type = models.CharField(max_length=80, verbose_name="Tipo de objeto")
    object_id = models.CharField(max_length=80, verbose_name="ID eliminado")
    object_repr = models.CharField(max_length=300, verbose_name="Registro eliminado")
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="supervivencia_deletion_logs",
        verbose_name="Eliminado por",
        blank=True,
        null=True,
    )
    deleted_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de eliminacion")

    class Meta:
        verbose_name = "Registro de borrado"
        verbose_name_plural = "Registros de borrado"
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"{self.object_type} - {self.object_repr}"


class Aircraft(models.Model):
    code = models.CharField(max_length=30, unique=True, verbose_name="Codigo")
    name = models.CharField(max_length=120, verbose_name="Aeronave")
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Aeronave"
        verbose_name_plural = "Aeronaves"
        ordering = ["code"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper().strip()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)


class AircraftVariant(models.Model):
    aircraft = models.ForeignKey(
        Aircraft,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="Aeronave",
    )
    name = models.CharField(max_length=120, verbose_name="Modelo")
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Modelo de aeronave"
        verbose_name_plural = "Modelos de aeronave"
        ordering = ["aircraft__code", "name"]
        unique_together = ("aircraft", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.upper().strip()
        super().save(*args, **kwargs)


class PyrotechnicItemType(models.Model):
    code = models.CharField(max_length=150, unique=True, verbose_name="NOMENCLATURA")
    name = models.CharField(max_length=150, verbose_name="SISTEMA")
    part_number = models.CharField(max_length=80, blank=True, null=True, verbose_name="N° / PARTE")
    nsn = models.CharField(max_length=80, blank=True, null=True, verbose_name="N.S.N")
    alternate_part_number = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name="NUMERO DE PARTE ALTERNATIVO",
    )
    description = models.TextField(blank=True, null=True, verbose_name="Descripcion")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Tipo de elemento pirotecnico"
        verbose_name_plural = "Tipos de elementos pirotecnicos"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper().strip()
        if self.name:
            self.name = self.name.upper().strip()
        if self.part_number:
            self.part_number = self.part_number.upper().strip()
        if self.nsn:
            self.nsn = self.nsn.upper().strip()
        if self.alternate_part_number:
            self.alternate_part_number = self.alternate_part_number.upper().strip()
        super().save(*args, **kwargs)


class PyrotechnicRequirement(models.Model):
    STATUS_CHOICES = [
        ("SIN_ALARMA", "Sin alarma"),
        ("INICIO_GESTION", "Inicio de gestion"),
        ("ADQUISICION", "Adquisicion"),
        ("SIN_GESTION", "Sin gestion de compra"),
        ("ENTREGADO", "Entregado / cerrado"),
        ("CANCELADO", "Cancelado"),
    ]

    MONTH_CHOICES = [
        (1, "Enero"),
        (2, "Febrero"),
        (3, "Marzo"),
        (4, "Abril"),
        (5, "Mayo"),
        (6, "Junio"),
        (7, "Julio"),
        (8, "Agosto"),
        (9, "Septiembre"),
        (10, "Octubre"),
        (11, "Noviembre"),
        (12, "Diciembre"),
    ]

    aircraft = models.ForeignKey(
        Aircraft,
        on_delete=models.PROTECT,
        related_name="pyrotechnic_requirements",
        verbose_name="Aeronave",
    )
    variant = models.ForeignKey(
        AircraftVariant,
        on_delete=models.PROTECT,
        related_name="pyrotechnic_requirements",
        verbose_name="Modelo",
        blank=True,
        null=True,
    )
    item_type = models.ForeignKey(
        PyrotechnicItemType,
        on_delete=models.PROTECT,
        related_name="requirements",
        verbose_name="Tipo de elemento",
    )
    year = models.PositiveIntegerField(default=2026, verbose_name="Año")
    month = models.PositiveSmallIntegerField(
        choices=MONTH_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Mes",
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Cantidad")
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="SIN_ALARMA",
        verbose_name="Estado",
    )
    tender_process = models.ForeignKey(
        "licitaciones.TenderProcess",
        on_delete=models.SET_NULL,
        related_name="pyrotechnic_requirements",
        verbose_name="Proceso licitatorio asociado",
        blank=True,
        null=True,
    )
    reference = models.CharField(max_length=180, blank=True, null=True, verbose_name="Referencia documental")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_pyrotechnic_requirements",
        verbose_name="Creado por",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")

    class Meta:
        verbose_name = "Necesidad de supervivencia / pirotecnia"
        verbose_name_plural = "Necesidades de supervivencia / pirotecnia"
        ordering = ["year", "month", "aircraft__code", "variant__name", "item_type__code"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        variant = f" / {self.variant.name}" if self.variant else ""
        return f"{self.aircraft.code}{variant} - {self.item_type.code} - {self.month:02d}/{self.year}"

    def get_absolute_url(self):
        return reverse("supervivencia:dashboard")


class PyrotechnicRequirementNote(models.Model):
    requirement = models.ForeignKey(
        PyrotechnicRequirement,
        on_delete=models.CASCADE,
        related_name="history_notes",
        verbose_name="Necesidad",
    )
    note_date = models.DateField(verbose_name="Fecha")
    text = models.TextField(verbose_name="Novedad")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_pyrotechnic_notes",
        verbose_name="Creado por",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")

    class Meta:
        verbose_name = "Novedad de supervivencia / pirotecnia"
        verbose_name_plural = "Novedades de supervivencia / pirotecnia"
        ordering = ["-note_date", "-created_at"]

    def __str__(self):
        return f"{self.requirement} - {self.note_date:%d/%m/%Y}"
