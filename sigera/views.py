from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db import transaction
from django.contrib import messages
from .models import ClothingType, ClothingSize, ClothingBatch, Personnel, ClothingAssignment, StockThreshold
from .forms import PersonnelForm, ClothingAssignmentForm
import pandas as pd
from core.models import Unit

@login_required
def home(request):
    """
    Vista principal de SIGERA (Dashboard)
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()

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
    
    # Actividad reciente: últimas 5 entregas
    recent_assignments = assignments_qs.select_related(
        'personnel', 'batch__clothing_size__clothing_type'
    ).order_by('-assigned_date', '-id')[:5]
    
    context = {
        'total_stock': total_stock,
        'total_personnel': total_personnel,
        'active_assignments': active_assignments,
        'recent_assignments': recent_assignments,
    }
    return render(request, 'sigera/home.html', context)

@login_required
def stock_list(request):
    """
    Vista de Inventario Detallado por Lotes
    """
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
            
    # Agrupar lotes por modelo y talle para la vista
    grouped_stock = []
    current_group = None
    
    for batch in stock_batches:
        if current_group is None or current_group['clothing_size'] != batch.clothing_size:
            if current_group is not None:
                # Calculate category for the total
                total_qty = current_group['total_available']
                for threshold in stock_thresholds:
                    if threshold.matches(total_qty):
                        current_group['stock_category'] = threshold
                        break
                grouped_stock.append(current_group)
                
            current_group = {
                'clothing_size': batch.clothing_size,
                'clothing_type_name': batch.clothing_size.clothing_type.name,
                'size': batch.clothing_size.size,
                'total_available': 0,
                'total_initial': 0,
                'batches': [],
                'stock_category': None
            }
        current_group['batches'].append(batch)
        current_group['total_available'] += (batch.available_quantity or 0)
        current_group['total_initial'] += (batch.initial_quantity or 0)
        
    if current_group is not None:
        total_qty = current_group['total_available']
        for threshold in stock_thresholds:
            if threshold.matches(total_qty):
                current_group['stock_category'] = threshold
                break
        grouped_stock.append(current_group)
    
    context = {
        'grouped_stock': grouped_stock,
    }
    return render(request, 'sigera/stock_list.html', context)

@login_required
def size_batch_detail(request, size_id):
    """
    Vista detallada de batches para un talle específico
    """
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
    personnel = Personnel.objects.select_related('assigned_unit')
    
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    
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
        
    personnel = personnel.order_by('last_name', 'first_name')
    
    context = {
        'personnel_list': personnel,
        'search_query': query,
    }
    return render(request, 'sigera/personnel_list.html', context)

@login_required
def assignment_list(request):
    """
    Vista de historial de entregas de ropa con búsqueda y control de provisiones
    """
    query = request.GET.get('q', '')
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    
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
        returned=False
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
    
    context = {
        'assignment_list': assignments,
        'personnel_first_provision': personnel_first_provision,
        'renewals_list': renewals_list,
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
            return redirect('sigera:personnel_list')
    else:
        form = PersonnelForm(user=request.user)
        
    return render(request, 'sigera/personnel_form.html', {'form': form})

@login_required
def personnel_import(request):
    """
    Vista para importar personal masivamente desde un archivo Excel.
    """
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
def personnel_delete(request, pk):
    """
    Vista para eliminar un registro de personal
    """
    person = get_object_or_404(Personnel, pk=pk)
    if request.method == 'POST':
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
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
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
                    assignment.save()
                    messages.success(request, "La entrega se ha registrado correctamente y el inventario del pañol fue actualizado.")
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

from django.utils import timezone
from .forms import ClothingTypeForm, ClothingBatchForm

@login_required
def catalog_list(request):
    """
    Vista de listado del catálogo de prendas (modelos de vestuario).
    """
    clothing_types = ClothingType.objects.prefetch_related('sizes').order_by('name')
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
    if request.method == 'POST':
        form = ClothingTypeForm(request.POST)
        if form.is_valid():
            ct = form.save()
            messages.success(request, f"¡Modelo de prenda '{ct.name}' registrado exitosamente!")
            return redirect('sigera:catalog_list')
    else:
        form = ClothingTypeForm()
        
    return render(request, 'sigera/catalog_form.html', {'form': form})

from .forms import ClothingSizeForm

@login_required
def catalog_size_create(request):
    """
    Vista para agregar un talle a un modelo de prenda existente.
    """
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
    size = get_object_or_404(ClothingSize, pk=pk)
    if request.method == 'POST':
        form = ClothingSizeForm(request.POST, instance=size)
        if form.is_valid():
            form.save()
            messages.success(request, f"Talle '{size.size}' actualizado correctamente.")
            return redirect('sigera:stock_list')
    else:
        form = ClothingSizeForm(instance=size)
    return render(request, 'sigera/size_form.html', {'form': form, 'edit_mode': True, 'size': size})

@login_required
def catalog_size_delete(request, pk):
    size = get_object_or_404(ClothingSize, pk=pk)
    if request.method == 'POST':
        size.delete()
        messages.success(request, f"Talle {size.size} eliminado correctamente.")
        return redirect('sigera:stock_list')
    return render(request, 'sigera/confirm_delete.html', {
        'title': 'Eliminar Talle',
        'message': f"¿Eliminar el talle {size.size} de {size.clothing_type.name}? Esto eliminará también los ingresos asociados.",
        'cancel_url': reverse('sigera:stock_list'),
    })

@login_required
def batch_create(request):
    """
    Vista para registrar un nuevo Ingreso a Pañol (Stock).
    """
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
        
    sizes_by_type = list(ClothingSize.objects.order_by('clothing_type__name', 'size').values('id', 'clothing_type_id', 'size'))
    return render(request, 'sigera/batch_form.html', {'form': form, 'sizes_by_type': sizes_by_type})

@login_required
def assignment_return_view(request, pk):
    """
    Vista para procesar la devolución de una prenda.
    Cambia el estado del cargo y repone el stock.
    """
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    if not is_admin:
        messages.error(request, "Acceso denegado: No tienes permisos para registrar devoluciones.")
        return redirect('sigera:assignment_list')

    if request.method == 'POST':
        assignment = get_object_or_404(ClothingAssignment, pk=pk, returned=False)

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
    batch = get_object_or_404(ClothingBatch, pk=pk)
    assignments = batch.assignments.all().order_by('-assigned_date', '-id')
    
    context = {
        'batch': batch,
        'assignments': assignments,
    }
    return render(request, 'sigera/batch_movements.html', context)
