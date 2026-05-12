from django import forms
from .models import Unit, MeasurementUnit, AircraftModel, GreaseType, AircraftGrease, FlightPlan, GreaseBatch, GreaseReferencePrice, ProcurementRequirement

class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'description']

class MeasurementUnitForm(forms.ModelForm):
    class Meta:
        model = MeasurementUnit
        fields = ['name']

class AircraftModelForm(forms.ModelForm):
    class Meta:
        model = AircraftModel
        fields = ['name', 'unit', 'total_aircraft', 'is_active']

class GreaseTypeForm(forms.ModelForm):
    class Meta:
        model = GreaseType
        fields = ['nomenclatura', 'unidad', 'nne_nsn', 'sibys', 'nato', 'normas_mil_otras', 'shelf_life_months', 'recertification_allowed', 'minimum_stock']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the unidad field with a dropdown from MeasurementUnit
        unit_choices = [(u.name, u.name) for u in MeasurementUnit.objects.all()]
        
        # If there's an instance (editing), ensure its current value is in the choices
        if self.instance and self.instance.pk and self.instance.unidad:
            current_unit = self.instance.unidad
            if not any(current_unit == choice[0] for choice in unit_choices):
                unit_choices.insert(0, (current_unit, f"{current_unit} (Actual)"))
        
        unit_choices.insert(0, ('', 'Seleccione una Unidad...'))
        
        self.fields['unidad'] = forms.ChoiceField(
            choices=unit_choices,
            label="UNIDAD",
            required=True
        )

class AircraftGreaseForm(forms.ModelForm):
    class Meta:
        model = AircraftGrease
        fields = ['aircraft_model', 'grease_type', 'hourly_consumption_rate', 'notes']
        widgets = {
            'hourly_consumption_rate': forms.NumberInput(attrs={'step': '0.001'}),
        }
                
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Deduplicate greases by nomenclatura for the dropdown
        # We find the first ID for each unique nomenclatura to represent the "type".
        unique_greases = {}
        for gt in GreaseType.objects.all():
            if gt.nomenclatura not in unique_greases:
                unique_greases[gt.nomenclatura] = gt.id
        
        # In case we're editing, we must ensure the currently selected grease is in the choices
        if self.instance and self.instance.pk and self.instance.grease_type:
            current_gt = self.instance.grease_type
            if current_gt.nomenclatura in unique_greases:
                # Override the representative ID with the one actually saved
                unique_greases[current_gt.nomenclatura] = current_gt.id
                
        allowed_ids = list(unique_greases.values())
        
        self.fields['grease_type'].queryset = GreaseType.objects.filter(id__in=allowed_ids).order_by('nomenclatura')
        
        # Adjust the label function slightly to not show presentation if we want it completely clean
        self.fields['grease_type'].label_from_instance = lambda obj: obj.nomenclatura

