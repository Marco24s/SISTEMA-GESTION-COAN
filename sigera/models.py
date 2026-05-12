from django.db import models
from core.models import CustomUser, Unit

class ClothingType(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nombre de la Prenda", help_text="Ej: Mameluco de Vuelo, Borceguíes")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    nato_stock_number = models.CharField(max_length=100, verbose_name="N.N.E. / N.S.N.", blank=True, null=True)
    shelf_life_months = models.PositiveIntegerField(verbose_name="Vida Útil Teórica (Meses)", help_text="Tiempo estimado de uso antes de requerir reemplazo")
    must_be_returned = models.BooleanField(default=True, verbose_name="¿Debe ser devuelta?", help_text="Indica si esta prenda debe ser devuelta al pañol cuando el personal la cese de usar.")

    class Meta:
        verbose_name = "Tipo de Prenda"
        verbose_name_plural = "Tipos de Prendas"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name: self.name = self.name.upper()
        if self.description: self.description = self.description.upper()
        if self.nato_stock_number: self.nato_stock_number = self.nato_stock_number.upper()
        super().save(*args, **kwargs)

class ClothingSize(models.Model):
    clothing_type = models.ForeignKey(ClothingType, on_delete=models.CASCADE, related_name="sizes", verbose_name="Prenda")
    size = models.CharField(max_length=50, verbose_name="Talle", help_text="Ej: S, M, L, XL, 42, 44")
    
    class Meta:
        verbose_name = "Talle de Prenda"
        verbose_name_plural = "Talles de Prendas"
        unique_together = ('clothing_type', 'size')

    def __str__(self):
        return f"{self.clothing_type.name} - Talle {self.size}"

    def save(self, *args, **kwargs):
        if self.size: self.size = self.size.upper()
        super().save(*args, **kwargs)

class ClothingBatch(models.Model):
    clothing_size = models.ForeignKey(ClothingSize, on_delete=models.CASCADE, related_name="batches", verbose_name="Prenda y Talle")
    reception_date = models.DateField(verbose_name="Fecha de Recepción")
    initial_quantity = models.PositiveIntegerField(verbose_name="Cantidad Recibida Inicial")
    available_quantity = models.PositiveIntegerField(verbose_name="Cantidad Disponible en Pañol")
    provider = models.CharField(max_length=150, blank=True, null=True, verbose_name="Proveedor")
    purchase_order = models.CharField(max_length=100, blank=True, null=True, verbose_name="Orden de Compra / Remito / Factura")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Precio Unitario ($)")
    
    class Meta:
        verbose_name = "Lote/Ingreso de Ropa"
        verbose_name_plural = "Lotes/Ingresos de Ropa"
        ordering = ['-reception_date']

    def __str__(self):
        return f"Ingreso {self.reception_date} - {self.clothing_size} ({self.available_quantity} disp.)"

    def save(self, *args, **kwargs):
        if self.provider: self.provider = self.provider.upper()
        if self.purchase_order: self.purchase_order = self.purchase_order.upper()
        super().save(*args, **kwargs)

class Personnel(models.Model):
    RANK_CHOICES = [
        ('CAPITAN_NAVIO', 'Capitán de Navío'),
        ('CAPITAN_FRAGATA', 'Capitán de Fragata'),
        ('CAPITAN_CORBETA', 'Capitán de Corbeta'),
        ('TENIENTE_NAVIO', 'Teniente de Navío'),
        ('TENIENTE_FRAGATA', 'Teniente de Fragata'),
        ('TENIENTE_CORBETA', 'Teniente de Corbeta'),
        ('GUARDIAMARINA', 'Guardiamarina'),
        ('SUBOFICIAL_MAYOR', 'Suboficial Mayor'),
        ('SUBOFICIAL_PRINCIPAL', 'Suboficial Principal'),
        ('SUBOFICIAL_PRIMERO', 'Suboficial Primero'),
        ('SUBOFICIAL_SEGUNDO', 'Suboficial Segundo'),
        ('CABO_PRINCIPAL', 'Cabo Principal'),
        ('CABO_PRIMERO', 'Cabo Primero'),
        ('CABO_SEGUNDO', 'Cabo Segundo'),
        ('MARINERO_PRIMERO', 'Marinero Primero'),
        ('MARINERO_SEGUNDO', 'Marinero Segundo'),
        ('AGENTE_CIVIL', 'Agente Civil'),
    ]
    first_name = models.CharField(max_length=100, verbose_name="Nombres")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    dni = models.CharField(max_length=20, unique=True, verbose_name="Matrícula de Revista")
    rank = models.CharField(max_length=20, choices=RANK_CHOICES, verbose_name="Jerarquía/Rango")
    assigned_unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Unidad Asignada")
    
    class Meta:
        verbose_name = "Personal"
        verbose_name_plural = "Personal"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.get_rank_display()})"

    def save(self, *args, **kwargs):
        if self.first_name: self.first_name = self.first_name.upper()
        if self.last_name: self.last_name = self.last_name.upper()
        if self.dni: self.dni = self.dni.upper()
        super().save(*args, **kwargs)

