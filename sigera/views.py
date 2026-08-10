from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.db import transaction
from django.contrib import messages
from django.http import HttpResponse
from .models import ClothingType, ClothingSize, ClothingBatch, Personnel, ClothingAssignment, PersonnelClothingMeasure, StockThreshold
from .forms import PersonnelForm, ClothingAssignmentForm, ClothingTypeMeasuresForm
import pandas as pd
import io
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from core.models import Unit
def check_sigera_delete_pin(request):
    from core.models import UserSystemPIN
    from django.contrib.auth.hashers import check_password
    pin = request.POST.get('pin', '')
    try:
        access = UserSystemPIN.objects.get(user=request.user, system_code='sigera_delete')
    except UserSystemPIN.DoesNotExist:
        return False, "No tiene configurado el PIN de Borrado para SIGERA."
    if not check_password(pin, access.pin_hash):
        return False, "PIN incorrecto. No se realizó la eliminación."
    return True, ""

@login_required
def home(request):
    """
    Vista principal de SIGERA (Dashboard)
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()

    total_stock = ClothingType.objects.count()
    
    personnel_qs = Personnel.objects.all()
    assignments_qs = ClothingAssignment.objects.all()
    
    if not is_admin:
        if getattr(user, 'unit', None):
            personnel_qs = personnel_qs.filter(assigned_unit=user.unit)
            assignments_qs = assignments_qs.filter(personnel__assigned_unit=user.unit)
        else:
            personnel_qs = personnel_qs.none()
            assignments_qs = assignments_qs.none()

    total_personnel = personnel_qs.count()
    active_assignments = assignments_qs.filter(returned=False).count()
    pending_receptions = assignments_qs.filter(returned=False, reception_status='PENDING').count()
    
    # Actividad reciente: últimas 5 entregas
    recent_assignments = assignments_qs.select_related(
        'personnel', 'batch__clothing_size__clothing_type'
    ).order_by('-assigned_date', '-id')[:5]
    
    context = {
        'total_stock': total_stock,
        'total_personnel': total_personnel,
        'active_assignments': active_assignments,
        'pending_receptions': pending_receptions,
        'recent_assignments': recent_assignments,
        'is_admin': is_admin,
    }
    return render(request, 'sigera/home.html', context)

@login_required
def stock_list(request):
    """
    Vista de Inventario Detallado por Lotes
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para acceder al inventario.")
        return redirect('sigera:home')

    from django.db.models import Sum
    
    # Obtener las categorías configurables
    stock_thresholds = list(StockThreshold.objects.order_by('order'))
    
    stock_batches = ClothingBatch.objects.filter(
        available_quantity__gt=0
    ).select_related('clothing_size__clothing_type').order_by(
        'clothing_size__clothing_type__name', 'clothing_size__size', 'reception_date'
    )
    
    # Asignar categoría a cada batch
    for batch in stock_batches:
        quantity = batch.available_quantity or 0
        for threshold in stock_thresholds:
            if threshold.matches(quantity):
                batch.stock_category = threshold
                break
        else:
            batch.stock_category = None
            
    # Agrupar lotes por tipo de prenda, luego por talle para la vista
    grouped_stock = []
    current_type_group = None
    
    for batch in stock_batches:
        clothing_type = batch.clothing_size.clothing_type
        
        # 1. Agrupación por Prenda
        if current_type_group is None or current_type_group['clothing_type_id'] != clothing_type.id:
            if current_type_group is not None:
                # Calcular la categoría global para la prenda sumando todo
                total_qty = current_type_group['total_available']
                for threshold in stock_thresholds:
                    if threshold.matches(total_qty):
                        current_type_group['stock_category'] = threshold
                        break
                grouped_stock.append(current_type_group)
                
            current_type_group = {
                'clothing_type_id': clothing_type.id,
                'clothing_type_name': clothing_type.name,
                'total_available': 0,
                'total_initial': 0,
                'sizes': [],
                'stock_category': None
            }
        
        # 2. Agrupación por Talle dentro de la Prenda
        sizes_list = current_type_group['sizes']
        if not sizes_list or sizes_list[-1]['clothing_size_id'] != batch.clothing_size.id:
            # Calcular categoría para el talle anterior si existe
            if sizes_list:
                prev_size_qty = sizes_list[-1]['total_available']
                for threshold in stock_thresholds:
                    if threshold.matches(prev_size_qty):
                        sizes_list[-1]['stock_category'] = threshold
                        break
            
            sizes_list.append({
                'clothing_size_id': batch.clothing_size.id,
                'size': batch.clothing_size.size,
                'total_available': 0,
                'total_initial': 0,
                'batches': [],
                'stock_category': None
            })
            
        current_size_group = sizes_list[-1]
        
        # Añadir batch al talle
        current_size_group['batches'].append(batch)
        
        qty_avail = batch.available_quantity or 0
        qty_init = batch.initial_quantity or 0
        
        current_size_group['total_available'] += qty_avail
        current_size_group['total_initial'] += qty_init
        
        current_type_group['total_available'] += qty_avail
        current_type_group['total_initial'] += qty_init

    if current_type_group is not None:
        # Calcular categoría para el último talle
        if current_type_group['sizes']:
            prev_size_qty = current_type_group['sizes'][-1]['total_available']
            for threshold in stock_thresholds:
                if threshold.matches(prev_size_qty):
                    current_type_group['sizes'][-1]['stock_category'] = threshold
                    break
                    
        # Calcular categoría para la última prenda
        total_qty = current_type_group['total_available']
        for threshold in stock_thresholds:
            if threshold.matches(total_qty):
                current_type_group['stock_category'] = threshold
                break
        grouped_stock.append(current_type_group)
    
    context = {
        'grouped_stock': grouped_stock,
    }
    return render(request, 'sigera/stock_list.html', context)

