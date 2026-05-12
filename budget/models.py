from django.db import models
from core.models import Unit, CustomUser

class InsufficientFundsError(Exception):
    """Excepción lanzada cuando no hay saldo disponible en el techo presupuestario."""
    pass

class BudgetFiscalYear(models.Model):
    year = models.PositiveIntegerField(unique=True, verbose_name="Año / Ejercicio")
    status = models.CharField(max_length=10, choices=[('OPEN', 'Abierto'), ('CLOSED', 'Cerrado')], default='OPEN', verbose_name="Estado")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    class Meta: verbose_name = "Ejercicio Económico"; verbose_name_plural = "Ejercicios Económicos"; ordering = ['-year']
    def __str__(self): return f"Ejercicio {self.year} ({self.get_status_display()})"

class BudgetFF(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name="Código FF")
    name = models.CharField(max_length=100, verbose_name="Descripción FF", blank=True)
    class Meta: verbose_name = "Fuente"; verbose_name_plural = "Fuentes"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code

class BudgetCreditType(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Código")
    name = models.CharField(max_length=150, verbose_name="Nombre / Descripción")
    class Meta: verbose_name = "Tipo de Crédito"; verbose_name_plural = "Tipos de Crédito"
    def __str__(self): return f"{self.code} - {self.name}"

class BudgetSubprog(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name="Código SUBPROG")
    name = models.CharField(max_length=100, verbose_name="Descripción SUBPROG", blank=True)
    class Meta: verbose_name = "Subprograma"; verbose_name_plural = "Subprogramas"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code

class BudgetProg(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Código PROG")
    name = models.CharField(max_length=255, verbose_name="Nombre Programa")
    admin_code = models.CharField(max_length=3, blank=True, null=True, verbose_name="Administrador de Programa (3 chars)")
    class Meta: verbose_name = "Programa"; verbose_name_plural = "Programas"
    def __str__(self): return f"{self.code} - {self.name}"

class BudgetPPPInc(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Código PPAL")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre PPAL")
    class Meta: verbose_name = "PPAL"; verbose_name_plural = "PPALs"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code

class BudgetPPInc(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Código PARCIAL")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre PARCIAL")
    class Meta: verbose_name = "PARCIAL"; verbose_name_plural = "PARCIALes"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code

class BudgetPreInc(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Código SUBPC")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre SUBPC")
    class Meta: verbose_name = "SUBPC"; verbose_name_plural = "SUBPCs"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code

class BudgetIncisosAgrupado(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Código MONEDA")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre MONEDA")
    class Meta: verbose_name = "MONEDA"; verbose_name_plural = "MONEDAs"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code

class BudgetInc(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name="Código INCISO")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre INCISO")
    class Meta: verbose_name = "INCISO"; verbose_name_plural = "INCISOs"
    def __str__(self): return f"{self.code} - {self.name}" if self.name else self.code


class BudgetClassification(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Clasificación")
    notes = models.TextField(blank=True, null=True, verbose_name="Descripción / Notas")
    
    class Meta:
        verbose_name = "Clasificación Personalizada"
        verbose_name_plural = "Clasificaciones Personalizadas"
        
    def __str__(self):
        return self.name


class BudgetCredit(models.Model):
    fiscal_year = models.ForeignKey(BudgetFiscalYear, on_delete=models.PROTECT, related_name="credits", verbose_name="Ejercicio")
    credit_type = models.ForeignKey(BudgetCreditType, on_delete=models.PROTECT, null=True, blank=True, related_name='credits', verbose_name="Tipo de Crédito")
    ff = models.ForeignKey(BudgetFF, on_delete=models.PROTECT, verbose_name="FF", null=True, blank=True)
    programa = models.ForeignKey(BudgetProg, on_delete=models.PROTECT, verbose_name="Programa", null=True, blank=True)
    subprog = models.ForeignKey(BudgetSubprog, on_delete=models.PROTECT, verbose_name="SUBPROG", null=True, blank=True)
    inc = models.ForeignKey(BudgetInc, on_delete=models.PROTECT, verbose_name="INCISO", null=True, blank=True)
    ppp_inc = models.ForeignKey(BudgetPPPInc, on_delete=models.PROTECT, verbose_name="PPAL", null=True, blank=True)
    pp_inc = models.ForeignKey(BudgetPPInc, on_delete=models.PROTECT, verbose_name="PARCIAL", null=True, blank=True)
    pre_inc = models.ForeignKey(BudgetPreInc, on_delete=models.PROTECT, verbose_name="SUBPC", null=True, blank=True)
    incisos_agrupado = models.ForeignKey(BudgetIncisosAgrupado, on_delete=models.PROTECT, verbose_name="MONEDA", null=True, blank=True)
    q1_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    q2_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    q3_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    q4_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro", null=True)
    
    class Meta:
        verbose_name = "Crédito Presupuestario"
        verbose_name_plural = "Créditos Presupuestarios"
        ordering = ['-created_at']

    def __str__(self):
        parts = []
        parts.append(self.ff.code if self.ff else "?")
        parts.append(self.programa.code if self.programa else "00")
        parts.append(self.subprog.code if self.subprog else "00")
        parts.append(self.inc.code if self.inc else "?")
        parts.append(self.ppp_inc.code if self.ppp_inc else "?")
        parts.append(self.pp_inc.code if self.pp_inc else "?")
        parts.append(self.pre_inc.code if self.pre_inc else "?")
        parts.append(self.incisos_agrupado.code if self.incisos_agrupado else "?")
        return "-".join(parts)
    def save(self, *args, **kwargs):
        self.total_amount = self.q1_amount + self.q2_amount + self.q3_amount + self.q4_amount
        super().save(*args, **kwargs)

class BudgetAllocation(models.Model):
    credit = models.ForeignKey(BudgetCredit, on_delete=models.PROTECT, related_name="allocations", verbose_name="Crédito Origen")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="budget_allocations", verbose_name="Unidad Destino")
    custom_classes = models.ManyToManyField(BudgetClassification, blank=True, related_name='allocations', verbose_name="Clasificaciones Especiales")
    q1_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T1")
    q2_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T2")
    q3_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T3")
    q4_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T4")
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="Monto Asignado (Techo Total)")
    spent_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto Comprometido (Acumulado)")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    class Meta: 
        verbose_name = "Distribución de Crédito"
        verbose_name_plural = "Distribuciones de Crédito"
    
    def save(self, *args, **kwargs):
        self.allocated_amount = self.q1_amount + self.q2_amount + self.q3_amount + self.q4_amount
        super().save(*args, **kwargs)

    @property
    def available_amount(self):
        return self.allocated_amount - self.spent_amount

    @property
    def get_quarters_display(self):
        qs = []
        if self.q1_amount > 0: qs.append("T1")
        if self.q2_amount > 0: qs.append("T2")
        if self.q3_amount > 0: qs.append("T3")
        if self.q4_amount > 0: qs.append("T4")
        return ", ".join(qs) if qs else "--"

    def __str__(self):
        return f"Distribución {self.unit.name} - {self.credit}"

class BudgetCompensacion(models.Model):
    STATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado (Listo para Ejecutar)'),
        ('RECHAZADO', 'Rechazado'),
        ('EJECUTADO', 'Ejecutado'),
    ]

    fiscal_year = models.ForeignKey(BudgetFiscalYear, on_delete=models.CASCADE, verbose_name="Ejercicio")
    programa = models.ForeignKey(BudgetProg, on_delete=models.CASCADE, verbose_name="Programa")
    source_credit = models.ForeignKey(BudgetCredit, on_delete=models.CASCADE, related_name='compensaciones_salida', verbose_name="Crédito de Origen")
    
    # Destino (pueden ser los mismos componentes u otros)
    target_ff = models.ForeignKey(BudgetFF, on_delete=models.PROTECT, verbose_name="FF Destino")
    target_subprog = models.ForeignKey(BudgetSubprog, on_delete=models.PROTECT, verbose_name="Subprog Destino")
    target_inc = models.ForeignKey(BudgetInc, on_delete=models.PROTECT, verbose_name="Inciso Destino")
    target_ppp_inc = models.ForeignKey(BudgetPPPInc, on_delete=models.PROTECT, null=True, blank=True, verbose_name="PPAL Destino")
    target_pp_inc = models.ForeignKey(BudgetPPInc, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Parcial Destino")
    target_pre_inc = models.ForeignKey(BudgetPreInc, on_delete=models.PROTECT, null=True, blank=True, verbose_name="SubParcial Destino")
    target_incisos_agrupado = models.ForeignKey(BudgetIncisosAgrupado, on_delete=models.PROTECT, verbose_name="Moneda Destino")
    
    q1_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T1")
    q2_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T2")
    q3_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T3")
    q4_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto T4")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDIENTE', verbose_name="Estado")
    notes = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    requested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='compensaciones_solicitadas', verbose_name="Solicitado por")
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='compensaciones_aprobadas', verbose_name="Aprobado por")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compensación de Partida"
        verbose_name_plural = "Compensaciones de Partidas"

    def __str__(self):
        return f"Compensación #{self.id} - {self.programa.code} ({self.total_amount})"

    @property
    def total_amount(self):
        return self.q1_amount + self.q2_amount + self.q3_amount + self.q4_amount

