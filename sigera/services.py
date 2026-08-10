from datetime import date
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from sigera.models import Personnel, PersonnelClothingMeasure, ClothingSize, ClothingBatch, ClothingType, ClothingAssignment
from core.models import Unit
import math

def calculate_clothing_forecast(unit_ids=None, rank_codes=None, clothing_ids=None, horizon_months=0, safety_margin=0.0, unit_id=None):
    """
    Calcula la necesidad de compras de prendas para el personal activo en función de las medidas y vencimientos.
    """
    # Mantener compatibilidad si se proporciona unit_id en vez de unit_ids
    if unit_id is not None:
        if unit_ids is None:
            unit_ids = []
        if isinstance(unit_id, list):
            unit_ids.extend(unit_id)
        else:
            unit_ids.append(unit_id)

    # 1. Filtrar el personal activo
    personnel_qs = Personnel.objects.all()
    if unit_ids:
        personnel_qs = personnel_qs.filter(assigned_unit_id__in=unit_ids)
    if rank_codes:
        personnel_qs = personnel_qs.filter(rank__in=rank_codes)
    
    # 2. Filtrar las prendas y talles a analizar
    clothing_types = ClothingType.objects.all()
    if clothing_ids:
        clothing_types = clothing_types.filter(id__in=clothing_ids)
        
    # La fecha límite para vencimientos
    today = timezone.localdate()
    limit_date = today + relativedelta(months=int(horizon_months))
    
    # Estructura para agrupar resultados por (clothing_type, clothing_size)
    results = {}
    
    # Para cada tipo de prenda seleccionado, analizamos sus talles
    for ct in clothing_types:
        # Obtenemos todos los talles de esta prenda
        sizes = ct.sizes.all()
        for sz in sizes:
            # Clave única para agrupar
            key = (ct.id, sz.id)
            results[key] = {
                'clothing_type': ct,
                'clothing_size': sz,
                'personnel_demanding': [],
                'active_valid_assignments': 0,
                'expired_or_pending_assignments': 0,
                'available_stock': 0,
                'suggested_purchase': 0,
                'estimated_cost': 0.0,
            }
            
    # Para cada miembro del personal filtrado, analizamos sus medidas registradas
    for person in personnel_qs:
        # Obtenemos sus medidas para las prendas seleccionadas
        measures = PersonnelClothingMeasure.objects.filter(personnel=person, clothing_type__in=clothing_types)
        for m in measures:
            # Si tiene un talle asignado en el catálogo
            if m.clothing_size:
                ct = m.clothing_type
                sz = m.clothing_size
                key = (ct.id, sz.id)
                
                # Nos aseguramos que exista en results
                if key not in results:
                    continue
                
                results[key]['personnel_demanding'].append(person)
                
                # Analizar asignaciones activas de esta prenda para este miembro del personal
                # Una asignación es activa si returned = False
                assignments = ClothingAssignment.objects.filter(
                    personnel=person,
                    batch__clothing_size=sz,
                    returned=False
                )
                
                has_valid = False
                for assignment in assignments:
                    # Comprobar si está vencido o vence dentro de la fecha límite
                    exp_date = assignment.expiration_date
                    if exp_date and exp_date > limit_date:
                        # Tiene una entrega activa y está vigente
                        has_valid = True
                        break
                        
                if has_valid:
                    results[key]['active_valid_assignments'] += 1
                else:
                    results[key]['expired_or_pending_assignments'] += 1

    # Ahora calculamos stock y sugerencias finales
    final_breakdown = []
    total_suggested_qty = 0
    total_estimated_cost = 0.0
    critical_items = []
    
    for key, data in results.items():
        ct = data['clothing_type']
        sz = data['clothing_size']
        
        # 1. Calcular stock disponible en pañol para esta combinación
        available_stock = ClothingBatch.objects.filter(clothing_size=sz).aggregate(total=Sum('available_quantity'))['total'] or 0
        data['available_stock'] = available_stock
        
        # 2. La necesidad real son las personas con prendas vencidas o sin prendas entregadas
        deficit = data['expired_or_pending_assignments']
        
        # 3. Necesidad de compra recomendada
        net_need = deficit - available_stock
        if net_need < 0:
            net_need = 0
            
        suggested = net_need
        if net_need > 0 and safety_margin > 0:
            suggested = math.ceil(net_need * (1.0 + float(safety_margin) / 100.0))
            
        data['suggested_purchase'] = suggested
        
        # 4. Estimar costo
        # Buscamos el precio unitario del último lote ingresado de este talle de prenda
        latest_batch = ClothingBatch.objects.filter(clothing_size=sz).order_by('-reception_date', '-id').first()
        unit_price = latest_batch.unit_price if latest_batch else None
        if unit_price:
            data['estimated_cost'] = float(unit_price) * suggested
        else:
            data['estimated_cost'] = 0.0
            
        total_suggested_qty += suggested
        total_estimated_cost += data['estimated_cost']
        
        # Añadir al desglose si tiene demanda o si queremos mostrarlo
        if len(data['personnel_demanding']) > 0 or available_stock > 0:
            final_breakdown.append({
                'clothing_type_name': ct.name,
                'clothing_type_id': ct.id,
                'size_name': sz.size,
                'size_id': sz.id,
                'demand_count': len(data['personnel_demanding']),
                'active_count': data['active_valid_assignments'],
                'deficit_count': data['expired_or_pending_assignments'],
                'stock_qty': available_stock,
                'suggested_qty': suggested,
                'unit_price': float(unit_price) if unit_price else 0.0,
                'cost': data['estimated_cost'],
            })
            
            # Guardamos para identificar los más críticos
            if suggested > 0:
                critical_items.append({
                    'name': f"{ct.name} - Talle {sz.size}",
                    'deficit': suggested
                })
                
    # Ordenar desglose: primero los que tengan sugerencias de compra más altas
    final_breakdown.sort(key=lambda x: (-x['suggested_qty'], x['clothing_type_name'], x['size_name']))
    
    # Identificar los 3 más críticos
    critical_items.sort(key=lambda x: -x['deficit'])
    top_critical = [item['name'] for item in critical_items[:3]]
    
    return {
        'breakdown': final_breakdown,
        'total_suggested_qty': total_suggested_qty,
        'total_estimated_cost': total_estimated_cost,
        'top_critical': top_critical,
    }