@login_required
def size_batch_detail(request, size_id):
    """
    Vista detallada de batches para un talle específico
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para acceder al inventario.")
        return redirect('sigera:home')

    size = get_object_or_404(ClothingSize, id=size_id)
    batches = ClothingBatch.objects.filter(
        clothing_size=size,
        available_quantity__gt=0
    ).select_related('clothing_size__clothing_type').order_by('reception_date')
    
    # Obtener las categorías configurables
    stock_thresholds = list(StockThreshold.objects.order_by('order'))
    
    # Asignar categoría a cada batch
    for batch in batches:
        quantity = batch.available_quantity or 0
        for threshold in stock_thresholds:
            if threshold.matches(quantity):
                batch.stock_category = threshold
                break
        else:
            batch.stock_category = None
    
    context = {
        'size': size,
        'batches': batches,
    }
    return render(request, 'sigera/size_batch_detail.html', context)

@login_required
def personnel_list(request):
    """
    Vista de listado de personal con búsqueda (Q objects)
    """
    query = request.GET.get('q', '')
    required_measure_count = ClothingType.objects.filter(show_in_measure_sheet=True).count()
    personnel = Personnel.objects.select_related('assigned_unit').annotate(
        loaded_measure_count=Count(
            'clothing_measures',
            filter=Q(clothing_measures__clothing_type__show_in_measure_sheet=True),
            distinct=True,
        )
    )
    
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    
    if not is_admin:
        if getattr(user, 'unit', None):
            personnel = personnel.filter(assigned_unit=user.unit)
        else:
            personnel = personnel.none()
    
    if query:
        personnel = personnel.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(dni__icontains=query)
        )
        
    personnel = personnel.order_by('assigned_unit__name', 'last_name', 'first_name')
    rank_labels = dict(Personnel.RANK_CHOICES)
    rank_order = {rank_key: index for index, (rank_key, _label) in enumerate(Personnel.RANK_CHOICES)}
    grouped_personnel_map = {}

    for person in personnel:
        unit_key = person.assigned_unit_id or 'sin-unidad'
        if unit_key not in grouped_personnel_map:
            grouped_personnel_map[unit_key] = {
                'id': unit_key,
                'name': person.assigned_unit.name if person.assigned_unit else 'Sin unidad asignada',
                'is_unassigned': person.assigned_unit_id is None,
                'count': 0,
                'complete_measure_count': 0,
                'partial_measure_count': 0,
                'empty_measure_count': 0,
                'rank_map': {},
            }

        unit_group = grouped_personnel_map[unit_key]
        unit_group['count'] += 1

        person.loaded_measure_count = person.loaded_measure_count or 0
        if required_measure_count and person.loaded_measure_count >= required_measure_count:
            person.measure_badge_label = f"Completo ({person.loaded_measure_count}/{required_measure_count})"
            person.measure_badge_class = "bg-success-subtle text-success border border-success-subtle"
            unit_group['complete_measure_count'] += 1
        elif person.loaded_measure_count:
            person.measure_badge_label = f"Parcial ({person.loaded_measure_count}/{required_measure_count})"
            person.measure_badge_class = "bg-warning-subtle text-warning border border-warning-subtle"
            unit_group['partial_measure_count'] += 1
        else:
            person.measure_badge_label = "Sin cargar"
            person.measure_badge_class = "bg-light text-muted border"
            unit_group['empty_measure_count'] += 1

        if person.rank not in unit_group['rank_map']:
            unit_group['rank_map'][person.rank] = {
                'id': person.rank,
                'name': rank_labels.get(person.rank, person.rank),
                'order': rank_order.get(person.rank, 999),
                'people': [],
                'complete_measure_count': 0,
                'partial_measure_count': 0,
                'empty_measure_count': 0,
            }
        rank_group = unit_group['rank_map'][person.rank]
        rank_group['people'].append(person)
        if required_measure_count and person.loaded_measure_count >= required_measure_count:
            rank_group['complete_measure_count'] += 1
        elif person.loaded_measure_count:
            rank_group['partial_measure_count'] += 1
        else:
            rank_group['empty_measure_count'] += 1

    grouped_personnel = sorted(
        grouped_personnel_map.values(),
        key=lambda group: (group['is_unassigned'], group['name'])
    )
    for unit_group in grouped_personnel:
        unit_group['ranks'] = sorted(
            unit_group['rank_map'].values(),
            key=lambda rank_group: rank_group['order']
        )
    
    context = {
        'personnel_list': personnel,
        'grouped_personnel': grouped_personnel,
        'required_measure_count': required_measure_count,
        'search_query': query,
        'is_admin': is_admin,
    }
    return render(request, 'sigera/personnel_list.html', context)

@login_required
def assignment_list(request):
    """
    Vista de historial de entregas de ropa con búsqueda y control de provisiones
    """
    query = request.GET.get('q', '')
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    
    # 1. Historial General
    assignments = ClothingAssignment.objects.select_related(
        'personnel', 'batch__clothing_size__clothing_type', 'issued_by'
    )
    
    if not is_admin:
        if getattr(user, 'unit', None):
            assignments = assignments.filter(personnel__assigned_unit=user.unit)
        else:
            assignments = assignments.none()
    
    if query:
        assignments = assignments.filter(
            Q(personnel__first_name__icontains=query) |
            Q(personnel__last_name__icontains=query) |
            Q(personnel__dni__icontains=query) |
            Q(batch__clothing_size__clothing_type__name__icontains=query)
        )
        
    assignments = assignments.order_by('personnel__last_name', 'personnel__first_name', '-assigned_date', '-id')
    
    # 2. Primera Provisión
    from django.db.models import Count
    personnel_first_provision = Personnel.objects.annotate(
        num_assignments=Count('assignments')
    ).filter(num_assignments=0).select_related('assigned_unit')
    
    if not is_admin:
        if getattr(user, 'unit', None):
            personnel_first_provision = personnel_first_provision.filter(assigned_unit=user.unit)
        else:
            personnel_first_provision = personnel_first_provision.none()
    
    if query:
        personnel_first_provision = personnel_first_provision.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(dni__icontains=query)
        )
        
    # 3. Renovaciones (Vencidos o próximos a vencer en <= 30 días)
    from datetime import date, timedelta
    active_assignments = ClothingAssignment.objects.filter(
        returned=False,
        reception_status='CONFIRMED',
    ).select_related('personnel', 'batch__clothing_size__clothing_type')
    
    if not is_admin:
        if getattr(user, 'unit', None):
            active_assignments = active_assignments.filter(personnel__assigned_unit=user.unit)
        else:
            active_assignments = active_assignments.none()
    
    if query:
        active_assignments = active_assignments.filter(
            Q(personnel__first_name__icontains=query) |
            Q(personnel__last_name__icontains=query) |
            Q(personnel__dni__icontains=query) |
            Q(batch__clothing_size__clothing_type__name__icontains=query)
        )
        
    renewals_list = []
    today = date.today()
    threshold_date = today + timedelta(days=30)
    
    for act in active_assignments:
        exp_date = act.expiration_date
        if exp_date and exp_date <= threshold_date:
            renewals_list.append(act)
            
    # Ordenar: los más vencidos primero
    renewals_list.sort(key=lambda x: x.expiration_date)
    
    pending_personnel_ids = set(assignments.filter(reception_status='PENDING').values_list('personnel_id', flat=True))
    
    context = {
        'assignment_list': assignments,
        'personnel_first_provision': personnel_first_provision,
        'renewals_list': renewals_list,
        'pending_personnel_ids': pending_personnel_ids,
        'search_query': query,
        'is_admin': is_admin,
    }
    return render(request, 'sigera/assignment_list.html', context)

@login_required
def personnel_create(request):
    """
    Vista para añadir nuevo personal
    """
    if request.method == 'POST':
        form = PersonnelForm(request.POST, user=request.user)
        if form.is_valid():
            person = form.save()
            messages.success(request, f"¡Legajo de {person.last_name}, {person.first_name} creado!")
            return redirect(f"{reverse('sigera:personnel_measure_sheet', kwargs={'pk': person.pk})}?edit=1")
    else:
        form = PersonnelForm(user=request.user)
        
    return render(request, 'sigera/personnel_form.html', {'form': form})

@login_required
def personnel_import(request):
    """
    Vista para importar personal masivamente desde un archivo Excel.
    """
    if not request.user.is_superuser:
        messages.error(request, "Solo el superusuario puede importar personal desde Excel.")
        return redirect('sigera:personnel_list')

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            df = pd.read_excel(excel_file)
            
            # Normalizar nombres de columnas
            df.columns = [c.strip().lower() for c in df.columns]
            
            # Columnas esperadas
            required_cols = ['nombres', 'apellidos', 'matricula', 'jerarquia']
            missing_cols = [c for c in required_cols if c not in df.columns]
            
            if missing_cols:
                messages.error(request, f"Faltan las siguientes columnas en el Excel: {', '.join(missing_cols)}")
                return redirect('sigera:personnel_import')

            rank_map = {
                'capitan de navio': 'CAPITAN_NAVIO', 'cn': 'CAPITAN_NAVIO',
                'capitan de fragata': 'CAPITAN_FRAGATA', 'cf': 'CAPITAN_FRAGATA',
                'capitan de corbeta': 'CAPITAN_CORBETA', 'cc': 'CAPITAN_CORBETA',
                'teniente de navio': 'TENIENTE_NAVIO', 'tn': 'TENIENTE_NAVIO',
                'teniente de fragata': 'TENIENTE_FRAGATA', 'tf': 'TENIENTE_FRAGATA',
                'teniente de corbeta': 'TENIENTE_CORBETA', 'tc': 'TENIENTE_CORBETA',
                'guardiamarina': 'GUARDIAMARINA', 'gu': 'GUARDIAMARINA',
                'suboficial mayor': 'SUBOFICIAL_MAYOR', 'sm': 'SUBOFICIAL_MAYOR',
                'suboficial principal': 'SUBOFICIAL_PRINCIPAL', 'sp': 'SUBOFICIAL_PRINCIPAL',
                'suboficial primero': 'SUBOFICIAL_PRIMERO', 'si': 'SUBOFICIAL_PRIMERO',
                'suboficial segundo': 'SUBOFICIAL_SEGUNDO', 'ss': 'SUBOFICIAL_SEGUNDO',
                'cabo principal': 'CABO_PRINCIPAL', 'cp': 'CABO_PRINCIPAL',
                'cabo primero': 'CABO_PRIMERO', 'ci': 'CABO_PRIMERO',
                'cabo segundo': 'CABO_SEGUNDO', 'cs': 'CABO_SEGUNDO',
                'marinero primero': 'MARINERO_PRIMERO', 'm1': 'MARINERO_PRIMERO',
                'marinero segundo': 'MARINERO_SEGUNDO', 'm2': 'MARINERO_SEGUNDO',
                'agente civil': 'AGENTE_CIVIL', 'ac': 'AGENTE_CIVIL',
            }

            created_count = 0
            updated_count = 0
            errors = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        dni = str(row['matricula']).strip().upper()
                        if not dni or dni == 'NAN': continue
                        
                        first_name = str(row['nombres']).strip().upper()
                        last_name = str(row['apellidos']).strip().upper()
                        rank_raw = str(row['jerarquia']).strip().lower()
                        
                        # Buscar jerarquía
                        rank_key = rank_map.get(rank_raw)
                        if not rank_key:
                            # Intento de búsqueda parcial
                            for k, v in rank_map.items():
                                if k in rank_raw:
                                    rank_key = v
                                    break
                            if not rank_key: rank_key = 'AGENTE_CIVIL' # Default

                        unit = None
                        if 'unidad' in df.columns:
                            unit_name = str(row['unidad']).strip()
                            unit = Unit.objects.filter(name__icontains=unit_name).first()

                        person, created = Personnel.objects.update_or_create(
                            dni=dni,
                            defaults={
                                'first_name': first_name,
                                'last_name': last_name,
                                'rank': rank_key,
                                'assigned_unit': unit
                            }
                        )
                        
                        if created: created_count += 1
                        else: updated_count += 1
                        
                    except Exception as e:
                        errors.append(f"Fila {index+2}: {str(e)}")

            if created_count > 0 or updated_count > 0:
                messages.success(request, f"Importación finalizada. Creados: {created_count}, Actualizados: {updated_count}")
            if errors:
                messages.warning(request, f"Hubo {len(errors)} errores durante la importación. Revise el formato.")
            
            return redirect('sigera:personnel_list')
            
        except Exception as e:
            messages.error(request, f"Error al procesar el archivo: {str(e)}")
            return redirect('sigera:personnel_import')

    return render(request, 'sigera/personnel_import.html')

@login_required
def personnel_edit(request, pk):
    person = get_object_or_404(Personnel, pk=pk)
    if request.method == 'POST':
        form = PersonnelForm(request.POST, instance=person, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"¡Datos de {person.last_name} actualizados correctamente!")
            return redirect('sigera:personnel_list')
    else:
        form = PersonnelForm(instance=person, user=request.user)
        
    return render(request, 'sigera/personnel_form.html', {'form': form, 'edit_mode': True})


@login_required
def personnel_measure_sheet(request, pk):
    person = get_object_or_404(Personnel.objects.select_related('assigned_unit'), pk=pk)
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()

    if not is_admin and getattr(user, 'unit', None) and person.assigned_unit_id != user.unit_id:
        messages.error(request, "Acceso denegado: No tienes permisos para modificar esta planilla.")
        return redirect('sigera:personnel_list')
    if not is_admin and not getattr(user, 'unit', None):
        messages.error(request, "Acceso denegado: No tienes unidad asignada.")
        return redirect('sigera:personnel_list')

    clothing_types = ClothingType.objects.filter(show_in_measure_sheet=True).prefetch_related('sizes').order_by('name')
    all_measures = PersonnelClothingMeasure.objects.filter(personnel=person).select_related('clothing_type', 'clothing_size')
    edit_mode = request.GET.get('edit') == '1' or request.method == 'POST'

    if request.method == 'POST':
        forms_by_type = []
        is_valid = True
        for clothing_type in clothing_types:
            prefix = f"measure_{clothing_type.id}"
            form = ClothingTypeMeasuresForm(
                request.POST,
                prefix=prefix,
                clothing_type=clothing_type,
                existing_measures=all_measures.filter(clothing_type=clothing_type),
            )
            forms_by_type.append((clothing_type, form))
            if not form.is_valid():
                is_valid = False

        if is_valid:
            with transaction.atomic():
                for clothing_type, form in forms_by_type:
                    custom_measure = form.cleaned_data.get('custom_measure')
                    notes = form.cleaned_data.get('notes')
                    
                    for sys, field_name in form.system_fields:
                        clothing_size = form.cleaned_data.get(field_name)
                        existing = all_measures.filter(
                            clothing_type=clothing_type,
                            size_system=sys
                        ).first()
                        
                        is_first_system = (sys == form.system_fields[0][0])
                        
                        if clothing_size or (is_first_system and (custom_measure or notes)):
                            if not existing:
                                existing = PersonnelClothingMeasure(
                                    personnel=person,
                                    clothing_type=clothing_type,
                                    size_system=sys
                                )
                            existing.clothing_size = clothing_size
                            existing.custom_measure = custom_measure
                            existing.notes = notes
                            existing.save()
                        elif existing:
                            existing.delete()

            messages.success(request, "Planilla de medidas actualizada correctamente.")
            return redirect('sigera:personnel_measure_sheet', pk=person.pk)
    else:
        forms_by_type = []
        for clothing_type in clothing_types:
            prefix = f"measure_{clothing_type.id}"
            form = ClothingTypeMeasuresForm(
                prefix=prefix,
                clothing_type=clothing_type,
                existing_measures=all_measures.filter(clothing_type=clothing_type),
            )
            forms_by_type.append((clothing_type, form))

    rows = [
        {
            'clothing_type': clothing_type,
            'form': form,
            'sizes_count': clothing_type.sizes.count(),
        }
        for clothing_type, form in forms_by_type
    ]

    from collections import defaultdict
    grouped = defaultdict(list)
    for measure in all_measures:
        grouped[measure.clothing_type].append(measure)

    completed_rows = []
    for clothing_type, measures in grouped.items():
        custom_measure = next((m.custom_measure for m in measures if m.custom_measure), "")
        notes = next((m.notes for m in measures if m.notes), "")
        completed_rows.append({
            'clothing_type': clothing_type,
            'measures': measures,
            'custom_measure': custom_measure,
            'notes': notes,
        })

    return render(
        request,
        'sigera/personnel_measure_sheet.html',
        {
            'person': person,
            'rows': rows,
            'completed_rows': completed_rows,
            'edit_mode': edit_mode,
            'is_admin': is_admin,
        },
    )


@login_required
def size_curve(request):
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    selected_clothing_type = request.GET.get('clothing_type', '')
    selected_unit = request.GET.get('unit', '')

    measures = PersonnelClothingMeasure.objects.select_related(
        'personnel__assigned_unit',
        'clothing_type',
        'clothing_size',
    ).filter(
        Q(clothing_size__isnull=False) | Q(custom_measure__isnull=False)
    )

    if not is_admin:
        if getattr(user, 'unit', None):
            measures = measures.filter(personnel__assigned_unit=user.unit)
            selected_unit = str(user.unit_id)
        else:
            measures = measures.none()
    elif selected_unit:
        measures = measures.filter(personnel__assigned_unit_id=selected_unit)

    if selected_clothing_type:
        measures = measures.filter(clothing_type_id=selected_clothing_type)

    stock_by_size = {
        row['clothing_size_id']: row['total'] or 0
        for row in ClothingBatch.objects.values('clothing_size_id').annotate(total=Sum('available_quantity'))
    }

    curve_map = {}
    for measure in measures:
        if measure.clothing_size:
            size_label = measure.clothing_size.size
            size_id = measure.clothing_size_id
            stock_available = stock_by_size.get(size_id, 0)
            sort_value = size_label
        else:
            size_label = measure.custom_measure
            size_id = None
            stock_available = None
            sort_value = size_label or ''

        if not size_label:
            continue

        key = (measure.clothing_type_id, size_id, size_label)
        if key not in curve_map:
            curve_map[key] = {
                'clothing_type': measure.clothing_type,
                'size_label': size_label,
                'size_id': size_id,
                'required_quantity': 0,
                'stock_available': stock_available,
                'sort_value': sort_value,
                'people': [],
            }
        curve_map[key]['required_quantity'] += 1
        curve_map[key]['people'].append({
            'person': measure.personnel,
            'measure': measure,
        })

    curve_rows = []
    for row in curve_map.values():
        if row['stock_available'] is None:
            row['missing_quantity'] = row['required_quantity']
        else:
            row['missing_quantity'] = max(row['required_quantity'] - row['stock_available'], 0)
        row['people'].sort(key=lambda item: (item['person'].last_name, item['person'].first_name))
        curve_rows.append(row)

    curve_rows.sort(key=lambda row: (row['clothing_type'].name, row['sort_value']))

    grouped_curve = []
    current_group = None
    for row in curve_rows:
        if current_group is None or current_group['clothing_type'] != row['clothing_type']:
            if current_group:
                grouped_curve.append(current_group)
            current_group = {
                'clothing_type': row['clothing_type'],
                'rows': [],
                'required_total': 0,
                'stock_total': 0,
                'missing_total': 0,
            }
        current_group['rows'].append(row)
        current_group['required_total'] += row['required_quantity']
        current_group['stock_total'] += row['stock_available'] or 0
        current_group['missing_total'] += row['missing_quantity']
    if current_group:
        grouped_curve.append(current_group)

    measured_personnel_map = {}
    for measure in measures:
        person = measure.personnel
        if person.id not in measured_personnel_map:
            measured_personnel_map[person.id] = {
                'person': person,
                'measure_count': 0,
            }
        measured_personnel_map[person.id]['measure_count'] += 1

    measured_personnel_details = sorted(
        measured_personnel_map.values(),
        key=lambda item: (
            item['person'].assigned_unit.name if item['person'].assigned_unit else '',
            item['person'].last_name,
            item['person'].first_name,
        )
    )
    missing_detail_rows = [row for row in curve_rows if row['missing_quantity']]

    context = {
        'grouped_curve': grouped_curve,
        'curve_rows': curve_rows,
        'missing_detail_rows': missing_detail_rows,
        'measured_personnel_details': measured_personnel_details,
        'clothing_types': ClothingType.objects.order_by('name'),
        'units': Unit.objects.order_by('name') if is_admin else Unit.objects.filter(pk=getattr(user, 'unit_id', None)),
        'selected_clothing_type': selected_clothing_type,
        'selected_unit': selected_unit,
        'is_admin': is_admin,
        'total_required': sum(row['required_quantity'] for row in curve_rows),
        'total_missing': sum(row['missing_quantity'] for row in curve_rows),
        'measured_personnel_count': len(measured_personnel_details),
    }
    return render(request, 'sigera/size_curve.html', context)

@login_required
def personnel_delete(request, pk):
    """
    Vista para eliminar un registro de personal
    """
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
        messages.error(request, "Acceso denegado: No tienes permisos para eliminar personal.")
        return redirect('sigera:personnel_list')
    person = get_object_or_404(Personnel, pk=pk)
    if request.method == 'POST':
        ok, error_msg = check_sigera_delete_pin(request)
        if not ok:
            messages.error(request, error_msg)
            return render(request, 'sigera/confirm_delete.html', {
                'title': 'Eliminar Personal',
                'message': f"¿Está seguro que desea eliminar a {person.last_name}, {person.first_name} ({person.dni})? Esta acción borrará permanentemente su legajo del sistema.",
                'cancel_url': reverse('sigera:personnel_list'),
            })
        name = f"{person.last_name}, {person.first_name}"
        person.delete()
        messages.success(request, f"¡Legajo de {name} eliminado correctamente!")
        return redirect('sigera:personnel_list')
    
    return render(request, 'sigera/confirm_delete.html', {
        'title': 'Eliminar Personal',
        'message': f"¿Está seguro que desea eliminar a {person.last_name}, {person.first_name} ({person.dni})? Esta acción borrará permanentemente su legajo del sistema.",
        'cancel_url': reverse('sigera:personnel_list'),
    })

@login_required
def assignment_create(request):
    """
    Vista para registrar una nueva entrega de cargo con deducción de stock
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para registrar entregas de material.")
        return redirect('sigera:assignment_list')

    if request.method == 'POST':
        form = ClothingAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.issued_by = request.user
            
            # Usar transacción atómica para asegurar consistencia
            with transaction.atomic():
                # Reducir el stock del lote
                batch = assignment.batch
                requested_qty = assignment.quantity
                
                # Double check de seguridad (aunque el form ya lo validó)
                if batch.available_quantity >= requested_qty:
                    batch.available_quantity -= requested_qty
                    batch.save()
                    
                    # Guardar la asignación
                    assignment.reception_status = 'PENDING'
                    assignment.save()
                    messages.success(request, "La entrega se registró como pendiente de recepción y el inventario del pañol fue actualizado.")
                    return redirect('sigera:assignment_list')
                else:
                    messages.error(request, "Error crítico: El stock disponible cambió concurridamente. Reintente.")
    else:
        person_id = request.GET.get('person')
        initial_data = {}
        if person_id:
            initial_data['personnel'] = person_id
        form = ClothingAssignmentForm(initial=initial_data)
        
    return render(request, 'sigera/assignment_form.html', {'form': form})


