from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from core.models import UserSystemPIN
from sigera.models import Personnel
import time

class SigeraDeletePinTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='admin_test_sigera',
            password='password123',
            email='admin@sigera.com'
        )
        # Create user system PIN for general access to sigera (required by PINSecurityMiddleware)
        UserSystemPIN.objects.create(
            user=self.user,
            system_code='sigera',
            pin_hash=make_password('1234')
        )
        # Create user system PIN for sigera_delete
        UserSystemPIN.objects.create(
            user=self.user,
            system_code='sigera_delete',
            pin_hash=make_password('4321')
        )
        # Create a personnel record to delete
        self.person = Personnel.objects.create(
            dni='12345678',
            last_name='Perez',
            first_name='Juan',
            rank='SUBOFICIAL_PRIMERO',
        )
        self.client = Client()
        self.client.login(username='admin_test_sigera', password='password123')
        
        # Bypass the PINSecurityMiddleware for general access sigera
        session = self.client.session
        session['verified_pins'] = {'sigera': time.time()}
        session.save()

    def test_personnel_delete_get_shows_confirm_page(self):
        response = self.client.get(reverse('sigera:personnel_delete', kwargs={'pk': self.person.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sigera/confirm_delete.html')
        self.assertContains(response, 'PIN de Seguridad (Borrado)')

    def test_personnel_delete_post_incorrect_pin_fails(self):
        url = reverse('sigera:personnel_delete', kwargs={'pk': self.person.pk})
        # Try with incorrect PIN
        response = self.client.post(url, {'pin': '1111'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Personnel.objects.filter(pk=self.person.pk).exists())
        self.assertContains(response, 'PIN incorrecto. No se realizó la eliminación.')

    def test_personnel_delete_post_correct_pin_succeeds(self):
        url = reverse('sigera:personnel_delete', kwargs={'pk': self.person.pk})
        # Try with correct PIN
        response = self.client.post(url, {'pin': '4321'})
        self.assertRedirects(response, reverse('sigera:personnel_list'))
        self.assertFalse(Personnel.objects.filter(pk=self.person.pk).exists())


from sigera.models import ClothingType, ClothingSize, ClothingBatch, PersonnelClothingMeasure, ClothingAssignment
from sigera.services import calculate_clothing_forecast
from django.utils import timezone
from datetime import date
import decimal
from dateutil.relativedelta import relativedelta

class SigeraPurchaseForecastTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='admin_test_forecast',
            password='password123',
            email='admin@forecast.com'
        )
        # Create user system PIN for general access to sigera (required by PINSecurityMiddleware)
        UserSystemPIN.objects.create(
            user=self.user,
            system_code='sigera',
            pin_hash=make_password('1234')
        )
        # Create user system PIN for sigera_delete
        UserSystemPIN.objects.create(
            user=self.user,
            system_code='sigera_delete',
            pin_hash=make_password('4321')
        )
        self.client = Client()
        self.client.login(username='admin_test_forecast', password='password123')
        
        # Bypass general PIN
        session = self.client.session
        session['verified_pins'] = {'sigera': time.time()}
        session.save()

        # Create mock data
        self.clothing_type = ClothingType.objects.create(
            name='CAMISA DE VUELO',
            shelf_life_months=12,
            must_be_returned=True
        )
        self.clothing_size = ClothingSize.objects.create(
            clothing_type=self.clothing_type,
            size='L',
            size_system='NACIONAL'
        )
        # Create a batch with stock 5
        self.batch = ClothingBatch.objects.create(
            clothing_size=self.clothing_size,
            reception_date=date(2026, 1, 1),
            initial_quantity=10,
            available_quantity=5,
            unit_price=decimal.Decimal('150.00')
        )
        # Create 8 personnel demanding size L
        self.personnel_list = []
        for i in range(8):
            p = Personnel.objects.create(
                dni=f'9999900{i}',
                last_name=f'LastName{i}',
                first_name=f'FirstName{i}',
                rank='SUBOFICIAL_PRIMERO'
            )
            PersonnelClothingMeasure.objects.create(
                personnel=p,
                clothing_type=self.clothing_type,
                clothing_size=self.clothing_size
            )
            self.personnel_list.append(p)

    def test_forecast_calculation_no_assignments(self):
        # 8 people demand size L. Stock is 5. No assignments.
        # Suggested purchase should be 8 - 5 = 3.
        # Cost should be 3 * 150 = 450.
        results = calculate_clothing_forecast(
            clothing_ids=[self.clothing_type.id],
            horizon_months=0,
            safety_margin=0.0
        )
        self.assertEqual(results['total_suggested_qty'], 3)
        self.assertEqual(results['total_estimated_cost'], 450.0)

    def test_forecast_calculation_with_active_assignments(self):
        # 2 people have valid active assignments.
        # 8 people total demand. 2 active. 6 pending.
        # Stock is 5.
        # Suggested purchase should be 6 - 5 = 1.
        for i in range(2):
            ClothingAssignment.objects.create(
                personnel=self.personnel_list[i],
                batch=self.batch,
                quantity=1,
                issued_by=self.user,
                reception_status='CONFIRMED',
                assigned_date=timezone.localdate()
            )
        results = calculate_clothing_forecast(
            clothing_ids=[self.clothing_type.id],
            horizon_months=0,
            safety_margin=0.0
        )
        self.assertEqual(results['total_suggested_qty'], 1)

    def test_forecast_calculation_with_expired_assignments(self):
        # 2 people have expired assignments (assigned 2 years ago, shelf life is 12 months).
        # 8 people total demand. 2 expired. 6 no assignments. Total deficit is 8.
        # Stock is 5.
        # Suggested purchase should be 8 - 5 = 3.
        for i in range(2):
            ClothingAssignment.objects.create(
                personnel=self.personnel_list[i],
                batch=self.batch,
                quantity=1,
                issued_by=self.user,
                reception_status='CONFIRMED',
                received_at=timezone.now() - relativedelta(years=2)
            )
        results = calculate_clothing_forecast(
            clothing_ids=[self.clothing_type.id],
            horizon_months=0,
            safety_margin=0.0
        )
        self.assertEqual(results['total_suggested_qty'], 3)

    def test_forecast_view_get_and_post(self):
        # GET request
        response = self.client.get(reverse('sigera:purchase_forecast'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sigera/purchase_forecast.html')

        # POST request
        response = self.client.post(reverse('sigera:purchase_forecast'), {
            'clothing_ids': [self.clothing_type.id],
            'horizon_months': 0,
            'safety_margin': 10.0
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CAMISA DE VUELO')
        self.assertContains(response, 'Compra Sugerida')
