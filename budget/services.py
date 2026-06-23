from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F
from decimal import Decimal
from .models import (
    BudgetFiscalYear, BudgetFF, BudgetSubprog, BudgetProg,
    BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado,
    BudgetInc, BudgetCredit, BudgetAllocation, BudgetExecution,
    BudgetCreditTypeLog, BudgetCompensacion, BudgetAllocationReclassification,
    InsufficientFundsError
)

@transaction.atomic
def create_fiscal_year(year, notes=""):
    if BudgetFiscalYear.objects.filter(year=year).exists():
        raise ValidationError(f"El ejercicio {year} ya existe.")
    return BudgetFiscalYear.objects.create(year=year, notes=notes)


@transaction.atomic
def create_credit(fiscal_year, ff, programa, subprog, inc, ppp_inc, pp_inc, pre_inc, 
                  incisos_agrupado, credit_type=None, q1=0, q2=0, q3=0, q4=0, notes=""):
    """
    Registra un nuevo crédito presupuestario utilizando objetos de catálogo.
    """
    if fiscal_year.status == 'CLOSED':
        raise ValidationError("No se puede registrar crédito en un ejercicio cerrado.")
    
    return BudgetCredit.objects.create(
        fiscal_year=fiscal_year,
        credit_type=credit_type,
        ff=ff, programa=programa, subprog=subprog,
        inc=inc, ppp_inc=ppp_inc, pp_inc=pp_inc, pre_inc=pre_inc,
        incisos_agrupado=incisos_agrupado,
        q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
        notes=notes
    )


@transaction.atomic
def allocate_credit(credit, unit, q1=0, q2=0, q3=0, q4=0, notes="", classifications=None):
    amount = q1 + q2 + q3 + q4
    if amount <= 0:
        raise ValidationError("El monto total a distribuir debe ser mayor a cero.")

    credit = BudgetCredit.objects.select_for_update().get(pk=credit.pk)
    reserved_q1, reserved_q2, reserved_q3, reserved_q4 = _compensation_reserved_by_quarter(credit)

    # Validaciones contra el crédito de origen por cada trimestre
    allocated_q1 = credit.allocations.aggregate(Sum('q1_amount'))['q1_amount__sum'] or 0
    allocated_q2 = credit.allocations.aggregate(Sum('q2_amount'))['q2_amount__sum'] or 0
    allocated_q3 = credit.allocations.aggregate(Sum('q3_amount'))['q3_amount__sum'] or 0
    allocated_q4 = credit.allocations.aggregate(Sum('q4_amount'))['q4_amount__sum'] or 0

    if allocated_q1 + reserved_q1 + q1 > credit.q1_amount:
        raise ValidationError(f"La distribucion en T1 (${q1}) supera el disponible real (${credit.q1_amount - allocated_q1 - reserved_q1}).")
    if allocated_q2 + reserved_q2 + q2 > credit.q2_amount:
        raise ValidationError(f"La distribucion en T2 (${q2}) supera el disponible real (${credit.q2_amount - allocated_q2 - reserved_q2}).")
    if allocated_q3 + reserved_q3 + q3 > credit.q3_amount:
        raise ValidationError(f"La distribucion en T3 (${q3}) supera el disponible real (${credit.q3_amount - allocated_q3 - reserved_q3}).")
    if allocated_q4 + reserved_q4 + q4 > credit.q4_amount:
        raise ValidationError(f"La distribucion en T4 (${q4}) supera el disponible real (${credit.q4_amount - allocated_q4 - reserved_q4}).")
    
    allocation = BudgetAllocation.objects.create(
        credit=credit, unit=unit, 
        q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
        notes=notes
    )
    if classifications:
        allocation.custom_classes.set(classifications)
    return allocation


