from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import Unit
from budget.models import (
    BudgetFiscalYear, BudgetCredit, BudgetAllocation, BudgetExecution,
    BudgetInc, BudgetSubprog, BudgetFF, BudgetProg,
    BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado,
    InsufficientFundsError
)
from budget import services
import threading
import decimal

User = get_user_model()

class BudgetConcurrencyTest(TransactionTestCase):
    """
    Test para validar el control de concurrencia en el registro de compromisos.
    Nota: TransactionTestCase es necesario para probar transacciones reales y bloqueos.
    """
    
    def setUp(self):
        # Configuración básica de nomencladores y ejercicio
        self.user = User.objects.create_user(username='testuser', password='password')
        self.year = BudgetFiscalYear.objects.create(year=2026, status='OPEN')
        self.ff = BudgetFF.objects.create(code='11', name='Tesoro')
        self.subprog = BudgetSubprog.objects.create(code='01')
        self.prog = BudgetProg.objects.create(code='01', name='Programa Test')
        self.inc = BudgetInc.objects.create(code='2', name='Bienes')
        
        # Otros campos requeridos por el modelo actual
        self.ppp_inc = BudgetPPPInc.objects.create(code='1')
        self.pp_inc = BudgetPPInc.objects.create(code='1')
        self.pre_inc = BudgetPreInc.objects.create(code='1')
        self.inc_agrup = BudgetIncisosAgrupado.objects.create(code='1')

        self.credit = BudgetCredit.objects.create(
            fiscal_year=self.year, ff=self.ff, subprog=self.subprog, 
            programa=self.prog, inc=self.inc,
            ppp_inc=self.ppp_inc, pp_inc=self.pp_inc, pre_inc=self.pre_inc,
            incisos_agrupado=self.inc_agrup,
            q1_amount=1000, q2_amount=0, q3_amount=0, q4_amount=0
        )
        self.unit = Unit.objects.create(name='Unidad Test')
        # Techo de $100
        self.allocation = BudgetAllocation.objects.create(
            credit=self.credit, unit=self.unit, allocated_amount=100
        )

    def test_concurrent_commitments(self):
        """
        Simula múltiples hilos intentando registrar gastos simultáneamente.
        Límite: $100. Intentamos registrar 10 gastos de $15 cada uno ($150 total).
        Solo 6 deberían tener éxito ($15 * 6 = $90), el 7mo debería fallar.
        """
        num_threads = 10
        amount_per_thread = 15
        results = []
        errors = []

        def worker():
            from django.db import connection
            try:
                # Cada hilo necesita su propia conexión en Django tests
                connection.connect()
                execution = services.register_commitment(
                    allocation_id=self.allocation.id,
                    reference_code=f"REF-{threading.get_ident()}",
                    amount=amount_per_thread,
                    commitment_date=timezone.now().date(),
                    user=self.user
                )
                results.append(execution)
            except InsufficientFundsError as e:
                errors.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads: t.start()
        for t in threads: t.join()

        # Verificaciones
        self.allocation.refresh_from_db()
        
        # El total comprometido no debe superar los $100
        total_spent = BudgetExecution.objects.filter(allocation=self.allocation).aggregate(
            total=models.Sum('commitment_amount')
        )['total'] or 0
        
        print(f"\n--- Resultados de Concurrencia ---")
        print(f"Exitosos: {len(results)}")
        print(f"Fallidos: {len(errors)}")
        print(f"Monto Total Comprometido: ${total_spent}")
        print(f"spent_amount en DB: ${self.allocation.spent_amount}")

        self.assertLessEqual(total_spent, 100)
        self.assertEqual(total_spent, self.allocation.spent_amount)
        self.assertEqual(len(results), 6) # 15 * 6 = 90. 15 * 7 = 105 (no entra)
        self.assertEqual(len(errors), 4)

    def test_concurrent_idempotency_same_id(self):
        """
        Escenario: 10 threads intentan registrar el MISMO external_id al mismo tiempo.
        Validar: Solo se crea un registro y el saldo aumenta una sola vez.
        """
        external_id = "concurrent-same-id-999"
        num_threads = 10
        amount = 10
        results = []
        errors = []

        def worker():
            from django.db import connection
            try:
                connection.connect()
                execution = services.register_commitment(
                    allocation_id=self.allocation.id,
                    reference_code="REF-X",
                    external_id=external_id,
                    amount=amount,
                    commitment_date=timezone.now().date(),
                    user=self.user
                )
                results.append(execution)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.allocation.refresh_from_db()
        
        # Debe haber exactamente 1 registro creado
        self.assertEqual(BudgetExecution.objects.filter(external_id=external_id).count(), 1)
        # El saldo solo se descontó una vez ($10 en vez de $100)
        self.assertEqual(self.allocation.spent_amount, decimal.Decimal('10.00'))
        # Todos los threads terminaron con éxito (porque el servicio es idempotente y devuelve el registro existente)
        self.assertEqual(len(results), num_threads)
        self.assertEqual(len(errors), 0)

    def test_edge_case_limit_and_concurrency(self):
        """
        Escenario: Saldo disponible $100. Llegan 2 requests simuláneas con el mismo ID, cada una de $100.
        Validar: No se supera el techo y no hay doble descuento.
        """
        external_id = "edge-case-limit-id"
        amount = 100
        
        def worker():
            from django.db import connection
            try:
                connection.connect()
                services.register_commitment(
                    allocation_id=self.allocation.id,
                    reference_code="LIMIT-REF",
                    external_id=external_id,
                    amount=amount,
                    commitment_date=timezone.now().date(),
                    user=self.user
                )
            finally:
                connection.close()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.allocation.refresh_from_db()
        
        # El saldo gastado debe ser exactamente $100
        self.assertEqual(self.allocation.spent_amount, decimal.Decimal('100.00'))
        # Solo existe un registro
        self.assertEqual(BudgetExecution.objects.filter(external_id=external_id).count(), 1)

from django.db import models # Necesario para models.Sum en el test
