import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

class GroupRequiredMixin(UserPassesTestMixin):
    group_required = None

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if not self.group_required:
            return True
        groups = self.group_required if isinstance(self.group_required, list) else [self.group_required]
        return self.request.user.groups.filter(name__in=groups).exists()
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django.views import View

from core.models import Unit

from .forms import (
    ForeignTenderProcessForm,
    ForeignTenderPurchaseOrderForm,
    ForeignTenderRequirementForm,
    ForeignTenderUpdateForm,
    TenderProcessForm,
    TenderStageUpdateForm,
)
from .models import (
    ForeignTenderProcess,
    ForeignTenderPurchaseOrder,
    ForeignTenderRequirement,
    ForeignTenderUpdate,
    ProcurementDestination,
    TenderProcess,
    TenderStage,
)


class TenderTypeSelectionView(LoginRequiredMixin, TemplateView):
    template_name = "licitaciones/type_selection.html"


def _clean_int(value):
    if value in (None, ""):
        return None
    text = str(value).strip().replace(".", "").replace(",", "")
    return int(text) if text.isdigit() else None


def _percent(part, total):
    if not total:
        return 0
    return round((part * 100) / total, 1)


def _status_filter_for_group(group):
    if group == "ADJUDICADO":
        return ["ADJUDICADO"]
    if group == "DISPONIBLE":
        return ["PREADJUDICADO", "DISPONIBLE_ADJUDICAR"]
    if group == "EN_PROCESO":
        return ["PUBLICADO", "EN_EVALUACION"]
    if group == "SIN_EFECTO":
        return ["FRACASADO", "DESIERTO", "DEJADO_SIN_EFECTO"]
    return []


class TenderDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "licitaciones/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        years = list(
            TenderProcess.objects.filter(is_active=True)
            .order_by("-year")
            .values_list("year", flat=True)
            .distinct()
        )
        selected_year = _clean_int(self.request.GET.get("year"))
        if not selected_year and years:
            selected_year = years[0]

        processes = TenderProcess.objects.select_related("unit", "destination").filter(is_active=True)
        if selected_year:
            processes = processes.filter(year=selected_year)

        process_list = list(processes)
        total_count = len(process_list)
        adjudicated = [p for p in process_list if p.operational_group == "ADJUDICADO"]
        available = [p for p in process_list if p.operational_group == "DISPONIBLE"]
        cancelled = [p for p in process_list if p.operational_group == "SIN_EFECTO"]
        in_progress = [p for p in process_list if p.operational_group == "EN_PROCESO"]

        def amount_sum(items):
            return sum((p.amount_ars or 0) for p in items)

        destination_rows = []
        units = Unit.objects.filter().order_by("name")
        for unit in units:
            items = [p for p in process_list if p.unit_id == unit.id]
            item_count = len(items)
            if item_count == 0:
                continue
            destination_rows.append(
                {
                    "unit": unit,
                    "total": item_count,
                    "adjudicated_count": len([p for p in items if p.operational_group == "ADJUDICADO"]),
                    "adjudicated_amount": amount_sum([p for p in items if p.operational_group == "ADJUDICADO"]),
                    "available_count": len([p for p in items if p.operational_group == "DISPONIBLE"]),
                    "available_amount": amount_sum([p for p in items if p.operational_group == "DISPONIBLE"]),
                    "in_progress_count": len([p for p in items if p.operational_group == "EN_PROCESO"]),
                    "cancelled_count": len([p for p in items if p.operational_group == "SIN_EFECTO"]),
                    "percent": _percent(item_count, total_count),
                }
            )

        status_rows = []
        for value, label in TenderProcess.STATUS_CHOICES:
            items = [p for p in process_list if p.status == value]
            count = len(items)
            if count:
                status_rows.append(
                    {
                        "value": value,
                        "label": label,
                        "count": count,
                        "amount": amount_sum(items),
                        "percent": _percent(count, total_count),
                    }
                )

        today = timezone.localdate()
        upcoming_opening_alerts = []
        overdue_opening_alerts = []
        opening_processes = [
            p
            for p in process_list
            if p.opening_date and p.operational_group in ["EN_PROCESO", "DISPONIBLE"]
        ]
        for process in sorted(opening_processes, key=lambda p: p.opening_date):
            opening_date = timezone.localtime(process.opening_date).date()
            days_until = (opening_date - today).days
            if days_until > 7:
                break
            if days_until < 0:
                days_late = abs(days_until)
                alert_label = f"Vencida hace {days_late} dia" if days_late == 1 else f"Vencida hace {days_late} dias"
                alert_class = "text-bg-danger"
            elif days_until == 0:
                alert_label = "Abre hoy"
                alert_class = "text-bg-warning"
            elif days_until <= 7:
                alert_label = f"En {days_until} dia" if days_until == 1 else f"En {days_until} dias"
                alert_class = "text-bg-info"
            else:
                alert_label = f"En {days_until} dia(s)"
                alert_class = "text-bg-light border"
            alert = {
                "process": process,
                "alert_label": alert_label,
                "alert_class": alert_class,
                "days_until": days_until,
            }
            if days_until < 0:
                overdue_opening_alerts.append(alert)
            else:
                upcoming_opening_alerts.append(alert)

        overdue_opening_alerts = sorted(overdue_opening_alerts, key=lambda item: item["days_until"], reverse=True)
        opening_alerts = upcoming_opening_alerts + overdue_opening_alerts[:5]

        context.update(
            {
                "years": years,
                "selected_year": selected_year or "",
                "total_count": total_count,
                "total_amount": amount_sum(process_list),
                "adjudicated_count": len(adjudicated),
                "adjudicated_amount": amount_sum(adjudicated),
                "adjudicated_percent": _percent(len(adjudicated), total_count),
                "available_count": len(available),
                "available_amount": amount_sum(available),
                "available_percent": _percent(len(available), total_count),
                "in_progress_count": len(in_progress),
                "in_progress_percent": _percent(len(in_progress), total_count),
                "cancelled_count": len(cancelled),
                "cancelled_percent": _percent(len(cancelled), total_count),
                "foreign_count": len([p for p in process_list if p.currency in ["USD", "EUR", "OTRA"]]),
                "missing_amount_count": len([p for p in process_list if p.amount_ars is None]),
                "destination_rows": destination_rows,
                "status_rows": status_rows,
                "opening_alerts": opening_alerts,
                "opening_alert_days": 7,
            }
        )
        return context