@transaction.atomic
def register_commitment(allocation_id, reference_code, amount, commitment_date, user, external_id=None, tipo_gasto=None, afecta_pg117=False, numero_obra=None, subcuenta=None):
    """
    Registra un compromiso con control de concurrencia e idempotencia extrema.
    Orden de operaciones:
    1. select_for_update() (Bloqueo de fila)
    2. Validar saldo
    3. Intentar crear execution (con manejo de IntegrityError por colisión de external_id)
    4. Si se creó, actualizar spent_amount atómicamente
    """
    if amount <= 0:
        raise ValidationError("El monto del compromiso debe ser positivo.")

    # 1. Bloqueamos la fila de la asignación (SELECT FOR UPDATE)
    allocation = BudgetAllocation.objects.select_for_update().get(pk=allocation_id)

    if allocation.credit.fiscal_year.status == 'CLOSED':
        raise ValidationError("No se pueden registrar gastos en un ejercicio cerrado.")

    # 2. Validación de saldo disponible
    available = allocation.allocated_amount - allocation.spent_amount
    if amount > available:
        raise InsufficientFundsError(f"Saldo insuficiente. Disponible: ${available:.2f}, Solicitado: ${amount:.2f}")

    # 3. Creación del registro con manejo de colisiones simultáneas
    try:
        # Usamos un bloque atomic interno para crear un savepoint. 
        # Sin esto, un IntegrityError rompería la transacción externa.
        with transaction.atomic():
            execution = BudgetExecution.objects.create(
                allocation=allocation, 
                reference_code=reference_code,
                external_id=external_id,
                tipo_gasto=tipo_gasto,
                afecta_pg117=afecta_pg117,
                numero_obra=numero_obra,
                subcuenta=subcuenta,
                commitment_amount=amount, 
                commitment_date=commitment_date, 
                user=user
            )
    except IntegrityError:
        # Alguien más creó el registro con el mismo external_id en el microsegundo anterior
        return BudgetExecution.objects.get(external_id=external_id)

    # 4. SOLO si la creación fue exitosa (no saltamos al except), actualizamos el saldo.
    # Usamos .filter().update() para asegurar atomicidad máxima y evitar race conditions.
    BudgetAllocation.objects.filter(pk=allocation.id).update(
        spent_amount=F('spent_amount') + amount
    )
    
    execution.refresh_from_db()
    return execution


@transaction.atomic
def register_accrual(execution, amount, accrued_date):
    if amount < 0: raise ValidationError("Monto negativo.")
    if amount > execution.commitment_amount:
        raise ValidationError("No puede superar el compromiso.")
    execution.accrued_amount = amount
    execution.accrued_date = accrued_date
    execution.save()
    return execution


@transaction.atomic
def register_payment(execution, amount, paid_date):
    if amount < 0: raise ValidationError("Monto negativo.")
    if amount > execution.accrued_amount:
        raise ValidationError("No puede superar el devengado.")
    execution.paid_amount = amount
    execution.paid_date = paid_date
    execution.save()
    return execution


@transaction.atomic
def close_fiscal_year(fiscal_year):
    fiscal_year.status = 'CLOSED'
    fiscal_year.save()
    return True


def reprogram_commitment(original_execution, target_allocation, user):
    if original_execution.accrued_amount > 0:
        raise ValueError("Solo compromisos no devengados.")
    if target_allocation.credit.fiscal_year.status == 'CLOSED':
        raise ValueError("Ejercicio de destino cerrado.")
    amount = original_execution.commitment_amount
    executed_total = target_allocation.executions.aggregate(Sum('commitment_amount'))['commitment_amount__sum'] or 0
    available = target_allocation.allocated_amount - executed_total
    if available < amount:
        raise ValueError(f"Faltan ${amount - available} en el nuevo ejercicio.")
    return register_commitment(
        allocation=target_allocation, reference_code=f"REP-{original_execution.reference_code}",
        amount=amount, commitment_date=timezone.now(), user=user
    )


@transaction.atomic
def release_commitment_surplus(execution_id, user):
    """
    Libera el saldo comprometido que no fue devengado.
    Ajusta el compromiso original al monto devengado/pagado y devuelve la diferencia al Techo.
    """
    execution = BudgetExecution.objects.select_related('allocation').get(pk=execution_id)
    
    if execution.commitment_amount <= execution.accrued_amount:
        raise ValidationError("No hay saldo sobrante para liberar.")
    
    surplus = execution.commitment_amount - execution.accrued_amount
    
    # 1. Ajustamos el compromiso en el registro de ejecución
    execution.commitment_amount = execution.accrued_amount
    execution.save()
    
    # 2. Devolvemos el saldo a la asignación (Techo)
    BudgetAllocation.objects.filter(pk=execution.allocation.id).update(
        spent_amount=F('spent_amount') - surplus
    )
    
    return execution, surplus


@transaction.atomic
def delete_execution(execution_id, user):
    """
    Hard delete de un Compromiso (BudgetExecution).
    Resta el monto comprometido del total gastado (spent_amount) en la Distribución (Techo),
    liberando los fondos de vuelta a la unidad.
    """
    if not hasattr(user, 'is_superuser') or not user.is_superuser:
        raise PermissionError("Solo los superusuarios pueden eliminar físicamente un registro de ejecución.")
        
    execution = BudgetExecution.objects.select_related('allocation').get(pk=execution_id)
    amount_to_restore = execution.commitment_amount
    
    # Bloqueamos la asignación y devolvemos el dinero al Techo
    allocation = BudgetAllocation.objects.select_for_update().get(pk=execution.allocation_id)
    allocation.spent_amount -= amount_to_restore
    allocation.save(update_fields=['spent_amount'])
    
    # Eliminamos el registro de ejecución físicamente
    execution.delete()
    
    return amount_to_restore


