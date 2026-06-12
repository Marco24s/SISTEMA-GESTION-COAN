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
def consume_grease(grease_type, quantity_to_consume, user, reference="", reason="", location=None, specific_batch=None):
    """
    Consume grasa aplicando lógica estricta de vencimiento.
    Retorna True si fue exitoso, lanza ValidationError si no hay stock o hay errores.
    """
    if quantity_to_consume <= 0:
        raise ValidationError("La cantidad a consumir debe ser mayor a cero.")

    if specific_batch:
        if specific_batch.available_quantity < quantity_to_consume:
            raise ValidationError(f"El lote {specific_batch.batch_number} solo tiene {specific_batch.available_quantity} disponible, pero intentó consumir {quantity_to_consume}.")
        
        specific_batch.available_quantity -= quantity_to_consume
        specific_batch.save()
        StockMovement.objects.create(
            batch=specific_batch,
            movement_type='CONSUMPTION',
            quantity_changed=-quantity_to_consume,
            user=user,
            reference=reference,
            reason=reason
        )
        return True

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
    Calculates the procurement forecast from employment plans and current stock.
    Returns a list of dictionaries, one per GreaseType, containing:
    - grease_type
    - total_available
    - total_projected
    - total_consumed_in_period
    - total_pending_projected
    - shortfall
    - plan_details (list of active plans contributing to consumption)
    - active_requirement
    """
    from datetime import date
    from django.db.models import Sum
    from .models import GreaseType

    def merge_ranges(ranges):
        ordered_ranges = sorted(ranges, key=lambda item: item[0])
        merged = []
        for start, end in ordered_ranges:
            if not merged or start > merged[-1][1] + timedelta(days=1):
                merged.append([start, end])
            elif end > merged[-1][1]:
                merged[-1][1] = end
        return [(start, end) for start, end in merged]
    
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
                
        active_req = gt.requirements.filter(status__in=['PENDING', 'ORDERED']).first()
        
        fg = {
            'grease_type': gt,
            'total_available': total_available,
            'stock_breakdown': [],
            'total_projected': 0.0,
            'total_consumed_in_period': 0.0,
            'total_pending_projected': 0.0,
            'shortfall': 0.0,
            'plan_details': [],
            'consumption_details': [],
            'active_requirement': active_req,
        }
        
        # Gather all plans and daily rates
        plans_to_simulate = []
        projected_by_location = {}
        plan_ranges_by_location = {}
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
                plan_location = assoc.aircraft_model.unit.name
                projected_by_location[plan_location] = projected_by_location.get(plan_location, 0.0) + total_consumption

                executed_until = min(plan.period_end_date, today)
                if plan.period_start_date <= executed_until:
                    plan_ranges_by_location.setdefault(plan_location, []).append((plan.period_start_date, executed_until))
                
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

        consumed_by_location = {}
        for plan_location, ranges in plan_ranges_by_location.items():
            consumed = 0.0
            for start, end in merge_ranges(ranges):
                movement_total = StockMovement.objects.filter(
                    batch__grease_type=gt,
                    batch__storage_location=plan_location,
                    movement_type='CONSUMPTION',
                    movement_date__date__gte=start,
                    movement_date__date__lte=end,
                ).aggregate(total=Sum('quantity_changed'))['total'] or 0
                range_consumed = abs(float(movement_total))
                consumed += range_consumed
                fg['consumption_details'].append({
                    'location': plan_location,
                    'start': start,
                    'end': end,
                    'consumed': range_consumed,
                })
            consumed_by_location[plan_location] = consumed
            fg['total_consumed_in_period'] += consumed

        fg['total_consumed_in_period'] = min(fg['total_consumed_in_period'], fg['total_projected'])
        fg['total_pending_projected'] = max(fg['total_projected'] - fg['total_consumed_in_period'], 0.0)

        stock_breakdown_locations = sorted(set(stock_by_location) | set(projected_by_location) | set(consumed_by_location))
        fg['stock_breakdown'] = [
            {
                'location': loc,
                'quantity': stock_by_location.get(loc, 0.0),
                'projected': projected_by_location.get(loc, 0.0),
                'consumed': consumed_by_location.get(loc, 0.0),
                'pending': max(projected_by_location.get(loc, 0.0) - consumed_by_location.get(loc, 0.0), 0.0),
            }
            for loc in stock_breakdown_locations
        ]
        
        if not plans_to_simulate and total_available == 0:
            # If no plans and no stock, nothing to report or shortfall is 0
            # But we might want to see catalog items? 
            # Original code included them if forecast_data.append(fg) is called.
            pass
            
        # Operational purchase need compares current stock against the full plan need.
        # Consumption remains visible as an audit/control value, but it does not reduce
        # the purchase requirement.
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
    new_expiration = form_cleaned_data.get('new_expiration_date')
    can_be_retested = form_cleaned_data['can_be_retested']
    retest_status = form_cleaned_data.get('retest_status')
    
    if retest_status == 'REJECTED':
        batch.status = 'REJECTED'
        batch.can_be_retested = False
        movement_reason = f"Retesteo RECHAZADO por laboratorio. Lote inutilizable. {reason}"
    else:
        batch.expiration_date = new_expiration
        batch.can_be_retested = can_be_retested
        batch.status = 'SERVICEABLE'
        movement_reason = f"Retesteo APROBADO. Nuevo vencimiento: {new_expiration.strftime('%d/%m/%Y')}. {reason}"
    
    new_quantity = form_cleaned_data.get('available_quantity', 0)
    diff = new_quantity - old_quantity

    batch.save()
    
    StockMovement.objects.create(
        batch=batch,
        movement_type='RETEST',
        quantity_changed=diff,
        user=user,
        reason=movement_reason
    )
    
    matching_batches = GreaseBatch.objects.filter(
        batch_number=batch.batch_number,
        grease_type=batch.grease_type,
        status='PENDING_RETEST'
    ).exclude(pk=batch.pk)
    
    for matched_batch in matching_batches:
        if retest_status == 'REJECTED':
            matched_batch.status = 'REJECTED'
            matched_batch.can_be_retested = False
            matched_reason = "Retesteo RECHAZADO sincronizado desde otra dependencia."
        else:
            matched_batch.expiration_date = new_expiration
            matched_batch.can_be_retested = can_be_retested
            matched_batch.status = 'SERVICEABLE'
            matched_reason = f"Retesteo APROBADO sincronizado desde otra dependencia. Nuevo vencimiento: {new_expiration.strftime('%d/%m/%Y')}."
            
        matched_batch.save()
        
        StockMovement.objects.create(
            batch=matched_batch,
            movement_type='RETEST',
            quantity_changed=0, 
            user=user,
            reason=matched_reason
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


def optimize_grease_usage(selected_grease_ids=None, start_date=None, end_date=None, location=None):
    """
    Builds a read-only usage recommendation for grease/oil stock.

    The optimizer never mutates stock. It estimates operational demand from flight
    plans and aircraft consumption rates, then proposes which available batches
    should be used first based on expiration date.
    """
    from decimal import Decimal
    from django.db.models import Min
    from .models import AircraftGrease, FlightPlan, GreaseType

    today = timezone.localdate()
    start_date = start_date or today
    end_date = end_date or start_date
    selected_grease_ids = [str(item) for item in selected_grease_ids or [] if str(item)]

    representative_ids = GreaseType.objects.values('nomenclatura').annotate(
        min_id=Min('id')
    ).values_list('min_id', flat=True)
    grease_queryset = GreaseType.objects.filter(pk__in=representative_ids).order_by('nomenclatura')

    if selected_grease_ids:
        selected_names = set(
            GreaseType.objects.filter(pk__in=selected_grease_ids).values_list('nomenclatura', flat=True)
        )
        grease_queryset = grease_queryset.filter(nomenclatura__in=selected_names)

    results = []

    for grease in grease_queryset:
        grease_type_ids = list(
            GreaseType.objects.filter(nomenclatura=grease.nomenclatura).values_list('id', flat=True)
        )
        demand_by_location = {}
        demand_details = []

        associations = AircraftGrease.objects.select_related(
            'aircraft_model',
            'aircraft_model__unit',
            'grease_type',
        ).filter(grease_type_id__in=grease_type_ids)

        if location:
            associations = associations.filter(aircraft_model__unit__name=location)

        for assoc in associations:
            plans = FlightPlan.objects.filter(
                aircraft_model=assoc.aircraft_model,
                period_start_date__lte=end_date,
                period_end_date__gte=start_date,
            )
            for plan in plans:
                if not plan.period_start_date or not plan.period_end_date:
                    continue

                total_days = (plan.period_end_date - plan.period_start_date).days + 1
                if total_days <= 0:
                    continue

                overlap_start = max(plan.period_start_date, start_date)
                overlap_end = min(plan.period_end_date, end_date)
                overlap_days = (overlap_end - overlap_start).days + 1
                if overlap_days <= 0:
                    continue

                plan_consumption = assoc.hourly_consumption_rate * plan.planned_hours
                projected = plan_consumption * Decimal(overlap_days) / Decimal(total_days)
                plan_location = assoc.aircraft_model.unit.name

                demand_by_location[plan_location] = demand_by_location.get(plan_location, Decimal('0')) + projected
                demand_details.append({
                    'location': plan_location,
                    'aircraft': assoc.aircraft_model,
                    'plan': plan,
                    'rate': assoc.hourly_consumption_rate,
                    'projected': projected,
                    'overlap_start': overlap_start,
                    'overlap_end': overlap_end,
                })

        batches = GreaseBatch.objects.active().available_with_stock().filter(
            grease_type_id__in=grease_type_ids
        ).select_related('grease_type').order_by('expiration_date', 'storage_location', 'batch_number')

        if location:
            batches = batches.filter(storage_location=location)

        stock_items = [
            {
                'batch': batch,
                'remaining': batch.available_quantity,
            }
            for batch in batches
        ]

        allocations = []
        unmet_demand = []
        location_summary = {}
        stock_by_location = {}
        all_locations = set(demand_by_location)

        for item in stock_items:
            batch = item['batch']
            all_locations.add(batch.storage_location)
            stock_by_location[batch.storage_location] = (
                stock_by_location.get(batch.storage_location, Decimal('0')) + batch.available_quantity
            )

        for loc in sorted(all_locations):
            location_summary[loc] = {
                'location': loc,
                'demand': demand_by_location.get(loc, Decimal('0')),
                'stock': stock_by_location.get(loc, Decimal('0')),
                'initial_balance': stock_by_location.get(loc, Decimal('0')) - demand_by_location.get(loc, Decimal('0')),
                'covered_local': Decimal('0'),
                'incoming': Decimal('0'),
                'outgoing': Decimal('0'),
                'unmet': Decimal('0'),
                'surplus_after_need': Decimal('0'),
            }

        # First, each location covers its own need with its own stock, using the
        # closest expiration dates first. Only real surplus is later offered out.
        remaining_need_by_location = {}
        for demand_location, required_amount in sorted(demand_by_location.items()):
            remaining_need = required_amount
            local_items = [
                item for item in stock_items
                if item['batch'].storage_location == demand_location and item['remaining'] > 0
            ]
            local_items.sort(key=lambda item: (item['batch'].expiration_date, item['batch'].batch_number))

            for stock_item in local_items:
                if remaining_need <= 0:
                    break

                assigned = min(stock_item['remaining'], remaining_need)
                batch = stock_item['batch']
                stock_item['remaining'] -= assigned
                remaining_need -= assigned

                allocations.append({
                    'source_location': batch.storage_location,
                    'target_location': demand_location,
                    'batch': batch,
                    'expiration_date': batch.expiration_date,
                    'quantity': assigned,
                    'requires_transfer': False,
                })
                location_summary[demand_location]['covered_local'] += assigned

            remaining_need_by_location[demand_location] = remaining_need

        # Then transfer only remaining stock toward unresolved needs. This makes
        # total stock behave as a shared pool without stripping a unit below its
        # own operational requirement.
        transfer_pool = [
            item for item in stock_items
            if item['remaining'] > 0
        ]
        transfer_pool.sort(key=lambda item: (
            item['batch'].expiration_date,
            item['batch'].storage_location,
            item['batch'].batch_number,
        ))

        for demand_location, remaining_need in sorted(
            remaining_need_by_location.items(),
            key=lambda item: (-item[1], item[0])
        ):
            if remaining_need <= 0:
                continue

            for stock_item in transfer_pool:
                if remaining_need <= 0:
                    break
                if stock_item['remaining'] <= 0:
                    continue
                if stock_item['batch'].storage_location == demand_location:
                    continue

                assigned = min(stock_item['remaining'], remaining_need)
                batch = stock_item['batch']
                stock_item['remaining'] -= assigned
                remaining_need -= assigned

                allocations.append({
                    'source_location': batch.storage_location,
                    'target_location': demand_location,
                    'batch': batch,
                    'expiration_date': batch.expiration_date,
                    'quantity': assigned,
                    'requires_transfer': True,
                })
                location_summary[demand_location]['incoming'] += assigned
                location_summary[batch.storage_location]['outgoing'] += assigned

            if remaining_need > 0:
                unmet_demand.append({
                    'location': demand_location,
                    'quantity': remaining_need,
                })
                location_summary[demand_location]['unmet'] = remaining_need

        remaining_stock = [
            {
                'batch': item['batch'],
                'quantity': item['remaining'],
                'expires_within_period': item['batch'].expiration_date <= end_date,
            }
            for item in stock_items
            if item['remaining'] > 0
        ]

        total_demand = sum(demand_by_location.values(), Decimal('0'))
        total_stock = sum((item['remaining'] for item in stock_items), Decimal('0')) + sum(
            (item['quantity'] for item in allocations), Decimal('0')
        )
        total_allocated = sum((item['quantity'] for item in allocations), Decimal('0'))
        total_unmet = sum((item['quantity'] for item in unmet_demand), Decimal('0'))
        expiring_unused = sum(
            (item['quantity'] for item in remaining_stock if item['expires_within_period']),
            Decimal('0')
        )
        for summary in location_summary.values():
            summary['surplus_after_need'] = max(
                summary['stock'] - summary['demand'] - summary['outgoing'] + summary['incoming'],
                Decimal('0')
            )

        results.append({
            'grease_type': grease,
            'demand_by_location': demand_by_location,
            'demand_details': demand_details,
            'location_summary': list(location_summary.values()),
            'allocations': allocations,
            'remaining_stock': remaining_stock,
            'unmet_demand': unmet_demand,
            'total_demand': total_demand,
            'total_stock': total_stock,
            'total_allocated': total_allocated,
            'total_unmet': total_unmet,
            'expiring_unused': expiring_unused,
            'has_activity': total_demand > 0 or total_stock > 0,
        })

    return results
