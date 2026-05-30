from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from core.models import Unit

from .forms import TenderProcessForm
from .models import ProcurementDestination, TenderProcess


def _clean_int(value):
    if value in (None, ""):
        return None
    text = str(value).strip().replace(".", "").replace(",", "")
    return int(text) if text.isdigit() else None


def _percent(part, total):
    if not total:
        return 0
    return round((part * 100) / total, 1)


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
                "recent_processes": process_list[:8],
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
        control = self.request.GET.get("control")
        q = self.request.GET.get("q")

        if year:
            queryset = queryset.filter(year=year)
        if unit:
            queryset = queryset.filter(unit_id=unit)
        if status:
            queryset = queryset.filter(status=status)
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
        context["selected_year"] = _clean_int(self.request.GET.get("year")) or ""
        context["selected_unit"] = _clean_int(self.request.GET.get("unit")) or ""
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_control"] = self.request.GET.get("control", "")
        context["search_query"] = self.request.GET.get("q", "")
        context["years"] = (
            TenderProcess.objects.order_by("-year")
            .values_list("year", flat=True)
            .distinct()
        )
        return context


class TenderProcessCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
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


class TenderProcessUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = TenderProcess
    form_class = TenderProcessForm
    template_name = "licitaciones/process_form.html"
    success_url = reverse_lazy("licitaciones:process_list")
    success_message = "Proceso licitatorio actualizado correctamente."
