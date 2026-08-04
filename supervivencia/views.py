from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
    PyrotechnicAssignmentForm,
    PyrotechnicCatalogItemForm,
    PyrotechnicCatalogLifeRuleFormSet,
    PyrotechnicPhysicalItemMovementForm,
    PyrotechnicPhysicalItemForm,
    PyrotechnicStorageLocationForm,
    SurvivalMediumForm,
)
from .models import (
    PyrotechnicAssignment,
    PyrotechnicCatalogItem,
    PyrotechnicCatalogLifeRule,
    PyrotechnicMovement,
    PyrotechnicPhysicalItem,
    PyrotechnicStorageLocation,
    SupervivenciaDeletionLog,
    SurvivalMedium,
)


def _clean_int(value):
    if value in (None, ""):
        return None
    text = str(value).strip().replace(".", "").replace(",", "")
    return int(text) if text.isdigit() else None


def _assignment_destination(assignment):
    destination = str(assignment.medium)
    if assignment.position:
        destination = f"{destination} / {assignment.position}"
    return destination


def _create_pyrotechnic_movement(
    *,
    assignment,
    movement_type,
    movement_date,
    user,
    from_reference=None,
    to_reference=None,
    notes=None,
):
    return PyrotechnicMovement.objects.create(
        physical_item=assignment.physical_item,
        medium=assignment.medium,
        assignment=assignment,
        movement_type=movement_type,
        movement_date=movement_date,
        from_reference=from_reference,
        to_reference=to_reference,
        notes=notes,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


def _item_location_reference(item):
    if item.current_storage_location:
        return str(item.current_storage_location)
    return item.current_location or ""


def _physical_item_delete_blockers(item):
    assignments = list(
        PyrotechnicAssignment.objects.filter(physical_item=item)
        .select_related("medium", "medium__unit")
        .order_by("-is_active", "-installed_at", "-removed_at")
    )
    movements = list(
        PyrotechnicMovement.objects.filter(physical_item=item)
        .select_related("medium", "assignment", "created_by")
        .order_by("-movement_date", "-created_at")
    )
    blockers = []
    if assignments:
        blockers.append(
            {
                "label": "Asignaciones / montajes",
                "count": len(assignments),
                "objects": assignments,
            }
        )
    if movements:
        blockers.append(
            {
                "label": "Movimientos",
                "count": len(movements),
                "objects": movements,
            }
        )
    return blockers


def _physical_item_force_delete(item, user):
    object_repr = str(item)
    object_id = str(item.pk)
    assignment_count = PyrotechnicAssignment.objects.filter(physical_item=item).count()
    movement_count = PyrotechnicMovement.objects.filter(physical_item=item).count()

    with transaction.atomic():
        PyrotechnicMovement.objects.filter(physical_item=item).delete()
        PyrotechnicAssignment.objects.filter(physical_item=item).delete()
        item.delete()
        SupervivenciaDeletionLog.objects.create(
            object_type="Material fisico (borrado forzado)",
            object_id=object_id,
            object_repr=(
                f"{object_repr} | Movimientos eliminados: {movement_count} | "
                f"Asignaciones eliminadas: {assignment_count}"
            )[:300],
            deleted_by=user,
        )

    return object_repr, movement_count, assignment_count


ADMIN_DELETE_MODELS = {
    "medium": {
        "label": "Medios",
        "model": SurvivalMedium,
        "search": ("identifier", "name", "model", "unit__name"),
        "order": ("identifier",),
    },
    "catalog": {
        "label": "Catalogo",
        "model": PyrotechnicCatalogItem,
        "search": ("nomenclature", "system", "part_number", "nsn", "alternate_part_number"),
        "order": ("nomenclature",),
    },
    "life_rule": {
        "label": "Reglas de vida util",
        "model": PyrotechnicCatalogLifeRule,
        "search": ("catalog_item__nomenclature", "catalog_item__system", "notes"),
        "order": ("catalog_item__nomenclature", "situation"),
    },
    "physical": {
        "label": "Material fisico",
        "model": PyrotechnicPhysicalItem,
        "search": (
            "catalog_item__nomenclature",
            "catalog_item__system",
            "catalog_item__part_number",
            "catalog_item__nsn",
            "catalog_item__alternate_part_number",
            "serial_number",
            "lot_number",
            "manufacturer",
            "current_location",
            "current_storage_location__code",
            "current_storage_location__unit__name",
        ),
        "order": ("expiration_date", "catalog_item__nomenclature"),
        "select_related": ("catalog_item", "current_storage_location", "current_storage_location__unit"),
    },
    "location": {
        "label": "Ubicaciones",
        "model": PyrotechnicStorageLocation,
        "search": ("code", "name", "unit__name", "notes"),
        "order": ("code",),
    },
    "assignment": {
        "label": "Asignaciones",
        "model": PyrotechnicAssignment,
        "search": (
            "medium__identifier",
            "medium__name",
            "physical_item__catalog_item__nomenclature",
            "physical_item__serial_number",
            "physical_item__lot_number",
        ),
        "order": ("-installed_at",),
    },
    "movement": {
        "label": "Movimientos",
        "model": PyrotechnicMovement,
        "search": (
            "physical_item__catalog_item__nomenclature",
            "physical_item__serial_number",
            "physical_item__lot_number",
            "medium__identifier",
            "from_reference",
            "to_reference",
            "notes",
        ),
        "order": ("-movement_date", "-created_at"),
    },
}


def _superuser_required(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden("Solo un superusuario puede acceder a esta administracion.")
    return None


class SupervivenciaDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "supervivencia/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        next_6_months = today + timedelta(days=183)
        next_1_year = today + timedelta(days=365)
        next_2_years = today + timedelta(days=730)

        active_items = PyrotechnicPhysicalItem.objects.filter(is_active=True)
        active_assignments = PyrotechnicAssignment.objects.filter(is_active=True).select_related(
            "medium", "physical_item"
        )
        assignment_by_item = {assignment.physical_item_id: assignment for assignment in active_assignments}

        alert_items = (
            active_items.filter(expiration_date__lte=next_2_years)
            .select_related("catalog_item", "current_storage_location")
            .order_by("expiration_date", "catalog_item__nomenclature")[:15]
        )
        expiration_alerts = []
        for item in alert_items:
            assignment = assignment_by_item.get(item.id)
            if item.expiration_date <= today:
                item.alert_label = "Vencido"
                item.alert_class = "danger"
            elif item.expiration_date <= next_6_months:
                item.alert_label = "Vence dentro de 6 meses"
                item.alert_class = "warning"
            elif item.expiration_date <= next_1_year:
                item.alert_label = "Vence entre 6 meses y 1 año"
                item.alert_class = "info"
            else:
                item.alert_label = "Vence entre 1 y 2 años"
                item.alert_class = "secondary"
            item.current_assignment = assignment
            expiration_alerts.append(item)

        latest_movements = PyrotechnicMovement.objects.select_related(
            "physical_item",
            "physical_item__catalog_item",
            "medium",
            "created_by",
        ).order_by("-movement_date", "-created_at")[:8]

        context.update(
            {
                "medium_count": SurvivalMedium.objects.filter(is_active=True).count(),
                "catalog_count": PyrotechnicCatalogItem.objects.filter(is_active=True).count(),
                "total_active_material": active_items.count(),
                "mounted_count": active_assignments.count(),
                "stock_count": active_items.filter(operational_status="STOCK").count(),
                "expired_count": active_items.filter(expiration_date__lte=today).count(),
                "next_6_months_count": active_items.filter(
                    expiration_date__gt=today, expiration_date__lte=next_6_months
                ).count(),
                "next_1_year_count": active_items.filter(
                    expiration_date__gt=next_6_months, expiration_date__lte=next_1_year
                ).count(),
                "next_2_years_count": active_items.filter(
                    expiration_date__gt=next_1_year, expiration_date__lte=next_2_years
                ).count(),
                "expiration_alerts": expiration_alerts,
                "latest_movements": latest_movements,
            }
        )
        return context


class SupervivenciaAdminDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "supervivencia/admin_delete_list.html"

    def dispatch(self, request, *args, **kwargs):
        forbidden = _superuser_required(request)
        if forbidden:
            return forbidden
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_type = self.request.GET.get("type", "medium")
        if selected_type not in ADMIN_DELETE_MODELS:
            selected_type = "medium"
        config = ADMIN_DELETE_MODELS[selected_type]
        queryset = config["model"].objects.all().order_by(*config["order"])
        if config.get("select_related"):
            queryset = queryset.select_related(*config["select_related"])
        q = self.request.GET.get("q", "").strip()
        if q:
            query = Q()
            for field in config["search"]:
                query |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(query)

        context.update(
            {
                "model_options": ADMIN_DELETE_MODELS,
                "selected_type": selected_type,
                "selected_label": config["label"],
                "search_query": q,
                "objects": queryset[:100],
            }
        )
        return context


class SupervivenciaAdminDeleteConfirmView(LoginRequiredMixin, TemplateView):
    template_name = "supervivencia/admin_delete_confirm.html"

    def dispatch(self, request, *args, **kwargs):
        forbidden = _superuser_required(request)
        if forbidden:
            return forbidden
        self.model_type = kwargs.get("model_type")
        if self.model_type not in ADMIN_DELETE_MODELS:
            return HttpResponseForbidden("Tipo de registro no permitido.")
        config = ADMIN_DELETE_MODELS[self.model_type]
        self.config = config
        self.object = get_object_or_404(config["model"], pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        blockers = _physical_item_delete_blockers(self.object) if self.model_type == "physical" else []
        context.update(
            {
                "model_type": self.model_type,
                "model_label": self.config["label"],
                "object": self.object,
                "blockers": blockers,
                "protected_objects": getattr(self, "protected_objects", []),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        confirmation = request.POST.get("confirmation", "").strip().upper()
        if confirmation != "BORRAR":
            messages.error(request, "Debe escribir BORRAR para confirmar la eliminacion definitiva.")
            return self.get(request, *args, **kwargs)

        object_repr = str(self.object)
        object_id = str(self.object.pk)
        object_type = self.config["label"]
        try:
            self.object.delete()
        except ProtectedError as error:
            protected_objects = list(error.protected_objects)
            messages.error(
                request,
                "No se pudo borrar porque tiene datos relacionados protegidos. Revise el detalle listado abajo.",
            )
            self.protected_objects = protected_objects
            return self.get(request, *args, **kwargs)

        SupervivenciaDeletionLog.objects.create(
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr[:300],
            deleted_by=request.user,
        )
        messages.success(request, f"Registro eliminado definitivamente: {object_repr}")
        return redirect(f"{reverse_lazy('supervivencia:admin_delete')}?type={self.model_type}")


class SurvivalMediumListView(LoginRequiredMixin, ListView):
    model = SurvivalMedium
    template_name = "supervivencia/medium_list.html"
    context_object_name = "mediums"

    def get_queryset(self):
        queryset = SurvivalMedium.objects.select_related("unit").order_by("identifier")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(identifier__icontains=q)
                | Q(name__icontains=q)
                | Q(model__icontains=q)
                | Q(unit__name__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        return context


class SurvivalMediumDetailView(LoginRequiredMixin, DetailView):
    model = SurvivalMedium
    template_name = "supervivencia/medium_detail.html"
    context_object_name = "medium"

    def get_queryset(self):
        return SurvivalMedium.objects.select_related("unit")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        next_6_months = today + timedelta(days=183)
        assignments = (
            PyrotechnicAssignment.objects.filter(medium=self.object)
            .select_related("physical_item", "physical_item__catalog_item", "physical_item__current_storage_location")
            .order_by("-is_active", "physical_item__expiration_date", "position")
        )
        active_assignments = []
        history_assignments = []
        for assignment in assignments:
            expiration_date = assignment.physical_item.expiration_date
            if expiration_date <= today:
                assignment.expiration_state = "Vencido"
                assignment.expiration_class = "danger"
            elif expiration_date <= next_6_months:
                assignment.expiration_state = "Vence dentro de 6 meses"
                assignment.expiration_class = "warning"
            else:
                assignment.expiration_state = "Vigente"
                assignment.expiration_class = "success"

            if assignment.is_active:
                active_assignments.append(assignment)
            else:
                history_assignments.append(assignment)

        context.update(
            {
                "active_assignments": active_assignments,
                "history_assignments": history_assignments,
                "active_count": len(active_assignments),
                "expired_count": sum(1 for row in active_assignments if row.physical_item.expiration_date <= today),
                "next_6_months_count": sum(
                    1 for row in active_assignments if today < row.physical_item.expiration_date <= next_6_months
                ),
            }
        )
        return context


class SurvivalMediumCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = SurvivalMedium
    form_class = SurvivalMediumForm
    template_name = "supervivencia/form.html"
    success_url = reverse_lazy("supervivencia:medium_list")
    success_message = "Medio cargado correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nuevo medio"
        return context


class SurvivalMediumUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = SurvivalMedium
    form_class = SurvivalMediumForm
    template_name = "supervivencia/form.html"
    success_url = reverse_lazy("supervivencia:medium_list")
    success_message = "Medio actualizado correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar medio"
        return context


@login_required
@require_POST
def medium_delete(request, pk):
    medium = get_object_or_404(SurvivalMedium, pk=pk)
    name = str(medium)
    medium.is_active = False
    medium.save(update_fields=["is_active"])
    messages.success(request, f"Medio {name} desactivado correctamente.")
    return redirect("supervivencia:medium_list")


class PyrotechnicCatalogListView(LoginRequiredMixin, ListView):
    model = PyrotechnicCatalogItem
    template_name = "supervivencia/catalog_list.html"
    context_object_name = "items"

    def get_queryset(self):
        queryset = PyrotechnicCatalogItem.objects.prefetch_related("life_rules").order_by("nomenclature")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(nomenclature__icontains=q)
                | Q(system__icontains=q)
                | Q(part_number__icontains=q)
                | Q(nsn__icontains=q)
                | Q(alternate_part_number__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        return context


class PyrotechnicCatalogCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = PyrotechnicCatalogItem
    form_class = PyrotechnicCatalogItemForm
    template_name = "supervivencia/catalog_form.html"
    success_url = reverse_lazy("supervivencia:catalog_list")
    success_message = "Elemento de pirotecnia cargado correctamente."

    def _get_life_rule_formset(self, instance=None):
        return PyrotechnicCatalogLifeRuleFormSet(
            self.request.POST or None,
            instance=instance,
            prefix="life_rules",
        )

    def form_valid(self, form):
        self.object = form.save(commit=False)
        life_rule_formset = self._get_life_rule_formset(self.object)
        if life_rule_formset.is_valid():
            with transaction.atomic():
                self.object.save()
                life_rule_formset.instance = self.object
                life_rule_formset.save()
            messages.success(self.request, self.success_message)
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form, life_rule_formset=life_rule_formset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nuevo elemento de pirotecnia"
        context.setdefault("life_rule_formset", self._get_life_rule_formset(self.object if hasattr(self, "object") else None))
        return context


class PyrotechnicCatalogUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = PyrotechnicCatalogItem
    form_class = PyrotechnicCatalogItemForm
    template_name = "supervivencia/catalog_form.html"
    success_url = reverse_lazy("supervivencia:catalog_list")
    success_message = "Elemento de pirotecnia actualizado correctamente."

    def _get_life_rule_formset(self, instance=None):
        return PyrotechnicCatalogLifeRuleFormSet(
            self.request.POST or None,
            instance=instance or self.object,
            prefix="life_rules",
        )

    def form_valid(self, form):
        self.object = form.save(commit=False)
        life_rule_formset = self._get_life_rule_formset(self.object)
        if life_rule_formset.is_valid():
            with transaction.atomic():
                self.object.save()
                life_rule_formset.instance = self.object
                life_rule_formset.save()
            messages.success(self.request, self.success_message)
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form, life_rule_formset=life_rule_formset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar elemento de pirotecnia"
        context.setdefault("life_rule_formset", self._get_life_rule_formset(self.object))
        return context


@login_required
@require_POST
def catalog_delete(request, pk):
    item = get_object_or_404(PyrotechnicCatalogItem, pk=pk)
    name = str(item)
    item.is_active = False
    item.save(update_fields=["is_active"])
    messages.success(request, f"Elemento {name} desactivado correctamente.")
    return redirect("supervivencia:catalog_list")


class PyrotechnicPhysicalItemListView(LoginRequiredMixin, ListView):
    model = PyrotechnicPhysicalItem
    template_name = "supervivencia/physical_item_list.html"
    context_object_name = "items"
    paginate_by = 30

    def get_queryset(self):
        queryset = PyrotechnicPhysicalItem.objects.select_related(
            "catalog_item", "created_by", "current_storage_location"
        ).order_by("expiration_date", "catalog_item__nomenclature", "serial_number", "lot_number")
        q = self.request.GET.get("q")
        condition = self.request.GET.get("condition")
        status = self.request.GET.get("status")
        expiration = self.request.GET.get("expiration")
        location = self.request.GET.get("location")
        today = timezone.localdate()
        next_6_months = today + timedelta(days=183)
        next_1_year = today + timedelta(days=365)
        next_2_years = today + timedelta(days=730)

        if q:
            queryset = queryset.filter(
                Q(catalog_item__nomenclature__icontains=q)
                | Q(catalog_item__system__icontains=q)
                | Q(serial_number__icontains=q)
                | Q(lot_number__icontains=q)
                | Q(manufacturer__icontains=q)
                | Q(current_location__icontains=q)
                | Q(current_storage_location__code__icontains=q)
                | Q(current_storage_location__name__icontains=q)
                | Q(certificate_reference__icontains=q)
            )
        if condition:
            queryset = queryset.filter(condition=condition)
        if status:
            queryset = queryset.filter(operational_status=status)
        if location:
            queryset = queryset.filter(current_storage_location_id=location)
        if expiration == "expired":
            queryset = queryset.filter(expiration_date__lte=today)
        elif expiration == "next_6_months":
            queryset = queryset.filter(expiration_date__gt=today, expiration_date__lte=next_6_months)
        elif expiration == "next_1_year":
            queryset = queryset.filter(expiration_date__gt=next_6_months, expiration_date__lte=next_1_year)
        elif expiration == "next_2_years":
            queryset = queryset.filter(expiration_date__gt=next_1_year, expiration_date__lte=next_2_years)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        next_6_months = today + timedelta(days=183)
        active_items = PyrotechnicPhysicalItem.objects.filter(is_active=True)
        context.update(
            {
                "search_query": self.request.GET.get("q", ""),
                "selected_condition": self.request.GET.get("condition", ""),
                "selected_status": self.request.GET.get("status", ""),
                "selected_expiration": self.request.GET.get("expiration", ""),
                "selected_location": self.request.GET.get("location", ""),
                "condition_choices": PyrotechnicPhysicalItem.CONDITION_CHOICES,
                "status_choices": PyrotechnicPhysicalItem.STATUS_CHOICES,
                "locations": PyrotechnicStorageLocation.objects.filter(is_active=True).order_by("code"),
                "total_active": active_items.count(),
                "expired_count": active_items.filter(expiration_date__lte=today).count(),
                "next_6_months_count": active_items.filter(
                    expiration_date__gt=today, expiration_date__lte=next_6_months
                ).count(),
            }
        )
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["pagination_query"] = query_params.urlencode()
        return context


class PyrotechnicPhysicalItemCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = PyrotechnicPhysicalItem
    form_class = PyrotechnicPhysicalItemForm
    template_name = "supervivencia/physical_item_form.html"
    success_url = reverse_lazy("supervivencia:physical_item_list")
    success_message = "Material fisico cargado correctamente."

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nuevo material fisico"
        context["catalog_count"] = PyrotechnicCatalogItem.objects.filter(is_active=True).count()
        return context


class PyrotechnicPhysicalItemDetailView(LoginRequiredMixin, DetailView):
    model = PyrotechnicPhysicalItem
    template_name = "supervivencia/physical_item_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return PyrotechnicPhysicalItem.objects.select_related(
            "catalog_item", "current_storage_location", "created_by"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        next_6_months = today + timedelta(days=183)

        if self.object.expiration_date <= today:
            expiration_state = "Vencido"
            expiration_class = "danger"
        elif self.object.expiration_date <= next_6_months:
            expiration_state = "Vence dentro de 6 meses"
            expiration_class = "warning"
        else:
            expiration_state = "Vigente"
            expiration_class = "success"

        assignments = (
            PyrotechnicAssignment.objects.filter(physical_item=self.object)
            .select_related("medium", "medium__unit")
            .order_by("-is_active", "-installed_at", "-removed_at")
        )
        active_assignment = next((assignment for assignment in assignments if assignment.is_active), None)
        movements = (
            PyrotechnicMovement.objects.filter(physical_item=self.object)
            .select_related("medium", "created_by")
            .order_by("-movement_date", "-created_at")
        )

        context.update(
            {
                "expiration_state": expiration_state,
                "expiration_class": expiration_class,
                "active_assignment": active_assignment,
                "assignments": assignments,
                "movements": movements,
            }
        )
        return context


class PyrotechnicPhysicalItemUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = PyrotechnicPhysicalItem
    form_class = PyrotechnicPhysicalItemForm
    template_name = "supervivencia/physical_item_form.html"
    success_url = reverse_lazy("supervivencia:physical_item_list")
    success_message = "Material fisico actualizado correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar material fisico"
        context["catalog_count"] = PyrotechnicCatalogItem.objects.filter(is_active=True).count()
        context["is_edit"] = True
        return context


class PyrotechnicPhysicalItemMovementView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = PyrotechnicPhysicalItem
    form_class = PyrotechnicPhysicalItemMovementForm
    template_name = "supervivencia/physical_item_movement_form.html"
    success_url = reverse_lazy("supervivencia:physical_item_list")
    success_message = "Movimiento registrado correctamente."

    def form_valid(self, form):
        previous = PyrotechnicPhysicalItem.objects.select_related("current_storage_location", "catalog_item").get(
            pk=form.instance.pk
        )
        previous_location = _item_location_reference(previous)
        previous_condition = previous.get_condition_display()
        previous_status = previous.get_operational_status_display()

        response = super().form_valid(form)
        item = form.instance
        new_location = _item_location_reference(item)
        location_changed = previous_location != new_location
        condition_changed = previous.condition != item.condition
        status_changed = previous.operational_status != item.operational_status

        active_assignment = (
            PyrotechnicAssignment.objects.filter(physical_item=item, is_active=True)
            .select_related("medium")
            .first()
        )
        movement_notes = form.cleaned_data.get("movement_notes")

        if location_changed:
            PyrotechnicMovement.objects.create(
                physical_item=item,
                medium=active_assignment.medium if active_assignment else None,
                assignment=active_assignment,
                movement_type="LOCATION_CHANGE",
                movement_date=timezone.localdate(),
                from_reference=previous_location,
                to_reference=new_location,
                notes=movement_notes or "Cambio de ubicacion registrado desde material.",
                created_by=self.request.user,
            )

        if condition_changed or status_changed:
            from_reference = f"{previous_condition} / {previous_status}"
            to_reference = f"{item.get_condition_display()} / {item.get_operational_status_display()}"
            PyrotechnicMovement.objects.create(
                physical_item=item,
                medium=active_assignment.medium if active_assignment else None,
                assignment=active_assignment,
                movement_type="STATUS_CHANGE",
                movement_date=timezone.localdate(),
                from_reference=from_reference,
                to_reference=to_reference,
                notes=movement_notes or "Cambio de estado registrado desde material.",
                created_by=self.request.user,
            )

        if not location_changed and not condition_changed and not status_changed:
            PyrotechnicMovement.objects.create(
                physical_item=item,
                medium=active_assignment.medium if active_assignment else None,
                assignment=active_assignment,
                movement_type="NOTE",
                movement_date=timezone.localdate(),
                from_reference=new_location,
                to_reference=new_location,
                notes=movement_notes or "Movimiento sin cambios de estado o ubicacion.",
                created_by=self.request.user,
            )

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Registrar movimiento de material"
        context["item"] = self.object
        return context


class PyrotechnicPhysicalItemForceDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "supervivencia/physical_item_force_delete.html"

    def dispatch(self, request, *args, **kwargs):
        forbidden = _superuser_required(request)
        if forbidden:
            return forbidden
        self.item = get_object_or_404(
            PyrotechnicPhysicalItem.objects.select_related("catalog_item", "current_storage_location"),
            pk=kwargs.get("pk"),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "item": self.item,
                "blockers": _physical_item_delete_blockers(self.item),
                "confirmation_text": "BORRAR MATERIAL",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        confirmation = request.POST.get("confirmation", "").strip().upper()
        if confirmation != "BORRAR MATERIAL":
            messages.error(request, "Debe escribir BORRAR MATERIAL para confirmar el borrado forzado.")
            return self.get(request, *args, **kwargs)

        object_repr, movement_count, assignment_count = _physical_item_force_delete(self.item, request.user)
        messages.success(
            request,
            (
                f"Material eliminado definitivamente: {object_repr}. "
                f"Tambien se eliminaron {movement_count} movimientos y {assignment_count} asignaciones."
            ),
        )
        return redirect("supervivencia:physical_item_list")


@login_required
@require_POST
def physical_item_delete(request, pk):
    item = get_object_or_404(PyrotechnicPhysicalItem, pk=pk)
    name = str(item)
    active_assignment = (
        PyrotechnicAssignment.objects.filter(physical_item=item, is_active=True)
        .select_related("medium")
        .first()
    )
    if active_assignment:
        active_assignment.is_active = False
        active_assignment.removed_at = timezone.localdate()
        active_assignment.save(update_fields=["is_active", "removed_at", "updated_at"])
        _create_pyrotechnic_movement(
            assignment=active_assignment,
            movement_type="REMOVED",
            movement_date=active_assignment.removed_at,
            user=request.user,
            from_reference=_assignment_destination(active_assignment),
            to_reference=_item_location_reference(item),
            notes="Asignacion retirada automaticamente por baja de material.",
        )
    item.is_active = False
    item.operational_status = "DISCARDED"
    item.condition = "BLOCKED"
    item.save(update_fields=["is_active", "operational_status", "condition", "updated_at"])
    PyrotechnicMovement.objects.create(
        physical_item=item,
        medium=active_assignment.medium if active_assignment else None,
        assignment=active_assignment,
        movement_type="DISCARDED",
        movement_date=timezone.localdate(),
        from_reference=_item_location_reference(item),
        to_reference="BAJA / INACTIVO",
        notes="Material desactivado desde el listado.",
        created_by=request.user,
    )
    messages.success(request, f"Material {name} desactivado correctamente.")
    return redirect("supervivencia:physical_item_list")


class PyrotechnicAssignmentListView(LoginRequiredMixin, ListView):
    model = PyrotechnicAssignment
    template_name = "supervivencia/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 30

    def get_queryset(self):
        queryset = PyrotechnicAssignment.objects.select_related(
            "medium", "medium__unit", "physical_item", "physical_item__catalog_item"
        ).order_by("medium__identifier", "-is_active", "physical_item__expiration_date")
        q = self.request.GET.get("q")
        medium = self.request.GET.get("medium")
        active = self.request.GET.get("active")

        if q:
            queryset = queryset.filter(
                Q(medium__identifier__icontains=q)
                | Q(medium__name__icontains=q)
                | Q(physical_item__catalog_item__nomenclature__icontains=q)
                | Q(physical_item__catalog_item__system__icontains=q)
                | Q(physical_item__serial_number__icontains=q)
                | Q(physical_item__lot_number__icontains=q)
                | Q(position__icontains=q)
            )
        if medium:
            queryset = queryset.filter(medium_id=medium)
        if active == "1":
            queryset = queryset.filter(is_active=True)
        elif active == "0":
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search_query": self.request.GET.get("q", ""),
                "selected_medium": self.request.GET.get("medium", ""),
                "selected_active": self.request.GET.get("active", ""),
                "mediums": SurvivalMedium.objects.filter(is_active=True).order_by("identifier"),
                "active_count": PyrotechnicAssignment.objects.filter(is_active=True).count(),
            }
        )
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["pagination_query"] = query_params.urlencode()
        return context


class PyrotechnicMovementListView(LoginRequiredMixin, ListView):
    model = PyrotechnicMovement
    template_name = "supervivencia/movement_list.html"
    context_object_name = "movements"
    paginate_by = 40

    def get_queryset(self):
        queryset = PyrotechnicMovement.objects.select_related(
            "physical_item",
            "physical_item__catalog_item",
            "medium",
            "created_by",
        ).order_by("-movement_date", "-created_at")
        q = self.request.GET.get("q")
        movement_type = self.request.GET.get("type")
        medium = self.request.GET.get("medium")

        if q:
            queryset = queryset.filter(
                Q(physical_item__catalog_item__nomenclature__icontains=q)
                | Q(physical_item__catalog_item__system__icontains=q)
                | Q(physical_item__serial_number__icontains=q)
                | Q(physical_item__lot_number__icontains=q)
                | Q(medium__identifier__icontains=q)
                | Q(medium__name__icontains=q)
                | Q(from_reference__icontains=q)
                | Q(to_reference__icontains=q)
                | Q(notes__icontains=q)
            )
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        if medium:
            queryset = queryset.filter(medium_id=medium)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search_query": self.request.GET.get("q", ""),
                "selected_type": self.request.GET.get("type", ""),
                "selected_medium": self.request.GET.get("medium", ""),
                "movement_type_choices": PyrotechnicMovement.MOVEMENT_TYPE_CHOICES,
                "mediums": SurvivalMedium.objects.filter(is_active=True).order_by("identifier"),
            }
        )
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["pagination_query"] = query_params.urlencode()
        return context


class PyrotechnicAssignmentCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = PyrotechnicAssignment
    form_class = PyrotechnicAssignmentForm
    template_name = "supervivencia/assignment_form.html"
    success_url = reverse_lazy("supervivencia:assignment_list")
    success_message = "Asignacion cargada correctamente."

    def form_valid(self, form):
        item = form.instance.physical_item
        mount_qty = form.cleaned_data.get("mount_quantity")
        previous_location = item.current_location

        if mount_qty and mount_qty < item.lot_quantity:
            original_qty = item.lot_quantity
            item.lot_quantity = original_qty - mount_qty
            item.save(update_fields=["lot_quantity", "updated_at"])

            clone = PyrotechnicPhysicalItem.objects.get(pk=item.pk)
            clone.pk = None
            clone.lot_quantity = mount_qty
            if form.instance.is_active:
                clone.operational_status = "INSTALLED"
            clone.save()

            form.instance.physical_item = clone
            form.instance.created_by = self.request.user
            response = super().form_valid(form)

            if form.instance.is_active:
                _create_pyrotechnic_movement(
                    assignment=form.instance,
                    movement_type="INSTALLED",
                    movement_date=form.instance.installed_at,
                    user=self.request.user,
                    from_reference=previous_location,
                    to_reference=_assignment_destination(form.instance),
                    notes=f"Asignacion parcial ({mount_qty} de {original_qty}).",
                )
        else:
            form.instance.created_by = self.request.user
            response = super().form_valid(form)
            if form.instance.is_active:
                item.operational_status = "INSTALLED"
                item.save(update_fields=["operational_status", "updated_at"])
                _create_pyrotechnic_movement(
                    assignment=form.instance,
                    movement_type="INSTALLED",
                    movement_date=form.instance.installed_at,
                    user=self.request.user,
                    from_reference=previous_location,
                    to_reference=_assignment_destination(form.instance),
                    notes="Asignacion cargada desde el modulo.",
                )
        return response

    def get_initial(self):
        initial = super().get_initial()
        medium_id = self.request.GET.get("medium")
        if medium_id:
            initial["medium"] = medium_id
        physical_item_id = self.request.GET.get("physical_item")
        if physical_item_id:
            initial["physical_item"] = physical_item_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nueva asignacion de pirotecnia"
        context["available_material_count"] = context["form"].fields["physical_item"].queryset.count()
        context["medium_count"] = context["form"].fields["medium"].queryset.count()
        context["is_edit"] = False
        return context


class PyrotechnicAssignmentUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = PyrotechnicAssignment
    form_class = PyrotechnicAssignmentForm
    template_name = "supervivencia/assignment_form.html"
    success_url = reverse_lazy("supervivencia:assignment_list")
    success_message = "Asignacion actualizada correctamente."

    def form_valid(self, form):
        previous = PyrotechnicAssignment.objects.get(pk=form.instance.pk)
        response = super().form_valid(form)
        item = form.instance.physical_item
        item.operational_status = "INSTALLED" if form.instance.is_active else "REMOVED"
        item.save(update_fields=["operational_status", "updated_at"])
        if previous.is_active and not form.instance.is_active:
            _create_pyrotechnic_movement(
                assignment=form.instance,
                movement_type="REMOVED",
                movement_date=form.instance.removed_at or timezone.localdate(),
                user=self.request.user,
                from_reference=_assignment_destination(form.instance),
                to_reference=item.current_location,
                notes="Asignacion marcada como retirada.",
            )
        elif not previous.is_active and form.instance.is_active:
            _create_pyrotechnic_movement(
                assignment=form.instance,
                movement_type="INSTALLED",
                movement_date=form.instance.installed_at,
                user=self.request.user,
                from_reference=item.current_location,
                to_reference=_assignment_destination(form.instance),
                notes="Asignacion reactivada.",
            )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar asignacion de pirotecnia"
        context["available_material_count"] = context["form"].fields["physical_item"].queryset.count()
        context["medium_count"] = context["form"].fields["medium"].queryset.count()
        context["is_edit"] = True
        return context


@login_required
@require_POST
def assignment_delete(request, pk):
    assignment = get_object_or_404(PyrotechnicAssignment, pk=pk)
    assignment.is_active = False
    assignment.removed_at = timezone.localdate()
    assignment.save(update_fields=["is_active", "removed_at", "updated_at"])
    item = assignment.physical_item
    item.operational_status = "REMOVED"
    item.save(update_fields=["operational_status", "updated_at"])
    _create_pyrotechnic_movement(
        assignment=assignment,
        movement_type="REMOVED",
        movement_date=assignment.removed_at,
        user=request.user,
        from_reference=_assignment_destination(assignment),
        to_reference=item.current_location,
        notes="Retiro realizado desde el listado.",
    )
    messages.success(request, "Asignacion retirada correctamente.")
    return redirect("supervivencia:assignment_list")


class PyrotechnicStorageLocationListView(LoginRequiredMixin, ListView):
    model = PyrotechnicStorageLocation
    template_name = "supervivencia/location_list.html"
    context_object_name = "locations"

    def get_queryset(self):
        queryset = PyrotechnicStorageLocation.objects.select_related("unit").order_by("code")
        q = self.request.GET.get("q")
        location_type = self.request.GET.get("type")
        if q:
            queryset = queryset.filter(
                Q(code__icontains=q)
                | Q(name__icontains=q)
                | Q(unit__name__icontains=q)
                | Q(notes__icontains=q)
            )
        if location_type:
            queryset = queryset.filter(name=location_type)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        context["selected_type"] = self.request.GET.get("type", "")
        context["location_choices"] = PyrotechnicStorageLocation.LOCATION_CHOICES
        return context


class PyrotechnicStorageLocationCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = PyrotechnicStorageLocation
    form_class = PyrotechnicStorageLocationForm
    template_name = "supervivencia/form.html"
    success_url = reverse_lazy("supervivencia:location_list")
    success_message = "Ubicacion cargada correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nueva ubicacion"
        return context


class PyrotechnicStorageLocationUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = PyrotechnicStorageLocation
    form_class = PyrotechnicStorageLocationForm
    template_name = "supervivencia/form.html"
    success_url = reverse_lazy("supervivencia:location_list")
    success_message = "Ubicacion actualizada correctamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Editar ubicacion"
        return context


@login_required
@require_POST
def location_delete(request, pk):
    location = get_object_or_404(PyrotechnicStorageLocation, pk=pk)
    name = str(location)
    location.is_active = False
    location.save(update_fields=["is_active"])
    messages.success(request, f"Ubicacion {name} desactivada correctamente.")
    return redirect("supervivencia:location_list")
