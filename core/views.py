from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView, View
from django.urls import reverse_lazy

from django.contrib import messages
from django.shortcuts import redirect, render
from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError

import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Unit, MeasurementUnit, AircraftModel, GreaseType, AircraftGrease, FlightPlan, GreaseBatch, StockMovement, GreaseReferencePrice, ProcurementRequirement
from .forms import UnitForm, MeasurementUnitForm, AircraftModelForm, GreaseTypeForm, AircraftGreaseForm, FlightPlanForm, GreaseBatchForm, ConsumeGreaseForm, GreaseReferencePriceForm, RetestBatchForm, ProcurementRequirementForm
from .services import update_batch_statuses, consume_grease
from django.db.models import ProtectedError

class ActiveUserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists() or user.unit is not None

class LogisticsRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        # RBAC: Requiere que el usuario pertenezca al grupo Administrador o Logistica,
        # o que sea superusuario.
        user = self.request.user
        if not user.is_authenticated:
            return False
        return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()

# Portal View
@login_required
def portal(request):
    return render(request, 'core/portal.html')

# Home View
def home(request):
    expiration_alerts = []
    stock_alerts = []
    critical_stock_alerts = []
    
    if request.user.is_authenticated:
        update_batch_statuses()
        
        user = request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
        user_unit_name = user.unit.name if getattr(user, 'unit', None) else None
        
        # Alertas de Vencimiento
        expiration_qs = GreaseBatch.objects.filter(
            status__in=['NEAR_EXPIRATION', 'EXPIRED'],
            available_quantity__gt=0
        )
        if not is_admin:
            if user_unit_name:
                expiration_qs = expiration_qs.filter(storage_location=user_unit_name)
            else:
                expiration_qs = expiration_qs.none()
            
        expiration_alerts = expiration_qs.order_by('expiration_date')
        
        # Alertas de Stock Mínimo (Previsión de Abastecimiento)
        grease_types = GreaseType.objects.all()
        forecast_dict = {}
        for gt in grease_types:
            batches_qs = gt.batches.filter(status__in=['SERVICEABLE', 'NEAR_EXPIRATION'])
            if not is_admin:
                if user_unit_name:
                    batches_qs = batches_qs.filter(storage_location=user_unit_name)
                else:
                    batches_qs = batches_qs.none() # User without a unit shouldn't see stock from anywhere unless admin
                
            total_available = sum(b.available_quantity for b in batches_qs)
            
            if gt.nomenclatura not in forecast_dict:
                forecast_dict[gt.nomenclatura] = {
                    'grease_type': gt,
                    'available': 0,
                    'minimum_stock': 0,
                    'plan_details_map': {}
                }
                
            forecast_dict[gt.nomenclatura]['available'] += total_available
            forecast_dict[gt.nomenclatura]['minimum_stock'] += gt.minimum_stock
            
            for assoc in gt.aircraft_associations.all():
                if not is_admin:
                    if user_unit_name and assoc.aircraft_model.unit.name == user_unit_name:
                        pass
                    else:
                        continue
                        
                for plan in assoc.aircraft_model.flight_plans.all():
                    proj = assoc.hourly_consumption_rate * plan.planned_hours
                    forecast_dict[gt.nomenclatura]['plan_details_map'][(assoc.aircraft_model.id, plan.id)] = proj
                    
        for nom, data in forecast_dict.items():
            total_projected = sum(data['plan_details_map'].values())
            
            # Solo mostrar alerta si el usuario (o admin) al menos está proyectando un consumo o tiene stock de esta grasa
            if not is_admin and user_unit_name:
                has_involvement = total_projected > 0 or data['available'] > 0
                if not has_involvement:
                    continue
                    
            if total_projected > data['available']:
                active_req = ProcurementRequirement.objects.filter(
                    grease_type__nomenclatura=nom,
                    status__in=['PENDING', 'ORDERED']
                ).first()
                stock_alerts.append({
                    'grease_type': data['grease_type'],
                    'shortfall': total_projected - data['available'],
                    'available': data['available'],
                    'projected': total_projected,
                    'active_requirement': active_req,
                })
                
            # Alertas de Stock Crítico (por debajo del Stock Mínimo)
            if data['available'] < data['minimum_stock']:
                active_req_critical = ProcurementRequirement.objects.filter(
                    grease_type__nomenclatura=nom,
                    status__in=['PENDING', 'ORDERED']
                ).first()
                critical_stock_alerts.append({
                    'grease_type': data['grease_type'],
                    'available': data['available'],
                    'minimum_stock': data['minimum_stock'],
                    'shortfall': data['minimum_stock'] - data['available'],
                    'active_requirement': active_req_critical,
                })
                
    return render(request, 'core/home.html', {
        'alerts': expiration_alerts,
        'stock_alerts': stock_alerts,
        'critical_stock_alerts': critical_stock_alerts
    })