class TenderProcessListView(LoginRequiredMixin, ListView):
    model = TenderProcess
    template_name = "licitaciones/process_list.html"
    context_object_name = "processes"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            TenderProcess.objects.select_related("unit", "destination", "created_by")
            .filter(is_active=True)
            .order_by("-year", "unit__name", "-opening_date", "process_number")
        )
        year = _clean_int(self.request.GET.get("year"))
        unit = _clean_int(self.request.GET.get("unit"))
        status = self.request.GET.get("status")
        classification = self.request.GET.get("classification")
        group = self.request.GET.get("group")
        control = self.request.GET.get("control")
        q = self.request.GET.get("q")

        if year:
            queryset = queryset.filter(year=year)
        if unit:
            queryset = queryset.filter(unit_id=unit)
        if status:
            queryset = queryset.filter(status=status)
        elif group:
            group_statuses = _status_filter_for_group(group)
            if group_statuses:
                queryset = queryset.filter(status__in=group_statuses)
        if classification:
            queryset = queryset.filter(classification=classification)
        if control == "missing_amount":
            queryset = queryset.filter(amount_ars__isnull=True)
        elif control == "foreign_currency":
            queryset = queryset.filter(currency__in=["USD", "EUR", "OTRA"])
        if q:
            queryset = queryset.filter(
                Q(process_number__icontains=q)
                | Q(expediente__icontains=q)
                | Q(name__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["units"] = Unit.objects.filter().order_by("name")
        context["status_choices"] = TenderProcess.STATUS_CHOICES
        context["classification_choices"] = [choice for choice in TenderProcess.CLASSIFICATION_CHOICES if choice[0]]
        context["selected_year"] = _clean_int(self.request.GET.get("year")) or ""
        context["selected_unit"] = _clean_int(self.request.GET.get("unit")) or ""
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_classification"] = self.request.GET.get("classification", "")
        context["selected_group"] = self.request.GET.get("group", "")
        context["selected_control"] = self.request.GET.get("control", "")
        context["search_query"] = self.request.GET.get("q", "")
        context["years"] = (
            TenderProcess.objects.order_by("-year")
            .values_list("year", flat=True)
            .distinct()
        )
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["pagination_query"] = query_params.urlencode()
        return context


class TenderProcessHistoryView(LoginRequiredMixin, ListView):
    model = TenderProcess
    template_name = "licitaciones/process_history.html"
    context_object_name = "processes"
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            TenderProcess.objects.select_related("unit", "destination", "created_by")
            .filter(is_active=False)
            .order_by("-year", "unit__name", "-opening_date", "process_number")
        )
        year = _clean_int(self.request.GET.get("year"))
        unit = _clean_int(self.request.GET.get("unit"))
        status = self.request.GET.get("status")
        classification = self.request.GET.get("classification")
        q = self.request.GET.get("q")

        if year:
            queryset = queryset.filter(year=year)
        if unit:
            queryset = queryset.filter(unit_id=unit)
        if status:
            queryset = queryset.filter(status=status)
        if classification:
            queryset = queryset.filter(classification=classification)
        if q:
            queryset = queryset.filter(
                Q(process_number__icontains=q)
                | Q(expediente__icontains=q)
                | Q(name__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["units"] = Unit.objects.filter().order_by("name")
        context["status_choices"] = TenderProcess.STATUS_CHOICES
        context["classification_choices"] = [choice for choice in TenderProcess.CLASSIFICATION_CHOICES if choice[0]]
        context["selected_year"] = _clean_int(self.request.GET.get("year")) or ""
        context["selected_unit"] = _clean_int(self.request.GET.get("unit")) or ""
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_classification"] = self.request.GET.get("classification", "")
        context["search_query"] = self.request.GET.get("q", "")
        context["years"] = (
            TenderProcess.objects.filter(is_active=False)
            .order_by("-year")
            .values_list("year", flat=True)
            .distinct()
        )
        return context


class TenderProcessCreateView(LoginRequiredMixin, GroupRequiredMixin, SuccessMessageMixin, CreateView):
    group_required = ["Supervisor", "Capturista"]
    model = TenderProcess
    form_class = TenderProcessForm
    template_name = "licitaciones/process_form.html"
    success_url = reverse_lazy("licitaciones:process_list")
    success_message = "Proceso licitatorio creado correctamente."

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TenderProcessDetailView(LoginRequiredMixin, DetailView):
    model = TenderProcess
    template_name = "licitaciones/process_detail.html"
    context_object_name = "process"

    def get_queryset(self):
        return TenderProcess.objects.select_related("unit", "destination", "created_by")


class TenderProcessUpdateView(LoginRequiredMixin, GroupRequiredMixin, SuccessMessageMixin, UpdateView):
    group_required = ["Supervisor", "Capturista"]
    model = TenderProcess
    form_class = TenderProcessForm
    template_name = "licitaciones/process_form.html"
    success_message = "Proceso licitatorio actualizado correctamente."

    def get_success_url(self):
        if self.object.is_active:
            return reverse_lazy("licitaciones:process_list")
        return reverse_lazy("licitaciones:process_history")


class ForeignTenderDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "licitaciones/foreign_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        years = list(
            ForeignTenderProcess.objects.filter(is_active=True).order_by("-year")
            .values_list("year", flat=True)
            .distinct()
        )
        selected_year = _clean_int(self.request.GET.get("year"))
        if not selected_year and years:
            selected_year = years[0]

        processes = ForeignTenderProcess.objects.filter(is_active=True).prefetch_related("requirements", "updates")
        if selected_year:
            processes = processes.filter(year=selected_year)

        process_list = list(processes)
        totals_by_currency = list(
            ForeignTenderProcess.objects.filter(year=selected_year, is_active=True)
            .values("currency", "custom_currency")
            .annotate(
                evaluation_total=Sum("evaluation_amount"),
                awarded_total=Sum("awarded_amount"),
                process_count=Count("id"),
            )
            .order_by("currency")
        ) if selected_year else []

        context.update(
            {
                "years": years,
                "selected_year": selected_year,
                "processes": process_list,
                "total_count": len(process_list),
                "active_count": len([p for p in process_list if p.is_active]),
                "awarded_count": len([p for p in process_list if p.status == "ADJUDICADO"]),
                "pending_count": len(
                    [
                        p
                        for p in process_list
                        if p.status
                        not in {"ADJUDICADO", "FINALIZADO", "FRACASADO", "DEJADO_SIN_EFECTO"}
                    ]
                ),
                "totals_by_currency": totals_by_currency,
            }
        )
        return context


class ForeignTenderProcessListView(LoginRequiredMixin, ListView):
    model = ForeignTenderProcess
    template_name = "licitaciones/foreign_list.html"
    context_object_name = "processes"

    def get_queryset(self):
        queryset = ForeignTenderProcess.objects.filter(is_active=True).prefetch_related("requirements", "purchase_orders", "updates")
        year = _clean_int(self.request.GET.get("year"))
        status = self.request.GET.get("status", "")
        currency = self.request.GET.get("currency", "")
        query = self.request.GET.get("q", "").strip()
        if year:
            queryset = queryset.filter(year=year)
        if status:
            queryset = queryset.filter(status=status)
        if currency:
            queryset = queryset.filter(currency=currency)
        if query:
            queryset = queryset.filter(
                Q(process_number__icontains=query)
                | Q(expediente__icontains=query)
                | Q(requirements__requirement_number__icontains=query)
                | Q(requirements__description__icontains=query)
                | Q(purchase_orders__order_number__icontains=query)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "years": ForeignTenderProcess.objects.filter(is_active=True).order_by("-year")
                .values_list("year", flat=True)
                .distinct(),
                "status_choices": ForeignTenderProcess.STATUS_CHOICES,
                "currency_choices": ForeignTenderProcess.CURRENCY_CHOICES,
                "selected_year": self.request.GET.get("year", ""),
                "selected_status": self.request.GET.get("status", ""),
                "selected_currency": self.request.GET.get("currency", ""),
                "search_query": self.request.GET.get("q", ""),
            }
        )
        return context


class ForeignTenderProcessHistoryView(LoginRequiredMixin, ListView):
    model = ForeignTenderProcess
    template_name = "licitaciones/foreign_history.html"
    context_object_name = "processes"

    def get_queryset(self):
        queryset = ForeignTenderProcess.objects.filter(is_active=False).prefetch_related(
            "requirements", "purchase_orders", "updates"
        )
        year = _clean_int(self.request.GET.get("year"))
        status = self.request.GET.get("status", "")
        currency = self.request.GET.get("currency", "")
        query = self.request.GET.get("q", "").strip()
        if year:
            queryset = queryset.filter(year=year)
        if status:
            queryset = queryset.filter(status=status)
        if currency:
            queryset = queryset.filter(currency=currency)
        if query:
            queryset = queryset.filter(
                Q(process_number__icontains=query)
                | Q(expediente__icontains=query)
                | Q(requirements__requirement_number__icontains=query)
                | Q(purchase_orders__order_number__icontains=query)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "years": ForeignTenderProcess.objects.filter(is_active=False)
                .order_by("-year")
                .values_list("year", flat=True)
                .distinct(),
                "status_choices": ForeignTenderProcess.STATUS_CHOICES,
                "currency_choices": ForeignTenderProcess.CURRENCY_CHOICES,
                "selected_year": self.request.GET.get("year", ""),
                "selected_status": self.request.GET.get("status", ""),
                "selected_currency": self.request.GET.get("currency", ""),
                "search_query": self.request.GET.get("q", ""),
            }
        )
        return context


