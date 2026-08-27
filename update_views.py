import re

def update_views():
    with open('budget/views.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find budget_consolidation function
    pattern = re.compile(r'def budget_consolidation\(request\):.*?(?=\ndef [a-z]|\Z)', re.DOTALL)
    match = pattern.search(content)
    
    if not match:
        print("Function not found!")
        return

    new_func = '''def budget_consolidation(request):
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
'''
    new_content = content[:match.start()] + new_func + content[match.end():]
    with open('budget/views.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

update_views()