class BudgetTipoGasto(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name="Código")
    name = models.CharField(max_length=150, verbose_name="Nombre / Descripción")
    class Meta:
        verbose_name = "Tipo de Gasto"
        verbose_name_plural = "Tipos de Gasto"
    def __str__(self): return f"{self.code} - {self.name}"

class BudgetExecution(models.Model):
    allocation = models.ForeignKey(BudgetAllocation, on_delete=models.PROTECT, related_name="executions", verbose_name="Distribución / Techo")
    reference_code = models.CharField(max_length=100, verbose_name="Nro. Expediente / Referencia")
    external_id = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name="ID de Control Único (Opcional)", help_text="Código para evitar registros duplicados (Ej: Nro. Factura, ID de sistema externo, etc).")
    
    # Nuevos campos para Rendición
    tipo_gasto = models.ForeignKey(BudgetTipoGasto, on_delete=models.PROTECT, blank=True, null=True, verbose_name="Tipo de Gasto (TG)")
    afecta_pg117 = models.BooleanField(default=False, verbose_name="Afecta PG 117")
    numero_obra = models.CharField(max_length=5, blank=True, null=True, verbose_name="Número de Obra")
    subcuenta = models.CharField(max_length=2, blank=True, null=True, verbose_name="Subcuenta (SC)")
    
    commitment_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto Comprometido")
    commitment_date = models.DateField(verbose_name="Fecha de Compromiso")
    accrued_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto Devengado")
    accrued_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Devengado")
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto Pagado")
    paid_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Pago")
    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT, verbose_name="Usuario")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    class Meta:
        verbose_name = "Ejecución Presupuestaria"
        verbose_name_plural = "Ejecuciones Presupuestarias"
    def __str__(self): return self.reference_code
    
    def save(self, *args, **kwargs):
        # Lógica automática para Subcuenta (SC)
        if not self.subcuenta and self.allocation and self.allocation.credit:
            ff_code = self.allocation.credit.ff.code if self.allocation.credit.ff else ""
            if ff_code in ['13', '99']:
                self.subcuenta = '99'
            else:
                self.subcuenta = '51'
        super().save(*args, **kwargs)

    def get_subparcial_calculado(self):
        """Calcula los 5 dígitos del Subparcial según FF e Inciso"""
        if not self.allocation or not self.allocation.credit:
            return "00000"
        
        credit = self.allocation.credit
        ff_code = credit.ff.code if credit.ff else ""
        inc_code = credit.inc.code if credit.inc else ""
        
        # Nomenclador base (2 dígitos). Usamos pre_inc si existe, o '00'
        nom_base = "00"
        if credit.pre_inc and credit.pre_inc.code:
            nom_base = credit.pre_inc.code[:2].zfill(2)

        if ff_code in ['13', '99'] and inc_code == '4':
            return "99999"
        elif inc_code == '4':
            # Asumimos que FF es 11 o cualquier otra que aplique número de obra
            return str(self.numero_obra).zfill(5) if self.numero_obra else "00000"
        else:
            # Incisos 1, 2, 3, 5 (FF 11, 13, 99)
            tg = self.tipo_gasto.code if self.tipo_gasto else "0"
            afecta = "17" if self.afecta_pg117 else "00"
            return f"{nom_base}{tg}{afecta}"

    def get_imputacion_variable(self):
        """Genera la cadena de la Parte Variable de la imputación: UUUUUU.I.P.p.SSSSS.M.OOO.CC"""
        if not self.allocation or not self.allocation.credit:
            return ""
        
        unit = self.allocation.unit
        credit = self.allocation.credit
        
        # UUUUUU
        uc = unit.component_code.zfill(6) if unit.component_code else "000000"
        # I
        inc = credit.inc.code[:1] if credit.inc else "0"
        # P
        ppal = credit.ppp_inc.code[:1] if credit.ppp_inc else "0"
        # p
        parcial = credit.pp_inc.code[:1] if credit.pp_inc else "0"
        # SSSSS
        subparcial = self.get_subparcial_calculado()
        # M
        moneda = credit.incisos_agrupado.code[:1] if credit.incisos_agrupado else "1"
        # OOO
        ot = unit.ot_code.zfill(3) if unit.ot_code else "000"
        # CC
        sc = self.subcuenta.zfill(2) if self.subcuenta else "51"
        
        return f"{uc}.{inc}.{ppal}.{parcial}.{subparcial}.{moneda}.{ot}.{sc}"


