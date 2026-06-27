import time
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import Unit, UserSystemPIN
from licitaciones.models import (
    ForeignTenderProcess,
    ForeignTenderRequirement,
    ForeignTenderUpdate,
)


class TenderTypeSelectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="licitaciones_test",
            password="test-password",
        )
        UserSystemPIN.objects.create(
            user=self.user,
            system_code="licitaciones",
            pin_hash=make_password("1234"),
        )

    def login_with_licitaciones_pin(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["verified_pins"] = {"licitaciones": time.time()}
        session.save()

    def test_selection_requires_login(self):
        response = self.client.get(reverse("licitaciones:type_selection"))

        self.assertEqual(response.status_code, 302)

    def test_selection_links_to_national_dashboard(self):
        self.login_with_licitaciones_pin()

        response = self.client.get(reverse("licitaciones:type_selection"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("licitaciones:dashboard"))
        self.assertContains(response, "Licitacion en el extranjero")
        self.assertContains(response, "disabled")

    def test_national_dashboard_keeps_its_named_route(self):
        self.assertEqual(reverse("licitaciones:dashboard"), "/licitaciones/nacional/")


class ForeignTenderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="foreign_tender_test",
            password="test-password",
        )
        UserSystemPIN.objects.create(
            user=self.user,
            system_code="licitaciones",
            pin_hash=make_password("1234"),
        )
        self.unit = Unit.objects.create(name="ARCE")

    def login_with_pin(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["verified_pins"] = {"licitaciones": time.time()}
        session.save()

    def create_process(self):
        return ForeignTenderProcess.objects.create(
            year=2026,
            process_number="LIC PUBLICA 03/26",
            process_type="PUBLICA",
            status="EN_EVALUACION",
            currency="USD",
            created_by=self.user,
        )

    def test_other_currency_requires_a_name(self):
        process = ForeignTenderProcess(
            year=2026,
            process_number="LIC 01/26",
            currency="OTRA",
        )

        with self.assertRaises(ValidationError):
            process.full_clean()

    def test_requirement_uses_process_currency_and_contributes_to_total(self):
        process = self.create_process()
        ForeignTenderRequirement.objects.create(
            process=process,
            requirement_number="500006",
            requested_amount=Decimal("97146.10"),
            unit=self.unit,
            description="Repuestos sistematicos",
        )
        ForeignTenderRequirement.objects.create(
            process=process,
            requirement_number="500007",
            requested_amount=Decimal("20297.90"),
            unit=self.unit,
            description="Repuestos sistematicos",
        )

        self.assertEqual(process.requested_amount, Decimal("117444.00"))
        self.assertFalse(hasattr(process.requirements.first(), "currency"))

    def test_foreign_flow_renders_process_requirements_and_updates(self):
        self.login_with_pin()
        process = self.create_process()
        requirement = ForeignTenderRequirement.objects.create(
            process=process,
            requirement_number="500006",
            requested_amount=Decimal("97146.10"),
            unit=self.unit,
            aircraft="UH-3H",
            description="Repuestos sistematicos",
        )
        ForeignTenderUpdate.objects.create(
            process=process,
            event_date=date(2026, 2, 13),
            organization="MNLA",
            document_type="GFH",
            document_number="GFH 071010 ENE 26",
            description="Solicita temperamento a seguir.",
            created_by=self.user,
        )

        dashboard_response = self.client.get(reverse("licitaciones:foreign_dashboard"))
        detail_response = self.client.get(
            reverse("licitaciones:foreign_detail", args=[process.pk])
        )

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, process.process_number)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, requirement.requirement_number)
        self.assertContains(detail_response, "GFH 071010 ENE 26")

    def test_create_requirement_attaches_it_to_the_selected_process(self):
        self.login_with_pin()
        process = self.create_process()

        response = self.client.post(
            reverse("licitaciones:foreign_requirement_create", args=[process.pk]),
            {
                "requirement_number": "500010",
                "requested_amount": "9558.56",
                "unit": self.unit.pk,
                "workshop": "",
                "aircraft": "UH-3H",
                "description": "Inverter",
                "notes": "",
            },
        )

        self.assertRedirects(response, process.get_absolute_url())
        self.assertTrue(
            process.requirements.filter(requirement_number="500010").exists()
        )
