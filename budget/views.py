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
    BudgetClassification, BudgetCreditType, BudgetCreditTypeLog, BudgetCompensacion, BudgetTipoGasto, InsufficientFundsError
)
import csv
from django.http import HttpResponse
from .forms import (
    BudgetFiscalYearForm, BudgetCreditForm, BudgetAllocationForm,
    BudgetExecutionCommitmentForm, BudgetExecutionAccrualForm, 
    BudgetExecutionPaymentForm, BudgetClassificationForm, BudgetClassificationAssignForm,
    BudgetCompensacionForm, BudgetFFForm, BudgetSubprogForm, BudgetProgForm,
    BudgetPPPIncForm, BudgetPPIncForm, BudgetPreIncForm,
    BudgetIncisosAgrupadoForm, BudgetIncForm, BudgetCreditTypeForm,
    BudgetCreditAdjustmentForm, BudgetTipoGastoForm
)
from . import services

def is_admin(user):
    return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()

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

        stats['total_credit'] = credits.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        stats['total_allocated'] = allocations.aggregate(Sum('allocated_amount'))['allocated_amount__sum'] or 0
        stats['total_commitment'] = executions.aggregate(Sum('commitment_amount'))['commitment_amount__sum'] or 0
        stats['total_accrued'] = executions.aggregate(Sum('accrued_amount'))['accrued_amount__sum'] or 0
        stats['total_paid'] = executions.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        stats['available_to_allocate'] = stats['total_credit'] - stats['total_allocated']
        stats['available_to_execute'] = stats['total_allocated'] - stats['total_commitment']
        
        # Agregación por trimestre y tipo
        for q in ['q1', 'q2', 'q3', 'q4']:
            field = f'{q}_amount'
            stats[f'{q}_total'] = credits.aggregate(Sum(field))[f'{field}__sum'] or 0
            stats[f'{q}_asignacion'] = credits.filter(credit_type__code='ASIGNACION').aggregate(Sum(field))[f'{field}__sum'] or 0
            stats[f'{q}_refuerzo'] = credits.filter(credit_type__code='REFUERZO').aggregate(Sum(field))[f'{field}__sum'] or 0

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
            q_credits = credits.annotate(
                q_total=F(field_name),
                q_alloc=Coalesce(Sum(f'allocations__{field_name}'), 0, output_field=models.DecimalField())
            ).filter(models.Q(q_total__gt=0) | models.Q(q_alloc__gt=0)).prefetch_related('allocations__unit')

            table_rows = []
            for c in q_credits:
                avail = c.q_total - c.q_alloc
                t_str = f"{c.q_total:,.0f}".replace(",", ".")
                a_str = f"{c.q_alloc:,.0f}".replace(",", ".")
                v_str = f"{avail:,.0f}".replace(",", ".")

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
                    f"  <td class='small fw-bold'>{c}</td>"
                    f"  <td class='text-end small'>${t_str}</td>"
                    f"  <td class='text-end small'>{dist_cell}</td>"
                    f"  <td class='text-end small text-info fw-bold'>${v_str}</td>"
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
                "      <th class='text-end'>Presupuesto</th>"
                "      <th class='text-end'>Distribuido</th>"
                "      <th class='text-end'>Disponible</th>"
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
                    'name': item['credit_type__name'],
                    'total': 0,
                    'subpcs': []
                }
            grouped_stats[code]['total'] += item['subtotal'] or 0
            if item['subtotal'] and item['subtotal'] > 0:
                grouped_stats[code]['subpcs'].append({
                    'code': item['pre_inc__code'] or 'S/D',
                    'amount': item['subtotal']
                })
        
        stats['credit_by_type'] = grouped_stats.values()

        # Desglose de Crédito Distribuido por SUBPC
        if is_admin_user:
            stats['allocated_by_subpc'] = (
                BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year)
                .values('credit__pre_inc__code')
                .annotate(subtotal=Sum('allocated_amount'))
                .order_by('credit__pre_inc__code')
            )
        else:
            stats['allocated_by_subpc'] = (
                BudgetAllocation.objects.filter(credit__fiscal_year=fiscal_year, unit=request.user.unit)
                .values('credit__pre_inc__code')
                .annotate(subtotal=Sum('allocated_amount'))
                .order_by('credit__pre_inc__code')
            )

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
        credit_by_type = BudgetCredit.objects.filter(fiscal_year=fiscal_year, credit_type__isnull=False, allocations__unit=request.user.unit).values('credit_type__name').annotate(total=Sum('allocations__allocated_amount'))
        
    # 2. Crédito por SUBPC
    if is_admin_user:
        credit_by_subpc = BudgetCredit.objects.filter(fiscal_year=fiscal_year).values('pre_inc__code').annotate(total=Sum('total_amount')).order_by('pre_inc__code')
    else:
        credit_by_subpc = BudgetCredit.objects.filter(fiscal_year=fiscal_year, allocations__unit=request.user.unit).values('pre_inc__code').annotate(total=Sum('allocations__allocated_amount')).order_by('pre_inc__code')

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
    fiscal_year = BudgetFiscalYear.objects.filter(status='ACTIVE').first()
    
    if is_admin_user:
        credits = BudgetCredit.objects.annotate(
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
        credits = BudgetCredit.objects.filter(allocations__unit=request.user.unit).annotate(
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
        'is_admin': is_admin_user
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
        'is_admin': is_admin(request.user),
        'adjustments': credit.adjustments.all().select_related('user').order_by('-timestamp'),
    }
    return render(request, 'budget/credit_detail.html', context)

def compensacion_list(request):
    if not is_admin(request.user): return redirect('budget:dashboard')
    compensaciones = BudgetCompensacion.objects.all().order_by('-created_at').select_related(
        'fiscal_year', 'programa', 'source_credit', 'requested_by'
    )
    return render(request, 'budget/compensacion_list.html', {'compensaciones': compensaciones})

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
                    fiscal_year=form.cleaned_data['fiscal_year'],
                    programa=form.cleaned_data['programa'],
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
                initial['fiscal_year'] = sc.fiscal_year.pk if sc.fiscal_year else None
                initial['programa'] = sc.programa.pk if sc.programa else None
                
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
            services.execute_compensacion(compensacion.id, request.user)
            messages.success(request, f"Compensación #{compensacion.id} ejecutada con éxito.")
        except Exception as e:
            error_msg = ", ".join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Error: {error_msg}")
        return redirect('budget:compensacion_list')
    return render(request, 'budget/compensacion_confirm.html', {'compensacion': compensacion})

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

        services.unassign_credit_type(
            credit=credit,
            unassign_amount=unassign_amount,
            user=request.user,
            notes=notes
        )
        
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

def allocation_list(request):
    if is_admin(request.user): allocations = BudgetAllocation.objects.all()
    else: allocations = BudgetAllocation.objects.filter(unit=request.user.unit)
    return render(request, 'budget/allocation_list.html', {'allocations': allocations})

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
                    notes=form.cleaned_data['notes']
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

def allocation_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Solo los superusuarios pueden eliminar distribuciones.")
        return redirect('budget:allocation_list')
    
    allocation = get_object_or_404(BudgetAllocation, pk=pk)
    
    if request.method == 'POST':
        try:
            allocation.delete()
            messages.success(request, "Distribución de crédito eliminada exitosamente.")
            return redirect('budget:allocation_list')
        except ProtectedError:
            messages.error(request, "No se puede eliminar esta distribución porque ya tiene gastos (ejecuciones) registrados. Debe eliminar los gastos asociados primero.")
            return redirect('budget:allocation_list')
        
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
    if is_admin(request.user): executions = BudgetExecution.objects.all()
    else: executions = BudgetExecution.objects.filter(allocation__unit=request.user.unit)
    return render(request, 'budget/execution_list.html', {'executions': executions.order_by('-created_at')})

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
    if not is_admin(request.user): return redirect('budget:dashboard')
    
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

    return render(request, 'budget/classification_detail.html', {
        'classification': classification,
        'stats': stats,
        'allocation_details': allocation_details
    })


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