@login_required
def assignment_confirm_reception(request, pk):
    user = request.user
    assignment = get_object_or_404(
        ClothingAssignment.objects.select_related('personnel__assigned_unit'),
        pk=pk,
        returned=False,
        reception_status='PENDING',
    )

    user_unit = getattr(user, 'unit', None)
    can_confirm = user_unit and assignment.personnel.assigned_unit_id == user_unit.id
    if not can_confirm:
        messages.error(request, "Solo el usuario del destino del causante puede confirmar esta recepción.")
        return redirect('sigera:assignment_list')

    if request.method == 'POST':
        assignment.reception_status = 'CONFIRMED'
        assignment.received_by = user
        assignment.received_at = timezone.now()
        assignment.save(update_fields=['reception_status', 'received_by', 'received_at'])
        messages.success(request, "Recepción confirmada correctamente.")
        return redirect(f"{reverse('sigera:assignment_list')}?download_pdf={assignment.pk}")

    return redirect('sigera:assignment_list')


@login_required
def assignment_reception_pdf(request, pk):
    user = request.user
    assignment = get_object_or_404(
        ClothingAssignment.objects.select_related(
            'personnel__assigned_unit',
            'batch__clothing_size__clothing_type',
            'issued_by',
            'received_by',
        ),
        pk=pk,
    )

    user_unit = getattr(user, 'unit', None)
    can_download = user.is_superuser or (user_unit and assignment.personnel.assigned_unit_id == user_unit.id)
    if not can_download:
        messages.error(request, "No tiene permisos para descargar esta constancia.")
        return redirect('sigera:assignment_list')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    title_style = styles['Title']
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading3'],
        textColor=colors.HexColor('#462880'),
        spaceBefore=10,
        spaceAfter=6,
    )
    table_value_style = ParagraphStyle(
        'TableValue',
        parent=normal,
        fontSize=10,
        leading=13,
    )

    personnel = assignment.personnel
    clothing_size = assignment.batch.clothing_size
    clothing_type = clothing_size.clothing_type
    unit_name = personnel.assigned_unit.name if personnel.assigned_unit else 'Sin destino'

    inst_style = ParagraphStyle(
        'InstTitle',
        parent=styles['Normal'],
        alignment=1,
        fontName='Helvetica-Bold',
        fontSize=11,
    )

    elements = [
        Paragraph("CONSTANCIA DE RECEPCION DE PRENDA / EQUIPAMIENTO", title_style),
        Spacer(1, 10),
        Paragraph("ARMADA ARGENTINA - COMANDO DE LA AVIACIÓN NAVAL", inst_style),
        Spacer(1, 10),
        Paragraph("Sistema de Gestion de Ropa Aeronaval - SIGERA", normal),
        Spacer(1, 14),
        Paragraph("Datos del personal receptor", section_style),
    ]

    personnel_data = [
        ["Apellido y nombre", f"{personnel.last_name}, {personnel.first_name}"],
        ["Jerarquia / rango", personnel.get_rank_display()],
        ["Matricula", personnel.dni],
        ["Destino", unit_name],
    ]
    personnel_table = Table(personnel_data, colWidths=[5 * cm, 11 * cm])
    personnel_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f3f5')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#adb5bd')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(personnel_table)

    elements.extend([
        Spacer(1, 12),
        Paragraph("Material entregado", section_style),
    ])
    deliverer_unit = getattr(assignment.received_by, 'unit', None) or personnel.assigned_unit
    if deliverer_unit and deliverer_unit.description:
        deliverer_text = deliverer_unit.description
    elif deliverer_unit and deliverer_unit.name:
        deliverer_text = deliverer_unit.name
    else:
        deliverer_text = "Unidad no informada"

    material_data = [
        ["Prenda / equipamiento", clothing_type.name],
        ["Talle", clothing_size.size],
        ["Cantidad", str(assignment.quantity)],
        ["Lote / ingreso", str(assignment.batch.id)],
        ["Fecha de entrega", assignment.assigned_date.strftime('%d/%m/%Y') if assignment.assigned_date else '-'],
        ["Entregado por", Paragraph(escape(deliverer_text), table_value_style)],
        ["Estado de recepcion", assignment.get_reception_status_display()],
        ["Observaciones", assignment.notes or "-"],
    ]
    material_table = Table(material_data, colWidths=[5 * cm, 11 * cm])
    material_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fff3cd')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#adb5bd')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(material_table)

    elements.extend([
        Spacer(1, 20),
        Paragraph(
            "Declaro haber recibido el material detallado precedentemente, en la cantidad indicada, para su uso y control conforme las normas internas vigentes.",
            normal,
        ),
        Spacer(1, 36),
    ])

    signature_data = [
        ["", ""],
        ["Firma y aclaracion del receptor", "Firma y aclaracion del responsable del destino"],
        ["Fecha: ____ / ____ / ______", "Fecha: ____ / ____ / ______"],
    ]
    signature_table = Table(signature_data, colWidths=[8 * cm, 8 * cm])
    signature_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),
        ('LINEABOVE', (1, 1), (1, 1), 1, colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#495057')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(signature_table)

    doc.build(elements)
    buffer.seek(0)
    filename = f"recepcion_sigera_{assignment.id}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

from django.utils import timezone
from .forms import ClothingTypeForm, ClothingBatchForm

@login_required
def catalog_list(request):
    """
    Vista de listado del catálogo de prendas (modelos de vestuario).
    """
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')

    from django.db.models import Prefetch
    clothing_types = ClothingType.objects.prefetch_related(
        Prefetch('sizes', queryset=ClothingSize.objects.order_by('size_system', 'size'))
    ).order_by('name')
    sizes_in_stock = set(
        ClothingSize.objects.filter(batches__available_quantity__gt=0)
        .values_list('id', flat=True)
    )
    context = {
        'clothing_types': clothing_types,
        'sizes_in_stock': sizes_in_stock,
    }
    return render(request, 'sigera/catalog_list.html', context)

@login_required
def catalog_create(request):
    """
    Vista para dar de alta un nuevo modelo de prenda.
    """
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')
    if request.method == 'POST':
        form = ClothingTypeForm(request.POST)
        if form.is_valid():
            ct = form.save()
            messages.success(request, f"¡Modelo de prenda '{ct.name}' registrado exitosamente!")
            return redirect('sigera:catalog_list')
    else:
        form = ClothingTypeForm()
        
    return render(request, 'sigera/catalog_form.html', {'form': form})

@login_required
def catalog_edit(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')
    item = get_object_or_404(ClothingType, pk=pk)
    if request.method == 'POST':
        form = ClothingTypeForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"¡Modelo de prenda '{item.name}' actualizado exitosamente!")
            return redirect('sigera:catalog_list')
    else:
        form = ClothingTypeForm(instance=item)
        
    return render(request, 'sigera/catalog_form.html', {'form': form, 'edit_mode': True})

@login_required
def catalog_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')
        
    item = get_object_or_404(ClothingType, pk=pk)
    if request.method == 'POST':
        ok, error_msg = check_sigera_delete_pin(request)
        if not ok:
            messages.error(request, error_msg)
            return render(request, 'sigera/confirm_delete.html', {
                'title': 'Eliminar Modelo del Catálogo',
                'message': f"¿Está seguro que desea borrar el modelo '{item.name}'? Si existen lotes o cargos asociados, no se podrá eliminar.",
                'cancel_url': reverse('sigera:catalog_list'),
            })
        try:
            name = item.name
            item.delete()
            messages.success(request, f"El modelo de prenda '{name}' ha sido eliminado.")
        except Exception as e:
            messages.error(request, f"No se pudo eliminar el modelo porque está siendo usado en otros registros. Error: {str(e)}")
        return redirect('sigera:catalog_list')
        
    return render(request, 'sigera/confirm_delete.html', {
        'title': 'Eliminar Modelo del Catálogo',
        'message': f"¿Está seguro que desea borrar el modelo '{item.name}'? Si existen lotes o cargos asociados, no se podrá eliminar.",
        'cancel_url': reverse('sigera:catalog_list'),
    })

from .forms import ClothingSizeForm

@login_required
def catalog_size_create(request):
    """
    Vista para agregar un talle a un modelo de prenda existente.
    """
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')
    if request.method == 'POST':
        form = ClothingSizeForm(request.POST)
        if form.is_valid():
            sz = form.save()
            messages.success(request, f"¡Talle '{sz.size}' añadido exitosamente al modelo {sz.clothing_type.name}!")
            return redirect('sigera:catalog_list')
    else:
        form = ClothingSizeForm()
        
    return render(request, 'sigera/size_form.html', {'form': form, 'edit_mode': False})

@login_required
def catalog_size_edit(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')
    size = get_object_or_404(ClothingSize, pk=pk)
    if request.method == 'POST':
        form = ClothingSizeForm(request.POST, instance=size)
        if form.is_valid():
            form.save()
            messages.success(request, f"Talle '{size.size}' actualizado correctamente.")
            return redirect('sigera:catalog_list')
    else:
        form = ClothingSizeForm(instance=size)
    return render(request, 'sigera/size_form.html', {'form': form, 'edit_mode': True, 'size': size})

@login_required
def catalog_size_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Solo el superusuario puede acceder al Catálogo.")
        return redirect('sigera:home')
    size = get_object_or_404(ClothingSize, pk=pk)
    if request.method == 'POST':
        ok, error_msg = check_sigera_delete_pin(request)
        if not ok:
            messages.error(request, error_msg)
            return render(request, 'sigera/confirm_delete.html', {
                'title': 'Eliminar Talle',
                'message': f"¿Eliminar el talle {size.size} de {size.clothing_type.name}? Esto eliminará también los ingresos asociados.",
                'cancel_url': reverse('sigera:catalog_list'),
            })
        size.delete()
        messages.success(request, f"Talle {size.size} eliminado correctamente.")
        return redirect('sigera:catalog_list')
    return render(request, 'sigera/confirm_delete.html', {
        'title': 'Eliminar Talle',
        'message': f"¿Eliminar el talle {size.size} de {size.clothing_type.name}? Esto eliminará también los ingresos asociados.",
        'cancel_url': reverse('sigera:catalog_list'),
    })

@login_required
def batch_create(request):
    """
    Vista para registrar un nuevo Ingreso a Pañol (Stock).
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para registrar ingresos de stock.")
        return redirect('sigera:home')

    if request.method == 'POST':
        form = ClothingBatchForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            # La cantidad disponible inicial es igual a lo recibido
            batch.available_quantity = batch.initial_quantity
            batch.save()
            messages.success(request, "¡Ingreso de material a pañol registrado exitosamente. El inventario ha aumentado!")
            return redirect('sigera:stock_list')
    else:
        form = ClothingBatchForm()
        
    sizes_qs = ClothingSize.objects.order_by('clothing_type__name', 'size_system', 'size')
    sizes_by_type = []
    for s in sizes_qs:
        display_name = f"{s.size} ({s.size_system})" if s.size_system else s.size
        sizes_by_type.append({
            'id': s.id,
            'clothing_type_id': s.clothing_type_id,
            'size': display_name
        })
    return render(request, 'sigera/batch_form.html', {'form': form, 'sizes_by_type': sizes_by_type})

@login_required
def assignment_return_view(request, pk):
    """
    Vista para procesar la devolución de una prenda.
    Cambia el estado del cargo y repone el stock.
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para registrar devoluciones.")
        return redirect('sigera:assignment_list')

    if request.method == 'POST':
        assignment = get_object_or_404(ClothingAssignment, pk=pk, returned=False, reception_status='CONFIRMED')

        if not assignment.batch.clothing_size.clothing_type.must_be_returned:
            messages.error(request, "Esta entrega no puede devolverse porque la prenda está marcada como no retornable.")
            return redirect('sigera:assignment_list')
        
        with transaction.atomic():
            # Reponer el stock al lote original
            batch = assignment.batch
            batch.available_quantity += assignment.quantity
            batch.save()
            
            # Cerrar el cargo
            assignment.returned = True
            assignment.return_date = timezone.now().date()
            assignment.save()
            
            messages.success(request, "Devolución registrada correctamente. El material retornó al pañol.")
            
    return redirect('sigera:assignment_list')

@login_required
def batch_movements(request, pk):
    """
    Vista para ver el historial de movimientos (entregas y devoluciones) de un lote específico.
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para ver movimientos de stock.")
        return redirect('sigera:home')

    batch = get_object_or_404(ClothingBatch, pk=pk)
    assignments = batch.assignments.all().order_by('-assigned_date', '-id')
    
    context = {
        'batch': batch,
        'assignments': assignments,
    }
    return render(request, 'sigera/batch_movements.html', context)

@login_required
def batch_delete(request, pk):
    """
    Vista para eliminar completamente un lote de la base de datos.
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para eliminar lotes del inventario.")
        return redirect('sigera:stock_list')

    batch = get_object_or_404(ClothingBatch, pk=pk)
    
    if request.method == 'POST':
        ok, error_msg = check_sigera_delete_pin(request)
        if not ok:
            messages.error(request, error_msg)
            assignments_count = batch.assignments.count()
            warnings = []
            if assignments_count > 0:
                warnings.append(f"Este lote tiene {assignments_count} entregas (cargos) asociadas a personal. Si continuás, TODAS esas entregas también serán eliminadas irreversiblemente de la base de datos.")
            return render(request, 'sigera/confirm_delete.html', {
                'title': 'Eliminar Lote de Inventario',
                'message': f"¿Está seguro que desea borrar de la base de datos el lote '{batch}'?",
                'warnings': warnings,
                'cancel_url': reverse('sigera:stock_list'),
            })
        try:
            name = str(batch)
            # Como los cargos (ClothingAssignment) tienen on_delete=PROTECT,
            # debemos eliminarlos manualmente primero si queremos forzar el borrado del lote.
            assignments_count = batch.assignments.count()
            if assignments_count > 0:
                batch.assignments.all().delete()
            
            batch.delete()
            messages.success(request, f"¡El lote '{name}' y sus {assignments_count} entregas asociadas se eliminaron de la base de datos correctamente!")
        except Exception as e:
            messages.error(request, f"No se pudo eliminar el lote. Error: {str(e)}")
        return redirect('sigera:stock_list')
        
    assignments_count = batch.assignments.count()
    warnings = []
    if assignments_count > 0:
        warnings.append(f"Este lote tiene {assignments_count} entregas (cargos) asociadas a personal. Si continuás, TODAS esas entregas también serán eliminadas irreversiblemente de la base de datos.")

    return render(request, 'sigera/confirm_delete.html', {
        'title': 'Eliminar Lote de Inventario',
        'message': f"¿Está seguro que desea borrar de la base de datos el lote '{batch}'?",
        'warnings': warnings,
        'cancel_url': reverse('sigera:stock_list'),
    })

@login_required
def purchase_forecast(request):
    """
    Vista de la Calculadora de Pronóstico de Abastecimiento de SIGERA.
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica', 'Editor']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para acceder a la calculadora.")
        return redirect('sigera:home')
        
    # Obtener modelos para el formulario
    units = Unit.objects.all().order_by('name')
    clothing_types = ClothingType.objects.all().order_by('name')
    ranks = Personnel.RANK_CHOICES
    
    # Parámetros por defecto
    selected_unit_ids = []
    selected_rank_codes = []
    selected_clothing_ids = []
    horizon_months = 0
    safety_margin = 10.0 # 10% por defecto
    calculated = False
    results = {}
    
    if request.method == 'POST':
        selected_unit_ids_raw = request.POST.getlist('unit_ids')
        if selected_unit_ids_raw:
            selected_unit_ids = [int(i) for i in selected_unit_ids_raw if i]
        else:
            selected_unit_id_raw = request.POST.get('unit_id')
            if selected_unit_id_raw:
                selected_unit_ids = [int(selected_unit_id_raw)]
            
        selected_rank_codes = request.POST.getlist('rank_codes')
        selected_clothing_ids = [int(i) for i in request.POST.getlist('clothing_ids')]
        
        horizon_months_raw = request.POST.get('horizon_months')
        if horizon_months_raw:
            try:
                horizon_months = int(horizon_months_raw)
            except ValueError:
                horizon_months = 0
                
        safety_margin_raw = request.POST.get('safety_margin')
        if safety_margin_raw:
            try:
                safety_margin = float(safety_margin_raw)
            except ValueError:
                safety_margin = 0.0
                
        from .services import calculate_clothing_forecast
        results = calculate_clothing_forecast(
            unit_ids=selected_unit_ids,
            rank_codes=selected_rank_codes,
            clothing_ids=selected_clothing_ids,
            horizon_months=horizon_months,
            safety_margin=safety_margin
        )
        calculated = True
        
        # Si se solicita exportar a CSV
        if request.POST.get('export') == 'csv':
            import csv
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="pronostico_compra_ropa.csv"'
            response.write('\ufeff') # BOM
            writer = csv.writer(response, dialect='excel', delimiter=';')
            writer.writerow([
                'Prenda', 'Talle', 'Demanda (Personal)', 'En Uso (Vigente)', 
                'Déficit (Pendiente/Vencido)', 'Stock Disponible', 'Sugerencia de Compra', 'Precio Ref. ($)', 'Costo Est. ($)'
            ])
            for row in results['breakdown']:
                writer.writerow([
                    row['clothing_type_name'],
                    row['size_name'],
                    row['demand_count'],
                    row['active_count'],
                    row['deficit_count'],
                    row['stock_qty'],
                    row['suggested_qty'],
                    row['unit_price'],
                    row['cost']
                ])
            return response
            
    context = {
        'units': units,
        'clothing_types': clothing_types,
        'ranks': ranks,
        'selected_unit_ids': selected_unit_ids,
        'selected_unit_id': selected_unit_ids[0] if selected_unit_ids else None,
        'selected_rank_codes': selected_rank_codes,
        'selected_clothing_ids': selected_clothing_ids,
        'horizon_months': horizon_months,
        'safety_margin': safety_margin,
        'calculated': calculated,
        'results': results,
    }
    return render(request, 'sigera/purchase_forecast.html', context)

