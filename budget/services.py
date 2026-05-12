from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F
from .models import (
    BudgetFiscalYear, BudgetFF, BudgetSubprog, BudgetProg,
    BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado,
    BudgetInc, BudgetCredit, BudgetAllocation, BudgetExecution,
    BudgetCreditTypeLog, BudgetCompensacion, InsufficientFundsError
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
def allocate_credit(credit, unit, q1=0, q2=0, q3=0, q4=0, notes=""):
    amount = q1 + q2 + q3 + q4
    if amount <= 0:
        raise ValidationError("El monto total a distribuir debe ser mayor a cero.")

    # Validaciones contra el crédito de origen por cada trimestre
    allocated_q1 = credit.allocations.aggregate(Sum('q1_amount'))['q1_amount__sum'] or 0
    allocated_q2 = credit.allocations.aggregate(Sum('q2_amount'))['q2_amount__sum'] or 0
    allocated_q3 = credit.allocations.aggregate(Sum('q3_amount'))['q3_amount__sum'] or 0
    allocated_q4 = credit.allocations.aggregate(Sum('q4_amount'))['q4_amount__sum'] or 0

    if allocated_q1 + q1 > credit.q1_amount:
        raise ValidationError(f"La distribución en T1 (${q1}) supera el disponible del crédito (${credit.q1_amount - allocated_q1}).")
    if allocated_q2 + q2 > credit.q2_amount:
        raise ValidationError(f"La distribución en T2 (${q2}) supera el disponible del crédito (${credit.q2_amount - allocated_q2}).")
    if allocated_q3 + q3 > credit.q3_amount:
        raise ValidationError(f"La distribución en T3 (${q3}) supera el disponible del crédito (${credit.q3_amount - allocated_q3}).")
    if allocated_q4 + q4 > credit.q4_amount:
        raise ValidationError(f"La distribución en T4 (${q4}) supera el disponible del crédito (${credit.q4_amount - allocated_q4}).")
    
    return BudgetAllocation.objects.create(
        credit=credit, unit=unit, 
        q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
        notes=notes
    )


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
        allocations = BudgetAllocation.objects.filter(unit=unit, credit__fiscal_year=fiscal_year).select_related('credit__ff', 'credit__programa', 'credit__subprog', 'credit__inc', 'credit__ppp_inc', 'credit__pp_inc', 'credit__pre_inc')
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
                'notes': alloc.notes
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
    Registra la acción en el historial.
    """
    if unassign_amount and unassign_amount > 0:
        # Descontamos de los trimestres de atrás hacia adelante
        remaining = unassign_amount
        for q_attr in ['q4_amount', 'q3_amount', 'q2_amount', 'q1_amount']:
            if remaining <= 0: break
            current_q = getattr(credit, q_attr)
            if current_q >= remaining:
                setattr(credit, q_attr, current_q - remaining)
                remaining = 0
            else:
                remaining -= current_q
                setattr(credit, q_attr, 0)
        
        # El save() del modelo BudgetCredit recalculará el total_amount
    
    # Mantenemos el tipo (No lo limpiamos para permitir múltiples desasignaciones parciales)
    previous_type = credit.credit_type
    # credit.credit_type = None  <-- Se elimina esta línea
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

@transaction.atomic
def request_compensacion(fiscal_year, programa, source_credit, target_params, q_amounts, user, notes=""):
    """
    Crea una solicitud de compensación validando fondos disponibles.
    """
    if source_credit.programa != programa:
        raise ValidationError("El crédito de origen no pertenece al programa seleccionado.")
    
    q1, q2, q3, q4 = q_amounts
    if q1 > source_credit.q1_amount or q2 > source_credit.q2_amount or q3 > source_credit.q3_amount or q4 > source_credit.q4_amount:
        raise ValidationError("Fondos insuficientes en uno o más trimestres del crédito de origen.")
    
    return BudgetCompensacion.objects.create(
        fiscal_year=fiscal_year,
        programa=programa,
        source_credit=source_credit,
        **target_params,
        q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
        requested_by=user,
        notes=notes
    )

@transaction.atomic
def execute_compensacion(compensacion_id, user):
    """
    Ejecuta el movimiento de fondos de forma atómica.
    """
    comp = BudgetCompensacion.objects.select_for_update().get(pk=compensacion_id)
    
    if comp.status != 'PENDIENTE':
        raise ValidationError("Esta compensación ya ha sido procesada o ejecutada.")
    
    source = comp.source_credit
    
    # 1. Restar de origen
    source.q1_amount -= comp.q1_amount
    source.q2_amount -= comp.q2_amount
    source.q3_amount -= comp.q3_amount
    source.q4_amount -= comp.q4_amount
    source.save()
    
    # 2. Buscar o crear destino (tomamos el más reciente si hay varios)
    target = BudgetCredit.objects.filter(
        fiscal_year=comp.fiscal_year,
        credit_type=source.credit_type,
        ff=comp.target_ff,
        programa=comp.programa,
        subprog=comp.target_subprog,
        inc=comp.target_inc,
        ppp_inc=comp.target_ppp_inc,
        pp_inc=comp.target_pp_inc,
        pre_inc=comp.target_pre_inc,
        incisos_agrupado=comp.target_incisos_agrupado,
    ).first()
    
    if not target:
        target = BudgetCredit.objects.create(
            fiscal_year=comp.fiscal_year,
            credit_type=source.credit_type,
            ff=comp.target_ff,
            programa=comp.programa,
            subprog=comp.target_subprog,
            inc=comp.target_inc,
            ppp_inc=comp.target_ppp_inc,
            pp_inc=comp.target_pp_inc,
            pre_inc=comp.target_pre_inc,
            incisos_agrupado=comp.target_incisos_agrupado,
        )
    
    # 3. Sumar a destino
    target.q1_amount += comp.q1_amount
    target.q2_amount += comp.q2_amount
    target.q3_amount += comp.q3_amount
    target.q4_amount += comp.q4_amount
    target.save()
    
    # 4. Marcar como ejecutada
    comp.status = 'EJECUTADO'
    comp.approved_by = user
    comp.save()
    
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

    # Si el usuario no envió un monto (campo vacío), mantenemos el actual
    q1_new = q1_new if q1_new is not None else credit.q1_amount
    q2_new = q2_new if q2_new is not None else credit.q2_amount
    q3_new = q3_new if q3_new is not None else credit.q3_amount
    q4_new = q4_new if q4_new is not None else credit.q4_amount

    if q1_new < q1_a: raise ValidationError(f"T1: El nuevo monto (${q1_new}) es inferior a lo ya distribuido (${q1_a}).")
    if q2_new < q2_a: raise ValidationError(f"T2: El nuevo monto (${q2_new}) es inferior a lo ya distribuido (${q2_a}).")
    if q3_new < q3_a: raise ValidationError(f"T3: El nuevo monto (${q3_new}) es inferior a lo ya distribuido (${q3_a}).")
    if q4_new < q4_a: raise ValidationError(f"T4: El nuevo monto (${q4_new}) es inferior a lo ya distribuido (${q4_a}).")

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