class FlightPlanForm(forms.ModelForm):
    class Meta:
        model = FlightPlan
        fields = ['aircraft_model', 'period_type', 'period_start_date', 'period_end_date', 'planned_hours']
        widgets = {
            'period_start_date': forms.DateInput(attrs={'type': 'date'}),
            'period_end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        period_type = cleaned_data.get('period_type')
        start_date = cleaned_data.get('period_start_date')
        end_date = cleaned_data.get('period_end_date')
        
        if period_type == 'CUSTOM' and not end_date:
            self.add_error('period_end_date', 'Debe especificar la fecha de finalización para un período Libre.')
            
        if start_date and end_date and start_date > end_date:
            self.add_error('period_end_date', 'La fecha de finalización debe ser posterior a la de inicio.')
            
        return cleaned_data

class GreaseBatchForm(forms.ModelForm):
    total_price = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        label="Costo Total Pagado ($)",
        help_text="Costo total abonado por la cantidad ingresada de este lote."
    )

    class Meta:
        model = GreaseBatch
        fields = ['grease_type', 'batch_number', 'manufacturing_date', 'expiration_date', 'container_size', 'container_count', 'initial_quantity', 'storage_location']
        widgets = {
            'manufacturing_date': forms.DateInput(attrs={'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make initial_quantity not required since it can be auto-calculated
        self.fields['initial_quantity'].required = False
        self.fields['initial_quantity'].help_text = "Se calcula automáticamente si ingresa cantidad por envase y cantidad de envases. O ingrese manualmente."
        
        # Populate choices dynamically from Unit models
        unit_choices = [(unit.name, unit.name) for unit in Unit.objects.all()]
        
        # Filter choices if the user is a unit user
        if user and not (user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
            if user.unit:
                unit_choices = [(user.unit.name, user.unit.name)]
        
        # If there's an instance (editing), ensure its current value is in the choices
        if self.instance and self.instance.pk and self.instance.storage_location:
            current_loc = self.instance.storage_location
            if not any(current_loc == choice[0] for choice in unit_choices):
                unit_choices.insert(0, (current_loc, f"{current_loc} (Actual)"))
        
        # Add an empty choice at the top if there's more than one choice
        if len(unit_choices) > 1 or getattr(self.instance, 'pk', None):
            unit_choices.insert(0, ('', 'Seleccione una Unidad...'))
        elif len(unit_choices) == 1:
            # Seleccionar automáticamente la única opción si solo hay una (ej. usuario de unidad)
            self.initial['storage_location'] = unit_choices[0][0]
        
        self.fields['storage_location'] = forms.ChoiceField(
            choices=unit_choices,
            label="Ubicación (Almacén/Unidad)",
            required=True
        )

    def clean(self):
        cleaned_data = super().clean()
        container_size = cleaned_data.get('container_size')
        container_count = cleaned_data.get('container_count')
        initial_quantity = cleaned_data.get('initial_quantity')
        total_price = cleaned_data.get('total_price')

        # Auto-calculate initial_quantity from container fields if both are provided
        if container_size and container_count:
            from decimal import Decimal
            calculated_qty = container_size * Decimal(str(container_count))
            if not initial_quantity:
                cleaned_data['initial_quantity'] = calculated_qty
                self.instance.initial_quantity = calculated_qty
            # If user also typed initial_quantity, use their value (they know best)
        
        # Final validation: initial_quantity must be set somehow
        final_qty = cleaned_data.get('initial_quantity')
        if not final_qty:
            self.add_error('initial_quantity', 'Debe ingresar la cantidad total, o completar cantidad por envase y cantidad de envases.')

        if final_qty and total_price is not None:
            self.instance.unit_price = total_price / final_qty
        return cleaned_data

class ConsumeGreaseForm(forms.Form):
    grease_type = forms.ModelChoiceField(queryset=GreaseType.objects.all(), label="Tipo de Grasa")
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, label="Cantidad a Consumir")
    reference = forms.CharField(max_length=255, required=False, label="Referencia (e.g., Plan de Empleo, Nro Orden)")
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label="Motivo o Notas")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not (user.is_superuser or user.groups.filter(name__in=['Administrador', 'Logistica']).exists()):
            if user.unit:
                # Filtrar grasas que tengan lotes disponibles en esta unidad
                self.fields['grease_type'].queryset = self.fields['grease_type'].queryset.filter(
                    batches__storage_location=user.unit.name,
                    batches__status__in=['SERVICEABLE', 'NEAR_EXPIRATION'],
                    batches__available_quantity__gt=0
                ).distinct()

class GreaseReferencePriceForm(forms.ModelForm):
    class Meta:
        model = GreaseReferencePrice
        fields = ['price', 'presentation_quantity', 'supplier', 'is_active']
        widgets = {
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'presentation_quantity': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'presentation_quantity' in self.fields:
            # We don't have direct access to grease_type unit here in ModelForm init easily without passing it,
            # but we can just use the help_text from the model.
            pass

class RetestBatchForm(forms.ModelForm):
    new_expiration_date = forms.DateField(
        required=True,
        label="Nueva Fecha de Vencimiento",
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Fecha de vencimiento otorgada por el laboratorio tras el retesteo."
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), 
        required=True, 
        label="Resultado / Motivo del Retesteo", 
        help_text="Documento de referencia o justificación técnica del ensayo aplicado."
    )
    
    class Meta:
        model = GreaseBatch
        fields = ['new_expiration_date', 'available_quantity', 'can_be_retested', 'reason']
        labels = {
            'can_be_retested': 'Puede volver a retestearse',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['available_quantity'].help_text = "Ajustar si la muestra para laboratorio consumió material."

    def clean_new_expiration_date(self):
        from datetime import date
        new_date = self.cleaned_data['new_expiration_date']
        if new_date <= date.today():
            raise forms.ValidationError("La nueva fecha de vencimiento debe ser posterior a hoy.")
        return new_date

class ProcurementRequirementForm(forms.ModelForm):
    class Meta:
        model = ProcurementRequirement
        fields = ['status', 'requested_quantity', 'notes']