def get_unit_execution_report(fiscal_year):
    from core.models import Unit
    report = []
    units = Unit.objects.filter(budget_allocations__credit__fiscal_year=fiscal_year).distinct()
    for unit in units:
        allocations = BudgetAllocation.objects.filter(unit=unit, credit__fiscal_year=fiscal_year).select_related('credit__ff', 'credit__programa', 'credit__subprog', 'credit__inc', 'credit__ppp_inc', 'credit__pp_inc', 'credit__pre_inc').prefetch_related('custom_classes')
        total_allocated = allocations.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
        executions = BudgetExecution.objects.filter(allocation__in=allocations)
        tc = executions.aggregate(Sum('commitment_amount'))['commitment_amount__sum'] or 0
        ta = executions.aggregate(Sum('accrued_amount'))['accrued_amount__sum'] or 0
        tp = executions.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        
        # Detalle de créditos
        credit_details = []
        for alloc in allocations:
            credit_details.append({
                'nomenclature': str(alloc.credit),
                'subpc': alloc.credit.pre_inc.code if alloc.credit.pre_inc else "--",
                'quarters': alloc.get_quarters_display,
                'total': alloc.allocated_amount,
                'spent': alloc.spent_amount,
                'available': alloc.allocated_amount - alloc.spent_amount,
                'ff': alloc.credit.ff.code if alloc.credit.ff else "--",
                'subprog': alloc.credit.subprog.code if alloc.credit.subprog else "--",
                'notes': alloc.notes,
                'projects': [project.name for project in alloc.custom_classes.all()],
            })

        report.append({
            'unit': unit, 
            'allocated': total_allocated, 
            'commitment': tc,
            'accrued': ta, 
            'paid': tp, 
            'available': total_allocated - tc,
            'residuos': tc - ta, 
            'deuda_flotante': ta - tp,
            'percent_executed': (tc / total_allocated * 100) if total_allocated > 0 else 0,
            'allocations': credit_details
        })
    return report

@transaction.atomic
def unassign_credit_type(credit, unassign_amount, user, notes=""):
    """
    Remueve el tipo de crédito y descuenta el monto de los trimestres (Q4 -> Q1).
    Registra la acción en el historial. Valida que no se reduzca por debajo de lo distribuido.
    """
    if unassign_amount and unassign_amount > 0:
        # 1. Calcular potenciales nuevos montos
        new_q = {
            'q1_amount': credit.q1_amount, 'q2_amount': credit.q2_amount,
            'q3_amount': credit.q3_amount, 'q4_amount': credit.q4_amount
        }
        remaining = unassign_amount
        for q_attr in ['q4_amount', 'q3_amount', 'q2_amount', 'q1_amount']:
            if remaining <= 0: break
            current_val = new_q[q_attr]
            if current_val >= remaining:
                new_q[q_attr] = current_val - remaining
                remaining = 0
            else:
                remaining -= current_val
                new_q[q_attr] = 0
        
        if remaining > 0:
            raise ValidationError(f"El monto a desasignar (${unassign_amount}) supera el crédito total disponible (${credit.total_amount}).")

        # 2. Validar contra distribuciones existentes
        allocs_q = credit.allocations.aggregate(
            q1=Sum('q1_amount'), q2=Sum('q2_amount'), 
            q3=Sum('q3_amount'), q4=Sum('q4_amount')
        )
        q1_a, q2_a, q3_a, q4_a = (allocs_q['q1'] or 0), (allocs_q['q2'] or 0), (allocs_q['q3'] or 0), (allocs_q['q4'] or 0)
        
        if new_q['q1_amount'] < q1_a: raise ValidationError(f"T1: La reducción supera el disponible no distribuido. Distribuido: ${q1_a}.")
        if new_q['q2_amount'] < q2_a: raise ValidationError(f"T2: La reducción supera el disponible no distribuido. Distribuido: ${q2_a}.")
        if new_q['q3_amount'] < q3_a: raise ValidationError(f"T3: La reducción supera el disponible no distribuido. Distribuido: ${q3_a}.")
        if new_q['q4_amount'] < q4_a: raise ValidationError(f"T4: La reducción supera el disponible no distribuido. Distribuido: ${q4_a}.")

        # 3. Aplicar si todo está ok
        for q_attr, val in new_q.items():
            setattr(credit, q_attr, val)
    
    # Mantenemos el tipo (No lo limpiamos para permitir múltiples desasignaciones parciales)
    previous_type = credit.credit_type
    credit.save()
    
    # Creamos el log de auditoría
    from .models import BudgetCreditTypeLog
    BudgetCreditTypeLog.objects.create(
        credit=credit,
        action=BudgetCreditTypeLog.ACTION_UNASSIGN,
        previous_type=previous_type,
        new_type=previous_type, # El tipo se mantiene
        user=user,
        notes=notes
    )
    
    return credit