class ClothingAssignment(models.Model):
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name="assignments", verbose_name="Personal")
    batch = models.ForeignKey(ClothingBatch, on_delete=models.PROTECT, related_name="assignments", verbose_name="Del Ingreso (Lote)")
    assigned_date = models.DateField(auto_now_add=True, verbose_name="Fecha de Entrega")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Cantidad Entregada")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    returned = models.BooleanField(default=False, verbose_name="¿Devuelto al Pañol?")
    return_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Devolución")
    issued_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, verbose_name="Entregado Por")

    class Meta:
        verbose_name = "Entrega de Ropa"
        verbose_name_plural = "Entregas de Ropa"
        ordering = ['-assigned_date']

    def __str__(self):
        return f"Entrega a {self.personnel} - {self.batch.clothing_size} ({self.assigned_date})"

    def save(self, *args, **kwargs):
        if self.notes: self.notes = self.notes.upper()
        super().save(*args, **kwargs)

    @property
    def expiration_date(self):
        """
        Calcula la fecha de vencimiento basada en la vida útil teórica de la prenda.
        """
        if not self.assigned_date:
            return None
        from dateutil.relativedelta import relativedelta
        months = self.batch.clothing_size.clothing_type.shelf_life_months
        return self.assigned_date + relativedelta(months=months)

    @property
    def is_expired(self):
        """
        Indica si el cargo ha superado su vida útil teórica.
        """
        exp = self.expiration_date
        if not exp:
            return False
        from datetime import date
        return exp <= date.today()


class StockThreshold(models.Model):
    name = models.CharField(max_length=50, verbose_name="Nombre de la Categoría", help_text="Ej: Suficiente, OK, Crítico")
    min_quantity = models.PositiveIntegerField(verbose_name="Cantidad Mínima", help_text="Incluye esta cantidad")
    max_quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name="Cantidad Máxima", help_text="Hasta esta cantidad (deja vacío para ilimitado)")
    color = models.CharField(max_length=20, choices=[
        ('danger', 'Rojo (Peligro)'),
        ('warning', 'Naranja (Advertencia)'),
        ('info', 'Azul (Información)'),
        ('success', 'Verde (Éxito)'),
        ('secondary', 'Gris (Secundario)'),
    ], default='secondary', verbose_name="Color del Badge")
    icon = models.CharField(max_length=50, default='fa-circle', verbose_name="Ícono de FontAwesome", help_text="Ej: fa-circle-check, fa-triangle-exclamation")
    order = models.PositiveIntegerField(default=0, verbose_name="Orden de Aparición")

    class Meta:
        verbose_name = "Umbral de Stock"
        verbose_name_plural = "Umbrales de Stock"
        ordering = ['order']

    def __str__(self):
        if self.max_quantity:
            return f"{self.name} ({self.min_quantity}-{self.max_quantity})"
        else:
            return f"{self.name} ({self.min_quantity}+)"

    def matches(self, quantity):
        if quantity is None:
            quantity = 0
        if self.max_quantity is not None:
            return self.min_quantity <= quantity <= self.max_quantity
        else:
            return quantity >= self.min_quantity
