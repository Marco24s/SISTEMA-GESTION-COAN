from django.test import TestCase

from .forms import PyrotechnicCatalogItemForm, PyrotechnicPhysicalItemForm
from .models import PyrotechnicCatalogItem


class PyrotechnicCatalogIdentityTests(TestCase):
    def setUp(self):
        self.existing = PyrotechnicCatalogItem.objects.create(
            nomenclature="BENGALA DE MANO",
            system="CHALECO",
            part_number="13",
            nsn="13",
            alternate_part_number="1",
        )

    def test_part_number_can_repeat_when_other_identity_data_differs(self):
        form = PyrotechnicCatalogItemForm(data={
            "nomenclature": "BENGALA DE SENALES",
            "system": "BALSA",
            "part_number": "13",
            "nsn": "99",
            "alternate_part_number": "2",
            "description": "",
            "is_active": True,
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_complete_identity_cannot_repeat(self):
        form = PyrotechnicCatalogItemForm(data={
            "nomenclature": "BENGALA DE MANO",
            "system": "CHALECO",
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