COMPENSATION_ACTIVE_STATUSES = ('PENDIENTE', 'APROBADO')
RECLASSIFICATION_ACTIVE_STATUSES = ('PENDIENTE', 'APROBADO')
QUARTER_FIELDS = ('q1_amount', 'q2_amount', 'q3_amount', 'q4_amount')


def _target_params_from_compensation(comp):
    return {
        'target_ff': comp.target_ff,
        'target_subprog': comp.target_subprog,
        'target_inc': comp.target_inc,
        'target_ppp_inc': comp.target_ppp_inc,
        'target_pp_inc': comp.target_pp_inc,
        'target_pre_inc': comp.target_pre_inc,
        'target_incisos_agrupado': comp.target_incisos_agrupado,
    }


def _compensation_reserved_by_quarter(source_credit, exclude_compensation_id=None):
    reservations = BudgetCompensacion.objects.filter(
        source_credit=source_credit,
        status__in=COMPENSATION_ACTIVE_STATUSES,
    )
    if exclude_compensation_id:
        reservations = reservations.exclude(pk=exclude_compensation_id)
    reserved = reservations.aggregate(
        q1=Sum('q1_amount'), q2=Sum('q2_amount'),
        q3=Sum('q3_amount'), q4=Sum('q4_amount'),
    )
    return tuple((reserved[f'q{index}'] or Decimal('0')) for index in range(1, 5))


def _compensation_available_by_quarter(source_credit, exclude_compensation_id=None):
    allocated = source_credit.allocations.aggregate(
        q1=Sum('q1_amount'), q2=Sum('q2_amount'),
        q3=Sum('q3_amount'), q4=Sum('q4_amount'),
    )
    reserved = _compensation_reserved_by_quarter(source_credit, exclude_compensation_id)

    return tuple(
        max(
            getattr(source_credit, field)
            - (allocated[f'q{index}'] or Decimal('0'))
            - reserved[index - 1],
            Decimal('0'),
        )
        for index, field in enumerate(QUARTER_FIELDS, start=1)
    )


def _validate_compensation(source_credit, target_params, q_amounts, exclude_compensation_id=None):
    if source_credit.fiscal_year.status == 'CLOSED':
        raise ValidationError("No se puede compensar credito de un ejercicio cerrado.")
    if source_credit.programa is None:
        raise ValidationError("El credito de origen no tiene un programa asociado.")

    amounts = tuple(Decimal(str(value or 0)) for value in q_amounts)
    if any(value < 0 for value in amounts):
        raise ValidationError("Los montos trimestrales no pueden ser negativos.")
    if not any(value > 0 for value in amounts):
        raise ValidationError("Debe ingresar un monto mayor a cero en al menos un trimestre.")

    target_identity = (
        target_params['target_ff'].pk,
        source_credit.programa_id,
        target_params['target_subprog'].pk,
        target_params['target_inc'].pk,
        target_params['target_ppp_inc'].pk if target_params.get('target_ppp_inc') else None,
        target_params['target_pp_inc'].pk if target_params.get('target_pp_inc') else None,
        target_params['target_pre_inc'].pk if target_params.get('target_pre_inc') else None,
        target_params['target_incisos_agrupado'].pk,
    )
    source_identity = (
        source_credit.ff_id,
        source_credit.programa_id,
        source_credit.subprog_id,
        source_credit.inc_id,
        source_credit.ppp_inc_id,
        source_credit.pp_inc_id,
        source_credit.pre_inc_id,
        source_credit.incisos_agrupado_id,
    )
    if target_identity == source_identity:
        raise ValidationError("La partida de destino debe ser diferente de la partida de origen.")

    available = _compensation_available_by_quarter(source_credit, exclude_compensation_id)
    errors = []
    for index, (requested, remaining) in enumerate(zip(amounts, available), start=1):
        if requested > remaining:
            errors.append(
                f"T{index}: intenta compensar ${requested}, pero solo hay ${remaining} "
                "sin distribuir."
            )
    if errors:
        raise ValidationError([
            "No se puede realizar la compensacion porque el monto solicitado ya esta "
            "distribuido, reservado o supera el saldo disponible."
        ] + errors)
    return amounts


@transaction.atomic
def request_compensacion(source_credit, target_params, q_amounts, user, notes=""):
    """Crea una solicitud y reserva saldo no distribuido del credito origen."""
    source = BudgetCredit.objects.select_for_update().get(pk=source_credit.pk)
    amounts = _validate_compensation(source, target_params, q_amounts)
    return BudgetCompensacion.objects.create(
        fiscal_year=source.fiscal_year,
        programa=source.programa,
        source_credit=source,
        **target_params,
        q1_amount=amounts[0], q2_amount=amounts[1],
        q3_amount=amounts[2], q4_amount=amounts[3],
        requested_by=user,
        notes=notes,
    )


