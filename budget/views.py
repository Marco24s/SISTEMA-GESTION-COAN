from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal
from django.contrib import messages
from django.db import models
from django.db.models import Sum, F, OuterRef, ProtectedError, Q
from django.db.models.functions import Coalesce
from .models import (
    BudgetFiscalYear, BudgetFF, BudgetSubprog, BudgetProg,
    BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado,
    BudgetInc, BudgetCredit, BudgetAllocation, BudgetExecution,
    BudgetClassification, BudgetCreditType, BudgetCreditTypeLog, BudgetCompensacion,
    BudgetAllocationReclassification, BudgetTipoGasto, InsufficientFundsError
)
import csv
from django.http import HttpResponse
from .forms import (
    BudgetFiscalYearForm, BudgetCreditForm, BudgetAllocationForm, BudgetAllocationMetadataForm,
    BudgetAllocationReclassificationForm,
    BudgetExecutionCommitmentForm, BudgetExecutionAccrualForm, 
    BudgetExecutionPaymentForm, BudgetClassificationForm, BudgetClassificationAssignForm,
    BudgetCompensacionForm, BudgetFFForm, BudgetSubprogForm, BudgetProgForm,
    BudgetPPPIncForm, BudgetPPIncForm, BudgetPreIncForm,
    BudgetIncisosAgrupadoForm, BudgetIncForm, BudgetCreditTypeForm,
    BudgetCreditAdjustmentForm, BudgetTipoGastoForm
)
from . import services
from core.decorators import pin_required
from django.contrib.auth.decorators import login_required

def is_admin(user):
    return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()

def is_strict_admin(user):
    return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()

def _get_fiscal_year_from_request(request):
    """Obtiene el ejercicio económico del parámetro ?year= o el activo por defecto.
    Limpia separadores de miles (ej: '2.026' -> '2026') que Django agrega con L10N."""
    raw = request.GET.get('year', '').replace('.', '').replace(',', '').strip()
    if raw:
        try:
            return BudgetFiscalYear.objects.filter(year=int(raw)).first()
        except (ValueError, TypeError):
            pass
    return BudgetFiscalYear.objects.filter(status='OPEN').first()

@login_required
def dashboard(request):
    fiscal_year = BudgetFiscalYear.objects.filter(status='OPEN').first()
    is_admin_user = is_admin(request.user)
    stats = {
        'total_credit': 0, 'total_allocated': 0, 'total_commitment': 0,
        'total_accrued': 0, 'total_paid': 0, 'available_to_allocate': 0,
        'available_to_execute': 0
    }
    unit_report = []
    if fiscal_year:
        if is_admin(request.user):
            credits = BudgetCredit.objects.filter(fiscal_year=fiscal_year)
            allocations = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year)
            executions = BudgetExecution.objects.filter(allocation__credit__fiscal_year=fiscal_year)
            unit_report = services.get_unit_execution_report(fiscal_year)
        else:
            credits = BudgetCredit.objects.filter(fiscal_year=fiscal_year, allocations__unit=request.user.unit)
            allocations = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year, unit=request.user.unit)
            executions = BudgetExecution.objects.filter(allocation__unit=request.user.unit)
            full_report = services.get_unit_execution_report(fiscal_year)
            unit_report = [r for r in full_report if r['unit'] == request.user.unit]

        if is_admin_user:
            stats['total_credit'] = credits.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        else:
            # Para unidades, su "Crédito Total" es la suma de lo que tienen asignado (Techos)
            stats['total_credit'] = allocations.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
            
        stats['total_allocated'] = allocations.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
        stats['total_commitment'] = executions.aggregate(Sum('commitment_amount'))['commitment_amount__sum'] or 0
        stats['total_accrued'] = executions.aggregate(Sum('accrued_amount'))['accrued_amount__sum'] or 0
        stats['total_paid'] = executions.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        stats['available_to_allocate'] = stats['total_credit'] - stats['total_allocated']
        stats['available_to_execute'] = stats['total_allocated'] - stats['total_commitment']
        
        # Agregación por trimestre y tipo
        for q in ['q1', 'q2', 'q3', 'q4']:
            field = f'{q}_amount'
            if is_admin_user:
                stats[f'{q}_total'] = credits.aggregate(Sum(field))[f'{field}__sum'] or 0
                stats[f'{q}_asignacion'] = credits.filter(credit_type__code='ASIGNACION').aggregate(Sum(field))[f'{field}__sum'] or 0
                stats[f'{q}_refuerzo'] = credits.filter(credit_type__code='REFUERZO').aggregate(Sum(field))[f'{field}__sum'] or 0
            else:
                stats[f'{q}_total'] = allocations.aggregate(Sum(field))[f'{field}__sum'] or 0
                stats[f'{q}_asignacion'] = allocations.filter(credit__credit_type__code='ASIGNACION').aggregate(Sum(field))[f'{field}__sum'] or 0
                stats[f'{q}_refuerzo'] = allocations.filter(credit__credit_type__code='REFUERZO').aggregate(Sum(field))[f'{field}__sum'] or 0

        # Cálculo de anchos para la barra de progreso trimestral (basado en compromisos REALES por fecha)
        q1_t, q2_t, q3_t, q4_t = stats['q1_total'], stats['q2_total'], stats['q3_total'], stats['q4_total']
        
        # Agrupación de compromisos por trimestre de ASIGNACIÓN (FIFO)
        q1_c = q2_c = q3_c = q4_c = 0
        for alloc in allocations:
            rem = alloc.spent_amount
            p1 = min(rem, alloc.q1_amount); q1_c += p1; rem -= p1
            p2 = min(rem, alloc.q2_amount); q2_c += p2; rem -= p2
            p3 = min(rem, alloc.q3_amount); q3_c += p3; rem -= p3
            p4 = min(rem, alloc.q4_amount); q4_c += p4; rem -= p4

        stats['q1_fill'] = (q1_c / q1_t * 100) if q1_t > 0 else 0
        stats['q2_fill'] = (q2_c / q2_t * 100) if q2_t > 0 else 0
        stats['q3_fill'] = (q3_c / q3_t * 100) if q3_t > 0 else 0
        stats['q4_fill'] = (q4_c / q4_t * 100) if q4_t > 0 else 0
        
        # Cálculo de anchos para la barra de DISTRIBUCIÓN (Techos REALES por trimestre)
        stats['q1_alloc'] = allocations.aggregate(Sum('q1_amount'))['q1_amount__sum'] or 0
        stats['q2_alloc'] = allocations.aggregate(Sum('q2_amount'))['q2_amount__sum'] or 0
        stats['q3_alloc'] = allocations.aggregate(Sum('q3_amount'))['q3_amount__sum'] or 0
        stats['q4_alloc'] = allocations.aggregate(Sum('q4_amount'))['q4_amount__sum'] or 0

        # Saldos disponibles por distribuir en cada trimestre
        stats['q1_available'] = stats['q1_total'] - stats['q1_alloc']
        stats['q2_available'] = stats['q2_total'] - stats['q2_alloc']
        stats['q3_available'] = stats['q3_total'] - stats['q3_alloc']
        stats['q4_available'] = stats['q4_total'] - stats['q4_alloc']

        stats['q1_alloc_fill'] = (stats['q1_alloc'] / q1_t * 100) if q1_t > 0 else 0
        stats['q2_alloc_fill'] = (stats['q2_alloc'] / q2_t * 100) if q2_t > 0 else 0
        stats['q3_alloc_fill'] = (stats['q3_alloc'] / q3_t * 100) if q3_t > 0 else 0
        stats['q4_alloc_fill'] = (stats['q4_alloc'] / q4_t * 100) if q4_t > 0 else 0

        # Detalle para Tooltips (Desglose por partida)
        def get_q_tooltip(q_idx):
            import json as _json
            field_name = f'q{q_idx}_amount'
            if is_admin_user:
                q_credits = credits.annotate(
                    q_total=F(field_name),
                    q_alloc=Coalesce(Sum(f'allocations__{field_name}'), 0, output_field=models.DecimalField())
                ).filter(models.Q(q_total__gt=0) | models.Q(q_alloc__gt=0)).prefetch_related('allocations__unit')
            else:
                q_credits = credits.annotate(
                    q_total=Coalesce(Sum(f'allocations__{field_name}', filter=models.Q(allocations__unit=request.user.unit)), 0, output_field=models.DecimalField()),
                    q_alloc=models.Value(0, output_field=models.DecimalField())
                ).filter(q_total__gt=0).prefetch_related(
                    models.Prefetch('allocations', queryset=BudgetAllocation.objects.filter(unit=request.user.unit))
                )

            table_rows = []
            for c in q_credits:
                avail = c.q_total - c.q_alloc
                t_str = f"{c.q_total:,.0f}".replace(",", ".")
                a_str = f"{c.q_alloc:,.0f}".replace(",", ".")
                v_str = f"{avail:,.0f}".replace(",", ".")
                compensation_filter = {f'{field_name}__gt': 0}
                is_compensated = BudgetCompensacion.objects.filter(
                    status='EJECUTADO',
                    source_credit=c,
                    **compensation_filter,
                ).exists() or BudgetCompensacion.objects.filter(
                    fiscal_year=fiscal_year,
                    status='EJECUTADO',
                    programa=c.programa,
                    target_ff=c.ff,
                    target_subprog=c.subprog,
                    target_inc=c.inc,
                    target_ppp_inc=c.ppp_inc,
                    target_pp_inc=c.pp_inc,
                    target_pre_inc=c.pre_inc,
                    target_incisos_agrupado=c.incisos_agrupado,
                    **compensation_filter,
                ).exists()
                compensation_badge = (
                    " <span class='badge rounded-pill text-bg-light border text-primary ms-1'>Compensado</span>"
                    if is_compensated else ""
                )
                available_class = "text-danger" if avail < 0 else "text-info"

                # Construir lista de distribuciones para este crédito y trimestre
                alloc_data = []
                for alloc in c.allocations.all():
                    q_val = getattr(alloc, field_name, 0) or 0
                    if q_val > 0:
                        alloc_data.append({
                            'unit': alloc.unit.name,
                            'subpc': c.pre_inc.code if c.pre_inc else "--",
                            'amount': f"{q_val:,.0f}".replace(",", "."),
                        })

                # Serializar y escapar para atributo HTML
                alloc_json = _json.dumps(alloc_data, ensure_ascii=False).replace("'", "&#39;").replace('"', '&quot;')
                credit_label = str(c).replace("'", "&#39;")

                if alloc_data:
                    dist_cell = (
                        f"<button type='button' class='btn btn-link btn-sm p-0 text-success fw-bold distrib-btn' "
                        f"data-credit='{credit_label}' data-allocations='{alloc_json}' "
                        f"title='Ver distribución por unidad'>"
                        f"${a_str} <i class='fa-solid fa-users fa-xs opacity-50 ms-1'></i>"
                        f"</button>"
                    )
                else:
                    dist_cell = f"<span class='text-success fw-bold'>${a_str}</span>"

                table_rows.append(
                    f"<tr>"
                    f"  <td class='small fw-bold'>{c}{compensation_badge}</td>"
                    f"  <td class='text-end small fw-semibold'>${t_str}</td>"
                    f"  <td class='text-end small'>{dist_cell}</td>"
                    f"  <td class='text-end small {available_class} fw-bold'>${v_str}</td>"
                    f"</tr>"
                )

            if not table_rows:
                return "<p class='text-muted text-center my-3'>No hay movimientos en este trimestre.</p>"

            table_header = (
                "<div class='table-responsive'>"
                "<table class='table table-sm table-hover align-middle mb-0'>"
                "  <thead class='bg-light text-muted'>"
                "    <tr style='font-size: 0.75rem; text-transform: uppercase;'>"
                "      <th class='ps-2'>Partida / Crédito</th>"
                "      <th class='text-end'>Cr&eacute;dito vigente</th>"
                "      <th class='text-end'>Distribuido</th>"
                "      <th class='text-end'>Por distribuir</th>"
                "    </tr>"
                "  </thead>"
                "  <tbody>"
            )
            return table_header + "".join(table_rows) + "</tbody></table></div>"

        stats['q1_tooltip'] = get_q_tooltip(1)
        stats['q2_tooltip'] = get_q_tooltip(2)
        stats['q3_tooltip'] = get_q_tooltip(3)
        stats['q4_tooltip'] = get_q_tooltip(4)

        # Ancho relativo de cada segmento (trimestre) respecto al total del presupuesto anual
        total_q = stats['total_credit']
        stats['q1_seg'] = (q1_t / total_q * 100) if total_q > 0 else 0
        stats['q2_seg'] = (q2_t / total_q * 100) if total_q > 0 else 0
        stats['q3_seg'] = (q3_t / total_q * 100) if total_q > 0 else 0
        stats['q4_seg'] = (q4_t / total_q * 100) if total_q > 0 else 0

        # Desglose por Tipo de Crédito y SUBPC
        if is_admin_user:
            raw_stats = (
                credits.filter(credit_type__isnull=False)
                .values('credit_type__name', 'credit_type__code', 'pre_inc__code')
                .annotate(subtotal=Sum('total_amount'))
                .order_by('credit_type__code', 'pre_inc__code')
            )
        else:
            raw_stats = (
                credits.filter(credit_type__isnull=False)
                .values('credit_type__name', 'credit_type__code', 'pre_inc__code')
                .annotate(subtotal=Sum('allocations__allocated_amount', filter=Q(allocations__unit=request.user.unit)))
                .order_by('credit_type__code', 'pre_inc__code')
            )

        # Agrupar en Python para facilitar el renderizado
        grouped_stats = {}
        for item in raw_stats:
            code = item['credit_type__code']
            if code not in grouped_stats:
                grouped_stats[code] = {
                    'code': code,
                    'name': item['credit_type__name'],
                    'total': 0,
                    'subpcs': [],
                    'q1': Decimal('0'), 'q2': Decimal('0'),
                    'q3': Decimal('0'), 'q4': Decimal('0'),
                    'allocated_q1': Decimal('0'), 'allocated_q2': Decimal('0'),
                    'allocated_q3': Decimal('0'), 'allocated_q4': Decimal('0'),
                    'allocated': Decimal('0'),
                    'details': [],
                    'subpc_lookup': {},
                }
            grouped_stats[code]['total'] += item['subtotal'] or 0
            if item['subtotal'] and item['subtotal'] > 0:
                subpc_code = item['pre_inc__code'] or 'S/D'
                subpc = {
                    'code': subpc_code,
                    'amount': item['subtotal'],
                    'total': item['subtotal'],
                    'q1': Decimal('0'), 'q2': Decimal('0'),
                    'q3': Decimal('0'), 'q4': Decimal('0'),
                    'allocated_q1': Decimal('0'), 'allocated_q2': Decimal('0'),
                    'allocated_q3': Decimal('0'), 'allocated_q4': Decimal('0'),
                    'allocated': Decimal('0'),
                    'details': [],
                    'modal_id': f"credit-type-{len(grouped_stats)}-subpc-{len(grouped_stats[code]['subpcs']) + 1}",
                }
                grouped_stats[code]['subpcs'].append(subpc)
                grouped_stats[code]['subpc_lookup'][subpc_code] = subpc

        if is_admin_user:
            detail_credits = BudgetCredit.objects.filter(
                fiscal_year=fiscal_year,
                credit_type__isnull=False,
            ).select_related(
                'credit_type', 'ff', 'programa', 'subprog', 'inc',
                'ppp_inc', 'pre_inc',
            ).prefetch_related('allocations')

            for credit in detail_credits:
                row = grouped_stats.get(credit.credit_type.code)
                if not row:
                    continue
                subpc = row['subpc_lookup'].get(credit.pre_inc.code if credit.pre_inc else 'S/D')
                if not subpc:
                    continue
                amounts = [credit.q1_amount, credit.q2_amount, credit.q3_amount, credit.q4_amount]
                allocated_quarters = [
                    sum((getattr(allocation, f'q{quarter}_amount') for allocation in credit.allocations.all()), Decimal('0'))
                    for quarter in range(1, 5)
                ]
                for quarter, amount in enumerate(amounts, start=1):
                    row[f'q{quarter}'] += amount
                    subpc[f'q{quarter}'] += amount
                    row[f'allocated_q{quarter}'] += allocated_quarters[quarter - 1]
                    subpc[f'allocated_q{quarter}'] += allocated_quarters[quarter - 1]
                row['allocated'] += sum(allocated_quarters, Decimal('0'))
                subpc['allocated'] += sum(allocated_quarters, Decimal('0'))
                detail = {
                    'ff': credit.ff.code if credit.ff else '-',
                    'programa': credit.programa.code if credit.programa else '-',
                    'subprograma': credit.subprog.code if credit.subprog else '-',
                    'inciso': credit.inc.code if credit.inc else '-',
                    'ppal': credit.ppp_inc.code if credit.ppp_inc else '-',
                    'subpc': credit.pre_inc.code if credit.pre_inc else '-',
                    'q1': amounts[0], 'q2': amounts[1],
                    'q3': amounts[2], 'q4': amounts[3],
                    'total': sum(amounts, Decimal('0')),
                }
                row['details'].append(detail)
                subpc['details'].append(detail)
        else:
            detail_allocations = allocations.filter(
                credit__credit_type__isnull=False,
            ).select_related(
                'credit__credit_type', 'credit__ff', 'credit__programa',
                'credit__subprog', 'credit__inc', 'credit__ppp_inc', 'credit__pre_inc',
            )
            for allocation in detail_allocations:
                credit = allocation.credit
                row = grouped_stats.get(credit.credit_type.code)
                if not row:
                    continue
                subpc = row['subpc_lookup'].get(credit.pre_inc.code if credit.pre_inc else 'S/D')
                if not subpc:
                    continue
                amounts = [allocation.q1_amount, allocation.q2_amount, allocation.q3_amount, allocation.q4_amount]
                for quarter, amount in enumerate(amounts, start=1):
                    row[f'q{quarter}'] += amount
                    subpc[f'q{quarter}'] += amount
                    row[f'allocated_q{quarter}'] += amount
                    subpc[f'allocated_q{quarter}'] += amount
                row['allocated'] += sum(amounts, Decimal('0'))
                subpc['allocated'] += sum(amounts, Decimal('0'))
                detail = {
                    'ff': credit.ff.code if credit.ff else '-',
                    'programa': credit.programa.code if credit.programa else '-',
                    'subprograma': credit.subprog.code if credit.subprog else '-',
                    'inciso': credit.inc.code if credit.inc else '-',
                    'ppal': credit.ppp_inc.code if credit.ppp_inc else '-',
                    'subpc': credit.pre_inc.code if credit.pre_inc else '-',
                    'q1': amounts[0], 'q2': amounts[1],
                    'q3': amounts[2], 'q4': amounts[3],
                    'total': sum(amounts, Decimal('0')),
                }
                row['details'].append(detail)
                subpc['details'].append(detail)

        for row in grouped_stats.values():
            row['available'] = row['total'] - row['allocated']
            for subpc in row['subpcs']:
                subpc['available'] = subpc['total'] - subpc['allocated']

        stats['credit_by_type'] = grouped_stats.values()

        # Desglose de credito distribuido por SUBPC, trimestre y unidad.
        allocated_groups = {}
        allocation_details = allocations.select_related(
            'unit', 'credit__ff', 'credit__programa', 'credit__subprog',
            'credit__inc', 'credit__ppp_inc', 'credit__pre_inc',
        )
        for allocation in allocation_details:
            credit = allocation.credit
            subpc_code = credit.pre_inc.code if credit.pre_inc else 'S/D'
            if subpc_code not in allocated_groups:
                allocated_groups[subpc_code] = {
                    'code': subpc_code,
                    'subtotal': Decimal('0'),
                    'spent': Decimal('0'),
                    'q1': Decimal('0'), 'q2': Decimal('0'),
                    'q3': Decimal('0'), 'q4': Decimal('0'),
                    'details': [],
                    'modal_id': f"allocated-subpc-{len(allocated_groups) + 1}",
                }

            row = allocated_groups[subpc_code]
            amounts = [allocation.q1_amount, allocation.q2_amount, allocation.q3_amount, allocation.q4_amount]
            row['subtotal'] += sum(amounts, Decimal('0'))
            row['spent'] += allocation.spent_amount
            for quarter, amount in enumerate(amounts, start=1):
                row[f'q{quarter}'] += amount
            row['details'].append({
                'unit': allocation.unit.name,
                'ff': credit.ff.code if credit.ff else '-',
                'programa': credit.programa.code if credit.programa else '-',
                'subprograma': credit.subprog.code if credit.subprog else '-',
                'inciso': credit.inc.code if credit.inc else '-',
                'ppal': credit.ppp_inc.code if credit.ppp_inc else '-',
                'q1': amounts[0], 'q2': amounts[1],
                'q3': amounts[2], 'q4': amounts[3],
                'total': sum(amounts, Decimal('0')),
            })

        for row in allocated_groups.values():
            row['available'] = row['subtotal'] - row['spent']
        stats['allocated_by_subpc'] = [allocated_groups[key] for key in sorted(allocated_groups)]

    return render(request, 'budget/dashboard.html', {'fiscal_year': fiscal_year, 'stats': stats, 'unit_report': unit_report, 'is_admin': is_admin_user})

