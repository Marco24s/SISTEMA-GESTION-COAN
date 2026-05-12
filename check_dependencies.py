from core.models import GreaseType, GreaseBatch, StockMovement, AircraftGrease, GreaseReferencePrice
from django.db.models import Count
import sys

# Get IDs or Nomenclatures to check
targets = ['AEROLUBRICANTE 1003', 'AEROGRASA 1005']
gts = GreaseType.objects.filter(nomenclatura__in=targets)

with open('dependency_report.txt', 'w', encoding='utf-8') as f:
    f.write(f"DEBUG: Found {gts.count()} grease types matching {targets}\n")

    for gt in gts:
        f.write(f"\n========================================\n")
        f.write(f"Analizando GT: {gt.id} - {gt.nomenclatura}\n")
        
        batches = GreaseBatch.objects.filter(grease_type=gt)
        f.write(f"  Lotes (GreaseBatch): {batches.count()}\n")
        for b in batches:
            f.write(f"    - Lote {b.id}: {b.batch_number} (Archivado: {getattr(b, 'is_archived', 'No tiene campo is_archived')})\n")
            f.write(f"      Estado: {b.status}\n")
            movements = StockMovement.objects.filter(batch=b)
            f.write(f"      Movimientos: {movements.count()}\n")
            
        associations = AircraftGrease.objects.filter(grease_type=gt)
        f.write(f"  Asociaciones (AircraftGrease): {associations.count()}\n")
        for a in associations:
            f.write(f"    - Asociado a: {a.aircraft_model}\n")
        
        prices = GreaseReferencePrice.objects.filter(grease_type=gt)
        f.write(f"  Precios de Referencia: {prices.count()}\n")
        
        if batches.count() == 0 and associations.count() == 0 and prices.count() == 0:
            f.write("  RESULT: Debería ser eliminable.\n")
        else:
            f.write("  RESULT: Bloqueado por las relaciones arriba indicadas.\n")
    f.write(f"========================================\n")
