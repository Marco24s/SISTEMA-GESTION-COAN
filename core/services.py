from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import timedelta
from .models import GreaseBatch, StockMovement

def update_batch_statuses():
    """Actualiza los estados de los lotes según su fecha de vencimiento."""
    today = timezone.now().date()
    warning_date = today + timedelta(days=180) # 6 months warning
    
    # Expirados
    GreaseBatch.objects.filter(
        expiration_date__lte=today,
        status__in=['SERVICEABLE', 'NEAR_EXPIRATION']
    ).update(status='EXPIRED')
    
    # Próximos a vencer (asegurar de no pisar vencidos por fecha si alguien los cambió a mano, aunque arriba ya se filtran)
    GreaseBatch.objects.filter(
        expiration_date__gt=today,
        expiration_date__lte=warning_date,
        status__in=['SERVICEABLE', 'EXPIRED'] # Added EXPIRED here to catch retests that are now near expiration
    ).update(status='NEAR_EXPIRATION')
    
    # Revertir lotes extendidos ("Retesteados") a Serviceable si ahora su vencimiento es mayor a 6 meses
    GreaseBatch.objects.filter(
        expiration_date__gt=warning_date,
        status__in=['EXPIRED', 'NEAR_EXPIRATION']
    ).update(status='SERVICEABLE')


@transaction.atomic
def consume_grease(grease_type, quantity_to_consume, user, reference="", reason="", location=None):
    """
    Consume grasa aplicando lógica estricta de vencimiento.
    Retorna True si fue exitoso, lanza ValidationError si no hay stock o hay errores.
    """
    if quantity_to_consume <= 0:
        raise ValidationError("La cantidad a consumir debe ser mayor a cero.")

    # Lotes disponibles: status SERVICEABLE o NEAR_EXPIRATION, ordenados por fecha de vencimiento más próxima
    batches_query = GreaseBatch.objects.available_with_stock().filter(grease_type=grease_type)
    
    if location:
        batches_query = batches_query.filter(storage_location=location)

    available_batches = batches_query.order_by('expiration_date')

    total_available = sum(batch.available_quantity for batch in available_batches)
    
    if total_available < quantity_to_consume:
        raise ValidationError(f"Stock insuficiente para la grasa {grease_type.nomenclatura}. Solicitado: {quantity_to_consume}, Disponible: {total_available}")

    remaining_to_consume = quantity_to_consume

    for batch in available_batches:
        if remaining_to_consume <= 0:
            break

        if batch.available_quantity >= remaining_to_consume:
            # Este lote puede cubrir lo que falta
            consumed_from_this_batch = remaining_to_consume
            batch.available_quantity -= remaining_to_consume
            remaining_to_consume = 0
        else:
            # Se consume todo este lote y se sigue con el próximo
            consumed_from_this_batch = batch.available_quantity
            remaining_to_consume -= batch.available_quantity
            batch.available_quantity = 0

        batch.save()
        
        # Registrar el movimiento auditable
        StockMovement.objects.create(
            batch=batch,
            movement_type='CONSUMPTION',
            quantity_changed=-consumed_from_this_batch,
            user=user,
            reference=reference,
            reason=reason
        )

    return True

def get_procurement_forecast(location=None):
    """
    Calculates the procurement forecast using a daily fractional simulation.
    Returns a list of dictionaries, one per GreaseType, containing:
    - grease_type
    - total_available
    - total_projected
    - shortfall (amount missing taking into account expirations over time)
    - plan_details (list of active plans contributing to consumption)
    - active_requirement
    """
    from datetime import date, timedelta
    from .models import GreaseType
    
    forecast_data = []
    today = date.today()
    
    for gt in GreaseType.objects.all():
        batches_qs = gt.batches.available()
        if location:
            batches_qs = batches_qs.filter(storage_location=location)
            
        total_available = 0.0
        stock_by_location = {}
        for b in batches_qs:
            qty = float(b.available_quantity)
            if qty > 0:
                total_available += qty
                loc = b.storage_location or "Sin Escuadrilla"
                stock_by_location[loc] = stock_by_location.get(loc, 0.0) + qty
                
        stock_breakdown = [{'location': k, 'quantity': v} for k, v in stock_by_location.items()]
        
        active_req = gt.requirements.filter(status__in=['PENDING', 'ORDERED']).first()
        
        fg = {
            'grease_type': gt,
            'total_available': total_available,
            'stock_breakdown': stock_breakdown,
            'total_projected': 0.0,
            'shortfall': 0.0,
            'plan_details': [],
            'active_requirement': active_req,
        }
        
        # Gather all plans and daily rates
        plans_to_simulate = []
        for assoc in gt.aircraft_associations.all():
            if location and assoc.aircraft_model.unit.name != location:
                continue
                
            for plan in assoc.aircraft_model.flight_plans.all():
                if not plan.period_start_date or not plan.period_end_date:
                    continue
                
                total_days = (plan.period_end_date - plan.period_start_date).days + 1
                if total_days <= 0: continue
                
                total_consumption = float(assoc.hourly_consumption_rate * plan.planned_hours)
                daily_consumption = total_consumption / total_days
                
                plans_to_simulate.append({
                    'start': plan.period_start_date,
                    'end': plan.period_end_date,
                    'daily_rate': daily_consumption
                })
                
                fg['plan_details'].append({
                    'aircraft': assoc.aircraft_model,
                    'plan': plan,
                    'rate': assoc.hourly_consumption_rate,
                    'projected': total_consumption
                })
                fg['total_projected'] += total_consumption
        
        if not plans_to_simulate and total_available == 0:
            # If no plans and no stock, nothing to report or shortfall is 0
            # But we might want to see catalog items? 
            # Original code included them if forecast_data.append(fg) is called.
            pass
            
        # The user requested the difference to be just the real difference between stock and projected consumption.
        # We compute the straightforward difference without simulating daily expirations.
        fg['shortfall'] = fg['total_projected'] - fg['total_available']
        forecast_data.append(fg)
        
    return forecast_data