@transaction.atomic
def approve_compensacion(compensacion_id, user):
    """Aprueba una solicitud sin mover fondos."""
    comp = BudgetCompensacion.objects.select_for_update().get(pk=compensacion_id)
    if comp.status != 'PENDIENTE':
        raise ValidationError("Solo se pueden aprobar compensaciones pendientes.")
    source = BudgetCredit.objects.select_for_update().get(pk=comp.source_credit_id)
    _validate_compensation(
        source,
        _target_params_from_compensation(comp),
        (comp.q1_amount, comp.q2_amount, comp.q3_amount, comp.q4_amount),
        exclude_compensation_id=comp.pk,
    )
    comp.status = 'APROBADO'
    comp.approved_by = user
    comp.save(update_fields=['status', 'approved_by', 'updated_at'])
    return comp


@transaction.atomic
def reject_compensacion(compensacion_id):
    """Rechaza una solicitud y libera el saldo reservado."""
    comp = BudgetCompensacion.objects.select_for_update().get(pk=compensacion_id)
    if comp.status not in COMPENSATION_ACTIVE_STATUSES:
        raise ValidationError("Esta compensacion ya fue procesada.")
    comp.status = 'RECHAZADO'
    comp.save(update_fields=['status', 'updated_at'])
    return comp


@transaction.atomic
def execute_compensacion(compensacion_id, user):
    """Revalida y ejecuta una compensacion previamente aprobada."""
    comp = BudgetCompensacion.objects.select_for_update().get(pk=compensacion_id)
    if comp.status != 'APROBADO':
        raise ValidationError("La compensacion debe estar aprobada antes de ejecutarse.")
    source = BudgetCredit.objects.select_for_update().get(pk=comp.source_credit_id)
    amounts = _validate_compensation(
        source,
        _target_params_from_compensation(comp),
        (comp.q1_amount, comp.q2_amount, comp.q3_amount, comp.q4_amount),
        exclude_compensation_id=comp.pk,
    )

    for field, amount in zip(QUARTER_FIELDS, amounts):
        setattr(source, field, getattr(source, field) - amount)
    source.save()

    target = BudgetCredit.objects.select_for_update().filter(
        fiscal_year=source.fiscal_year,
        credit_type=source.credit_type,
        ff=comp.target_ff,
        programa=source.programa,
        subprog=comp.target_subprog,
        inc=comp.target_inc,
        ppp_inc=comp.target_ppp_inc,
        pp_inc=comp.target_pp_inc,
        pre_inc=comp.target_pre_inc,
        incisos_agrupado=comp.target_incisos_agrupado,
    ).first()
    if not target:
        target = BudgetCredit.objects.create(
            fiscal_year=source.fiscal_year,
            credit_type=source.credit_type,
            ff=comp.target_ff,
            programa=source.programa,
            subprog=comp.target_subprog,
            inc=comp.target_inc,
            ppp_inc=comp.target_ppp_inc,
            pp_inc=comp.target_pp_inc,
            pre_inc=comp.target_pre_inc,
            incisos_agrupado=comp.target_incisos_agrupado,
        )

    for field, amount in zip(QUARTER_FIELDS, amounts):
        setattr(target, field, getattr(target, field) + amount)
    target.save()

    comp.status = 'EJECUTADO'
    comp.save(update_fields=['status', 'updated_at'])
    return comp


@transaction.atomic
def adjust_credit(credit_id, q1_new, q2_new, q3_new, q4_new, reason, user):
    """
    Ajusta los montos de un crédito existente y registra la modificación.
    Valida que los nuevos montos no sean inferiores a lo ya distribuido.
    """
    from .models import BudgetCredit, BudgetCreditAdjustment
    from django.db.models import Sum
    
    credit = BudgetCredit.objects.select_for_update().get(pk=credit_id)
    
    if credit.fiscal_year.status == 'CLOSED':
        raise ValidationError("No se puede ajustar crédito en un ejercicio cerrado.")

    # Validar contra distribuciones existentes
    allocs = credit.allocations.aggregate(
        q1=Sum('q1_amount'), q2=Sum('q2_amount'), 
        q3=Sum('q3_amount'), q4=Sum('q4_amount')
    )
    q1_a = allocs['q1'] or 0
    q2_a = allocs['q2'] or 0
    q3_a = allocs['q3'] or 0
    q4_a = allocs['q4'] or 0
    reserved_q1, reserved_q2, reserved_q3, reserved_q4 = _compensation_reserved_by_quarter(credit)

    # Si el usuario no envió un monto (campo vacío), mantenemos el actual
    q1_new = q1_new if q1_new is not None else credit.q1_amount
    q2_new = q2_new if q2_new is not None else credit.q2_amount
    q3_new = q3_new if q3_new is not None else credit.q3_amount
    q4_new = q4_new if q4_new is not None else credit.q4_amount

    if q1_new < q1_a + reserved_q1: raise ValidationError(f"T1: El nuevo monto no puede ser menor a lo distribuido y reservado (${q1_a + reserved_q1}).")
    if q2_new < q2_a + reserved_q2: raise ValidationError(f"T2: El nuevo monto no puede ser menor a lo distribuido y reservado (${q2_a + reserved_q2}).")
    if q3_new < q3_a + reserved_q3: raise ValidationError(f"T3: El nuevo monto no puede ser menor a lo distribuido y reservado (${q3_a + reserved_q3}).")
    if q4_new < q4_a + reserved_q4: raise ValidationError(f"T4: El nuevo monto no puede ser menor a lo distribuido y reservado (${q4_a + reserved_q4}).")

    # Guardar estado anterior
    adj = BudgetCreditAdjustment(
        credit=credit,
        q1_old=credit.q1_amount, q2_old=credit.q2_amount,
        q3_old=credit.q3_amount, q4_old=credit.q4_amount,
        q1_new=q1_new, q2_new=q2_new,
        q3_new=q3_new, q4_new=q4_new,
        reason=reason,
        user=user
    )

    # Actualizar crédito
    credit.q1_amount = q1_new
    credit.q2_amount = q2_new
    credit.q3_amount = q3_new
    credit.q4_amount = q4_new
    credit.save()
    
    adj.save()
    return credit, adj

