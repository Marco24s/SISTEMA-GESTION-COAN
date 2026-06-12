from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from core.models import CustomUser, Unit, AircraftModel, GreaseType, GreaseBatch, MeasurementUnit, AircraftGrease, FlightPlan, UserSystemPIN
from core.services import optimize_grease_usage
from datetime import date, timedelta
from decimal import Decimal
import time

class CoreViewsBasicCharacterizationTests(TestCase):
    """
    Test de Caracterización: aseguran que el comportamiento actual 
    se mantiene intacto antes de refactorizar la lógica (SOLID).
    No prueban la lógica profunda (aún), sino que las vistas y respuestas HTTP base sigan funcionando.
    """
    def setUp(self):
        self.client = Client()
        
        # 1. Crear Unidad
        self.unit = Unit.objects.create(name="Escuadra Test")
        
        # 2. Crear Usuarios
        self.admin_user = CustomUser.objects.create_superuser(
            username="admin_test", 
            password="password123",
            email="admin@test.com"
        )
        self.normal_user = CustomUser.objects.create_user(
            username="user_test",
            password="password123",
            unit=self.unit
        )
        UserSystemPIN.objects.create(
            user=self.admin_user,
            system_code='sgmg',
            pin_hash=make_password('1234')
        )
        
        # 3. Modelos de Dominio
        self.measurement_unit = MeasurementUnit.objects.create(name="Kg")
        self.grease_type = GreaseType.objects.create(
            unidad="Kg",
            nomenclatura="AEROGRASA TEST SOLID",
            shelf_life_months=24,
            minimum_stock=Decimal('10.00'),
            recertification_allowed=True
        )
        
        self.aircraft = AircraftModel.objects.create(
            name="Avion Test",
            unit=self.unit,
            total_aircraft=2,
            is_active=True
        )
        
        # 4. Crear Lote Activo
        self.batch = GreaseBatch.objects.create(
            grease_type=self.grease_type,
            batch_number="LOTE-001",
            manufacturing_date=date.today() - timedelta(days=365),
            expiration_date=date.today() + timedelta(days=365),
            initial_quantity=Decimal('50.00'),
            available_quantity=Decimal('50.00'),
            storage_location=self.unit.name,
            status='SERVICEABLE'
        )

    def login_with_sgmg_pin(self):
        self.client.login(username="admin_test", password="password123")
        session = self.client.session
        session['verified_pins'] = {'sgmg': time.time()}
        session.save()

    def test_flight_hours_calculator_accessibility(self):
        """Asegura que la calculadora de vuelos no se rompa al extraer su lógica a un servicio."""
        self.login_with_sgmg_pin()
        response = self.client.get(reverse('flight_hours_calculator'))
        
        self.assertEqual(response.status_code, 200, "La calculadora debería devolver un status 200")
        self.assertTemplateUsed(response, 'core/flight_hours_calculator.html')
        self.assertIn('aircrafts', response.context)
        self.assertIn('grease_types', response.context)

    def test_grease_usage_optimizer_accessibility(self):
        """Asegura que el optimizador consultivo renderice sin modificar stock."""
        self.login_with_sgmg_pin()
        response = self.client.get(reverse('grease_usage_optimizer'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/grease_usage_optimizer.html')
        self.assertIn('grease_types', response.context)

    def test_consume_grease_view_accessibility(self):
        """Asegura que la vista de consumo se sigue renderizando."""
        self.login_with_sgmg_pin()
        response = self.client.get(reverse('consume_grease'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/consume_grease.html')

    def test_non_authenticated_users_are_redirected(self):
        """Asegura que nadie sin login ingrese a las páginas post-refactor."""
        response = self.client.get(reverse('flight_hours_calculator'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))
        
    def test_batch_retest_accessibility(self):
        """Valida que un usuario Admin tiene acceso al formulario de retest."""
        self.login_with_sgmg_pin()
        response = self.client.get(reverse('batch_retest', kwargs={'pk': self.batch.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/form_base.html')

    def test_usage_optimizer_prioritizes_expiring_stock_without_moving_it(self):
        """El optimizador debe asesorar usando primero el lote que vence antes, sin alterar stock."""
        second_unit = Unit.objects.create(name="Escuadra Reserva")
        far_expiry_batch = GreaseBatch.objects.create(
            grease_type=self.grease_type,
            batch_number="LOTE-002",
            manufacturing_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=365),
            initial_quantity=Decimal('1.00'),
            available_quantity=Decimal('1.00'),
            storage_location=second_unit.name,
            status='SERVICEABLE'
        )
        self.batch.available_quantity = Decimal('10.00')
        self.batch.initial_quantity = Decimal('10.00')
        self.batch.expiration_date = date.today() + timedelta(days=21)
        self.batch.save()

        AircraftGrease.objects.create(
            aircraft_model=self.aircraft,
            grease_type=self.grease_type,
            hourly_consumption_rate=Decimal('1.0000'),
        )
        FlightPlan.objects.create(
            aircraft_model=self.aircraft,
            period_type='CUSTOM',
            period_start_date=date.today(),
            period_end_date=date.today() + timedelta(days=30),
            planned_hours=Decimal('8.00'),
        )

        results = optimize_grease_usage(
            selected_grease_ids=[self.grease_type.id],
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        result = results[0]
        self.assertEqual(result['total_demand'], Decimal('8.000000'))
        self.assertEqual(result['total_allocated'], Decimal('8.000000'))
        self.assertEqual(result['total_unmet'], Decimal('0'))
        self.assertEqual(len(result['allocations']), 1)
        self.assertEqual(result['allocations'][0]['batch'].batch_number, "LOTE-001")
        self.assertEqual(result['allocations'][0]['quantity'], Decimal('8.000000'))

        self.batch.refresh_from_db()
        far_expiry_batch.refresh_from_db()
        self.assertEqual(self.batch.available_quantity, Decimal('10.00'))
        self.assertEqual(far_expiry_batch.available_quantity, Decimal('1.00'))

    def test_usage_optimizer_covers_deficit_from_surplus_locations(self):
        """Si el stock global alcanza, debe sugerir transferencias hasta cubrir los faltantes."""
        self.batch.available_quantity = Decimal('0.00')
        self.batch.save()

        eah1 = Unit.objects.create(name="EAH1")
        eah2 = Unit.objects.create(name="EAH2")
        eah3 = Unit.objects.create(name="EAH3")

        aircraft_1 = AircraftModel.objects.create(name="EAH1 Test", unit=eah1, total_aircraft=1)
        aircraft_2 = AircraftModel.objects.create(name="EAH2 Test", unit=eah2, total_aircraft=1)

        AircraftGrease.objects.create(
            aircraft_model=aircraft_1,
            grease_type=self.grease_type,
            hourly_consumption_rate=Decimal('1.0000'),
        )
        AircraftGrease.objects.create(
            aircraft_model=aircraft_2,
            grease_type=self.grease_type,
            hourly_consumption_rate=Decimal('1.0000'),
        )

        FlightPlan.objects.create(
            aircraft_model=aircraft_1,
            period_type='CUSTOM',
            period_start_date=date.today(),
            period_end_date=date.today() + timedelta(days=30),
            planned_hours=Decimal('50.00'),
        )
        FlightPlan.objects.create(
            aircraft_model=aircraft_2,
            period_type='CUSTOM',
            period_start_date=date.today(),
            period_end_date=date.today() + timedelta(days=30),
            planned_hours=Decimal('456.00'),
        )

        GreaseBatch.objects.create(
            grease_type=self.grease_type,
            batch_number="EAH1-STOCK",
            manufacturing_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=180),
            initial_quantity=Decimal('106.00'),
            available_quantity=Decimal('106.00'),
            storage_location=eah1.name,
            status='SERVICEABLE',
        )
        GreaseBatch.objects.create(
            grease_type=self.grease_type,
            batch_number="EAH2-STOCK",
            manufacturing_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=210),
            initial_quantity=Decimal('192.00'),
            available_quantity=Decimal('192.00'),
            storage_location=eah2.name,
            status='SERVICEABLE',
        )
        GreaseBatch.objects.create(
            grease_type=self.grease_type,
            batch_number="EAH3-STOCK",
            manufacturing_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=240),
            initial_quantity=Decimal('275.00'),
            available_quantity=Decimal('275.00'),
            storage_location=eah3.name,
            status='SERVICEABLE',
        )

        results = optimize_grease_usage(
            selected_grease_ids=[self.grease_type.id],
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

        result = results[0]
        eah2_incoming = sum(
            item['quantity']
            for item in result['allocations']
            if item['target_location'] == eah2.name and item['requires_transfer']
        )

        self.assertEqual(result['total_demand'], Decimal('506.000000'))
        self.assertEqual(result['total_stock'], Decimal('573.00'))
        self.assertEqual(result['total_unmet'], Decimal('0'))
        self.assertEqual(eah2_incoming, Decimal('264.000000'))
