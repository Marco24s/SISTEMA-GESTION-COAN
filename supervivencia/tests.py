from datetime import date
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import UserSystemPIN

from .forms import PyrotechnicCatalogItemForm, PyrotechnicPhysicalItemForm
from .models import (
    ItemClassification,
    ItemSystem,
    PyrotechnicAssignment,
    PyrotechnicCatalogItem,
    PyrotechnicMovement,
    PyrotechnicPhysicalItem,
    SupervivenciaDeletionLog,
    SurvivalMedium,
)


class PyrotechnicCatalogIdentityTests(TestCase):
    def setUp(self):
        self.classification = ItemClassification.objects.create(name="PIROTECNIA")
        self.system_chaleco = ItemSystem.objects.create(classification=self.classification, name="CHALECO")
        self.system_balsa = ItemSystem.objects.create(classification=self.classification, name="BALSA")
        self.existing = PyrotechnicCatalogItem.objects.create(
            nomenclature="BENGALA DE MANO",
            system=self.system_chaleco,
            part_number="13",
            nsn="13",
            alternate_part_number="1",
        )

    def test_part_number_can_repeat_when_other_identity_data_differs(self):
        form = PyrotechnicCatalogItemForm(data={
            "classification": self.classification.pk,
            "nomenclature": "BENGALA DE SENALES",
            "system": self.system_balsa.pk,
            "part_number": "13",
            "nsn": "99",
            "alternate_part_number": "2",
            "description": "",
            "is_active": True,
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_complete_identity_cannot_repeat(self):
        form = PyrotechnicCatalogItemForm(data={
            "classification": self.classification.pk,
            "nomenclature": "BENGALA DE MANO",
            "system": self.system_chaleco.pk,
            "part_number": "13",
            "nsn": "13",
            "alternate_part_number": "1",
            "description": "OTRA DESCRIPCION",
            "is_active": True,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("misma combinacion", str(form.non_field_errors()).lower())

    def test_physical_item_catalog_choice_shows_identifiers(self):
        form = PyrotechnicPhysicalItemForm()

        label = form.fields["catalog_item"].label_from_instance(self.existing)

        self.assertEqual(label, "BENGALA DE MANO | N/P: 13 | NSN: 13")

    def test_catalog_list_search_by_system_and_query(self):
        user = get_user_model().objects.create_user(username="testuser", password="password")
        UserSystemPIN.objects.create(user=user, system_code="supervivencia", pin_hash=make_password("1234"))
        self.client.force_login(user)
        session = self.client.session
        session["verified_pins"] = {"supervivencia": time.time()}
        session.save()

        response = self.client.get(reverse("supervivencia:catalog_list"), {"q": "CHALECO"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BENGALA DE MANO")


@override_settings(ROOT_URLCONF="config.urls")
class PyrotechnicPhysicalItemForceDeleteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="supervivencia_admin",
            password="test-password",
            email="admin@example.com",
        )
        UserSystemPIN.objects.create(
            user=self.user,
            system_code="supervivencia",
            pin_hash=make_password("1234"),
        )
        UserSystemPIN.objects.create(
            user=self.user,
            system_code="supervivencia_admin",
            pin_hash=make_password("1234"),
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["verified_pins"] = {"supervivencia": time.time(), "supervivencia_admin": time.time()}
        session.save()
        self.classification = ItemClassification.objects.create(name="PIROTECNIA")
        self.system = ItemSystem.objects.create(classification=self.classification, name="ASIENTO EYECTABLE")
        self.catalog_item = PyrotechnicCatalogItem.objects.create(
            nomenclature="CARTUCHO IMPULSOR",
            system=self.system,
            part_number="PN-1",
            nsn="NSN-1",
        )
        self.physical_item = PyrotechnicPhysicalItem.objects.create(
            catalog_item=self.catalog_item,
            serial_number="SER-001",
            lot_number="LOTE-001",
            expiration_date=date(2027, 1, 31),
            current_location="DEPOSITO",
            created_by=self.user,
        )
        self.medium = SurvivalMedium.objects.create(
            identifier="A-001",
            name="AERONAVE 001",
        )
        self.assignment = PyrotechnicAssignment.objects.create(
            medium=self.medium,
            physical_item=self.physical_item,
            installed_at=date(2026, 8, 1),
            position="CABINA",
            created_by=self.user,
        )
        self.movement = PyrotechnicMovement.objects.create(
            physical_item=self.physical_item,
            medium=self.medium,
            assignment=self.assignment,
            movement_type="INSTALLED",
            movement_date=date(2026, 8, 1),
            from_reference="DEPOSITO",
            to_reference="A-001 / CABINA",
            created_by=self.user,
        )

    def test_force_delete_requires_admin_pin_scope(self):
        session = self.client.session
        session["verified_pins"] = {"supervivencia": time.time()}
        session.save()

        response = self.client.get(
            reverse("supervivencia:physical_item_force_delete", args=[self.physical_item.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("system=supervivencia_admin", response["Location"])

    def test_force_delete_preview_lists_blockers(self):
        response = self.client.get(
            reverse("supervivencia:physical_item_force_delete", args=[self.physical_item.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asignaciones / montajes")
        self.assertContains(response, "Movimientos")
        self.assertContains(response, self.assignment.pk)
        self.assertContains(response, self.movement.pk)

    def test_force_delete_requires_exact_confirmation(self):
        response = self.client.post(
            reverse("supervivencia:physical_item_force_delete", args=[self.physical_item.pk]),
            {"confirmation": "BORRAR"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(PyrotechnicPhysicalItem.objects.filter(pk=self.physical_item.pk).exists())
        self.assertTrue(PyrotechnicAssignment.objects.filter(pk=self.assignment.pk).exists())
        self.assertTrue(PyrotechnicMovement.objects.filter(pk=self.movement.pk).exists())

    def test_force_delete_removes_item_assignments_and_movements(self):
        response = self.client.post(
            reverse("supervivencia:physical_item_force_delete", args=[self.physical_item.pk]),
            {"confirmation": "BORRAR MATERIAL"},
        )

        self.assertRedirects(response, reverse("supervivencia:physical_item_list"))
        self.assertFalse(PyrotechnicPhysicalItem.objects.filter(pk=self.physical_item.pk).exists())
        self.assertFalse(PyrotechnicAssignment.objects.filter(pk=self.assignment.pk).exists())
        self.assertFalse(PyrotechnicMovement.objects.filter(pk=self.movement.pk).exists())
        self.assertTrue(PyrotechnicCatalogItem.objects.filter(pk=self.catalog_item.pk).exists())
        log = SupervivenciaDeletionLog.objects.get(object_id=str(self.physical_item.pk))
        self.assertEqual(log.object_type, "Material fisico (borrado forzado)")
        self.assertIn("Movimientos eliminados: 1", log.object_repr)