@transaction.atomic
def update_allocation(allocation_id, q1=None, q2=None, q3=None, q4=None, notes=None, classifications=None):
    """
    Actualiza una distribución existente validando contra el crédito y lo ya gastado.
    """
    allocation = BudgetAllocation.objects.select_for_update().get(pk=allocation_id)
    credit = BudgetCredit.objects.select_for_update().get(pk=allocation.credit_id)
    reserved_q1, reserved_q2, reserved_q3, reserved_q4 = _compensation_reserved_by_quarter(credit)

    if credit.fiscal_year.status == 'CLOSED':
        raise ValidationError("No se puede modificar una distribución en un ejercicio cerrado.")

    # Montos actuales si no se proveen nuevos
    q1 = q1 if q1 is not None else allocation.q1_amount
    q2 = q2 if q2 is not None else allocation.q2_amount
    q3 = q3 if q3 is not None else allocation.q3_amount
    q4 = q4 if q4 is not None else allocation.q4_amount
    
    new_total = q1 + q2 + q3 + q4

    # 1. Validar piso: No puede ser menor a lo ya gastado (spent_amount)
    if new_total < allocation.spent_amount:
        raise ValidationError(f"El nuevo monto total (${new_total}) es inferior a lo ya comprometido (${allocation.spent_amount}).")

    # 2. Validar techo: No puede superar el disponible en el crédito (contando otras distribuciones)
    other_allocs = credit.allocations.exclude(pk=allocation.pk).aggregate(
        q1_s=Sum('q1_amount'), q2_s=Sum('q2_amount'), 
        q3_s=Sum('q3_amount'), q4_s=Sum('q4_amount')
    )
    
    q1_o, q2_o, q3_o, q4_o = (other_allocs['q1_s'] or 0), (other_allocs['q2_s'] or 0), (other_allocs['q3_s'] or 0), (other_allocs['q4_s'] or 0)

    if q1 + q1_o + reserved_q1 > credit.q1_amount:
        raise ValidationError(f"T1: El monto (${q1}) supera el disponible real (${credit.q1_amount - q1_o - reserved_q1}).")
    if q2 + q2_o + reserved_q2 > credit.q2_amount:
        raise ValidationError(f"T2: El monto (${q2}) supera el disponible real (${credit.q2_amount - q2_o - reserved_q2}).")
    if q3 + q3_o + reserved_q3 > credit.q3_amount:
        raise ValidationError(f"T3: El monto (${q3}) supera el disponible real (${credit.q3_amount - q3_o - reserved_q3}).")
    if q4 + q4_o + reserved_q4 > credit.q4_amount:
        raise ValidationError(f"T4: El monto (${q4}) supera el disponible real (${credit.q4_amount - q4_o - reserved_q4}).")

    # 3. Actualizar
    allocation.q1_amount = q1
    allocation.q2_amount = q2
    allocation.q3_amount = q3
    allocation.q4_amount = q4
    if notes is not None:
        allocation.notes = notes
    if classifications is not None:
        allocation.custom_classes.set(classifications)
    allocation.save()
    
    return allocation


@transaction.atomic
def update_allocation_metadata(allocation_id, notes, classifications):
    """Actualiza solo proyectos asociados y observaciones de una distribucion."""
    allocation = BudgetAllocation.objects.select_for_update().select_related(
        'credit__fiscal_year'
    ).get(pk=allocation_id)

    if allocation.credit.fiscal_year.status == 'CLOSED':
        raise ValidationError("No se puede modificar una distribucion de un ejercicio cerrado.")

    allocation.notes = notes
    allocation.save(update_fields=['notes'])
    allocation.custom_classes.set(classifications)
    return allocation