def budget_statistics(request):
    fiscal_year = BudgetFiscalYear.objects.filter(status='OPEN').first()
    if not fiscal_year:
        return redirect('budget:dashboard')

    is_admin_user = is_admin(request.user)
    
    # 1. Crédito por Tipo
    if is_admin_user:
        credit_by_type = BudgetCredit.objects.filter(fiscal_year=fiscal_year, credit_type__isnull=False).values('credit_type__name').annotate(total=Sum('total_amount'))
    else:
        # Para unidades, usamos el monto asignado (Tech) con filtro explícito para evitar duplicados en el JOIN
        credit_by_type = BudgetCredit.objects.filter(
            fiscal_year=fiscal_year, 
            credit_type__isnull=False, 
            allocations__unit=request.user.unit
        ).values('credit_type__name').annotate(
            total=Sum('allocations__allocated_amount', filter=Q(allocations__unit=request.user.unit))
        )
        
    # 2. Crédito por SUBPC
    if is_admin_user:
        credit_by_subpc = BudgetCredit.objects.filter(fiscal_year=fiscal_year).values('pre_inc__code').annotate(total=Sum('total_amount')).order_by('pre_inc__code')
    else:
        credit_by_subpc = BudgetCredit.objects.filter(
            fiscal_year=fiscal_year, 
            allocations__unit=request.user.unit
        ).values('pre_inc__code').annotate(
            total=Sum('allocations__allocated_amount', filter=Q(allocations__unit=request.user.unit))
        ).order_by('pre_inc__code')

    # 3. Estado de Ejecución (Etapas)
    if is_admin_user:
        exec_stats = BudgetExecution.objects.filter(allocation__credit__fiscal_year=fiscal_year).aggregate(
            commitment=Sum('commitment_amount'),
            accrued=Sum('accrued_amount'),
            paid=Sum('paid_amount')
        )
        total_credit = BudgetCredit.objects.filter(fiscal_year=fiscal_year).aggregate(total=Sum('total_amount'))['total'] or 0
    else:
        exec_stats = BudgetExecution.objects.filter(allocation__unit=request.user.unit, allocation__credit__fiscal_year=fiscal_year).aggregate(
            commitment=Sum('commitment_amount'),
            accrued=Sum('accrued_amount'),
            paid=Sum('paid_amount')
        )
        total_credit = BudgetAllocation.objects.filter(unit=request.user.unit, credit__fiscal_year=fiscal_year).aggregate(total=Sum('allocated_amount'))['total'] or 0

    commitment = exec_stats['commitment'] or 0
    accrued = exec_stats['accrued'] or 0
    paid = exec_stats['paid'] or 0
    balance = total_credit - commitment

    execution_stages = [
        {'name': 'Por Ejecutar (Saldo)', 'value': float(balance)},
        {'name': 'Comprometido (Sin Devengar)', 'value': float(commitment - accrued)},
        {'name': 'Devengado (Sin Pagar)', 'value': float(accrued - paid)},
        {'name': 'Pagado', 'value': float(paid)},
    ]

    # 4. Distribución por Unidad (Solo para Admins)
    unit_distribution = []
    if is_admin_user:
        unit_distribution = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year).values('unit__name').annotate(total=Sum('allocated_amount')).order_by('-total')

    context = {
        'fiscal_year': fiscal_year,
        'credit_by_type_json': list(credit_by_type),
        'credit_by_subpc_json': list(credit_by_subpc),
        'execution_stages_json': execution_stages,
        'unit_distribution_json': list(unit_distribution),
        'total_credit': total_credit,
        'is_admin': is_admin_user
    }
    
    return render(request, 'budget/statistics.html', context)