class ForeignTenderProcessCreateView(LoginRequiredMixin, GroupRequiredMixin, SuccessMessageMixin, CreateView):
    group_required = ["Supervisor", "Capturista"]
    model = ForeignTenderProcess
    form_class = ForeignTenderProcessForm
    template_name = "licitaciones/foreign_form.html"
    success_message = "Licitacion en el exterior creada correctamente."

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ForeignTenderProcessUpdateView(LoginRequiredMixin, GroupRequiredMixin, SuccessMessageMixin, UpdateView):
    group_required = ["Supervisor", "Capturista"]
    model = ForeignTenderProcess
    form_class = ForeignTenderProcessForm
    template_name = "licitaciones/foreign_form.html"
    success_message = "Licitacion en el exterior actualizada correctamente."


class ForeignTenderProcessDetailView(LoginRequiredMixin, DetailView):
    model = ForeignTenderProcess
    template_name = "licitaciones/foreign_detail.html"
    context_object_name = "process"

    def get_queryset(self):
        return ForeignTenderProcess.objects.select_related("created_by").prefetch_related(
            "requirements__unit",
            "purchase_orders",
            "updates__created_by",
        )


class ForeignTenderArchiveToggleView(LoginRequiredMixin, GroupRequiredMixin, View):
    group_required = ["Supervisor", "Capturista"]

    def post(self, request, pk):
        process = get_object_or_404(ForeignTenderProcess, pk=pk)
        process.is_active = not process.is_active
        process.save(update_fields=["is_active", "updated_at"])
        if process.is_active:
            messages.success(request, "Licitacion reactivada correctamente.")
            return redirect(process.get_absolute_url())
        messages.success(request, "Licitacion archivada correctamente.")
        return redirect("licitaciones:foreign_history")


class ForeignTenderRequirementCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ForeignTenderRequirement
    form_class = ForeignTenderRequirementForm
    template_name = "licitaciones/foreign_child_form.html"
    success_message = "Requerimiento agregado correctamente."

    def dispatch(self, request, *args, **kwargs):
        self.process = get_object_or_404(ForeignTenderProcess, pk=kwargs["process_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.process = self.process
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"process": self.process, "child_type": "requirement"})
        return context

    def get_success_url(self):
        return self.process.get_absolute_url()


class ForeignTenderRequirementUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ForeignTenderRequirement
    form_class = ForeignTenderRequirementForm
    template_name = "licitaciones/foreign_child_form.html"
    success_message = "Requerimiento actualizado correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"process": self.object.process, "child_type": "requirement"})
        return context

    def get_success_url(self):
        return self.object.process.get_absolute_url()


class ForeignTenderUpdateCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ForeignTenderUpdate
    form_class = ForeignTenderUpdateForm
    template_name = "licitaciones/foreign_child_form.html"
    success_message = "Novedad documental registrada correctamente."

    def dispatch(self, request, *args, **kwargs):
        self.process = get_object_or_404(ForeignTenderProcess, pk=kwargs["process_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.process = self.process
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"process": self.process, "child_type": "update"})
        return context

    def get_success_url(self):
        return self.process.get_absolute_url()


class ForeignTenderPurchaseOrderCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ForeignTenderPurchaseOrder
    form_class = ForeignTenderPurchaseOrderForm
    template_name = "licitaciones/foreign_child_form.html"
    success_message = "Orden de compra agregada correctamente."

    def dispatch(self, request, *args, **kwargs):
        self.process = get_object_or_404(ForeignTenderProcess, pk=kwargs["process_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.process = self.process
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"process": self.process, "child_type": "purchase_order"})
        return context

    def get_success_url(self):
        return self.process.get_absolute_url()


class ForeignTenderPurchaseOrderUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ForeignTenderPurchaseOrder
    form_class = ForeignTenderPurchaseOrderForm
    template_name = "licitaciones/foreign_child_form.html"
    success_message = "Orden de compra actualizada correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"process": self.object.process, "child_type": "purchase_order"})
        return context

    def get_success_url(self):
        return self.object.process.get_absolute_url()


class TenderStageManageView(LoginRequiredMixin, GroupRequiredMixin, DetailView):
    group_required = ["Supervisor", "Capturista"]
    model = TenderProcess
    template_name = "licitaciones/tender_stages.html"
    context_object_name = "process"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stages"] = self.object.stages.all().order_by("stage_number")
        return context

class TenderStageUpdateView(LoginRequiredMixin, GroupRequiredMixin, SuccessMessageMixin, UpdateView):
    group_required = ["Supervisor", "Capturista"]
    model = TenderStage
    form_class = TenderStageUpdateForm
    template_name = "licitaciones/tender_stage_form.html"
    success_message = "Etapa actualizada correctamente."

    def get_success_url(self):
        return reverse_lazy('licitaciones:tender_stages', kwargs={'pk': self.object.tender.pk})

@login_required
def export_national_tenders_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="licitaciones_nacionales.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Año', 'Unidad/Destino', 'Proceso', 'Expediente', 'Objeto', 'Clasificación', 'Estado', 'Monto Adjudicado (ARS)'])

    processes = TenderProcess.objects.select_related("unit").all().order_by("-year", "unit__name", "-opening_date", "process_number")

    for p in processes:
        writer.writerow([
            p.year,
            p.unit.name if p.unit else "SIN UNIDAD",
            p.process_number,
            p.expediente,
            p.name,
            p.get_classification_display() if p.classification else "-",
            p.get_status_display(),
            p.amount_ars if p.amount_ars is not None else ""
        ])

    return response

@login_required
def mark_notification_read(request, pk):
    from .models import Notification
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
        notification.is_read = True
        notification.save()
        if notification.link:
            return redirect(notification.link)
    except Notification.DoesNotExist:
        pass
    return redirect('licitaciones:type_selection')