def _credit_identity(credit):
    return (
        credit.ff_id,
        credit.programa_id,
        credit.subprog_id,
        credit.inc_id,
        credit.ppp_inc_id,
        credit.pp_inc_id,
        credit.pre_inc_id,
        credit.incisos_agrupado_id,
    )


def _reclassification_target_params(item):
    return {
        'target_ff': item.target_ff,
        'target_subprog': item.target_subprog,
        'target_inc': item.target_inc,
        'target_ppp_inc': item.target_ppp_inc,
        'target_pp_inc': item.target_pp_inc,
        'target_pre_inc': item.target_pre_inc,
        'target_incisos_agrupado': item.target_incisos_agrupado,
    }


def _reclassification_reserved_by_quarter(source_allocation, exclude_reclassification_id=None):
    reservations = BudgetAllocationReclassification.objects.filter(
        source_allocation=source_allocation,
        status__in=RECLASSIFICATION_ACTIVE_STATUSES,
    )
    if exclude_reclassification_id:
        reservations = reservations.exclude(pk=exclude_reclassification_id)
    reserved = reservations.aggregate(
        q1=Sum('q1_amount'), q2=Sum('q2_amount'),
        q3=Sum('q3_amount'), q4=Sum('q4_amount'),
    )
    return tuple((reserved[f'q{index}'] or Decimal('0')) for index in range(1, 5))


def _validate_allocation_reclassification(source_allocation, source_credit, target_params, q_amounts, exclude_reclassification_id=None):
    if source_credit.fiscal_year.status == 'CLOSED':
        raise ValidationError("No se puede cambiar el inciso de una distribucion de un ejercicio cerrado.")
    if source_credit.programa is None:
        raise ValidationError("El credito de origen no tiene un programa asociado.")

    amounts = tuple(Decimal(str(value or 0)) for value in q_amounts)
    if any(value < 0 for value in amounts):
        raise ValidationError("Los montos trimestrales no pueden ser negativos.")
    if not any(value > 0 for value in amounts):
        raise ValidationError("Debe ingresar un monto mayor a cero en al menos un trimestre.")

    target_identity = (
        target_params['target_ff'].pk,
        source_credit.programa_id,
        target_params['target_subprog'].pk,
        target_params['target_inc'].pk,
        target_params['target_ppp_inc'].pk if target_params.get('target_ppp_inc') else None,
        target_params['target_pp_inc'].pk if target_params.get('target_pp_inc') else None,
        target_params['target_pre_inc'].pk if target_params.get('target_pre_inc') else None,
        target_params['target_incisos_agrupado'].pk,
    )
    if target_identity == _credit_identity(source_credit):
        raise ValidationError("La partida de destino debe ser diferente de la partida de origen.")

    reserved = _reclassification_reserved_by_quarter(source_allocation, exclude_reclassification_id)
    errors = []
    for index, (field, requested, reserved_amount) in enumerate(zip(QUARTER_FIELDS, amounts, reserved), start=1):
        available = getattr(source_allocation, field) - reserved_amount
        if requested > available:
            errors.append(f"T{index}: intenta cambiar ${requested}, pero solo hay ${available} disponible sin reservar.")

    total_to_move = sum(amounts, Decimal('0'))
    reserved_total = sum(reserved, Decimal('0'))
    real_available = source_allocation.available_amount - reserved_total
    if total_to_move > real_available:
        errors.append(
            f"El monto total a cambiar (${total_to_move}) supera el disponible sin comprometer "
            f"y sin reservar (${real_available})."
        )
    if source_allocation.allocated_amount - total_to_move < source_allocation.spent_amount:
        errors.append("La distribucion origen no puede quedar por debajo de lo ya comprometido.")
    if errors:
        raise ValidationError(errors)
    return amounts


@transaction.atomic
def request_allocation_reclassification(allocation_id, target_params, q_amounts, user, notes=""):
    """Crea una solicitud y reserva saldo disponible de una distribucion."""
    source_allocation = BudgetAllocation.objects.select_for_update().get(pk=allocation_id)
    source_credit = BudgetCredit.objects.select_for_update().get(pk=source_allocation.credit_id)
    amounts = _validate_allocation_reclassification(
        source_allocation, source_credit, target_params, q_amounts
    )

    return BudgetAllocationReclassification.objects.create(
        source_allocation=source_allocation,
        source_credit=source_credit,
        **target_params,
        q1_amount=amounts[0],
        q2_amount=amounts[1],
        q3_amount=amounts[2],
        q4_amount=amounts[3],
        status='PENDIENTE',
        notes=notes,
        user=user,
        requested_by=user,
    )