def fiscal_year_list(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    years = BudgetFiscalYear.objects.all().order_by('-year')
    return render(request, 'budget/fiscal_year_list.html', {'years': years})

def fiscal_year_create(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    if request.method == 'POST':
        form = BudgetFiscalYearForm(request.POST)
        if form.is_valid():
            services.create_fiscal_year(year=form.cleaned_data['year'], notes=form.cleaned_data['notes'])
            return redirect('budget:fiscal_year_list')
    else: form = BudgetFiscalYearForm()
    return render(request, 'budget/form_base.html', {'form': form, 'title': 'Crear Ejercicio Económico'})

def fiscal_year_update(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    year = get_object_or_404(BudgetFiscalYear, pk=pk)
    if request.method == 'POST':
        form = BudgetFiscalYearForm(request.POST, instance=year)
        if form.is_valid():
            form.save()
            messages.success(request, f"Ejercicio {year.year} actualizado.")
            return redirect('budget:fiscal_year_list')
    else:
        form = BudgetFiscalYearForm(instance=year)
    return render(request, 'budget/form_base.html', {'form': form, 'title': f'Editar Ejercicio {year.year}'})

def fiscal_year_close(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    year = get_object_or_404(BudgetFiscalYear, pk=pk)
    all_executions = BudgetExecution.objects.filter(allocation__credit__fiscal_year=year)
    pending_reprogram = []
    for e in all_executions:
        if e.commitment_amount > e.accrued_amount:
            e.pending_balance = e.commitment_amount - e.accrued_amount
            pending_reprogram.append(e)
    if request.method == 'POST':
        services.close_fiscal_year(year)
        return redirect('budget:fiscal_year_list')
    return render(request, 'budget/fiscal_year_close.html', {'year': year, 'pending_reprogram': pending_reprogram})

def credit_list(request):
    from django.db.models import Sum, Q
    is_admin_user = is_admin(request.user)
    
    fiscal_year = _get_fiscal_year_from_request(request)
    years = BudgetFiscalYear.objects.all().order_by('-year')

    base_qs = BudgetCredit.objects.select_related(
        'fiscal_year', 'ff', 'programa', 'subprog', 'inc',
        'ppp_inc', 'pp_inc', 'pre_inc', 'incisos_agrupado', 'credit_type',
    )
    if fiscal_year:
        base_qs = base_qs.filter(fiscal_year=fiscal_year)
    
    if is_admin_user:
        credits = base_qs.annotate(
            distributed_amount=Sum('allocations__allocated_amount')
        ).order_by(
            'fiscal_year', 'ff', 'programa', 'subprog',
            'inc__code', 'ppp_inc__code', 'pp_inc__code', 
            'pre_inc__code', 'incisos_agrupado__code'
        )
        
        raw_stats = (
            credits.filter(credit_type__isnull=False)
            .values('credit_type__name', 'credit_type__code', 'pre_inc__code')
            .annotate(subtotal=Sum('total_amount'))
            .order_by('credit_type__name', 'pre_inc__code')
        )
        unassigned_total = credits.filter(credit_type__isnull=True).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    else:
        # Para unidades, mostramos solo sus distribuciones
        credits = base_qs.filter(allocations__unit=request.user.unit).annotate(
            distributed_amount=Sum('allocations__allocated_amount', filter=Q(allocations__unit=request.user.unit))
        ).distinct().order_by(
            'fiscal_year', 'ff', 'programa', 'subprog',
            'inc__code', 'ppp_inc__code', 'pp_inc__code', 
            'pre_inc__code', 'incisos_agrupado__code'
        )
        
        raw_stats = (
            credits.filter(credit_type__isnull=False)
            .values('credit_type__name', 'credit_type__code', 'pre_inc__code')
            .annotate(subtotal=Sum('allocations__allocated_amount', filter=Q(allocations__unit=request.user.unit)))
            .order_by('credit_type__name', 'pre_inc__code')
        )
        unassigned_total = credits.filter(credit_type__isnull=True).aggregate(
            total=Sum('allocations__allocated_amount', filter=Q(allocations__unit=request.user.unit))
        )['total'] or 0

    # Agrupar por tipo para el resumen inferior con saldos de distribución
    credit_by_type_dict = {}
    
    # Obtener distribuciones totales por tipo para admins
    dist_map = {}
    if is_admin_user and fiscal_year:
        dist_raw = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year).values('credit__credit_type__code', 'credit__pre_inc__code').annotate(total=Sum('allocated_amount'))
        dist_map = {(d['credit__credit_type__code'], d['credit__pre_inc__code']): d['total'] for d in dist_raw}

    for item in raw_stats:
        code = item['credit_type__code']
        subpc = item['pre_inc__code']
        if code not in credit_by_type_dict:
            credit_by_type_dict[code] = {
                'name': item['credit_type__name'],
                'code': item['credit_type__code'],
                'total_aapp': 0,
                'total_dist': 0,
                'subpcs': []
            }
        
        amount = item['subtotal'] or 0
        dist_amount = dist_map.get((code, subpc), amount if not is_admin_user else 0)
        
        credit_by_type_dict[code]['total_aapp'] += amount
        if is_admin_user:
            credit_by_type_dict[code]['total_dist'] += dist_amount
        else:
            # Para unidades, "total_dist" es su propio asignado
            credit_by_type_dict[code]['total_dist'] += amount

        if amount > 0:
            credit_by_type_dict[code]['subpcs'].append({
                'code': subpc or '00',
                'amount_aapp': amount,
                'amount_dist': dist_amount,
                'available': amount - dist_amount if is_admin_user else 0
            })
    
    credit_by_type = credit_by_type_dict.values()

    return render(request, 'budget/credit_list.html', {
        'credits': credits,
        'credit_by_type': credit_by_type,
        'unassigned_total': unassigned_total,
        'is_admin': is_admin_user,
        'fiscal_year': fiscal_year,
        'years': years
    })

def credit_detail(request, pk):
    credit = get_object_or_404(BudgetCredit, pk=pk)
    if not is_admin(request.user) and not credit.allocations.filter(unit=request.user.unit).exists():
        return redirect('budget:credit_list')
        
    allocations = credit.allocations.all().select_related('unit')
    total_allocated = allocations.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
    available_to_allocate = credit.total_amount - total_allocated
    
    # Calcular anchos para la barra de progreso segmentada
    total = credit.total_amount
    q1, q2, q3, q4 = credit.q1_amount, credit.q2_amount, credit.q3_amount, credit.q4_amount
    
    # Cálculo de anchos para la barra de progreso segmentada REAL
    q1_a = allocations.aggregate(Sum('q1_amount'))['q1_amount__sum'] or 0
    q2_a = allocations.aggregate(Sum('q2_amount'))['q2_amount__sum'] or 0
    q3_a = allocations.aggregate(Sum('q3_amount'))['q3_amount__sum'] or 0
    q4_a = allocations.aggregate(Sum('q4_amount'))['q4_amount__sum'] or 0

    q1_fill = (q1_a / q1 * 100) if q1 > 0 else 0
    q2_fill = (q2_a / q2 * 100) if q2 > 0 else 0
    q3_fill = (q3_a / q3 * 100) if q3 > 0 else 0
    q4_fill = (q4_a / q4 * 100) if q4 > 0 else 0
    
    # Ancho relativo de cada segmento (trimestre) respecto al total
    q1_seg = (q1 / total * 100) if total > 0 else 0
    q2_seg = (q2 / total * 100) if total > 0 else 0
    q3_seg = (q3 / total * 100) if total > 0 else 0
    q4_seg = (q4 / total * 100) if total > 0 else 0

    # Calculate execution percentage for the whole credit if it's distributed
    total_spent = allocations.aggregate(Sum('spent_amount'))['spent_amount__sum'] or 0
    execution_percent = (total_spent / total_allocated * 100) if total_allocated > 0 else 0

    # Remanentes trimestrales
    q_rems = [q1 - q1_a, q2 - q2_a, q3 - q3_a, q4 - q4_a]

    def _quarter_totals(queryset):
        data = queryset.aggregate(
            q1=Sum('q1_amount'), q2=Sum('q2_amount'),
            q3=Sum('q3_amount'), q4=Sum('q4_amount'),
        )
        return [data[f'q{i}'] or Decimal('0') for i in range(1, 5)]

    comp_out_qs = BudgetCompensacion.objects.filter(
        source_credit=credit,
        status='EJECUTADO',
    )
    compensation_out = _quarter_totals(comp_out_qs)

    comp_in_qs = BudgetCompensacion.objects.filter(
        fiscal_year=credit.fiscal_year,
        source_credit__credit_type_id=credit.credit_type_id,
        programa=credit.programa,
        target_ff=credit.ff,
        target_subprog=credit.subprog,
        target_inc=credit.inc,
        target_ppp_inc=credit.ppp_inc,
        target_pp_inc=credit.pp_inc,
        target_pre_inc=credit.pre_inc,
        target_incisos_agrupado=credit.incisos_agrupado,
        status='EJECUTADO',
    )
    compensation_in = _quarter_totals(comp_in_qs)

    recl_out_qs = BudgetAllocationReclassification.objects.filter(
        source_credit=credit,
        status='EJECUTADO',
    )
    reclassification_out = _quarter_totals(recl_out_qs)

    recl_in_qs = BudgetAllocationReclassification.objects.filter(
        target_credit=credit,
        status='EJECUTADO',
    )
    reclassification_in = _quarter_totals(recl_in_qs)

    q_tooltips = ["", "", "", ""]
    
    def _add_tooltip(qs, is_in):
        for obj in qs:
            for i in range(4):
                amt = getattr(obj, f'q{i+1}_amount', Decimal('0'))
                if amt > 0:
                    sign = "+" if is_in else "-"
                    word = "Entró de" if is_in else "Salió a"
                    if not is_in and getattr(obj, 'target_inc', None):
                        inc_str = obj.target_inc.code
                    elif is_in and getattr(obj, 'source_credit', None) and getattr(obj.source_credit, 'inc', None):
                        inc_str = obj.source_credit.inc.code
                    else:
                        inc_str = "?"
                    
                    q_tooltips[i] += f"{word} Inc {inc_str}: {sign}${amt:,.2f}<br>"

    _add_tooltip(comp_out_qs, is_in=False)
    _add_tooltip(comp_in_qs, is_in=True)
    _add_tooltip(recl_out_qs, is_in=False)
    _add_tooltip(recl_in_qs, is_in=True)
    
    q_movements = [
        compensation_in[i] + reclassification_in[i] - compensation_out[i] - reclassification_out[i]
        for i in range(4)
    ]
    q_originals = [
        amount - movement
        for amount, movement in zip([q1, q2, q3, q4], q_movements)
    ]
    q_cards = [
        {
            'label': label,
            'original': original,
            'vigente': vigente,
            'movement': movement,
            'remaining': remaining,
            'tooltip': tooltip,
        }
        for label, original, vigente, movement, remaining, tooltip in zip(
            ['1er Trimestre', '2do Trimestre', '3er Trimestre', '4to Trimestre'],
            q_originals,
            [q1, q2, q3, q4],
            q_movements,
            q_rems,
            q_tooltips,
        )
    ]

    context = {
        'credit': credit,
        'allocations': allocations,
        'total_allocated': total_allocated,
        'available_to_allocate': available_to_allocate,
        'total_spent': total_spent,
        'execution_percent': execution_percent,
        'q_fills': [q1_fill, q2_fill, q3_fill, q4_fill],
        'q_segs': [q1_seg, q2_seg, q3_seg, q4_seg],
        'q_rems': q_rems,
        'q_cards': q_cards,
        'is_admin': is_admin(request.user),
        'adjustments': credit.adjustments.all().select_related('user').order_by('-timestamp'),
    }
    return render(request, 'budget/credit_detail.html', context)

def compensacion_list(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    compensaciones = BudgetCompensacion.objects.all().order_by('-created_at').select_related(
        'fiscal_year', 'programa', 'source_credit', 'requested_by',
        'target_ff', 'target_subprog', 'target_inc', 'target_ppp_inc',
        'target_pp_inc', 'target_pre_inc', 'target_incisos_agrupado',
    )
    reclassifications = BudgetAllocationReclassification.objects.all().order_by('-created_at').select_related(
        'source_allocation__unit', 'source_credit__programa', 'source_credit__ff',
        'target_allocation__unit', 'target_credit', 'target_ff', 'target_subprog',
        'target_inc', 'target_ppp_inc', 'target_pp_inc', 'target_pre_inc',
        'target_incisos_agrupado', 'requested_by', 'approved_by', 'executed_by',
    )
    return render(request, 'budget/compensacion_list.html', {
        'compensaciones': compensaciones,
        'reclassifications': reclassifications,
    })

def compensacion_create(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    if request.method == 'POST':
        form = BudgetCompensacionForm(request.POST)
        if form.is_valid():
            try:
                target_params = {
                    'target_ff': form.cleaned_data['target_ff'],
                    'target_subprog': form.cleaned_data['target_subprog'],
                    'target_inc': form.cleaned_data['target_inc'],
                    'target_ppp_inc': form.cleaned_data['target_ppp_inc'],
                    'target_pp_inc': form.cleaned_data['target_pp_inc'],
                    'target_pre_inc': form.cleaned_data['target_pre_inc'],
                    'target_incisos_agrupado': form.cleaned_data['target_incisos_agrupado'],
                }
                q_amounts = (
                    form.cleaned_data['q1_amount'], form.cleaned_data['q2_amount'],
                    form.cleaned_data['q3_amount'], form.cleaned_data['q4_amount']
                )
                services.request_compensacion(
                    source_credit=form.cleaned_data['source_credit'],
                    target_params=target_params,
                    q_amounts=q_amounts,
                    user=request.user,
                    notes=form.cleaned_data['notes']
                )
                messages.success(request, "Solicitud de compensación creada exitosamente.")
                return redirect('budget:compensacion_list')
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else:
        initial = {}
        source_credit_id = request.GET.get('source_credit')
        if source_credit_id:
            try:
                from .models import BudgetCredit
                sc = BudgetCredit.objects.get(pk=source_credit_id)
                initial['source_credit'] = sc.pk
                # Pre-completar los campos de destino con los del origen
                initial['target_ff'] = sc.ff.pk if sc.ff else None
                initial['target_subprog'] = sc.subprog.pk if sc.subprog else None
                initial['target_inc'] = sc.inc.pk if sc.inc else None
                initial['target_ppp_inc'] = sc.ppp_inc.pk if sc.ppp_inc else None
                initial['target_pp_inc'] = sc.pp_inc.pk if sc.pp_inc else None
                initial['target_pre_inc'] = sc.pre_inc.pk if sc.pre_inc else None
                initial['target_incisos_agrupado'] = sc.incisos_agrupado.pk if sc.incisos_agrupado else None
            except Exception:
                pass
        form = BudgetCompensacionForm(initial=initial)
    return render(request, 'budget/form_base.html', {'form': form, 'title': 'Solicitar Compensación de Partidas'})

def compensacion_approve(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    compensacion = get_object_or_404(BudgetCompensacion, pk=pk)
    if request.method == 'POST':
        try:
            services.approve_compensacion(compensacion.id, request.user)
            messages.success(request, f"Compensacion #{compensacion.id} aprobada. Ya puede ejecutarse.")
        except Exception as e:
            error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Error: {error_msg}")
        return redirect('budget:compensacion_list')
    return render(request, 'budget/compensacion_confirm.html', {
        'compensacion': compensacion,
        'confirmation_action': 'approve',
    })


def compensacion_execute(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    compensacion = get_object_or_404(BudgetCompensacion, pk=pk)
    if request.method == 'POST':
        try:
            services.execute_compensacion(compensacion.id, request.user)
            messages.success(request, f"Compensacion #{compensacion.id} ejecutada con exito.")
        except Exception as e:
            error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Error: {error_msg}")
        return redirect('budget:compensacion_list')
    return render(request, 'budget/compensacion_confirm.html', {
        'compensacion': compensacion,
        'confirmation_action': 'execute',
    })


def compensacion_reject(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    if request.method != 'POST':
        return redirect('budget:compensacion_list')
    try:
        services.reject_compensacion(pk)
        messages.success(request, f"Compensacion #{pk} rechazada.")
    except Exception as e:
        error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
        messages.error(request, f"Error: {error_msg}")
    return redirect('budget:compensacion_list')


def allocation_reclassification_approve(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    item = get_object_or_404(BudgetAllocationReclassification, pk=pk)
    if request.method == 'POST':
        try:
            services.approve_allocation_reclassification(item.id, request.user)
            messages.success(request, f"Reclasificacion #{item.id} aprobada. Ya puede ejecutarse.")
        except Exception as e:
            error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Error: {error_msg}")
        return redirect('budget:compensacion_list')
    return render(request, 'budget/reclassification_confirm.html', {
        'item': item,
        'confirmation_action': 'approve',
    })


def allocation_reclassification_execute(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    item = get_object_or_404(BudgetAllocationReclassification, pk=pk)
    if request.method == 'POST':
        try:
            services.execute_allocation_reclassification(item.id, request.user)
            messages.success(request, f"Reclasificacion #{item.id} ejecutada con exito.")
        except Exception as e:
            error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Error: {error_msg}")
        return redirect('budget:compensacion_list')
    return render(request, 'budget/reclassification_confirm.html', {
        'item': item,
        'confirmation_action': 'execute',
    })


def allocation_reclassification_reject(request, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    if request.method != 'POST':
        return redirect('budget:compensacion_list')
    try:
        services.reject_allocation_reclassification(pk)
        messages.success(request, f"Reclasificacion #{pk} rechazada.")
    except Exception as e:
        error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
        messages.error(request, f"Error: {error_msg}")
    return redirect('budget:compensacion_list')

def credit_create(request):
    if not is_admin(request.user): return redirect('budget:credit_list')
    if request.method == 'POST':
        form = BudgetCreditForm(request.POST)
        if form.is_valid():
            try:
                services.create_credit(
                    fiscal_year=form.cleaned_data['fiscal_year'],
                    credit_type=form.cleaned_data.get('credit_type'),
                    ff=form.cleaned_data['ff'], 
                    programa=form.cleaned_data['programa'],
                    subprog=form.cleaned_data['subprog'],
                    inc=form.cleaned_data['inc'],
                    ppp_inc=form.cleaned_data['ppp_inc'],
                    pp_inc=form.cleaned_data['pp_inc'], 
                    pre_inc=form.cleaned_data['pre_inc'],
                    incisos_agrupado=form.cleaned_data['incisos_agrupado'], 
                    q1=form.cleaned_data['q1_amount'], q2=form.cleaned_data['q2_amount'],
                    q3=form.cleaned_data['q3_amount'], q4=form.cleaned_data['q4_amount'],
                    notes=form.cleaned_data['notes']
                )
                return redirect('budget:credit_list')
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else: form = BudgetCreditForm()
    return render(request, 'budget/form_base.html', {'form': form, 'title': 'Registrar Crédito Presupuestario'})

def credit_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Solo los superusuarios pueden eliminar créditos.")
        return redirect('budget:credit_list')
    
    credit = get_object_or_404(BudgetCredit, pk=pk)
    
    if request.method == 'POST':
        try:
            credit.delete()
            messages.success(request, "Crédito presupuestario eliminado exitosamente.")
            return redirect('budget:credit_list')
        except ProtectedError:
            messages.error(request, "No se puede eliminar este crédito porque ya tiene distribuciones asignadas a unidades. Debe eliminar las distribuciones primero.")
            return redirect('budget:credit_list')
        
    return render(request, 'budget/confirm_delete.html', {
        'object': credit,
        'title': f"Eliminar Crédito: {credit}",
        'cancel_url': 'budget:credit_list'
    })

def credit_bulk_delete(request):
    if not request.user.is_superuser:
        messages.error(request, "Solo los superusuarios pueden realizar esta acción.")
        return redirect('budget:credit_list')
    
    if request.method == 'POST':
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No se seleccionaron créditos para eliminar.")
            return redirect('budget:credit_list')
        
        from django.db.models import Count
        
        # Obtener todos los seleccionados con el conteo de distribuciones
        all_selected = BudgetCredit.objects.filter(pk__in=ids).annotate(
            alloc_count=Count('allocations')
        )
        
        # Separar los que se pueden borrar de los que no
        to_delete = all_selected.filter(alloc_count=0)
        protected = all_selected.filter(alloc_count__gt=0)
        
        deleted_count = to_delete.count()
        protected_count = protected.count()
        
        if deleted_count > 0:
            to_delete.delete()
            messages.success(request, f"Se eliminaron {deleted_count} créditos exitosamente.")
            
        if protected_count > 0:
            messages.warning(request, f"{protected_count} créditos no se pudieron eliminar porque ya tienen distribuciones asignadas.")
            
    return redirect('budget:credit_list')


def credit_unassign_type(request, pk):
    """Removes the credit_type from a single credit with an optional reason, logging the event."""
    if not is_admin(request.user): return redirect('budget:credit_list')
    credit = get_object_or_404(BudgetCredit, pk=pk)
    
    if not credit.credit_type:
        messages.warning(request, "Este crédito ya no tiene un tipo asignado.")
        return redirect('budget:credit_list')
    
    def parse_currency(value):
        if not value:
            return None
        value = str(value).replace(' ', '')
        if ',' in value:
            # Formato español: los puntos son miles, la coma es decimal
            raw = value.replace('.', '').replace(',', '.')
        else:
            # Ya limpio por JS o formato punto-decimal: el punto es decimal
            raw = value
        return Decimal(raw)

    if request.method == 'POST':
        current_amount_txt = request.POST.get('current_amount', '').strip()
        unassign_amount_txt = request.POST.get('unassign_amount', '').strip()
        notes_txt = request.POST.get('notes', '').strip()
        current_amount = None
        unassign_amount = None
        has_error = False

        if current_amount_txt:
            try:
                current_amount = parse_currency(current_amount_txt)
            except Exception:
                messages.error(request, "El monto actual ingresado no es válido.")
                has_error = True
        if unassign_amount_txt:
            try:
                unassign_amount = parse_currency(unassign_amount_txt)
            except Exception:
                messages.error(request, "El monto a desasignar ingresado no es válido.")
                has_error = True

        if has_error:
            return render(request, 'budget/credit_unassign_confirm.html', {
                'credit': credit,
                'current_amount': current_amount_txt,
                'unassign_amount': unassign_amount_txt,
                'notes': notes_txt
            })

        details = []
        if current_amount is not None:
            details.append(f"Monto crédito: ${current_amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        if unassign_amount is not None:
            details.append(f"Monto desasignado: ${unassign_amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        if notes_txt:
            details.append(notes_txt)

        notes = ' | '.join(details) if details else None

        try:
            services.unassign_credit_type(
                credit=credit,
                unassign_amount=unassign_amount,
                user=request.user,
                notes=notes
            )
        except Exception as e:
            error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Error: {error_msg}")
            return render(request, 'budget/credit_unassign_confirm.html', {
                'credit': credit,
                'current_amount': current_amount_txt,
                'unassign_amount': unassign_amount_txt,
                'notes': notes_txt
            })
        
        success_msg = f"Tipo de crédito removido de {credit}."
        if unassign_amount and unassign_amount > 0:
            formatted_amount = f"${unassign_amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            success_msg += f" Se descontaron {formatted_amount} del total."
            
        messages.success(request, success_msg)
        return redirect('budget:credit_list')

    return render(request, 'budget/credit_unassign_confirm.html', {
        'credit': credit,
        'current_amount': credit.total_amount,
        'unassign_amount': '',
        'notes': ''
    })

def credit_type_log(request):
    """Shows the full audit log of credit type assignment changes."""
    if not is_admin(request.user): return redirect('budget:dashboard')
    logs = BudgetCreditTypeLog.objects.all().select_related('credit', 'previous_type', 'new_type', 'user').order_by('-timestamp')
    return render(request, 'budget/credit_type_log.html', {'logs': logs})

@login_required
def allocation_list(request):
    fiscal_year = _get_fiscal_year_from_request(request)
    years = BudgetFiscalYear.objects.all().order_by('-year')
    
    base_qs = BudgetAllocation.objects.all()
    if fiscal_year:
        base_qs = base_qs.filter(credit__fiscal_year=fiscal_year)
        
    if is_admin(request.user): 
        allocations = base_qs
    else: 
        allocations = base_qs.filter(unit=request.user.unit)
        
    return render(request, 'budget/allocation_list.html', {
        'allocations': allocations,
        'fiscal_year': fiscal_year,
        'years': years
    })

def allocation_create(request):
    if not is_admin(request.user): return redirect('budget:allocation_list')
    
    credit_id = request.GET.get('credit')
    fixed_credit = None
    initial = {}
    
    if credit_id:
        fixed_credit = get_object_or_404(BudgetCredit, pk=credit_id)
        initial['credit'] = fixed_credit.pk
        
    if request.method == 'POST':
        form = BudgetAllocationForm(request.POST)
        if form.is_valid():
            try:
                services.allocate_credit(
                    credit=form.cleaned_data['credit'], 
                    unit=form.cleaned_data['unit'], 
                    q1=form.cleaned_data['q1_amount'], 
                    q2=form.cleaned_data['q2_amount'], 
                    q3=form.cleaned_data['q3_amount'], 
                    q4=form.cleaned_data['q4_amount'], 
                    notes=form.cleaned_data['notes'],
                    classifications=form.cleaned_data.get('custom_classes')
                )
                if fixed_credit:
                    return redirect('budget:credit_detail', pk=fixed_credit.pk)
                return redirect('budget:allocation_list')
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else:
        form = BudgetAllocationForm(initial=initial)
    
    if fixed_credit:
        form.fields['credit'].widget = forms.HiddenInput()
        
    return render(request, 'budget/form_base.html', {
        'form': form, 
        'title': 'Distribuir Crédito a Unidad',
        'fixed_credit': fixed_credit
    })

def allocation_update(request, pk):
    if not is_admin(request.user): return redirect('budget:allocation_list')
    allocation = get_object_or_404(BudgetAllocation, pk=pk)
    
    if request.method == 'POST':
        form = BudgetAllocationMetadataForm(request.POST, instance=allocation)
        if form.is_valid():
            try:
                services.update_allocation_metadata(
                    allocation_id=allocation.pk,
                    notes=form.cleaned_data['notes'],
                    classifications=form.cleaned_data.get('custom_classes')
                )
                messages.success(request, f"Proyecto/plan y observaciones de {allocation.unit.name} actualizados.")
                return redirect('budget:credit_detail', pk=allocation.credit.pk)
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else:
        form = BudgetAllocationMetadataForm(instance=allocation)
        
    return render(request, 'budget/form_base.html', {
        'form': form, 
        'title': f'Editar proyecto y observaciones: {allocation.unit.name}',
        'fixed_credit': allocation.credit,
        'help_text': 'Los montos, la unidad de destino y el credito de origen no pueden modificarse desde esta accion.',
    })


def allocation_reclassify(request, pk):
    if not is_admin(request.user): return redirect('budget:allocation_list')
    allocation = get_object_or_404(
        BudgetAllocation.objects.select_related(
            'credit__fiscal_year', 'credit__ff', 'credit__programa', 'credit__subprog',
            'credit__inc', 'credit__ppp_inc', 'credit__pp_inc', 'credit__pre_inc',
            'credit__incisos_agrupado', 'unit'
        ),
        pk=pk
    )

    if request.method == 'POST':
        form = BudgetAllocationReclassificationForm(request.POST, allocation=allocation)
        if form.is_valid():
            try:
                target_params = {
                    'target_ff': form.cleaned_data['target_ff'],
                    'target_subprog': form.cleaned_data['target_subprog'],
                    'target_inc': form.cleaned_data['target_inc'],
                    'target_ppp_inc': form.cleaned_data['target_ppp_inc'],
                    'target_pp_inc': form.cleaned_data['target_pp_inc'],
                    'target_pre_inc': form.cleaned_data['target_pre_inc'],
                    'target_incisos_agrupado': form.cleaned_data['target_incisos_agrupado'],
                }
                q_amounts = (
                    form.cleaned_data['q1_amount'], form.cleaned_data['q2_amount'],
                    form.cleaned_data['q3_amount'], form.cleaned_data['q4_amount'],
                )
                item = services.request_allocation_reclassification(
                    allocation_id=allocation.pk,
                    target_params=target_params,
                    q_amounts=q_amounts,
                    user=request.user,
                    notes=form.cleaned_data['notes'],
                )
                messages.success(
                    request,
                    f"Solicitud de cambio de inciso #{item.id} creada. Queda pendiente de aprobacion."
                )
                return redirect('budget:compensacion_list')
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else:
        form = BudgetAllocationReclassificationForm(allocation=allocation)

    return render(request, 'budget/form_base.html', {
        'form': form,
        'title': f'Cambio de inciso asignado: {allocation.unit.name}',
        'fixed_credit': allocation.credit,
        'reference_label': 'Disponible sin comprometer en esta distribucion',
        'reference_amount': allocation.available_amount,
        'help_text': 'Esta accion mueve solo saldo disponible de esta distribucion. No modifica ni traslada gastos ya comprometidos/devengados.',
    })

def allocation_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Solo los superusuarios pueden eliminar distribuciones.")
        return redirect('budget:allocation_list')
    
    allocation = get_object_or_404(BudgetAllocation, pk=pk)

    def deletion_redirect():
        return_credit_id = request.POST.get('return_credit_id')
        if return_credit_id and str(allocation.credit_id) == return_credit_id:
            return redirect('budget:credit_detail', pk=allocation.credit_id)
        return redirect('budget:allocation_list')
    
    if request.method == 'POST':
        try:
            allocation.delete()
            messages.success(request, "Distribución de crédito eliminada exitosamente.")
            return deletion_redirect()
        except ProtectedError:
            messages.error(request, "No se puede eliminar esta distribución porque ya tiene gastos (ejecuciones) registrados. Debe eliminar los gastos asociados primero.")
            return deletion_redirect()
        
    return render(request, 'budget/confirm_delete.html', {
        'object': allocation,
        'title': f"Eliminar Distribución: {allocation}",
        'cancel_url': 'budget:allocation_list'
    })

def allocation_bulk_delete(request):
    if not request.user.is_superuser:
        messages.error(request, "Solo los superusuarios pueden realizar esta acción.")
        return redirect('budget:allocation_list')
    
    if request.method == 'POST':
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No se seleccionaron distribuciones para eliminar.")
            return redirect('budget:allocation_list')
        
        from django.db.models import Count
        
        # Obtener todas las seleccionadas con el conteo de ejecuciones
        all_selected = BudgetAllocation.objects.filter(pk__in=ids).annotate(
            exec_count=Count('executions')
        )
        
        # Separar las que se pueden borrar de las que no
        to_delete = all_selected.filter(exec_count=0)
        protected = all_selected.filter(exec_count__gt=0)
        
        deleted_count = to_delete.count()
        protected_count = protected.count()
        
        if deleted_count > 0:
            # Eliminar las permitidas
            to_delete.delete()
            messages.success(request, f"Se eliminaron {deleted_count} distribuciones exitosamente.")
            
        if protected_count > 0:
            # Informar sobre las protegidas
            messages.warning(request, f"{protected_count} distribuciones no se pudieron eliminar porque ya tienen gastos (ejecuciones) registrados.")
            
    return redirect('budget:allocation_list')

def execution_list(request):
    fiscal_year = _get_fiscal_year_from_request(request)
    years = BudgetFiscalYear.objects.all().order_by('-year')
    
    base_qs = BudgetExecution.objects.all()
    if fiscal_year:
        base_qs = base_qs.filter(allocation__credit__fiscal_year=fiscal_year)
        
    if is_admin(request.user): 
        executions = base_qs
    else: 
        executions = base_qs.filter(allocation__unit=request.user.unit)
        
    return render(request, 'budget/execution_list.html', {
        'executions': executions.order_by('-created_at'),
        'fiscal_year': fiscal_year,
        'years': years
    })

def execution_detail(request, pk):
    execution = get_object_or_404(BudgetExecution, pk=pk)
    if not is_admin(request.user) and execution.allocation.unit != request.user.unit: return redirect('budget:execution_list')
    surplus = execution.commitment_amount - execution.accrued_amount if execution.commitment_amount > execution.accrued_amount else 0
    return render(request, 'budget/execution_detail.html', {'execution': execution, 'surplus': surplus})

import json

def execution_step_commitment(request):
    if request.method == 'POST':
        form = BudgetExecutionCommitmentForm(request.POST)
        if form.is_valid():
            alloc = form.cleaned_data['allocation']
            try:
                services.register_commitment(
                    allocation_id=alloc.pk, 
                    reference_code=form.cleaned_data['reference_code'], 
                    external_id=form.cleaned_data.get('external_id'),
                    amount=form.cleaned_data['commitment_amount'], 
                    commitment_date=form.cleaned_data['commitment_date'], 
                    user=request.user,
                    tipo_gasto=form.cleaned_data.get('tipo_gasto'),
                    afecta_pg117=form.cleaned_data.get('afecta_pg117', False),
                    numero_obra=form.cleaned_data.get('numero_obra'),
                    subcuenta=form.cleaned_data.get('subcuenta')
                )
                messages.success(request, "Compromiso registrado exitosamente.")
                return redirect('budget:execution_list')
            except InsufficientFundsError as e:
                messages.error(request, str(e))
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Ocurrió un error inesperado: {error_msg}")
    else:
        initial_data = {}
        alloc_id = request.GET.get('allocation')
        if alloc_id:
            initial_data['allocation'] = alloc_id
            
        form = BudgetExecutionCommitmentForm(initial=initial_data)
        if not is_admin(request.user):
            form.fields['allocation'].queryset = BudgetAllocation.objects.filter(unit=request.user.unit)
            
    # Preparar el mapeo de montos para el JS
    allocations = form.fields['allocation'].queryset
    amounts_map = {a.id: float(a.available_amount) for a in allocations}
    
    # Preparar metadata para lógica condicional de la UI (FF e Inciso)
    allocations_metadata = {
        a.id: {
            'ff': a.credit.ff.code if a.credit.ff else "",
            'inciso': a.credit.inc.code if a.credit.inc else ""
        } for a in allocations.select_related('credit__ff', 'credit__inc')
    }
            
    help_text = "Para registrar un compromiso, primero debe existir una Distribución de Crédito (Techo) asignada a la unidad. Si no ve opciones en el desplegable, contacte a Logística para la distribución de fondos."
    return render(request, 'budget/execution_commitment_form.html', {
        'form': form, 
        'title': 'Paso 1: Registro de Compromiso',
        'help_text': help_text,
        'amounts_map': json.dumps(amounts_map),
        'allocations_metadata': json.dumps(allocations_metadata)
    })

def execution_step_accrual(request, pk):
    execution = get_object_or_404(BudgetExecution, pk=pk)
    if request.method == 'POST':
        form = BudgetExecutionAccrualForm(request.POST, instance=execution)
        if form.is_valid():
            try:
                services.register_accrual(execution=execution, amount=form.cleaned_data['accrued_amount'], accrued_date=form.cleaned_data['accrued_date'])
                return redirect('budget:execution_detail', pk=pk)
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else: form = BudgetExecutionAccrualForm(instance=execution)
    return render(request, 'budget/form_base.html', {
        'form': form, 
        'title': f'Paso 2: Devengado ({execution.reference_code})',
        'reference_amount': execution.commitment_amount,
        'reference_label': 'Monto Comprometido'
    })

def execution_step_payment(request, pk):
    execution = get_object_or_404(BudgetExecution, pk=pk)
    if request.method == 'POST':
        form = BudgetExecutionPaymentForm(request.POST, instance=execution)
        if form.is_valid():
            try:
                services.register_payment(execution=execution, amount=form.cleaned_data['paid_amount'], paid_date=form.cleaned_data['paid_date'])
                return redirect('budget:execution_detail', pk=pk)
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else: form = BudgetExecutionPaymentForm(instance=execution)
    return render(request, 'budget/form_base.html', {
        'form': form, 
        'title': f'Paso 3: Pago ({execution.reference_code})',
        'reference_amount': execution.accrued_amount,
        'reference_label': 'Monto Devengado'
    })

def execution_release_surplus(request, pk):
    """
    Controlador para liberar el saldo comprometido de un gasto.
    """
    execution = get_object_or_404(BudgetExecution, pk=pk)
    
    # Seguridad básica
    if not is_admin(request.user) and execution.allocation.unit != request.user.unit:
        messages.error(request, "No tiene permisos para realizar esta acción.")
        return redirect('budget:execution_detail', pk=pk)
        
    try:
        from . import services
        execution, surplus = services.release_commitment_surplus(pk, request.user)
        messages.success(request, f"Se han liberado ${surplus} exitosamente. El monto comprometido ahora coincide con el devengado.")
    except Exception as e:
        error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
        messages.error(request, f"No se pudo liberar el saldo: {error_msg}")
        
    return redirect('budget:execution_detail', pk=pk)

def execution_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado. Solo los superusuarios pueden borrar ejecuciones.")
        return redirect('budget:execution_list')
        
    execution = get_object_or_404(BudgetExecution, pk=pk)
    
    if request.method == 'POST':
        try:
            from . import services
            amount = services.delete_execution(pk, request.user)
            messages.success(request, f"Ejecución borrada exitosamente. Se restituyeron ${amount} al crédito de la unidad.")
            return redirect('budget:execution_list')
        except Exception as e:
            messages.error(request, f"Error al borrar: {str(e)}")
            return redirect('budget:execution_detail', pk=pk)
            
    return render(request, 'budget/confirm_delete.html', {
        'object': execution,
        'title': f"Borrar Ejecución: {execution.reference_code}",
        'cancel_url': 'budget:execution_list'
    })

def export_rendicion_csv(request):
    """Exporta los gastos en el formato requerido para la Rendición."""
    if not is_admin(request.user):
        return HttpResponse("Acceso denegado", status=403)
    
    # Filtrar por ejercicio actual si se desea, o todos
    fiscal_year = BudgetFiscalYear.objects.filter(status='OPEN').first()
    executions = BudgetExecution.objects.all().select_related(
        'allocation__unit', 'allocation__credit__ff', 'allocation__credit__programa',
        'allocation__credit__subprog', 'allocation__credit__inc', 
        'allocation__credit__ppp_inc', 'allocation__credit__pp_inc',
        'allocation__credit__pre_inc', 'allocation__credit__incisos_agrupado'
    ).order_by('-created_at')
    
    if fiscal_year:
        executions = executions.filter(allocation__credit__fiscal_year=fiscal_year)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="rendicion_presupuestaria.csv"'
    
    # Escribir con codificación latin-1 para compatibilidad con Excel en español si es necesario, 
    # o usar UTF-8 con BOM. Usaremos UTF-8 con BOM para máxima compatibilidad.
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')
    
    # Encabezados
    writer.writerow([
        'Expediente/Referencia', 'Unidad', 'Fecha Compromiso', 
        'Imputación Fija (Programa/FF)', 'Imputación Variable (28 chars)',
        'Monto Comprometido', 'Monto Devengado', 'Monto Pagado'
    ])
    
    for e in executions:
        # Formatear montos con coma
        def fmt(val): return str(val).replace('.', ',')
        
        writer.writerow([
            e.reference_code,
            e.allocation.unit.name,
            e.commitment_date.strftime('%d/%m/%Y'),
            f"{e.allocation.credit.programa.code} / FF {e.allocation.credit.ff.code}",
            e.get_imputacion_variable(),
            fmt(e.commitment_amount),
            fmt(e.accrued_amount),
            fmt(e.paid_amount)
        ])
        
    return response

# --- Gestión de Nomencladores (Configuración) ---


def nomenclature_dashboard(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    
    catalogs = [
        {'id': 'ff', 'name': 'Fuentes de Financiamiento (FF)', 'model': BudgetFF, 'icon': 'fa-money-bill'},
        {'id': 'program', 'name': 'Programas', 'model': BudgetProg, 'icon': 'fa-tasks'},
        {'id': 'subprog', 'name': 'Subprogramas', 'model': BudgetSubprog, 'icon': 'fa-diagram-project'},
        {'id': 'inc', 'name': 'INCISOs', 'model': BudgetInc, 'icon': 'fa-folder-open'},
        {'id': 'pppinc', 'name': 'PPALs', 'model': BudgetPPPInc, 'icon': 'fa-list-ol'},
        {'id': 'ppinc', 'name': 'PARCIALes', 'model': BudgetPPInc, 'icon': 'fa-list-ol'},
        {'id': 'preinc', 'name': 'SUBPCs', 'model': BudgetPreInc, 'icon': 'fa-list-ol'},
        {'id': 'inc_agrup', 'name': 'MONEDAs', 'model': BudgetIncisosAgrupado, 'icon': 'fa-boxes-stacked'},
        {'id': 'credit_type', 'name': 'Tipos de Crédito', 'model': BudgetCreditType, 'icon': 'fa-tags'},
        {'id': 'tipo_gasto', 'name': 'Tipos de Gasto (TG)', 'model': BudgetTipoGasto, 'icon': 'fa-receipt'},
    ]
    
    # Add counts to each catalog
    for cat in catalogs:
        cat['count'] = cat['model'].objects.count()
        
    return render(request, 'budget/nomenclature_dashboard.html', {'catalogs': catalogs})

def nomenclature_list(request, catalog_type):
    if not is_admin(request.user): return redirect('budget:dashboard')
    
    config = _get_catalog_config(catalog_type)
    if not config: return redirect('budget:nomenclature_dashboard')
    
    items = config['model'].objects.all().order_by('code' if hasattr(config['model'], 'code') else 'id')
    return render(request, 'budget/nomenclature_list.html', {
        'items': items,
        'config': config,
        'title': f"Catálogo: {config['name']}"
    })

def nomenclature_create(request, catalog_type):
    if not is_admin(request.user): return redirect('budget:dashboard')
    
    config = _get_catalog_config(catalog_type)
    if not config: return redirect('budget:nomenclature_dashboard')
    
    if request.method == 'POST':
        form = config['form_class'](request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"{config['model']._meta.verbose_name} creado exitosamente.")
            return redirect('budget:nomenclature_list', catalog_type=catalog_type)
    else:
        form = config['form_class']()
        
    return render(request, 'budget/form_base.html', {
        'form': form,
        'title': f"Agregar {config['model']._meta.verbose_name}",
        'config': config
    })

def nomenclature_update(request, catalog_type, pk):
    if not is_admin(request.user): return redirect('budget:dashboard')
    
    config = _get_catalog_config(catalog_type)
    if not config: return redirect('budget:nomenclature_dashboard')
    
    instance = get_object_or_404(config['model'], pk=pk)
    
    if request.method == 'POST':
        form = config['form_class'](request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"{config['model']._meta.verbose_name} actualizado exitosamente.")
            return redirect('budget:nomenclature_list', catalog_type=catalog_type)
    else:
        form = config['form_class'](instance=instance)
        
    return render(request, 'budget/form_base.html', {
        'form': form,
        'title': f"Editar {config['model']._meta.verbose_name}",
        'config': config
    })

def nomenclature_delete(request, catalog_type, pk):
    if not is_strict_admin(request.user): return redirect('budget:dashboard')
    
    config = _get_catalog_config(catalog_type)
    if not config: return redirect('budget:nomenclature_dashboard')
    
    instance = get_object_or_404(config['model'], pk=pk)
    
    if request.method == 'POST':
        try:
            instance.delete()
            messages.success(request, f"{config['model']._meta.verbose_name} eliminado exitosamente.")
        except ProtectedError:
            messages.error(request, f"No se puede eliminar '{instance}' porque ya está siendo utilizado en el sistema.")
        except Exception as e:
            messages.error(request, f"Error al eliminar: {e}")
        return redirect('budget:nomenclature_list', catalog_type=catalog_type)
        
    return render(request, 'budget/confirm_delete.html', {
        'object': instance,
        'title': f"Eliminar {config['model']._meta.verbose_name}",
        'cancel_url': 'budget:nomenclature_list'
    })

def _get_catalog_config(catalog_type):
    configs = {
        'ff': {'id': 'ff', 'model': BudgetFF, 'form_class': BudgetFFForm, 'name': 'Fuentes de Financiamiento'},
        'program': {'id': 'program', 'model': BudgetProg, 'form_class': BudgetProgForm, 'name': 'Programas'},
        'subprog': {'id': 'subprog', 'model': BudgetSubprog, 'form_class': BudgetSubprogForm, 'name': 'Subprogramas'},
        'pppinc': {'id': 'pppinc', 'model': BudgetPPPInc, 'form_class': BudgetPPPIncForm, 'name': 'PPALs'},
        'ppinc': {'id': 'ppinc', 'model': BudgetPPInc, 'form_class': BudgetPPIncForm, 'name': 'PARCIALes'},
        'preinc': {'id': 'preinc', 'model': BudgetPreInc, 'form_class': BudgetPreIncForm, 'name': 'SUBPCs'},
        'inc_agrup': {'id': 'inc_agrup', 'model': BudgetIncisosAgrupado, 'form_class': BudgetIncisosAgrupadoForm, 'name': 'MONEDAs'},
        'inc': {'id': 'inc', 'model': BudgetInc, 'form_class': BudgetIncForm, 'name': 'INCISOs'},
        'credit_type': {'id': 'credit_type', 'model': BudgetCreditType, 'form_class': BudgetCreditTypeForm, 'name': 'Tipos de Crédito'},
        'tipo_gasto': {'id': 'tipo_gasto', 'model': BudgetTipoGasto, 'form_class': BudgetTipoGastoForm, 'name': 'Tipos de Gasto'},
    }
    return configs.get(catalog_type)

def seed_tipo_gasto(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    
    defaults = [
        ('2', 'Gastos de Comida (JEMI)'),
        ('3', 'Mora en el Pago'),
        ('4', 'Mantenimiento Correctivo'),
        ('6', 'Viáticos Operativos'),
        ('7', 'Pasajes'),
        ('8', 'Viáticos con cargo'),
        ('9', 'I.C.D.'),
    ]
    
    created_count = 0
    for code, name in defaults:
        obj, created = BudgetTipoGasto.objects.get_or_create(code=code, defaults={'name': name})
        if created:
            created_count += 1
            
    if created_count > 0:
        messages.success(request, f"Se han cargado {created_count} tipos de gasto predeterminados.")
    else:
        messages.info(request, "Los tipos de gasto predeterminados ya existen.")
        
    return redirect('budget:nomenclature_list', catalog_type='tipo_gasto')

# --- Clasificaciones Personalizadas ---

def classification_list(request):
    classes = BudgetClassification.objects.annotate(
        total_assigned=Sum('allocations__allocated_amount')
    ).order_by('name')
    
    grand_total = sum((c.total_assigned or Decimal('0')) for c in classes)
    
    return render(request, 'budget/classification_list.html', {
        'classes': classes,
        'grand_total': grand_total
    })

def classification_create(request):
    if request.method == 'POST':
        form = BudgetClassificationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Clasificación creada.")
            return redirect('budget:classification_list')
    else:
        form = BudgetClassificationForm()
    return render(request, 'budget/form_base.html', {'form': form, 'title': 'Nueva Clasificación'})

def classification_update(request, pk):
    c = get_object_or_404(BudgetClassification, pk=pk)
    if request.method == 'POST':
        form = BudgetClassificationForm(request.POST, instance=c)
        if form.is_valid():
            form.save()
            messages.success(request, "Clasificación actualizada.")
            return redirect('budget:classification_list')
    else:
        form = BudgetClassificationForm(instance=c)
    return render(request, 'budget/form_base.html', {'form': form, 'title': f'Editar Clasificación: {c.name}'})

def classification_delete(request, pk):
    if not is_strict_admin(request.user): return redirect('budget:classification_list')
    c = get_object_or_404(BudgetClassification, pk=pk)
    if request.method == 'POST':
        c.delete()
        messages.success(request, "Clasificación eliminada.")
        return redirect('budget:classification_list')
    return render(request, 'budget/confirm_delete.html', {
        'object': c, 
        'title': f'Eliminar Clasificación: {c.name}',
        'cancel_url': 'budget:classification_list'
    })

def classification_assign(request, pk):
    c = get_object_or_404(BudgetClassification, pk=pk)
    if request.method == 'POST':
        form = BudgetClassificationAssignForm(request.POST, classification=c)
        if form.is_valid():
            # Assign this classification to the selected allocations (M2M)
            selected_allocs = form.cleaned_data['allocations']
            c.allocations.set(selected_allocs)
                
            messages.success(request, f"Créditos asignados a {c.name}.")
            return redirect('budget:classification_list')
    else:
        form = BudgetClassificationAssignForm(classification=c)
        
    return render(request, 'budget/classification_assign.html', {'form': form, 'classification': c})

def classification_detail(request, pk):
    classification = get_object_or_404(BudgetClassification, pk=pk)
    allocations = classification.allocations.all().select_related(
        'unit', 'credit__fiscal_year', 'credit__ff', 'credit__programa', 
        'credit__subprog', 'credit__inc', 'credit__ppp_inc', 'credit__pp_inc', 'credit__pre_inc'
    )
    
    total_allocated = Decimal('0')
    total_spent = Decimal('0')
    total_accrued = Decimal('0')
    total_paid = Decimal('0')
    
    allocation_details = []
    
    for alloc in allocations:
        execs_stats = BudgetExecution.objects.filter(allocation=alloc).aggregate(
            t_accrued=Sum('accrued_amount'),
            t_paid=Sum('paid_amount')
        )
        accrued = execs_stats['t_accrued'] or Decimal('0')
        paid = execs_stats['t_paid'] or Decimal('0')
        
        total_allocated += alloc.allocated_amount
        total_spent += alloc.spent_amount
        total_accrued += accrued
        total_paid += paid
        
        allocation_details.append({
            'allocation': alloc,
            'spent': alloc.spent_amount,
            'accrued': accrued,
            'paid': paid,
        })
        
    stats = {
        'total_allocated': total_allocated,
        'total_spent': total_spent,
        'total_accrued': total_accrued,
        'total_paid': total_paid,
        'available_to_execute': total_allocated - total_spent
    }

    original_credits = BudgetCredit.objects.filter(
        pre_inc__code=classification.name
    ).select_related('ff', 'inc', 'pre_inc').order_by('-fiscal_year__year', '-total_amount')
    
    return render(request, 'budget/classification_detail.html', {
        'classification': classification,
        'stats': stats,
        'allocation_details': allocation_details,
        'original_credits': original_credits
    })


@login_required
def credit_splits_manage(request, pk):
    """Gestión de reclasificaciones parciales de un crédito."""
    if not is_admin(request.user):
        return redirect('budget:credit_detail', pk=pk)
    credit = get_object_or_404(BudgetCredit, pk=pk)

    from .models import BudgetCreditSplit, BudgetPreInc as _PI
    from django import forms as _forms

    class _SplitForm(_forms.Form):
        pre_inc_destino = _forms.ModelChoiceField(
            queryset=_PI.objects.all().order_by('code'),
            label="SUBPC Destino",
            help_text="Fila del consolidado donde aparecerá este monto.",
            widget=_forms.Select(attrs={'class': 'form-select'})
        )
        amount = _forms.DecimalField(
            max_digits=18, decimal_places=2, min_value=Decimal('0.01'),
            label="Monto a reclasificar",
            widget=_forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0.00'})
        )
        notes = _forms.CharField(
            required=False,
            widget=_forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            label="Observaciones (opcional)"
        )

    splits = BudgetCreditSplit.objects.filter(credit=credit).select_related('pre_inc_destino')
    total_split = splits.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    remaining = credit.total_amount - total_split

    if request.method == 'POST':
        form = _SplitForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            if amount > remaining:
                form.add_error('amount', f'Excede el monto disponible para reclasificar (${remaining:,.0f}).')
            else:
                BudgetCreditSplit.objects.create(
                    credit=credit,
                    pre_inc_destino=form.cleaned_data['pre_inc_destino'],
                    amount=amount,
                    notes=form.cleaned_data.get('notes', '')
                )
                messages.success(request, f"Reclasificación de ${amount:,.0f} guardada correctamente.")
                return redirect('budget:credit_splits_manage', pk=credit.pk)
    else:
        form = _SplitForm()

    pct_split = int((total_split / credit.total_amount * 100)) if credit.total_amount else 0

    return render(request, 'budget/credit_splits.html', {
        'credit': credit,
        'splits': splits,
        'total_split': total_split,
        'remaining': remaining,
        'pct_split': pct_split,
        'form': form,
    })


@login_required
def credit_split_delete(request, pk, split_pk):
    """Elimina una reclasificación parcial."""
    if not is_admin(request.user):
        return redirect('budget:credit_detail', pk=pk)
    from .models import BudgetCreditSplit
    split = get_object_or_404(BudgetCreditSplit, pk=split_pk, credit__pk=pk)
    if request.method == 'POST':
        monto = split.amount
        split.delete()
        messages.success(request, f"Reclasificación de ${monto:,.0f} eliminada.")
    return redirect('budget:credit_splits_manage', pk=pk)



def credit_adjust(request, pk):

    if not is_admin(request.user): return redirect('budget:credit_list')
    credit = get_object_or_404(BudgetCredit, pk=pk)
    
    if request.method == 'POST':
        form = BudgetCreditAdjustmentForm(request.POST, credit=credit)
        if form.is_valid():
            try:
                services.adjust_credit(
                    credit_id=credit.pk,
                    q1_new=form.cleaned_data['q1_new'],
                    q2_new=form.cleaned_data['q2_new'],
                    q3_new=form.cleaned_data['q3_new'],
                    q4_new=form.cleaned_data['q4_new'],
                    reason=form.cleaned_data['reason'],
                    user=request.user
                )
                messages.success(request, f"Crédito {credit} ajustado exitosamente.")
                return redirect('budget:credit_detail', pk=credit.pk)
            except Exception as e:
                error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
                messages.error(request, f"Error: {error_msg}")
    else:
        form = BudgetCreditAdjustmentForm(credit=credit)
        
    return render(request, 'budget/form_base.html', {
        'form': form, 
        'title': f'Ajustar Montos: {credit}',
        'help_text': 'Use este formulario para modificar los montos trimestrales. El sistema validará que los nuevos montos no sean inferiores a lo ya distribuido a las unidades.'
    })


@login_required
@login_required
def foxtrot_ceilings_manage(request):
    """Gestión de techos Foxtrot manuales."""
    if not is_admin(request.user):
        return redirect('budget:consolidation')
    
    fiscal_year = _get_fiscal_year_from_request(request)
    if not fiscal_year:
        messages.error(request, "Debe seleccionar un ejercicio fiscal activo.")
        return redirect('budget:consolidation')

    from .models import BudgetPreInc, BudgetFoxtrotCeiling
    pre_incs = list(BudgetPreInc.objects.all().order_by('code'))
    # Include a None representation for "Sin Clasificar"
    all_rows = pre_incs + [None]
    
    if request.method == 'POST':
        for row in all_rows:
            key = f"ceiling_{row.id if row else 'unclassified'}"
            amount_str = request.POST.get(key, '0').replace(',', '.')
            try:
                amount = Decimal(amount_str or '0')
            except:
                amount = Decimal('0')
                
            BudgetFoxtrotCeiling.objects.update_or_create(
                fiscal_year=fiscal_year,
                pre_inc=row,
                defaults={'amount': amount}
            )
        messages.success(request, "Techos Foxtrot actualizados correctamente.")
        return redirect('budget:foxtrot_ceilings_manage')
        
    # Get current ceilings
    ceilings = BudgetFoxtrotCeiling.objects.filter(fiscal_year=fiscal_year)
    ceiling_dict = {c.pre_inc_id: c.amount for c in ceilings}
    
    context_rows = []
    for row in all_rows:
        amount = ceiling_dict.get(row.id if row else None, Decimal('0.00'))
        context_rows.append({
            'id': row.id if row else 'unclassified',
            'code': row.code if row else 'Sin Clasificar',
            'amount': amount
        })

    return render(request, 'budget/foxtrot_ceilings.html', {
        'fiscal_year': fiscal_year,
        'rows': context_rows
    })

@login_required
def budget_consolidation(request):
    fiscal_year = _get_fiscal_year_from_request(request)
    if not fiscal_year:
        return render(request, 'budget/consolidation.html', {
            'fiscal_year': None,
            'rows': [],
            'totals': {},
            'units': [],
            'selected_unit': None,
            'rsm_saldos': None
        })

    is_admin_user = is_admin(request.user)
    
    # Obtener listado de destinos
    from core.models import Unit
    units = Unit.objects.all().order_by('name')
    
    # Obtener destino seleccionado
    unit_id = request.GET.get('unit')
    selected_unit = None
    if unit_id:
        selected_unit = get_object_or_404(Unit, pk=unit_id)
        
    from .models import BudgetPreInc, BudgetCredit, BudgetAllocation, BudgetUnitBackup, BudgetClassification, BudgetFoxtrotCeiling
    
    custom_order = [
        '2+3',
        'PROM',
        'RyC PAIS',
        'RyC EN EL EXTERIOR',
        '4',
        'SS.BB',
        'PYV',
        '20',
        '40',
        '50',
        '70',
        '87',
        '90',
        '95',
        '99',
        'VERSTUARIO PACID',
    ]
    order_map = {code: i for i, code in enumerate(custom_order)}
    
    # Unificar nombres de BudgetPreInc y BudgetClassification
    pre_incs = list(BudgetPreInc.objects.all())
    classifications = list(BudgetClassification.objects.all())
    
    # Crear un diccionario para acceder rápido a los IDs si existen
    pre_inc_map = {pi.code: pi for pi in pre_incs}
    class_map = {c.name: c for c in classifications}
    
    all_codes = set([pi.code for pi in pre_incs] + [c.name for c in classifications])
    sorted_codes = sorted(list(all_codes), key=lambda code: (order_map.get(code, 999), code))
    
    rows = []
    modal_rows = []
    
    if selected_unit:
        # Vista detallada de Unidad Destino
        totals = {
            'respaldo': Decimal('0.00'),
            'asignacion': Decimal('0.00'),
            'com_dev': Decimal('0.00'),
            'saldo': Decimal('0.00'),
            'falta_asignar': Decimal('0.00')
        }
        
        # Cargar los respaldos guardados
        backups = {b.pre_inc_id: b.amount for b in BudgetUnitBackup.objects.filter(fiscal_year=fiscal_year, unit=selected_unit)}
        
        for code in sorted_codes:
            pi = pre_inc_map.get(code)
            c = class_map.get(code)
            
            respaldo = backups.get(pi.id, Decimal('0.00')) if pi else Decimal('0.00')
            
            # Asignación Distribuida (por proyecto/plan O pre_inc para mantener compatibilidad si no hay custom_classes)
            allocs = BudgetAllocation.objects.filter(
                credit__fiscal_year=fiscal_year,
                unit=selected_unit
            )
            
            if c:
                asignacion = allocs.filter(custom_classes=c).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
                com_dev = allocs.filter(custom_classes=c).aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
            else:
                asignacion = allocs.filter(credit__pre_inc=pi, custom_classes__isnull=True).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
                com_dev = allocs.filter(credit__pre_inc=pi, custom_classes__isnull=True).aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
            
            saldo = asignacion - com_dev
            falta_asignar = max(Decimal('0.00'), respaldo - asignacion)
            
            if pi:
                modal_rows.append({
                    'pre_inc_id': pi.id,
                    'code': code,
                    'category': code,
                    'respaldo': respaldo
                })
            
            if respaldo > 0 or asignacion > 0 or com_dev > 0:
                row_data = {
                    'pre_inc_id': pi.id if pi else f'class_{c.id}',
                    'code': code,
                    'category': code,
                    'respaldo': respaldo,
                    'asignacion': asignacion,
                    'com_dev': com_dev,
                    'saldo': saldo,
                    'falta_asignar': falta_asignar
                }
                rows.append(row_data)
                
                totals['respaldo'] += respaldo
                totals['asignacion'] += asignacion
                totals['com_dev'] += com_dev
                totals['saldo'] += saldo
                totals['falta_asignar'] += falta_asignar
                
        # Sin Clasificar
        respaldo_un = backups.get(None, Decimal('0.00'))
        allocs_un = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year, unit=selected_unit, custom_classes__isnull=True, credit__pre_inc__isnull=True)
        asignacion_un = allocs_un.aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
        com_dev_un = allocs_un.aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
        saldo_un = asignacion_un - com_dev_un
        falta_asignar_un = max(Decimal('0.00'), respaldo_un - asignacion_un)
        
        if respaldo_un > 0 or asignacion_un > 0 or com_dev_un > 0:
            row_data = {
                'pre_inc_id': 'None',
                'code': 'S/C',
                'category': 'Sin Clasificar / Otros',
                'respaldo': respaldo_un,
                'asignacion': asignacion_un,
                'com_dev': com_dev_un,
                'saldo': saldo_un,
                'falta_asignar': falta_asignar_un
            }
            rows.append(row_data)
            totals['respaldo'] += respaldo_un
            totals['asignacion'] += asignacion_un
            totals['com_dev'] += com_dev_un
            totals['saldo'] += saldo_un
            totals['falta_asignar'] += falta_asignar_un
            
        rsm_saldos_group1 = Decimal('0.00')
        for r in rows:
            if r['code'] in ['2+3', 'PROM', 'RyC PAIS', 'GGOO']:
                rsm_saldos_group1 += r['saldo']
                
        rsm_saldos_group2 = Decimal('0.00')
        for r in rows:
            if r['code'] == 'RyC EN EL EXTERIOR':
                rsm_saldos_group2 += r['saldo']
                
        rsm_saldos_group3 = Decimal('0.00')
        for r in rows:
            if r['code'] == '4':
                rsm_saldos_group3 += r['saldo']
                
        rsm_saldos_group4 = Decimal('0.00')
        for r in rows:
            if r['code'] == '87':
                rsm_saldos_group4 += r['saldo']
                
        rsm_saldos = {
            'group1': rsm_saldos_group1,
            'group2': rsm_saldos_group2,
            'group3': rsm_saldos_group3,
            'group4': rsm_saldos_group4
        }
        
    else:
        # Vista global de COAA
        totals = {
            'foxtrot': Decimal('0.00'),
            'asig_coaa': Decimal('0.00'),
            'falta_asig': Decimal('0.00'),
            'refuerzo': Decimal('0.00'),
            'total_asignado': Decimal('0.00'),
            'distribuido': Decimal('0.00'),
            'reserva': Decimal('0.00'),
            'com_dev': Decimal('0.00'),
            'saldo_disponible': Decimal('0.00')
        }
        
        for code in sorted_codes:
            pi = pre_inc_map.get(code)
            c = class_map.get(code)
            
            foxtrot = Decimal('0.00')
            if pi:
                fc = BudgetFoxtrotCeiling.objects.filter(fiscal_year=fiscal_year, pre_inc=pi).first()
                if fc:
                    foxtrot = fc.amount

            asig_coaa = Decimal('0.00')
            if pi:
                asig_coaa = BudgetCredit.objects.filter(
                    fiscal_year=fiscal_year,
                    pre_inc=pi
                ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

            falta_asig = max(Decimal('0.00'), foxtrot - asig_coaa)
            refuerzo = max(Decimal('0.00'), asig_coaa - foxtrot)
            total_asignado = asig_coaa
            
            if c:
                distribuido = BudgetAllocation.objects.filter(
                    credit__fiscal_year=fiscal_year,
                    custom_classes=c
                ).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
                com_dev = BudgetAllocation.objects.filter(
                    credit__fiscal_year=fiscal_year,
                    custom_classes=c
                ).aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
                
                allocs = BudgetAllocation.objects.filter(
                    credit__fiscal_year=fiscal_year,
                    custom_classes=c
                )
            else:
                distribuido = BudgetAllocation.objects.filter(
                    credit__fiscal_year=fiscal_year,
                    credit__pre_inc=pi,
                    custom_classes__isnull=True
                ).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
                com_dev = BudgetAllocation.objects.filter(
                    credit__fiscal_year=fiscal_year,
                    credit__pre_inc=pi,
                    custom_classes__isnull=True
                ).aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
                
                allocs = BudgetAllocation.objects.filter(
                    credit__fiscal_year=fiscal_year,
                    credit__pre_inc=pi,
                    custom_classes__isnull=True
                )
                
            reserva = max(Decimal('0.00'), total_asignado - distribuido)
            saldo_disponible = distribuido - com_dev
            
            if foxtrot > 0 or asig_coaa > 0 or distribuido > 0 or com_dev > 0:
                units_data = {}
                for alloc in allocs:
                    uid = alloc.unit.id
                    if uid not in units_data:
                        units_data[uid] = {
                            'unit_name': alloc.unit.name,
                            'respaldo': Decimal('0.00'),
                            'asignacion': Decimal('0.00'),
                            'com_dev': Decimal('0.00')
                        }
                    units_data[uid]['asignacion'] += alloc.allocated_amount
                    units_data[uid]['com_dev'] += alloc.spent_amount
                
                if pi:
                    unit_backups = BudgetUnitBackup.objects.filter(fiscal_year=fiscal_year, pre_inc=pi)
                    for b in unit_backups:
                        uid = b.unit.id
                        if uid not in units_data:
                            units_data[uid] = {
                                'unit_name': b.unit.name,
                                'respaldo': Decimal('0.00'),
                                'asignacion': Decimal('0.00'),
                                'com_dev': Decimal('0.00')
                            }
                        units_data[uid]['respaldo'] += b.amount
                        
                breakdown_list = []
                for uid, data in units_data.items():
                    r_val = data['respaldo']
                    a_val = data['asignacion']
                    cd_val = data['com_dev']
                    s_val = a_val - cd_val
                    f_val = max(Decimal('0.00'), r_val - a_val)
                    if r_val > 0 or a_val > 0 or cd_val > 0:
                        breakdown_list.append({
                            'unit_name': data['unit_name'],
                            'respaldo': float(r_val),
                            'asignacion': float(a_val),
                            'com_dev': float(cd_val),
                            'saldo': float(s_val),
                            'falta_asignar': float(f_val)
                        })
                breakdown_list.sort(key=lambda x: x['unit_name'])
                
                tooltip_lines = [f"{item['unit_name']}: ${item['asignacion']:,.2f}" for item in breakdown_list if item['asignacion'] > 0]
                tooltip = "<br>".join(tooltip_lines) if tooltip_lines else "Sin distribuciones"
                
                rows.append({
                    'code': code,
                    'foxtrot': foxtrot,
                    'asig_coaa': asig_coaa,
                    'falta_asig': falta_asig,
                    'refuerzo': refuerzo,
                    'total_asignado': total_asignado,
                    'distribuido': distribuido,
                    'reserva': reserva,
                    'com_dev': com_dev,
                    'saldo_disponible': saldo_disponible,
                    'breakdown_json': json.dumps(breakdown_list),
                    'allocations_tooltip': tooltip
                })
                
                totals['foxtrot'] += foxtrot
                totals['asig_coaa'] += asig_coaa
                totals['falta_asig'] += falta_asig
                totals['refuerzo'] += refuerzo
                totals['total_asignado'] += total_asignado
                totals['distribuido'] += distribuido
                totals['reserva'] += reserva
                totals['com_dev'] += com_dev
                totals['saldo_disponible'] += saldo_disponible
                
        # Sin Clasificar
        foxtrot_un = Decimal('0.00')
        fc_un = BudgetFoxtrotCeiling.objects.filter(fiscal_year=fiscal_year, pre_inc__isnull=True).first()
        if fc_un:
            foxtrot_un = fc_un.amount
            
        asig_coaa_un = BudgetCredit.objects.filter(
            fiscal_year=fiscal_year,
            pre_inc__isnull=True
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        falta_asig_un = max(Decimal('0.00'), foxtrot_un - asig_coaa_un)
        refuerzo_un = max(Decimal('0.00'), asig_coaa_un - foxtrot_un)
        total_asignado_un = asig_coaa_un
        
        distribuido_un = BudgetAllocation.objects.filter(
            credit__fiscal_year=fiscal_year,
            credit__pre_inc__isnull=True,
            custom_classes__isnull=True
        ).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
        com_dev_un = BudgetAllocation.objects.filter(
            credit__fiscal_year=fiscal_year,
            credit__pre_inc__isnull=True,
            custom_classes__isnull=True
        ).aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
        
        reserva_un = max(Decimal('0.00'), total_asignado_un - distribuido_un)
        saldo_disponible_un = distribuido_un - com_dev_un
        
        if foxtrot_un > 0 or asig_coaa_un > 0 or distribuido_un > 0 or com_dev_un > 0:
            rows.append({
                'code': 'S/C',
                'foxtrot': foxtrot_un,
                'asig_coaa': asig_coaa_un,
                'falta_asig': falta_asig_un,
                'refuerzo': refuerzo_un,
                'total_asignado': total_asignado_un,
                'distribuido': distribuido_un,
                'reserva': reserva_un,
                'com_dev': com_dev_un,
                'saldo_disponible': saldo_disponible_un,
                'breakdown_json': '[]',
                'allocations_tooltip': ''
            })
            totals['foxtrot'] += foxtrot_un
            totals['asig_coaa'] += asig_coaa_un
            totals['falta_asig'] += falta_asig_un
            totals['refuerzo'] += refuerzo_un
            totals['total_asignado'] += total_asignado_un
            totals['distribuido'] += distribuido_un
            totals['reserva'] += reserva_un
            totals['com_dev'] += com_dev_un
            totals['saldo_disponible'] += saldo_disponible_un
            
        rsm_saldos = None

    context = {
        'fiscal_year': fiscal_year,
        'rows': rows,
        'modal_rows': modal_rows,
        'totals': totals,
        'units': units,
        'selected_unit': selected_unit,
        'rsm_saldos': rsm_saldos,
        'is_admin': is_admin_user,
    }
    return render(request, 'budget/consolidation.html', context)

def export_consolidation_csv(request):
    fiscal_year = _get_fiscal_year_from_request(request)
    if not fiscal_year:
        return HttpResponse("No hay ejercicio fiscal activo", status=400)
        
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="consolidado_presupuestario_{fiscal_year.year}.csv"'
    response.write('\ufeff') # BOM
    writer = csv.writer(response, dialect='excel', delimiter=';')
    
    writer.writerow([
        'Incisos / Subparcial', 'Foxtrot (FF11)', 'Asignación Recibida x COAA', 
        'Falta Asignar COAA', 'Refuerzo Recibido', 'Total Asignado por COAA', 
        'Asignacion Distribuida', 'Reserva', 'Com + Dev', 'Saldo Disponible'
    ])
    
    from .models import BudgetPreInc, BudgetCredit, BudgetAllocation
    
    custom_order = [
        '2+3',
        'PROM',
        'RyC PAIS',
        'RyC EN EL EXTERIOR',
        '4',
        'SS.BB',
        'PYV',
        '20',
        '40',
        '50',
        '70',
        '87',
        '90',
        '95',
        '99',
        'VERSTUARIO PACID',
    ]
    order_map = {code: i for i, code in enumerate(custom_order)}
    pre_incs = sorted(BudgetPreInc.objects.all(), key=lambda pi: order_map.get(pi.code, 999))
    
    totals = {
        'foxtrot': 0, 'asig_coaa': 0, 'falta_asig': 0, 'refuerzo': 0, 
        'total_asignado': 0, 'distribuido': 0, 'reserva': 0, 'com_dev': 0, 'saldo_disponible': 0
    }
    
    def fmt(val):
        return str(val).replace('.', ',')
        
    for pi in pre_incs:
        foxtrot = BudgetCredit.objects.filter(fiscal_year=fiscal_year, pre_inc=pi, credit_type__code='ASIGNACION', ff__code='FF11').aggregate(total=Sum('total_amount'))['total'] or 0
        asig_coaa = BudgetCredit.objects.filter(fiscal_year=fiscal_year, pre_inc=pi, credit_type__code='ASIGNACION').aggregate(total=Sum('total_amount'))['total'] or 0
        falta_asig = max(0, foxtrot - asig_coaa)
        refuerzo = BudgetCredit.objects.filter(fiscal_year=fiscal_year, pre_inc=pi, credit_type__code='REFUERZO').aggregate(total=Sum('total_amount'))['total'] or 0
        total_asignado = asig_coaa + refuerzo
        distribuido = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year, credit__pre_inc=pi).aggregate(total=Sum('allocated_amount'))['total'] or 0
        reserva = total_asignado - distribuido
        com_dev = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year, credit__pre_inc=pi).aggregate(total=Sum('spent_amount'))['total'] or 0
        saldo_disponible = distribuido - com_dev
        
        if foxtrot > 0 or asig_coaa > 0 or refuerzo > 0 or distribuido > 0 or com_dev > 0:
            writer.writerow([
                pi.code,
                fmt(foxtrot),
                fmt(asig_coaa),
                fmt(falta_asig),
                fmt(refuerzo),
                fmt(total_asignado),
                fmt(distribuido),
                fmt(reserva),
                fmt(com_dev),
                fmt(saldo_disponible)
            ])
            totals['foxtrot'] += foxtrot
            totals['asig_coaa'] += asig_coaa
            totals['falta_asig'] += falta_asig
            totals['refuerzo'] += refuerzo
            totals['total_asignado'] += total_asignado
            totals['distribuido'] += distribuido
            totals['reserva'] += reserva
            totals['com_dev'] += com_dev
            totals['saldo_disponible'] += saldo_disponible

    unclassified_credits = BudgetCredit.objects.filter(fiscal_year=fiscal_year, pre_inc=None)
    unclassified_allocations = BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year, credit__pre_inc=None)
    foxtrot_un = unclassified_credits.filter(credit_type__code='ASIGNACION', ff__code='FF11').aggregate(total=Sum('total_amount'))['total'] or 0
    asig_coaa_un = unclassified_credits.filter(credit_type__code='ASIGNACION').aggregate(total=Sum('total_amount'))['total'] or 0
    falta_asig_un = max(0, foxtrot_un - asig_coaa_un)
    refuerzo_un = unclassified_credits.filter(credit_type__code='REFUERZO').aggregate(total=Sum('total_amount'))['total'] or 0
    total_asignado_un = asig_coaa_un + refuerzo_un
    distribuido_un = unclassified_allocations.aggregate(total=Sum('allocated_amount'))['total'] or 0
    reserva_un = total_asignado_un - distribuido_un
    com_dev_un = unclassified_allocations.aggregate(total=Sum('spent_amount'))['total'] or 0
    saldo_disponible_un = distribuido_un - com_dev_un
    
    if foxtrot_un > 0 or asig_coaa_un > 0 or refuerzo_un > 0 or distribuido_un > 0 or com_dev_un > 0:
        writer.writerow([
            'Sin Clasificar / Otros',
            fmt(foxtrot_un),
            fmt(asig_coaa_un),
            fmt(falta_asig_un),
            fmt(refuerzo_un),
            fmt(total_asignado_un),
            fmt(distribuido_un),
            fmt(reserva_un),
            fmt(com_dev_un),
            fmt(saldo_disponible_un)
        ])
        totals['foxtrot'] += foxtrot_un
        totals['asig_coaa'] += asig_coaa_un
        totals['falta_asig'] += falta_asig_un
        totals['refuerzo'] += refuerzo_un
        totals['total_asignado'] += total_asignado_un
        totals['distribuido'] += distribuido_un
        totals['reserva'] += reserva_un
        totals['com_dev'] += com_dev_un
        totals['saldo_disponible'] += saldo_disponible_un

    writer.writerow([
        'Total',
        fmt(totals['foxtrot']),
        fmt(totals['asig_coaa']),
        fmt(totals['falta_asig']),
        fmt(totals['refuerzo']),
        fmt(totals['total_asignado']),
        fmt(totals['distribuido']),
        fmt(totals['reserva']),
        fmt(totals['com_dev']),
        fmt(totals['saldo_disponible'])
    ])
    
    return response


@login_required
def save_budget_backup(request):
    if not is_admin(request.user):
        return redirect('budget:dashboard')
        
    if request.method == 'POST':
        fiscal_year = _get_fiscal_year_from_request(request)
        if not fiscal_year:
            messages.error(request, "No hay ejercicio fiscal activo.")
            return redirect('budget:consolidation')
            
        from core.models import Unit
        unit_id = request.POST.get('unit_id')
        unit = get_object_or_404(Unit, pk=unit_id)
        
        from .models import BudgetPreInc, BudgetUnitBackup
        
        for key, value in request.POST.items():
            if key.startswith('backup_pre_inc_'):
                pre_inc_id_str = key.replace('backup_pre_inc_', '')
                
                try:
                    clean_val = str(value or '').strip()
                    if '.' in clean_val and ',' in clean_val:
                        clean_val = clean_val.replace('.', '').replace(',', '.')
                    elif ',' in clean_val:
                        clean_val = clean_val.replace(',', '.')
                    else:
                        clean_val = clean_val.replace('.', '')
                    amount = Decimal(clean_val) if clean_val else Decimal('0.00')
                except Exception:
                    amount = Decimal('0.00')
                    
                if pre_inc_id_str == 'None':
                    pass
                else:
                    pre_inc_id = int(pre_inc_id_str)
                    pre_inc = get_object_or_404(BudgetPreInc, pk=pre_inc_id)
                    BudgetUnitBackup.objects.update_or_create(
                        fiscal_year=fiscal_year,
                        unit=unit,
                        pre_inc=pre_inc,
                        defaults={'amount': amount}
                    )
                    
        messages.success(request, f"Respaldos anuales para {unit.name} guardados exitosamente.")
        return redirect(f"/budget/consolidation/?unit={unit.id}")
        
    return redirect('budget:consolidation')


@login_required
def budget_queries(request):
    from .models import BudgetFiscalYear, BudgetFF, BudgetProg, BudgetSubprog, BudgetInc, BudgetPreInc, BudgetCredit, BudgetAllocation
    from django.db.models import Sum
    from decimal import Decimal
    
    def safe_int_list(values):
        """Convierte una lista de strings a lista de enteros, ignorando valores inválidos."""
        result = []
        for v in values:
            try:
                result.append(int(v))
            except (ValueError, TypeError):
                pass
        return result
    
    # 1. Obtener ejercicios
    fiscal_years = BudgetFiscalYear.objects.all().order_by('-year')
    active_year = BudgetFiscalYear.objects.filter(status='OPEN').first() or fiscal_years.first()
    
    fy_id = request.GET.get('fiscal_year')
    if fy_id:
        try:
            selected_year = BudgetFiscalYear.objects.get(id=int(fy_id))
        except (ValueError, BudgetFiscalYear.DoesNotExist):
            selected_year = active_year
    else:
        selected_year = active_year

    # 2. Cargar listas para filtros dinámicos (encadenados) — soporte multi-selección
    
    # A. FFs disponibles en el ejercicio
    ff_ids_available = BudgetCredit.objects.filter(fiscal_year=selected_year).values_list('ff_id', flat=True).distinct()
    ffs = BudgetFF.objects.filter(id__in=ff_ids_available).order_by('code')
    
    raw_ff_ids = safe_int_list(request.GET.getlist('ff'))
    selected_ff_ids = [x for x in raw_ff_ids if ffs.filter(id=x).exists()]
    
    # B. Programas disponibles según FFs seleccionados
    prog_qs = BudgetCredit.objects.filter(fiscal_year=selected_year)
    if selected_ff_ids:
        prog_qs = prog_qs.filter(ff_id__in=selected_ff_ids)
    prog_ids_available = prog_qs.values_list('programa_id', flat=True).distinct()
    programas = BudgetProg.objects.filter(id__in=prog_ids_available).order_by('code')
    
    raw_prog_ids = safe_int_list(request.GET.getlist('programa'))
    selected_prog_ids = [x for x in raw_prog_ids if programas.filter(id=x).exists()]
    
    # C. Subprogramas disponibles según FFs y Programas seleccionados
    subprog_qs = BudgetCredit.objects.filter(fiscal_year=selected_year)
    if selected_ff_ids:
        subprog_qs = subprog_qs.filter(ff_id__in=selected_ff_ids)
    if selected_prog_ids:
        subprog_qs = subprog_qs.filter(programa_id__in=selected_prog_ids)
    subprog_ids_available = subprog_qs.values_list('subprog_id', flat=True).distinct()
    subprogramas = BudgetSubprog.objects.filter(id__in=subprog_ids_available).order_by('code')
    
    raw_subprog_ids = safe_int_list(request.GET.getlist('subprog'))
    selected_subprog_ids = [x for x in raw_subprog_ids if subprogramas.filter(id=x).exists()]
    
    # D. Incisos disponibles según filtros anteriores
    inc_qs = BudgetCredit.objects.filter(fiscal_year=selected_year)
    if selected_ff_ids:
        inc_qs = inc_qs.filter(ff_id__in=selected_ff_ids)
    if selected_prog_ids:
        inc_qs = inc_qs.filter(programa_id__in=selected_prog_ids)
    if selected_subprog_ids:
        inc_qs = inc_qs.filter(subprog_id__in=selected_subprog_ids)
    inc_ids_available = inc_qs.values_list('inc_id', flat=True).distinct()
    incisos = BudgetInc.objects.filter(id__in=inc_ids_available).order_by('code')
    
    raw_inc_ids = safe_int_list(request.GET.getlist('inc'))
    selected_inc_ids = [x for x in raw_inc_ids if incisos.filter(id=x).exists()]
    
    # E. Subparciales disponibles según filtros anteriores
    pre_inc_qs = BudgetCredit.objects.filter(fiscal_year=selected_year)
    if selected_ff_ids:
        pre_inc_qs = pre_inc_qs.filter(ff_id__in=selected_ff_ids)
    if selected_prog_ids:
        pre_inc_qs = pre_inc_qs.filter(programa_id__in=selected_prog_ids)
    if selected_subprog_ids:
        pre_inc_qs = pre_inc_qs.filter(subprog_id__in=selected_subprog_ids)
    if selected_inc_ids:
        pre_inc_qs = pre_inc_qs.filter(inc_id__in=selected_inc_ids)
    pre_inc_ids_available = pre_inc_qs.values_list('pre_inc_id', flat=True).distinct()
    pre_incs = BudgetPreInc.objects.filter(id__in=pre_inc_ids_available).order_by('code')
    
    raw_pre_inc_ids = safe_int_list(request.GET.getlist('pre_inc'))
    selected_pre_inc_ids = [x for x in raw_pre_inc_ids if pre_incs.filter(id=x).exists()]
    
    # 3. Iniciar querysets base y aplicar filtros multi-selección
    credits_qs = BudgetCredit.objects.filter(fiscal_year=selected_year)
    allocations_qs = BudgetAllocation.objects.filter(credit__fiscal_year=selected_year)
    
    if selected_ff_ids:
        credits_qs = credits_qs.filter(ff_id__in=selected_ff_ids)
        allocations_qs = allocations_qs.filter(credit__ff_id__in=selected_ff_ids)
        
    if selected_prog_ids:
        credits_qs = credits_qs.filter(programa_id__in=selected_prog_ids)
        allocations_qs = allocations_qs.filter(credit__programa_id__in=selected_prog_ids)
        
    if selected_subprog_ids:
        credits_qs = credits_qs.filter(subprog_id__in=selected_subprog_ids)
        allocations_qs = allocations_qs.filter(credit__subprog_id__in=selected_subprog_ids)
            
    if selected_inc_ids:
        credits_qs = credits_qs.filter(inc_id__in=selected_inc_ids)
        allocations_qs = allocations_qs.filter(credit__inc_id__in=selected_inc_ids)
            
    if selected_pre_inc_ids:
        credits_qs = credits_qs.filter(pre_inc_id__in=selected_pre_inc_ids)
        allocations_qs = allocations_qs.filter(credit__pre_inc_id__in=selected_pre_inc_ids)
            
    # 4. Agrupar créditos y asignaciones por combinación única de (ff, programa, subprog, inc, pre_inc)
    credit_data = credits_qs.values(
        'ff_id', 'ff__code', 'ff__name',
        'programa_id', 'programa__code', 'programa__name',
        'subprog_id', 'subprog__code', 'subprog__name',
        'inc_id', 'inc__code', 'inc__name',
        'pre_inc_id', 'pre_inc__code', 'pre_inc__name'
    ).annotate(total_credit=Sum('total_amount'))
    
    alloc_data = allocations_qs.values(
        'credit__ff_id', 'credit__programa_id', 'credit__subprog_id', 'credit__inc_id', 'credit__pre_inc_id'
    ).annotate(total_alloc=Sum('allocated_amount'))
    
    # Consulta de asignaciones por unidad para armar los tooltips
    alloc_units_data = allocations_qs.values(
        'credit__ff_id', 'credit__programa_id', 'credit__subprog_id', 'credit__inc_id', 'credit__pre_inc_id',
        'unit__name'
    ).annotate(total_unit=Sum('allocated_amount')).order_by('-total_unit')
    
    unit_distributions = {}
    for au in alloc_units_data:
        key = (au['credit__ff_id'], au['credit__programa_id'], au['credit__subprog_id'], au['credit__inc_id'], au['credit__pre_inc_id'])
        if key not in unit_distributions:
            unit_distributions[key] = []
        if au['total_unit'] > 0:
            unit_distributions[key].append({
                'unit_name': au['unit__name'],
                'amount': float(au['total_unit'])
            })
            
    # 5. Mapear y consolidar la información
    row_map = {}
    
    def build_tooltip(key):
        dist_list = unit_distributions.get(key, [])
        tooltip_lines = ["<b>Distribución por Destino:</b>"]
        for d in dist_list:
            monto = f"{d['amount']:,.0f}".replace(",", ".")
            tooltip_lines.append(f"• {d['unit_name']}: ${monto}")
        if len(tooltip_lines) == 1:
            tooltip_lines.append("<i>Sin distribución a unidades</i>")
        return "<br/>".join(tooltip_lines)
    
    for c in credit_data:
        key = (c['ff_id'], c['programa_id'], c['subprog_id'], c['inc_id'], c['pre_inc_id'])
        row_map[key] = {
            'ff_code': c['ff__code'] or 'N/A',
            'ff_name': c['ff__name'] or 'Sin FF',
            'prog_code': c['programa__code'] or 'N/A',
            'prog_name': c['programa__name'] or 'Sin Programa',
            'subprog_code': c['subprog__code'] or 'N/A',
            'subprog_name': c['subprog__name'] or 'Sin Subprog',
            'inc_code': c['inc__code'] or 'S/C',
            'inc_name': c['inc__name'] or 'Sin Clasificar',
            'pre_inc_code': c['pre_inc__code'] or 'S/C',
            'pre_inc_name': c['pre_inc__name'] or 'Sin Clasificar',
            'asignado_coaa': c['total_credit'] or Decimal('0.00'),
            'asignado_destinos': Decimal('0.00'),
            'falta_asignar': c['total_credit'] or Decimal('0.00'),
            'allocations_tooltip': build_tooltip(key)
        }
        
    for a in alloc_data:
        key = (a['credit__ff_id'], a['credit__programa_id'], a['credit__subprog_id'], a['credit__inc_id'], a['credit__pre_inc_id'])
        if key not in row_map:
            ff_obj = BudgetFF.objects.filter(id=a['credit__ff_id']).first()
            prog_obj = BudgetProg.objects.filter(id=a['credit__programa_id']).first()
            subprog_obj = BudgetSubprog.objects.filter(id=a['credit__subprog_id']).first()
            inc_obj = BudgetInc.objects.filter(id=a['credit__inc_id']).first()
            pre_inc_obj = BudgetPreInc.objects.filter(id=a['credit__pre_inc_id']).first()
            row_map[key] = {
                'ff_code': ff_obj.code if ff_obj else 'N/A',
                'ff_name': ff_obj.name if ff_obj else 'Sin FF',
                'prog_code': prog_obj.code if prog_obj else 'N/A',
                'prog_name': prog_obj.name if prog_obj else 'Sin Programa',
                'subprog_code': subprog_obj.code if subprog_obj else 'N/A',
                'subprog_name': subprog_obj.name if subprog_obj else 'Sin Subprog',
                'inc_code': inc_obj.code if inc_obj else 'S/C',
                'inc_name': inc_obj.name if inc_obj else 'Sin Clasificar',
                'pre_inc_code': pre_inc_obj.code if pre_inc_obj else 'S/C',
                'pre_inc_name': pre_inc_obj.name if pre_inc_obj else 'Sin Clasificar',
                'asignado_coaa': Decimal('0.00'),
                'asignado_destinos': a['total_alloc'] or Decimal('0.00'),
                'falta_asignar': - (a['total_alloc'] or Decimal('0.00')),
                'allocations_tooltip': build_tooltip(key)
            }
        else:
            row_map[key]['asignado_destinos'] = a['total_alloc'] or Decimal('0.00')
            row_map[key]['falta_asignar'] = row_map[key]['asignado_coaa'] - row_map[key]['asignado_destinos']
            
    # Convertir a lista y ordenar por FF, Prog, Subprog, Inc, PreInc
    rows = list(row_map.values())
    rows.sort(key=lambda r: (r['ff_code'], r['prog_code'], r['subprog_code'], r['inc_code'], r['pre_inc_code']))
    
    # 6. Calcular totales generales
    totals = {
        'asignado_coaa': sum(r['asignado_coaa'] for r in rows),
        'asignado_destinos': sum(r['asignado_destinos'] for r in rows),
        'falta_asignar': sum(r['falta_asignar'] for r in rows),
    }
    
    # Convertir selected ids a strings para comparación en el template
    context = {
        'fiscal_years': fiscal_years,
        'selected_year': selected_year,
        'ffs': ffs,
        'programas': programas,
        'subprogramas': subprogramas,
        'incisos': incisos,
        'pre_incs': pre_incs,
        'selected_ff_ids': [str(x) for x in selected_ff_ids],
        'selected_prog_ids': [str(x) for x in selected_prog_ids],
        'selected_subprog_ids': [str(x) for x in selected_subprog_ids],
        'selected_inc_ids': [str(x) for x in selected_inc_ids],
        'selected_pre_inc_ids': [str(x) for x in selected_pre_inc_ids],
        'has_active_filters': bool(selected_ff_ids or selected_prog_ids or selected_subprog_ids or selected_inc_ids or selected_pre_inc_ids),
        'rows': rows,
        'totals': totals
    }
    
    return render(request, 'budget/queries.html', context)