# --- Units ---
class UnitListView(LoginRequiredMixin, ListView):
    model = Unit
    template_name = 'core/unit_list.html'
    context_object_name = 'units'

class UnitCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = Unit
    form_class = UnitForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('unit_list')
    success_message = "Unidad creada exitosamente."
    extra_context = {'title': 'Crear Unidad'}

class UnitUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Unit
    form_class = UnitForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('unit_list')
    success_message = "Unidad actualizada exitosamente."
    extra_context = {'title': 'Editar Unidad'}

class UnitDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Unit
    template_name = 'core/unit_confirm_delete.html'
    success_url = reverse_lazy('unit_list')
    success_message = "Unidad eliminada exitosamente."

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

# --- Measurement Units (Configuration) ---
class MeasurementUnitListView(LogisticsRequiredMixin, ListView):
    model = MeasurementUnit
    template_name = 'core/measurementunit_list.html'
    context_object_name = 'units'

class MeasurementUnitCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = MeasurementUnit
    form_class = MeasurementUnitForm
    template_name = 'core/measurementunit_form.html'
    success_url = reverse_lazy('measurementunit_list')
    success_message = "Unidad de medida creada exitosamente."

class MeasurementUnitUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = MeasurementUnit
    form_class = MeasurementUnitForm
    template_name = 'core/measurementunit_form.html'
    success_url = reverse_lazy('measurementunit_list')
    success_message = "Unidad de medida actualizada exitosamente."

class MeasurementUnitDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = MeasurementUnit
    template_name = 'core/measurementunit_confirm_delete.html'
    success_url = reverse_lazy('measurementunit_list')
    success_message = "Unidad de medida eliminada exitosamente."

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

# --- Aircraft Models ---
class AircraftListView(LoginRequiredMixin, ListView):
    model = AircraftModel
    template_name = 'core/aircraft_list.html'
    context_object_name = 'aircrafts'

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        
        # Admin y Logística ven todo
        if user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists():
            return qs
            
        # Usuarios con unidad ven solo sus modelos
        if getattr(user, 'unit', None):
            return qs.filter(unit=user.unit)
            
        # Sin unidad y sin privilegios no ve nada
        return qs.none()

class AircraftCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = AircraftModel
    form_class = AircraftModelForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('aircraft_list')
    success_message = "Aeronave creada exitosamente."
    extra_context = {'title': 'Crear Modelo de Aeronave'}

class AircraftUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = AircraftModel
    form_class = AircraftModelForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('aircraft_list')
    success_message = "Aeronave actualizada exitosamente."
    extra_context = {'title': 'Editar Modelo de Aeronave'}

class AircraftDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = AircraftModel
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('aircraft_list')
    success_message = "Aeronave eliminada exitosamente."

# --- Grease Types ---
class GreaseTypeListView(LoginRequiredMixin, ListView):
    model = GreaseType
    template_name = 'core/grease_list.html'
    context_object_name = 'greases'

class GreaseTypeCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = GreaseType
    form_class = GreaseTypeForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('grease_list')
    success_message = "Tipo de Grasa creado exitosamente."
    extra_context = {'title': 'Crear Tipo de Grasa'}

class GreaseTypeUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = GreaseType
    form_class = GreaseTypeForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('grease_list')
    success_message = "Tipo de Grasa actualizado exitosamente."
    extra_context = {'title': 'Editar Tipo de Grasa'}

class GreaseTypeDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = GreaseType
    template_name = 'core/grease_confirm_delete.html'
    success_url = reverse_lazy('grease_list')
    success_message = "Tipo de Grasa eliminado exitosamente."

    @transaction.atomic
    def form_valid(self, form):
        # Forced deletion logic:
        # 1. Catch all batches (active and archived)
        batches = self.object.batches.all()
        # 2. Bulk delete stock movements for these batches to bypass ProtectedError
        from .models import StockMovement
        StockMovement.objects.filter(batch__in=batches).delete()
        
        # Now we can safely delete the object (batches will cascade delete)
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_batches_count'] = self.object.batches.filter(is_archived=False).count()
        context['archived_batches_count'] = self.object.batches.filter(is_archived=True).count()
        return context

# --- Grease Reference Prices ---
class GreaseReferencePriceListView(LoginRequiredMixin, ListView):
    model = GreaseReferencePrice
    template_name = 'core/greasereferenceprice_list.html'
    context_object_name = 'prices'

    def get_queryset(self):
        return GreaseReferencePrice.objects.filter(grease_type_id=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grease_type'] = GreaseType.objects.get(pk=self.kwargs['pk'])
        return context

class GreaseReferencePriceCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = GreaseReferencePrice
    form_class = GreaseReferencePriceForm
    template_name = 'core/form_base.html'
    success_message = "Cotización / Precio de Referencia agregado exitosamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gt = GreaseType.objects.get(pk=self.kwargs['pk'])
        context['title'] = f'Agregar Precio de Referencia - {gt.nomenclatura}'
        return context
        
    def get_initial(self):
        initial = super().get_initial()
        return initial

    def form_valid(self, form):
        form.instance.grease_type_id = self.kwargs['pk']
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('grease_price_list', kwargs={'pk': self.kwargs['pk']})

class GreaseReferencePriceUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = GreaseReferencePrice
    form_class = GreaseReferencePriceForm
    template_name = 'core/form_base.html'
    success_message = "Cotización / Precio de Referencia actualizado exitosamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gt = self.object.grease_type
        context['title'] = f'Editar Precio de Referencia - {gt.nomenclatura}'
        return context

    def get_success_url(self):
        return reverse_lazy('grease_price_list', kwargs={'pk': self.object.grease_type_id})

class GreaseReferencePriceDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = GreaseReferencePrice
    template_name = 'core/confirm_delete.html'
    success_message = "Precio de Referencia eliminado exitosamente."

    def get_success_url(self):
        return reverse_lazy('grease_price_list', kwargs={'pk': self.object.grease_type_id})

# --- Aircraft - Grease Associations ---
class AircraftGreaseListView(LoginRequiredMixin, ListView):
    model = AircraftGrease
    template_name = 'core/aircraftgrease_list.html'
    context_object_name = 'associations'

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        
        # Admin y Logística ven todo
        if user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists():
            return qs
            
        # Usuarios con unidad ven solo lo de su aeronave
        if getattr(user, 'unit', None):
            return qs.filter(aircraft_model__unit=user.unit)
            
        # Sin unidad y sin privilegios no ve nada
        return qs.none()

class AircraftGreaseCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = AircraftGrease
    form_class = AircraftGreaseForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('association_list')
    success_message = "Asociación creada exitosamente."
    extra_context = {'title': 'Vincular Aeronave con Grasa'}

class AircraftGreaseUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = AircraftGrease
    form_class = AircraftGreaseForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('association_list')
    success_message = "Asociación actualizada exitosamente."
    extra_context = {'title': 'Editar Asociación Aeronave-Grasa'}

class AircraftGreaseDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = AircraftGrease
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('association_list')
    success_message = "Asociación eliminada exitosamente."

# --- Flight Plans ---
class FlightPlanListView(LoginRequiredMixin, ListView):
    model = FlightPlan
    template_name = 'core/flightplan_list.html'
    context_object_name = 'flight_plans'
    ordering = ['-period_start_date']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        
        # Admin y Logística ven todo
        if user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists():
            return qs
            
        # Usuarios con unidad ven solo sus planes
        if getattr(user, 'unit', None):
            return qs.filter(aircraft_model__unit=user.unit)
            
        # Sin unidad y sin privilegios no ve nada
        return qs.none()

class FlightPlanCreateView(LogisticsRequiredMixin, SuccessMessageMixin, CreateView):
    model = FlightPlan
    form_class = FlightPlanForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('flightplan_list')
    success_message = "Plan de empleo creado exitosamente."
    extra_context = {'title': 'Crear Plan de Empleo'}

class FlightPlanUpdateView(LogisticsRequiredMixin, SuccessMessageMixin, UpdateView):
    model = FlightPlan
    form_class = FlightPlanForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('flightplan_list')
    success_message = "Plan de empleo actualizado exitosamente."
    extra_context = {'title': 'Editar Plan de Empleo'}

class FlightPlanDeleteView(LogisticsRequiredMixin, SuccessMessageMixin, DeleteView):
    model = FlightPlan
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('flightplan_list')
    success_message = "Plan de empleo eliminado exitosamente."

# --- Stock Management & Batches ---
class GreaseBatchListView(LoginRequiredMixin, ListView):
    model = GreaseBatch
    template_name = 'core/greasebatch_list.html'
    context_object_name = 'batches'
    ordering = ['expiration_date']
    
    def get_queryset(self):
        # Primero actualizamos los estados antes de mostrar
        update_batch_statuses()
        qs = super().get_queryset().active()
        
        user = self.request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
        
        if not is_admin and getattr(user, 'unit', None):
            # Particular user: ONLY see their unit
            return qs.filter(storage_location=user.unit.name).order_by('expiration_date')
            
        if user.is_authenticated and getattr(user, 'unit', None):
            # Admin with a unit (optional sorting preference)
            from django.db.models import Case, When, Value, IntegerField
            qs = qs.annotate(
                is_own_unit=Case(
                    When(storage_location=user.unit.name, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).order_by('is_own_unit', 'expiration_date')
            return qs
            
        return qs.order_by('expiration_date')

class ArchivedBatchListView(LoginRequiredMixin, ListView):
    model = GreaseBatch
    template_name = 'core/greasebatch_archived_list.html'
    context_object_name = 'batches'
    
    def get_queryset(self):
        qs = super().get_queryset().archived()
        user = self.request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()

        if not is_admin and getattr(user, 'unit', None):
            # Particular user: ONLY see their unit
            return qs.filter(storage_location=user.unit.name).order_by('-manufacturing_date')

        if user.is_authenticated and getattr(user, 'unit', None):
            from django.db.models import Case, When, Value, IntegerField
            qs = qs.annotate(
                is_own_unit=Case(
                    When(storage_location=user.unit.name, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).order_by('is_own_unit', '-manufacturing_date')
            return qs
            
        return qs.order_by('-manufacturing_date')

class ArchiveBatchView(ActiveUserRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        batch = get_object_or_404(GreaseBatch, pk=pk)
        
        # Verify permissions
        user = request.user
        if not (user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
            if user.unit and batch.storage_location != user.unit.name:
                messages.error(request, "No tienes permiso para modificar lotes que no pertenecen a tu unidad.")
                return redirect('batch_list')
        
        if batch.available_quantity > 0:
            messages.error(request, "No se puede archivar un lote que todavía tiene stock disponible.")
            return redirect('batch_list')
            
        batch.is_archived = True
        batch.save()
        messages.success(request, f"El lote {batch.batch_number} fue archivado exitosamente y movido al historial.")
        return redirect('batch_list')

class GreaseBatchDetailView(LoginRequiredMixin, ListView):
    # Usado para ver los movimientos de un lote específico
    model = StockMovement
    template_name = 'core/greasebatch_detail.html'
    context_object_name = 'movements'
    
    def get_queryset(self):
        return StockMovement.objects.filter(batch_id=self.kwargs['pk']).order_by('-movement_date')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = GreaseBatch.objects.get(pk=self.kwargs['pk'])
        return context

class GreaseBatchCreateView(ActiveUserRequiredMixin, SuccessMessageMixin, CreateView):
    model = GreaseBatch
    form_class = GreaseBatchForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('batch_list')
    extra_context = {'title': 'Registrar Ingreso de Casamata'}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        # Set available quantity initially to the incoming amount
        # initial_quantity may have been auto-calculated by the form's clean() method
        final_qty = form.cleaned_data.get('initial_quantity') or form.instance.initial_quantity
        form.instance.initial_quantity = final_qty
        form.instance.available_quantity = final_qty
        response = super().form_valid(form)
        
        # Generar movimiento de auditoría (INCOMING) indescifrable / no borrable
        StockMovement.objects.create(
            batch=self.object,
            movement_type='INCOMING',
            quantity_changed=self.object.initial_quantity,
            user=self.request.user,
            reason="Ingreso inicial al sistema"
        )
        return response

class GreaseBatchUpdateView(ActiveUserRequiredMixin, SuccessMessageMixin, UpdateView):
    model = GreaseBatch
    form_class = GreaseBatchForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('batch_list')
    success_message = "Lote actualizado exitosamente."
    extra_context = {'title': 'Editar Lote / Casamata'}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        update_batch_statuses()
        return response

class ConsumeGreaseView(ActiveUserRequiredMixin, FormView):
    template_name = 'core/form_base.html'
    form_class = ConsumeGreaseForm
    success_url = reverse_lazy('batch_list')
    extra_context = {'title': 'Registrar Consumo de Grasa'}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        grease_type = form.cleaned_data['grease_type']
        quantity = form.cleaned_data['quantity']
        reference = form.cleaned_data['reference']
        reason = form.cleaned_data['reason']
        
        user = self.request.user
        location = None
        
        # Si el usuario no es staff/admin/logística, pero tiene una unidad, forzamos esa ubicación
        if not (user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
            if user.unit:
                location = user.unit.name
        
        try:
            update_batch_statuses() # Always good to ensure accurate expiration states before consuming
            consume_grease(
                grease_type=grease_type,
                quantity_to_consume=quantity,
                user=user,
                reference=reference,
                reason=reason,
                location=location
            )
            messages.success(self.request, f"Se consumieron {quantity} kg/uds de '{grease_type.nomenclatura}' exitosamente.")
            return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

class GreaseBatchDeleteView(LogisticsRequiredMixin, DeleteView):
    model = GreaseBatch
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('batch_list')
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Eliminar los movimientos asociados usando filter().delete()
        # Esto hace un "bulk delete" a nivel de base de datos y esquiva la validación
        # personalizada del modelo StockMovement que impide el borrado normal.
        StockMovement.objects.filter(batch=self.object).delete()
        
        messages.success(request, f"El lote {self.object.batch_number} fue eliminado exitosamente.")
        return super().post(request, *args, **kwargs)

class StartRetestView(ActiveUserRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        batch = get_object_or_404(GreaseBatch, pk=pk)
        
        # Verificar permisos de unidad
        user = request.user
        if not (user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
            if user.unit and batch.storage_location != user.unit.name:
                messages.error(request, "No tienes permiso para modificar lotes que no pertenecen a tu unidad.")
                return redirect('batch_detail', pk=batch.pk)
        
        if batch.status not in ['EXPIRED', 'NEAR_EXPIRATION']:
            messages.error(request, "Solo se pueden enviar a retesteo lotes vencidos o próximos a vencer.")
            return redirect('batch_detail', pk=batch.pk)
            
        if not batch.can_be_retested:
            messages.error(request, "Este lote no admite retesteo.")
            return redirect('batch_detail', pk=batch.pk)
            
        with transaction.atomic():
            matching_batches = GreaseBatch.objects.filter(
                batch_number=batch.batch_number,
                grease_type=batch.grease_type,
                status__in=['EXPIRED', 'NEAR_EXPIRATION']
            )
            
            for matched_batch in matching_batches:
                matched_batch.status = 'PENDING_RETEST'
                matched_batch.save()
                
                # Registrar el movimiento de que fue enviado a retesteo
                StockMovement.objects.create(
                    batch=matched_batch,
                    movement_type='RETEST',
                    quantity_changed=0,
                    user=request.user,
                    reason="Casamata enviada a laboratorio para retesteo. Estado en espera de resultados."
                )
            
        messages.success(request, f"El lote {batch.batch_number} fue marcado como 'Retesteando...'")
        return redirect('batch_detail', pk=batch.pk)

class RetestBatchView(ActiveUserRequiredMixin, UpdateView):
    model = GreaseBatch
    form_class = RetestBatchForm
    template_name = 'core/form_base.html'
    
    def dispatch(self, request, *args, **kwargs):
        batch = self.get_object()
        user = request.user
        if not (user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
            if user.unit and batch.storage_location != user.unit.name:
                messages.error(request, "No tienes permiso para modificar lotes que no pertenecen a tu unidad.")
                return redirect('batch_detail', pk=batch.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('batch_detail', kwargs={'pk': self.object.pk})
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Retestear Lote {self.object.batch_number} - {self.object.grease_type.nomenclatura}'
        return context

    def form_valid(self, form):
        from .services import process_retest_batch, update_batch_statuses
        from django.http import HttpResponseRedirect
        
        old_quantity = form.initial.get('available_quantity', 0)
        
        # Delegamos toda la lógica y transacciones a la capa "Servicios"
        process_retest_batch(
            batch=self.object, 
            user=self.request.user, 
            form_cleaned_data=form.cleaned_data, 
            old_quantity=old_quantity
        )
        
        # Actualizamos estados dependientes de lote
        update_batch_statuses()
        
        messages.success(self.request, "Retesteo registrado y lote actualizado exitosamente.")
        return HttpResponseRedirect(self.get_success_url())

# --- Procurement Forecasting ---
class ProcurementForecastingView(LoginRequiredMixin, TemplateView):
    template_name = 'core/procurement_forecast.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .services import get_procurement_forecast
        from .services import update_batch_statuses
        
        user = self.request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
        location = user.unit.name if (not is_admin and getattr(user, 'unit', None)) else None

        update_batch_statuses()
        forecast_data = get_procurement_forecast(location=location)
        context['forecast_data'] = forecast_data
        
        return context

# --- Flight Hours Calculator ---
class FlightHoursCalculatorView(LoginRequiredMixin, TemplateView):
    template_name = 'core/flight_hours_calculator.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
        
        aircraft_qs = AircraftModel.objects.all().order_by('name')
        if not is_admin and getattr(user, 'unit', None):
            aircraft_qs = aircraft_qs.filter(unit=user.unit)
        
        context['aircrafts'] = aircraft_qs
        # SQLite-compatible: get one GreaseType per unique nomenclatura
        from django.db.models import Min
        unique_ids = GreaseType.objects.values('nomenclatura').annotate(min_id=Min('id')).values_list('min_id', flat=True)
        context['grease_types'] = GreaseType.objects.filter(pk__in=unique_ids).order_by('nomenclatura')
        return context

    def post(self, request, *args, **kwargs):
        from .services import calculate_flight_hours_projection
        
        user = request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
        location = user.unit.name if (not is_admin and getattr(user, 'unit', None)) else None

        selected_aircraft_ids = request.POST.getlist('aircraft_ids')
        selected_grease_ids = request.POST.getlist('grease_ids')

        # Modelos bases necesarios para re-renderizar los selectores del form
        all_aircrafts = AircraftModel.objects.all().order_by('name')
        if not is_admin and getattr(user, 'unit', None):
            all_aircrafts = all_aircrafts.filter(unit=user.unit)

        from django.db.models import Min
        unique_ids = GreaseType.objects.values('nomenclatura').annotate(min_id=Min('id')).values_list('min_id', flat=True)
        all_grease_types = GreaseType.objects.filter(pk__in=unique_ids).order_by('nomenclatura')

        # Delegamos la lógica masiva de cálculo matemático al Servicio
        calc_results = calculate_flight_hours_projection(
            selected_aircraft_ids=selected_aircraft_ids,
            selected_grease_ids=selected_grease_ids,
            location=location
        )

        return render(request, self.template_name, {
            'aircrafts': all_aircrafts,
            'grease_types': all_grease_types,
            'selected_aircraft_ids': [int(i) for i in selected_aircraft_ids] if selected_aircraft_ids else [],
            'selected_grease_ids': [int(i) for i in selected_grease_ids] if selected_grease_ids else [],
            'breakdown': calc_results['breakdown'],
            'max_hours': calc_results['max_hours'],
            'bottleneck': calc_results['bottleneck'],
            'no_consumption': calc_results['no_consumption'],
            'calculated': True,
        })

# --- CSV Exports ---
@login_required
def export_grease_batches_csv(request):
    update_batch_statuses()
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="stock_casamatas.csv"'
    
    # Add BOM for UTF-8 so Excel recognizes special characters correctly
    response.write('\ufeff')
    writer = csv.writer(response, dialect='excel', delimiter=';')
    writer.writerow(['Tipo de Grasa', 'Casamata', 'Vencimiento', 'Estado', 'Ubicación', 'Cantidad Inicial', 'Cantidad Disponible'])
    
    batches = GreaseBatch.objects.all().order_by('expiration_date')
    if not is_admin and getattr(user, 'unit', None):
        batches = batches.filter(storage_location=user.unit.name)
        
    for b in batches:
        writer.writerow([
            b.grease_type.nomenclatura,
            b.batch_number,
            b.expiration_date.strftime('%Y-%m-%d'),
            b.get_status_display(),
            b.storage_location,
            b.initial_quantity,
            b.available_quantity
        ])
    return response

@login_required
def export_procurement_forecast_csv(request):
    update_batch_statuses()
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    location = user.unit.name if (not is_admin and getattr(user, 'unit', None)) else None

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="pronostico_abastecimiento.csv"'
    
    # Add BOM for UTF-8
    response.write('\ufeff')
    writer = csv.writer(response, dialect='excel', delimiter=';')
    writer.writerow(['Tipo de Grasa', 'Stock Disponible', 'Consumo Proyectado', 'Diferencia (Sobrante/Faltante)', 'Compra Recomendada'])
    
    from .services import get_procurement_forecast
    forecast_data = get_procurement_forecast(location=location)
    
    for row in forecast_data:
        recommended_purchase = row['shortfall'] if row['shortfall'] > 0 else 0
        
        writer.writerow([
            row['grease_type'].nomenclatura,
            row['total_available'],
            row['total_projected'],
            row['shortfall'],
            recommended_purchase
        ])
    return response

# --- PDF Exports ---
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

@login_required
def export_grease_batches_pdf(request):
    update_batch_statuses()
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title = "Reporte de Stock de Casamatas"
    if not is_admin and getattr(user, 'unit', None):
        title += f" - Unidad: {user.unit.name}"
        
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 12))
    
    data = [['Tipo de Grasa', 'Casamata', 'Vencimiento', 'Estado', 'Ubicación', 'Inicial', 'Disponible']]
    batches = GreaseBatch.objects.all().order_by('expiration_date')
    if not is_admin and getattr(user, 'unit', None):
        batches = batches.filter(storage_location=user.unit.name)

    for b in batches:
        data.append([
            b.grease_type.nomenclatura,
            b.batch_number,
            b.expiration_date.strftime('%d/%m/%Y'),
            b.get_status_display(),
            b.storage_location,
            str(b.initial_quantity),
            str(b.available_quantity)
        ])
    
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="stock_casamatas.pdf"'
    return response

@login_required
def export_procurement_forecast_pdf(request):
    update_batch_statuses()
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    location = user.unit.name if (not is_admin and getattr(user, 'unit', None)) else None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title = "Reporte de Pronóstico de Abastecimiento"
    if location:
        title += f" - Unidad: {location}"
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 12))
    
    data = [['Tipo de Grasa', 'Stock\nDisponible', 'Consumo\nProyectado', 'Diferencia\n(Sobrante/Faltante)', 'Recomendación\nde Compra']]
    
    from .services import get_procurement_forecast
    forecast_data = get_procurement_forecast(location=location)
                
    for row in forecast_data:
        total_projected = row['total_projected']
        shortfall = row['shortfall']
        recommended_purchase = shortfall if shortfall > 0 else 0
        
        data.append([
            row['grease_type'].nomenclatura,
            str(round(row['total_available'], 2)),
            str(round(total_projected, 2)),
            str(round(shortfall, 2)),
            str(round(recommended_purchase, 2))
        ])
    
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#198754')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="pronostico_abastecimiento.pdf"'
    return response

# --- Procurement Requirements ---
class ProcurementRequirementListView(ActiveUserRequiredMixin, ListView):
    model = ProcurementRequirement
    template_name = 'core/procurementrequirement_list.html'
    context_object_name = 'requirements'
    
    def get_queryset(self):
        qs = super().get_queryset().order_by('-request_date')
        user = self.request.user
        is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
        
        if not is_admin and getattr(user, 'unit', None):
            return qs.filter(requested_by__unit=user.unit)
        return qs
    
class CreateRequirementFromForecastView(ActiveUserRequiredMixin, View):
    def post(self, request, grease_type_id, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        gt = get_object_or_404(GreaseType, pk=grease_type_id)
        quantity = request.POST.get('requested_quantity', 0)
        
        # Check if already exists an active req
        active_req = ProcurementRequirement.objects.filter(grease_type=gt, status__in=['PENDING', 'ORDERED']).exists()
        if active_req:
            messages.warning(request, f"Ya existe un requerimiento activo para {gt.nomenclatura}.")
        else:
            ProcurementRequirement.objects.create(
                grease_type=gt,
                requested_quantity=quantity,
                requested_by=request.user,
                status='PENDING'
            )
            messages.success(request, f"Requerimiento de compra iniciado para {gt.nomenclatura}.")
            
        return redirect('procurement_forecast')

class ProcurementRequirementUpdateView(ActiveUserRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ProcurementRequirement
    form_class = ProcurementRequirementForm
    template_name = 'core/form_base.html'
    success_url = reverse_lazy('requirement_list')
    success_message = "Requerimiento actualizado exitosamente."
    extra_context = {'title': 'Editar Requerimiento de Adquisición'}

class ProcurementRequirementDeleteView(ActiveUserRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        req = get_object_or_404(ProcurementRequirement, pk=pk)
        grease_name = req.grease_type.nomenclatura
        req.delete()
        messages.success(request, f"Requerimiento #{pk} de {grease_name} eliminado exitosamente.")
        return redirect('requirement_list')

@login_required
def export_requirements_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="requerimientos_compra.csv"'

    # BOM para que Excel reconozca correctamente los caracteres especiales
    response.write('\ufeff')
    writer = csv.writer(response, dialect='excel', delimiter=';')
    writer.writerow(['ID Req.', 'Fecha de Solicitud', 'Grasa (Nomenclatura)', 'Unidad', 'Cantidad Solicitada', 'Estado', 'Solicitado Por', 'Notas'])

    STATUS_LABELS = {
        'PENDING': 'Pendiente',
        'ORDERED': 'En Compra',
        'DELIVERED': 'Completado',
        'CANCELLED': 'Cancelado',
    }

    requirements = ProcurementRequirement.objects.all().order_by('-request_date')
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
    
    if not is_admin and getattr(user, 'unit', None):
        requirements = requirements.filter(requested_by__unit=user.unit)

    for req in requirements:
        writer.writerow([
            f'#{req.id}',
            req.request_date.strftime('%d/%m/%Y %H:%M'),
            req.grease_type.nomenclatura,
            str(req.grease_type.unidad) if req.grease_type.unidad else '',
            req.requested_quantity,
            STATUS_LABELS.get(req.status, req.status),
            req.requested_by.username if req.requested_by else '-',
            getattr(req, 'notes', '') or '',
        ])
    return response