@transaction.atomic
def approve_allocation_reclassification(reclassification_id, user):
    item = BudgetAllocationReclassification.objects.select_for_update().get(pk=reclassification_id)
    if item.status != 'PENDIENTE':
        raise ValidationError("Solo se pueden aprobar reclasificaciones pendientes.")
    if not item.source_allocation_id or not item.source_credit_id:
        raise ValidationError("La solicitud ya no tiene una distribucion o credito de origen disponible.")

    source_allocation = BudgetAllocation.objects.select_for_update().get(pk=item.source_allocation_id)
    source_credit = BudgetCredit.objects.select_for_update().get(pk=item.source_credit_id)
    _validate_allocation_reclassification(
        source_allocation,
        source_credit,
        _reclassification_target_params(item),
        (item.q1_amount, item.q2_amount, item.q3_amount, item.q4_amount),
        exclude_reclassification_id=item.pk,
    )
    item.status = 'APROBADO'
    item.approved_by = user
    item.save(update_fields=['status', 'approved_by', 'updated_at'])
    return item


@transaction.atomic
def reject_allocation_reclassification(reclassification_id):
    item = BudgetAllocationReclassification.objects.select_for_update().get(pk=reclassification_id)
    if item.status not in RECLASSIFICATION_ACTIVE_STATUSES:
        raise ValidationError("Esta reclasificacion ya fue procesada.")
    item.status = 'RECHAZADO'
    item.save(update_fields=['status', 'updated_at'])
    return item


@transaction.atomic
def execute_allocation_reclassification(reclassification_id, user):
    item = BudgetAllocationReclassification.objects.select_for_update().get(pk=reclassification_id)
    if item.status != 'APROBADO':
        raise ValidationError("La reclasificacion debe estar aprobada antes de ejecutarse.")
    if not item.source_allocation_id or not item.source_credit_id:
        raise ValidationError("La solicitud ya no tiene una distribucion o credito de origen disponible.")

    source_allocation = BudgetAllocation.objects.select_for_update().select_related(
        'unit'
    ).prefetch_related('custom_classes').get(pk=item.source_allocation_id)
    source_credit = BudgetCredit.objects.select_for_update().get(pk=item.source_credit_id)
    target_params = _reclassification_target_params(item)
    amounts = _validate_allocation_reclassification(
        source_allocation,
        source_credit,
        target_params,
        (item.q1_amount, item.q2_amount, item.q3_amount, item.q4_amount),
        exclude_reclassification_id=item.pk,
    )

    for field, amount in zip(QUARTER_FIELDS, amounts):
        setattr(source_allocation, field, getattr(source_allocation, field) - amount)
        setattr(source_credit, field, getattr(source_credit, field) - amount)
    source_allocation.save()
    source_credit.save()

    target_credit = BudgetCredit.objects.select_for_update().filter(
        fiscal_year=source_credit.fiscal_year,
        credit_type_id=source_credit.credit_type_id,
        ff=target_params['target_ff'],
        programa_id=source_credit.programa_id,
        subprog=target_params['target_subprog'],
        inc=target_params['target_inc'],
        ppp_inc=target_params['target_ppp_inc'],
        pp_inc=target_params['target_pp_inc'],
        pre_inc=target_params['target_pre_inc'],
        incisos_agrupado=target_params['target_incisos_agrupado'],
    ).first()
    if not target_credit:
        target_credit = BudgetCredit.objects.create(
            fiscal_year=source_credit.fiscal_year,
            credit_type_id=source_credit.credit_type_id,
            ff=target_params['target_ff'],
            programa_id=source_credit.programa_id,
            subprog=target_params['target_subprog'],
            inc=target_params['target_inc'],
            ppp_inc=target_params['target_ppp_inc'],
            pp_inc=target_params['target_pp_inc'],
            pre_inc=target_params['target_pre_inc'],
            incisos_agrupado=target_params['target_incisos_agrupado'],
        )

    for field, amount in zip(QUARTER_FIELDS, amounts):
        setattr(target_credit, field, getattr(target_credit, field) + amount)
    target_credit.save()

    target_allocation = BudgetAllocation.objects.create(
        credit=target_credit,
        unit=source_allocation.unit,
        q1_amount=amounts[0],
        q2_amount=amounts[1],
        q3_amount=amounts[2],
        q4_amount=amounts[3],
        notes=item.notes or source_allocation.notes,
    )
    target_allocation.custom_classes.set(source_allocation.custom_classes.all())

    item.target_credit = target_credit
    item.target_allocation = target_allocation
    item.status = 'EJECUTADO'
    item.executed_by = user
    item.save(update_fields=['target_credit', 'target_allocation', 'status', 'executed_by', 'updated_at'])
    return target_allocation
