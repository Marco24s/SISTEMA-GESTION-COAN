from decimal import Decimal
from datetime import date
import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Unit, UserSystemPIN

from . import services
from .forms import (
    BudgetAllocationMetadataForm,
    BudgetAllocationReclassificationForm,
    BudgetCompensacionForm,
)
from .models import (
    BudgetAllocation,
    BudgetCredit,
    BudgetCreditType,
    BudgetAllocationReclassification,
    BudgetClassification,
    BudgetFF,
    BudgetFiscalYear,
    BudgetInc,
    BudgetIncisosAgrupado,
    BudgetPPInc,
    BudgetPPPInc,
    BudgetPreInc,
    BudgetProg,
    BudgetSubprog,
)


User = get_user_model()


class BudgetCompensacionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="comp-test", password="test")
        self.year = BudgetFiscalYear.objects.create(year=2026, status="OPEN")
        self.credit_type = BudgetCreditType.objects.create(code="ASIG", name="Asignacion")
        self.ff = BudgetFF.objects.create(code="11", name="Tesoro")
        self.programa = BudgetProg.objects.create(code="1", name="Programa")
        self.subprog = BudgetSubprog.objects.create(code="1", name="Subprograma")
        self.source_inc = BudgetInc.objects.create(code="2", name="Origen")
        self.target_inc = BudgetInc.objects.create(code="3", name="Destino")
        self.ppp = BudgetPPPInc.objects.create(code="1", name="Principal")
        self.pp = BudgetPPInc.objects.create(code="1", name="Parcial")
        self.pre = BudgetPreInc.objects.create(code="1", name="Subparcial")
        self.currency = BudgetIncisosAgrupado.objects.create(code="1", name="Pesos")
        self.source = BudgetCredit.objects.create(
            fiscal_year=self.year,
            credit_type=self.credit_type,
            ff=self.ff,
            programa=self.programa,
            subprog=self.subprog,
            inc=self.source_inc,
            ppp_inc=self.ppp,
            pp_inc=self.pp,
            pre_inc=self.pre,
            incisos_agrupado=self.currency,
            q1_amount=Decimal("1000.00"),
        )
        self.unit = Unit.objects.create(name="Unidad Compensacion")
        BudgetAllocation.objects.create(
            credit=self.source,
            unit=self.unit,
            q1_amount=Decimal("600.00"),
        )
        self.target_params = {
            "target_ff": self.ff,
            "target_subprog": self.subprog,
            "target_inc": self.target_inc,
            "target_ppp_inc": self.ppp,
            "target_pp_inc": self.pp,
            "target_pre_inc": self.pre,
            "target_incisos_agrupado": self.currency,
        }

    def request(self, amount):
        return services.request_compensacion(
            source_credit=self.source,
            target_params=self.target_params,
            q_amounts=(Decimal(str(amount)), 0, 0, 0),
            user=self.user,
        )

    def test_request_uses_only_unallocated_balance(self):
        with self.assertRaises(ValidationError) as error:
            self.request("500.00")
        self.assertIn("solo hay $400.00 sin distribuir", str(error.exception))

        compensation = self.request("400.00")
        self.assertEqual(compensation.status, "PENDIENTE")

    def test_pending_request_reserves_balance(self):
        self.request("300.00")

        with self.assertRaises(ValidationError):
            self.request("150.00")
        with self.assertRaises(ValidationError):
            services.allocate_credit(
                credit=self.source,
                unit=Unit.objects.create(name="Otra Unidad"),
                q1=Decimal("150.00"),
            )

    def test_approval_does_not_move_funds_and_execution_does(self):
        compensation = self.request("300.00")

        services.approve_compensacion(compensation.pk, self.user)
        compensation.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(compensation.status, "APROBADO")
        self.assertEqual(self.source.q1_amount, Decimal("1000.00"))

        services.execute_compensacion(compensation.pk, self.user)
        compensation.refresh_from_db()
        self.source.refresh_from_db()
        target = BudgetCredit.objects.get(
            fiscal_year=self.year,
            programa=self.programa,
            inc=self.target_inc,
        )
        self.assertEqual(compensation.status, "EJECUTADO")
        self.assertEqual(self.source.q1_amount, Decimal("700.00"))
        self.assertEqual(target.q1_amount, Decimal("300.00"))

    def test_rejection_releases_reserved_balance(self):
        compensation = self.request("300.00")
        services.reject_compensacion(compensation.pk)

        replacement = self.request("400.00")
        self.assertEqual(replacement.status, "PENDIENTE")

    def test_form_derives_year_and_program_from_source(self):
        form = BudgetCompensacionForm()
        self.assertNotIn("fiscal_year", form.fields)
        self.assertNotIn("programa", form.fields)

    def test_allocation_metadata_form_only_allows_project_and_notes(self):
        form = BudgetAllocationMetadataForm()
        self.assertEqual(set(form.fields), {"custom_classes", "notes"})

    def test_allocation_reclassification_form_has_destination_and_quarter_fields(self):
        form = BudgetAllocationReclassificationForm()
        self.assertIn("target_inc", form.fields)
        self.assertIn("q1_amount", form.fields)

    def test_metadata_update_does_not_change_allocation_amounts(self):
        allocation = self.source.allocations.get()
        project = BudgetClassification.objects.create(
            name="Proyecto de prueba",
            target_amount=Decimal("1000.00"),
        )

        services.update_allocation_metadata(
            allocation.pk,
            notes="Observacion actualizada",
            classifications=[project],
        )

        allocation.refresh_from_db()
        self.assertEqual(allocation.q1_amount, Decimal("600.00"))
        self.assertEqual(allocation.notes, "Observacion actualizada")
        self.assertEqual(list(allocation.custom_classes.all()), [project])

    def test_reclassification_request_approval_and_execution_flow(self):
        allocation = self.source.allocations.get()

        request = services.request_allocation_reclassification(
            allocation_id=allocation.pk,
            target_params=self.target_params,
            q_amounts=(Decimal("200.00"), 0, 0, 0),
            user=self.user,
            notes="Pedido de la unidad",
        )

        allocation.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(request.status, "PENDIENTE")
        self.assertEqual(allocation.q1_amount, Decimal("600.00"))
        self.assertEqual(self.source.q1_amount, Decimal("1000.00"))

        services.approve_allocation_reclassification(request.pk, self.user)
        request.refresh_from_db()
        allocation.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(request.status, "APROBADO")
        self.assertEqual(allocation.q1_amount, Decimal("600.00"))
        self.assertEqual(self.source.q1_amount, Decimal("1000.00"))

        target_allocation = services.execute_allocation_reclassification(request.pk, self.user)
        request.refresh_from_db()
        allocation.refresh_from_db()
        self.source.refresh_from_db()
        target_credit = target_allocation.credit
        self.assertEqual(request.status, "EJECUTADO")
        self.assertEqual(allocation.q1_amount, Decimal("400.00"))
        self.assertEqual(self.source.q1_amount, Decimal("800.00"))
        self.assertEqual(target_credit.inc, self.target_inc)
        self.assertEqual(target_credit.q1_amount, Decimal("200.00"))
        self.assertEqual(target_allocation.unit, self.unit)
        self.assertEqual(target_allocation.q1_amount, Decimal("200.00"))
        self.assertEqual(BudgetAllocationReclassification.objects.count(), 1)

    def test_reclassification_request_reserves_available_balance(self):
        allocation = self.source.allocations.get()
        services.request_allocation_reclassification(
            allocation_id=allocation.pk,
            target_params=self.target_params,
            q_amounts=(Decimal("500.00"), 0, 0, 0),
            user=self.user,
        )

        with self.assertRaises(ValidationError) as error:
            services.request_allocation_reclassification(
                allocation_id=allocation.pk,
                target_params=self.target_params,
                q_amounts=(Decimal("200.00"), 0, 0, 0),
                user=self.user,
            )

        self.assertIn("solo hay $100.00 disponible sin reservar", str(error.exception))

    def test_reclassification_does_not_move_committed_balance(self):
        allocation = self.source.allocations.get()
        services.register_commitment(
            allocation_id=allocation.pk,
            reference_code="EXP-1",
            amount=Decimal("500.00"),
            commitment_date=date(2026, 6, 23),
            user=self.user,
        )

        with self.assertRaises(ValidationError) as error:
            services.request_allocation_reclassification(
                allocation_id=allocation.pk,
                target_params=self.target_params,
                q_amounts=(Decimal("200.00"), 0, 0, 0),
                user=self.user,
            )

        self.assertIn("supera el disponible sin comprometer", str(error.exception))

    def test_reclassification_history_does_not_block_zero_origin_cleanup(self):
        allocation = self.source.allocations.get()

        item = services.request_allocation_reclassification(
            allocation_id=allocation.pk,
            target_params=self.target_params,
            q_amounts=(Decimal("600.00"), 0, 0, 0),
            user=self.user,
        )
        services.approve_allocation_reclassification(item.pk, self.user)
        services.execute_allocation_reclassification(item.pk, self.user)

        allocation.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(allocation.allocated_amount, Decimal("0.00"))
        self.assertEqual(allocation.spent_amount, Decimal("0.00"))
        self.assertEqual(self.source.total_amount, Decimal("400.00"))

        allocation.delete()

        self.source.q1_amount = Decimal("0.00")
        self.source.save()
        self.source.delete()

        history = BudgetAllocationReclassification.objects.get()
        self.assertIsNone(history.source_allocation)
        self.assertIsNone(history.source_credit)

    def test_dashboard_credit_type_modal_uses_quarter_amounts(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        credit_type_rows = list(response.context["stats"]["credit_by_type"])
        self.assertEqual(len(credit_type_rows), 1)
        self.assertEqual(credit_type_rows[0]["q1"], Decimal("1000.00"))
        self.assertEqual(credit_type_rows[0]["allocated"], Decimal("600.00"))
        self.assertEqual(len(credit_type_rows[0]["subpcs"]), 1)
        self.assertEqual(credit_type_rows[0]["subpcs"][0]["q1"], Decimal("1000.00"))
        self.assertEqual(credit_type_rows[0]["subpcs"][0]["allocated"], Decimal("600.00"))
        self.assertEqual(credit_type_rows[0]["subpcs"][0]["allocated_q1"], Decimal("600.00"))
        allocated_rows = response.context["stats"]["allocated_by_subpc"]
        self.assertEqual(len(allocated_rows), 1)
        self.assertEqual(allocated_rows[0]["q1"], Decimal("600.00"))
        self.assertEqual(allocated_rows[0]["available"], Decimal("600.00"))
        self.assertContains(response, "Programacion trimestral")
        self.assertContains(response, "SUBPC 1")
        self.assertContains(response, "Detalle por unidad")

    def test_credit_detail_quarter_cards_show_original_movement_and_remaining(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.client.force_login(self.user)
        UserSystemPIN.objects.create(user=self.user, system_code="sgmg", pin_hash="test")
        session = self.client.session
        session["verified_pins"] = {"sgmg": time.time()}
        session.save()
        compensation = self.request("300.00")
        services.approve_compensacion(compensation.pk, self.user)
        services.execute_compensacion(compensation.pk, self.user)

        response = self.client.get(f"/credits/{self.source.pk}/detail/")

        self.assertEqual(response.status_code, 200)
        q1_card = response.context["q_cards"][0]
        self.assertEqual(q1_card["original"], Decimal("1000.00"))
        self.assertEqual(q1_card["movement"], Decimal("-300.00"))
        self.assertEqual(q1_card["remaining"], Decimal("100.00"))