class BudgetCreditTypeLog(models.Model):
    ACTION_ASSIGN = 'ASSIGN'
    ACTION_UNASSIGN = 'UNASSIGN'
    ACTION_CHANGE = 'CHANGE'
    ACTION_CHOICES = [
        (ACTION_ASSIGN, 'Asignación'),
        (ACTION_UNASSIGN, 'Desasignación'),
        (ACTION_CHANGE, 'Cambio de Tipo'),
    ]

    credit = models.ForeignKey(BudgetCredit, on_delete=models.CASCADE, related_name='type_logs', verbose_name="Crédito")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="Acción")
    previous_type = models.ForeignKey(BudgetCreditType, on_delete=models.SET_NULL, null=True, blank=True, related_name='unassigned_logs', verbose_name="Tipo Anterior")
    new_type = models.ForeignKey(BudgetCreditType, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_logs', verbose_name="Tipo Nuevo")
    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT, verbose_name="Realizado por")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    notes = models.TextField(blank=True, null=True, verbose_name="Motivo / Observaciones")

    class Meta:
        verbose_name = "Registro de Cambio de Tipo"
        verbose_name_plural = "Registros de Cambios de Tipo"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_display()} — {self.credit} ({self.timestamp.strftime('%d/%m/%Y %H:%M')})"