from datetime import date


@transaction.atomic
def process_retest_batch(batch, user, form_cleaned_data, old_quantity):
    """
    Aplica la lógica de negocio para procesar el retesteo de un lote y sincronizar remanentes.
    Extraído de RetestBatchView para cumplir con SRP.
    """
    reason = form_cleaned_data['reason']
    new_expiration = form_cleaned_data['new_expiration_date']
    can_be_retested = form_cleaned_data['can_be_retested']
    
    batch.expiration_date = new_expiration
    batch.can_be_retested = can_be_retested
    batch.status = 'SERVICEABLE'
    
    new_quantity = form_cleaned_data.get('available_quantity', 0)
    diff = new_quantity - old_quantity

    batch.save()
    
    StockMovement.objects.create(
        batch=batch,
        movement_type='RETEST',
        quantity_changed=diff,
        user=user,
        reason=f"Retesteo / Extensión de Vencimiento. Nuevo vencimiento: {new_expiration.strftime('%d/%m/%Y')}. {reason}"
    )
    
    matching_batches = GreaseBatch.objects.filter(
        batch_number=batch.batch_number,
        grease_type=batch.grease_type,
        status='PENDING_RETEST'
    ).exclude(pk=batch.pk)
    
    for matched_batch in matching_batches:
        matched_batch.expiration_date = new_expiration
        matched_batch.can_be_retested = can_be_retested
        matched_batch.status = 'SERVICEABLE'
        matched_batch.save()
        
        StockMovement.objects.create(
            batch=matched_batch,
            movement_type='RETEST',
            quantity_changed=0, 
            user=user,
            reason=f"Retesteo / Extensión sincronizada desde otra dependencia. Nuevo vencimiento: {new_expiration.strftime('%d/%m/%Y')}."
        )
        
    return batch

def calculate_flight_hours_projection(selected_aircraft_ids=None, selected_grease_ids=None, location=None):
    """
    Calculates flight hours projection based on consumption and available stock.
    Supports filtering by aircraft, grease types, and unit location.
    """
    from decimal import Decimal
    from .models import AircraftModel, GreaseType

    all_aircrafts = AircraftModel.objects.all().order_by('name')
    if location:
        all_aircrafts = all_aircrafts.filter(unit__name=location)

    if selected_aircraft_ids:
        target_aircrafts = AircraftModel.objects.filter(pk__in=selected_aircraft_ids)
        if location:
            target_aircrafts = target_aircrafts.filter(unit__name=location)
    else:
        target_aircrafts = all_aircrafts

    # Recopilar tasas de consumo agrupadas por nomenclatura
    consumption_rates = {}  
    consumption_details = {} 

    for aircraft in target_aircrafts:
        for assoc in aircraft.grease_associations.all():
            nom = assoc.grease_type.nomenclatura
            if selected_grease_ids and str(assoc.grease_type.pk) not in selected_grease_ids:
                continue
            rate = assoc.hourly_consumption_rate
            if rate > 0:
                consumption_rates[nom] = consumption_rates.get(nom, Decimal('0')) + rate
                if nom not in consumption_details:
                    consumption_details[nom] = []
                consumption_details[nom].append(f"{aircraft.name}: {rate}")

    # Recopilar stock disponible agrupado por nomenclatura
    stock_by_nom = {}
    for gt in GreaseType.objects.all():
        if selected_grease_ids and str(gt.pk) not in selected_grease_ids:
            any_selected = GreaseType.objects.filter(
                pk__in=selected_grease_ids, nomenclatura=gt.nomenclatura
            ).exists()
            if not any_selected:
                continue
        nom = gt.nomenclatura
        batches_qs = gt.batches.available()
        if location:
            batches_qs = batches_qs.filter(storage_location=location)
        avail = sum(b.available_quantity for b in batches_qs)
        stock_by_nom[nom] = stock_by_nom.get(nom, Decimal('0')) + avail

    breakdown = []
    max_hours = None
    bottleneck = None
    no_consumption = True

    for nom, rate in consumption_rates.items():
        if rate <= 0: continue
        no_consumption = False
        stock = stock_by_nom.get(nom, Decimal('0'))
        h = stock / rate if rate > 0 else 0
        details_str = " + ".join(consumption_details.get(nom, []))
        breakdown.append({
            'nomenclatura': nom,
            'stock': stock,
            'rate': rate,
            'h_max': h,
            'is_bottleneck': False,
            'details_str': details_str,
        })
        if max_hours is None or h < max_hours:
            max_hours = h
            bottleneck = nom

    if max_hours is not None:
        for item in breakdown:
            item['consumption_at_max'] = item['rate'] * max_hours
            item['stock_remaining'] = item['stock'] - item['consumption_at_max']
            if item['nomenclatura'] == bottleneck:
                item['is_bottleneck'] = True

    for nom, stock in stock_by_nom.items():
        if nom not in consumption_rates:
            breakdown.append({
                'nomenclatura': nom,
                'stock': stock,
                'rate': Decimal('0'),
                'h_max': None,
                'consumption_at_max': Decimal('0'),
                'stock_remaining': stock,
                'is_bottleneck': False,
                'no_consumption': True,
            })

    breakdown.sort(key=lambda x: x['nomenclatura'])

    return {
        'breakdown': breakdown,
        'max_hours': max_hours,
        'bottleneck': bottleneck,
        'no_consumption': no_consumption
    }
