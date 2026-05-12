from django.test import TestCase, Client
from django.urls import reverse
from core.models import CustomUser, Unit, AircraftModel, GreaseType, GreaseBatch, MeasurementUnit
from datetime import date, timedelta
from decimal import Decimal

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

    def test_flight_hours_calculator_accessibility(self):
        """Asegura que la calculadora de vuelos no se rompa al extraer su lógica a un servicio."""
        self.client.login(username="admin_test", password="password123")
        response = self.client.get(reverse('flight_hours_calculator'))
        
        self.assertEqual(response.status_code, 200, "La calculadora debería devolver un status 200")
        self.assertTemplateUsed(response, 'core/flight_hours_calculator.html')
        self.assertIn('aircrafts', response.context)
        self.assertIn('grease_types', response.context)

    def test_consume_grease_view_accessibility(self):
        """Asegura que la vista de consumo se sigue renderizando."""
        self.client.login(username="admin_test", password="password123")
        response = self.client.get(reverse('consume_grease'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/form_base.html')

    def test_non_authenticated_users_are_redirected(self):
        """Asegura que nadie sin login ingrese a las páginas post-refactor."""
        response = self.client.get(reverse('flight_hours_calculator'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))
        
    def test_batch_retest_accessibility(self):
        """Valida que un usuario Admin tiene acceso al formulario de retest."""
        self.client.login(username="admin_test", password="password123")
        response = self.client.get(reverse('batch_retest', kwargs={'pk': self.batch.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/form_base.html')