class BudgetCreditAdjustment(models.Model):
    credit = models.ForeignKey(BudgetCredit, on_delete=models.CASCADE, related_name='adjustments', verbose_name="Crédito")
    
    q1_old = models.DecimalField(max_digits=18, decimal_places=2)
    q2_old = models.DecimalField(max_digits=18, decimal_places=2)
    q3_old = models.DecimalField(max_digits=18, decimal_places=2)
    q4_old = models.DecimalField(max_digits=18, decimal_places=2)
    
    q1_new = models.DecimalField(max_digits=18, decimal_places=2)
    q2_new = models.DecimalField(max_digits=18, decimal_places=2)
    q3_new = models.DecimalField(max_digits=18, decimal_places=2)
    q4_new = models.DecimalField(max_digits=18, decimal_places=2)
    
    reason = models.TextField(verbose_name="Motivo del Ajuste")
    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT, verbose_name="Realizado por")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Ajuste de Crédito"
        verbose_name_plural = "Ajustes de Crédito"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Ajuste #{self.id} - {self.credit}"

    @property
    def get_q1_delta(self): return self.q1_new - self.q1_old
    @property
    def get_q2_delta(self): return self.q2_new - self.q2_old
    @property
    def get_q3_delta(self): return self.q3_new - self.q3_old
    @property
    def get_q4_delta(self): return self.q4_new - self.q4_old
