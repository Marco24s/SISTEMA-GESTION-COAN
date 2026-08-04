import time
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Unit, UserSystemPIN
from licitaciones.forms import ForeignTenderProcessForm
from licitaciones.models import (
    ForeignTenderProcess,
    ForeignTenderPurchaseOrder,
    ForeignTenderRequirement,
    ForeignTenderUpdate,
    TenderProcess,
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

    def test_national_process_pagination_preserves_filters(self):
        self.login_with_licitaciones_pin()
        unit = Unit.objects.create(name="FAE2")
        base_date = timezone.make_aware(datetime(2026, 7, 1, 8, 0))
        for index in range(28):
            process_number = "38/25-0102-LPR26" if index == 26 else f"38/25-{index:04d}-LPR26"
            TenderProcess.objects.create(
                year=2026,
                unit=unit,
                process_number=process_number,
                expediente=f"EX-2026-{index:04d}-APN-COAN#ARA",
                name=f"Proceso FAE2 {index}",
                process_type="PUBLICA",
                opening_date=base_date - timedelta(days=index),
                status="PUBLICADO",
            )

        response = self.client.get(
            reverse("licitaciones:process_list"),
            {"year": "2026", "unit": str(unit.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"year=2026&amp;unit={unit.pk}&amp;page=2",
        )


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

    def test_foreign_process_form_requires_expediente(self):
        form = ForeignTenderProcessForm(
            data={
                "year": 2026,
                "process_number": "LIC 01/26",
                "process_type": "PUBLICA",
                "status": "INICIADO",
                "currency": "USD",
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("expediente", form.errors)
        self.assertEqual(form.fields["sp"].label, "Solicitud de provisión (SP)")

    def test_delivery_due_date_uses_calendar_or_business_days(self):
        process = ForeignTenderProcess(
            year=2026,
            process_number="LIC 02/26",
            currency="USD",
            oca_expiration="17/07/2026",
            delivery_term_days=3,
            delivery_term_day_type="CORRIDOS",
        )

        self.assertEqual(process.delivery_due_date, date(2026, 7, 20))

        process.delivery_term_day_type = "HABILES"
        self.assertEqual(process.delivery_due_date, date(2026, 7, 22))

    def test_delivery_term_is_required_when_oca_expiration_is_a_date(self):
        form = ForeignTenderProcessForm(
            data={
                "year": 2026,
                "process_number": "LIC 02/26",
                "expediente": "EX-2026-123-APN-COAN#ARA",
                "process_type": "PUBLICA",
                "status": "INICIADO",
                "currency": "USD",
                "oca_expiration": "17/07/2026",
                "is_active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("delivery_term_days", form.errors)
        self.assertIn("delivery_term_day_type", form.errors)

    def test_oca_no_clears_expiration_and_delivery_term(self):
        form = ForeignTenderProcessForm(
            data={
                "year": 2026,
                "process_number": "LIC 03/26",
                "expediente": "EX-2026-456-APN-COAN#ARA",
                "process_type": "PUBLICA",
                "has_oca": False,
                "status": "INICIADO",
                "currency": "USD",
                "oca_expiration": "17/07/2026",
                "delivery_term_days": 10,
                "delivery_term_day_type": "CORRIDOS",
                "is_active": True,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        process = form.save(commit=False)
        self.assertEqual(process.oca_expiration, "")
        self.assertIsNone(process.delivery_term_days)
        self.assertEqual(process.delivery_term_day_type, "")
        self.assertIsNone(process.delivery_due_date)

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

    def test_sitrep_fields_and_purchase_orders_are_available(self):
        self.login_with_pin()
        process = self.create_process()
        process.expediente = "EX-2025-73889265-APN-DEDGMA#ARA"
        process.allocation_gfh = "COAN 271054 FEB26"
        process.incoterm = "DAP"
        process.oca_expiration = "NO APLICA"
        process.sp = "1"
        process.saimb_number = "11/26"
        process.received = False
        process.evaluation_amount = Decimal("208538.74")
        process.awarded_amount = Decimal("145689.95")
        process.save()
        order = ForeignTenderPurchaseOrder.objects.create(
            process=process,
            order_number="oca 14/26",
            amount=Decimal("140854.95"),
            issue_date=date(2026, 5, 15),
        )

        detail_response = self.client.get(
            reverse("licitaciones:foreign_detail", args=[process.pk])
        )
        list_response = self.client.get(reverse("licitaciones:foreign_list"))

        self.assertEqual(process.remaining_amount, Decimal("62848.79"))
        self.assertEqual(order.order_number, "OCA 14/26")
        self.assertContains(detail_response, process.expediente)
        self.assertContains(detail_response, "OCA 14/26")
        self.assertContains(detail_response, "62.848,79")
        self.assertContains(list_response, "GFH DE")
        self.assertContains(list_response, process.saimb_number)

    def test_purchase_order_can_be_added_from_foreign_detail(self):
        self.login_with_pin()
        process = self.create_process()

        response = self.client.post(
            reverse("licitaciones:foreign_purchase_order_create", args=[process.pk]),
            {
                "order_number": "OC 15/26",
                "amount": "4835.00",
                "issue_date": "2026-05-15",
            },
        )

        self.assertRedirects(response, process.get_absolute_url())
        self.assertTrue(process.purchase_orders.filter(order_number="OC 15/26").exists())

    def test_foreign_process_can_be_archived_and_reactivated(self):
        self.login_with_pin()
        self.user.groups.add(Group.objects.create(name="Supervisor"))
        process = self.create_process()

        archive_response = self.client.post(
            reverse("licitaciones:foreign_archive_toggle", args=[process.pk])
        )
        process.refresh_from_db()

        self.assertFalse(process.is_active)
        self.assertRedirects(archive_response, reverse("licitaciones:foreign_history"))
        self.assertNotContains(
            self.client.get(reverse("licitaciones:foreign_list")),
            process.process_number,
        )
        self.assertNotContains(
            self.client.get(reverse("licitaciones:foreign_dashboard")),
            process.process_number,
        )
        self.assertContains(
            self.client.get(reverse("licitaciones:foreign_history")),
            process.process_number,
        )

        reactivate_response = self.client.post(
            reverse("licitaciones:foreign_archive_toggle", args=[process.pk])
        )
        process.refresh_from_db()

        self.assertTrue(process.is_active)
        self.assertRedirects(reactivate_response, process.get_absolute_url())

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
