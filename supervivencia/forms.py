from django import forms
from django.forms import inlineformset_factory

from licitaciones.models import TenderProcess

from .models import (
    Aircraft,
    AircraftVariant,
    PyrotechnicCatalogItem,
    PyrotechnicCatalogLifeRule,
    PyrotechnicAssignment,
    PyrotechnicPhysicalItem,
    PyrotechnicStorageLocation,
    PyrotechnicItemType,
    PyrotechnicRequirement,
    SurvivalMedium,
)


class AircraftChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class AircraftVariantChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class PyrotechnicItemTypeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        label_parts = [obj.code, obj.name]
        if obj.part_number:
            label_parts.append(obj.part_number)
        return " - ".join(label_parts)


class SurvivalMediumForm(forms.ModelForm):
    class Meta:
        model = SurvivalMedium
        fields = ["identifier", "name", "medium_type", "model", "unit", "notes", "is_active"]
        labels = {
            "identifier": "Identificacion / Matricula",
            "name": "Medio",
            "medium_type": "Tipo de medio",
            "model": "Modelo",
            "unit": "Unidad",
            "notes": "Observaciones",
            "is_active": "Activo",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class PyrotechnicCatalogItemForm(forms.ModelForm):
    class Meta:
        model = PyrotechnicCatalogItem
        fields = [
            "nomenclature",
            "system",
            "part_number",
            "nsn",
            "alternate_part_number",
            "description",
            "is_active",
        ]
        labels = {
            "nomenclature": "Nomenclatura",
            "system": "Sistema",
            "part_number": "N° / Parte",
            "nsn": "N.S.N",
            "alternate_part_number": "Numero de parte alternativo",
            "description": "Descripcion",
            "is_active": "Activo",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class PyrotechnicCatalogLifeRuleForm(forms.ModelForm):
    class Meta:
        model = PyrotechnicCatalogLifeRule
        fields = ["situation", "duration_value", "duration_unit", "notes"]
        labels = {
            "situation": "Situacion",
            "duration_value": "Vida util",
            "duration_unit": "Unidad",
            "notes": "Observaciones",
        }
        widgets = {
            "situation": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "duration_value": forms.NumberInput(attrs={"min": 1, "class": "form-control form-control-sm"}),
            "duration_unit": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "notes": forms.TextInput(
                attrs={"placeholder": "Referencia, certificado o criterio tecnico", "class": "form-control form-control-sm"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["situation"].required = False
        self.fields["duration_value"].required = False
        self.fields["duration_unit"].required = False
        self.fields["situation"].choices = [("", "Seleccione...")] + list(PyrotechnicCatalogLifeRule.SITUATION_CHOICES)
        self.fields["duration_unit"].choices = [("", "Seleccione...")] + list(PyrotechnicCatalogLifeRule.UNIT_CHOICES)
        if not self.instance.pk:
            self.fields["duration_unit"].initial = ""

    def clean(self):
        cleaned_data = super().clean()
        situation = cleaned_data.get("situation")
        duration_value = cleaned_data.get("duration_value")
        duration_unit = cleaned_data.get("duration_unit")
        notes = cleaned_data.get("notes")

        if cleaned_data.get("DELETE"):
            return cleaned_data
        if not situation and not duration_value and not duration_unit and not notes:
            return cleaned_data
        if not situation or not duration_value or not duration_unit:
            raise forms.ValidationError("Complete situacion, vida util y unidad, o deje la fila vacia.")
        return cleaned_data


PyrotechnicCatalogLifeRuleFormSet = inlineformset_factory(
    PyrotechnicCatalogItem,
    PyrotechnicCatalogLifeRule,
    form=PyrotechnicCatalogLifeRuleForm,
    extra=4,
    can_delete=True,
)


class PyrotechnicPhysicalItemForm(forms.ModelForm):
    class Meta:
        model = PyrotechnicPhysicalItem
        fields = [
            "catalog_item",
            "serial_number",
            "lot_number",
            "lot_quantity",
            "manufacturer",
            "manufacture_date",
            "expiration_date",
            "condition",
            "operational_status",
            "current_storage_location",
            "current_location",
            "certificate_reference",
            "notes",
            "is_active",
        ]
        labels = {
            "catalog_item": "Elemento de catalogo",
            "serial_number": "Numero de serie",
            "lot_number": "Lote / partida",
            "lot_quantity": "Cantidad del lote",
            "manufacturer": "Fabricante",
            "manufacture_date": "Fecha de fabricacion",
            "expiration_date": "Fecha de vencimiento",
            "condition": "Condicion",
            "operational_status": "Estado operativo",
            "current_storage_location": "Ubicacion controlada",
            "current_location": "Ubicacion actual",
            "certificate_reference": "Certificado / documento",
            "notes": "Observaciones",
            "is_active": "Activo",
        }
        widgets = {
            "serial_number": forms.TextInput(attrs={"placeholder": "Ej: SN-12345", "style": "text-transform: uppercase;"}),
            "lot_number": forms.TextInput(attrs={"placeholder": "Ej: LOTE-2026-01", "style": "text-transform: uppercase;"}),
            "lot_quantity": forms.NumberInput(attrs={"min": 1}),
            "manufacturer": forms.TextInput(attrs={"placeholder": "Fabricante", "style": "text-transform: uppercase;"}),
            "manufacture_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "expiration_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "current_location": forms.TextInput(attrs={"placeholder": "Pañol, polvorín, depósito o referencia actual", "style": "text-transform: uppercase;"}),
            "certificate_reference": forms.TextInput(attrs={"placeholder": "Certificado, acta o documento", "style": "text-transform: uppercase;"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["catalog_item"].queryset = PyrotechnicCatalogItem.objects.filter(is_active=True).order_by("nomenclature")
        self.fields["catalog_item"].label_from_instance = lambda obj: (
            f"{obj.nomenclature} | N/P: {obj.part_number or '-'} | NSN: {obj.nsn or '-'}"
        )
        self.fields["current_storage_location"].queryset = PyrotechnicStorageLocation.objects.filter(is_active=True).order_by("code")
        self.fields["serial_number"].required = False
        self.fields["lot_number"].required = False
        self.fields["lot_quantity"].required = False
        self.fields["lot_quantity"].help_text = "Si el material tiene numero de serie, la cantidad queda en 1. Si se identifica por lote, indique cuantas unidades contiene."
        self.fields["manufacturer"].required = False
        self.fields["manufacture_date"].required = False
        self.fields["current_storage_location"].required = False
        self.fields["current_location"].required = False
        self.fields["certificate_reference"].required = False
        self.fields["notes"].required = False

    def clean(self):
        cleaned_data = super().clean()
        serial_number = cleaned_data.get("serial_number")
        lot_number = cleaned_data.get("lot_number")
        lot_quantity = cleaned_data.get("lot_quantity") or 1
        current_storage_location = cleaned_data.get("current_storage_location")
        current_location = cleaned_data.get("current_location")
        if not serial_number and not lot_number:
            raise forms.ValidationError("Debe cargar al menos un numero de serie o un lote / partida.")
        if serial_number:
            cleaned_data["lot_quantity"] = 1
        elif lot_number and lot_quantity < 1:
            raise forms.ValidationError("La cantidad del lote debe ser mayor o igual a 1.")
        if not current_storage_location and not current_location:
            raise forms.ValidationError("Debe indicar una ubicacion controlada o una ubicacion manual.")
        return cleaned_data


class PyrotechnicStorageLocationForm(forms.ModelForm):
    class Meta:
        model = PyrotechnicStorageLocation
        fields = ["code", "name", "location_type", "unit", "is_restricted", "notes", "is_active"]
        labels = {
            "code": "Destino",
            "name": "Ubicacion",
            "location_type": "Tipo de ubicacion",
            "unit": "Unidad",
            "is_restricted": "Zona restringida",
            "notes": "Observaciones",
            "is_active": "Activo",
        }
        widgets = {
            "code": forms.TextInput(attrs={"style": "text-transform: uppercase;"}),
            "name": forms.TextInput(attrs={"style": "text-transform: uppercase;"}),
            "notes": forms.Textarea(attrs={"rows": 3, "style": "text-transform: uppercase;"}),
        }


class PyrotechnicPhysicalItemMovementForm(forms.ModelForm):
    movement_notes = forms.CharField(
        label="Observaciones del movimiento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "style": "text-transform: uppercase;"}),
    )

    class Meta:
        model = PyrotechnicPhysicalItem
        fields = ["condition", "operational_status", "current_storage_location", "current_location", "movement_notes"]
        labels = {
            "condition": "Condicion",
            "operational_status": "Estado operativo",
            "current_storage_location": "Ubicacion controlada",
            "current_location": "Ubicacion manual",
        }
        widgets = {
            "current_location": forms.TextInput(
                attrs={"placeholder": "Solo si no existe una ubicacion controlada", "style": "text-transform: uppercase;"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["current_storage_location"].queryset = PyrotechnicStorageLocation.objects.filter(
            is_active=True
        ).order_by("code")
        self.fields["condition"].help_text = "Si el material esta montado, primero debe retirar la asignacion antes de bloquearlo o pasarlo a no operativo."
        self.fields["operational_status"].help_text = "Si el material esta montado, primero debe retirar la asignacion antes de pasarlo a deposito, removido, consumido o baja."
        self.fields["current_storage_location"].required = False
        self.fields["current_location"].required = False

    def clean(self):
        cleaned_data = super().clean()
        condition = cleaned_data.get("condition")
        operational_status = cleaned_data.get("operational_status")
        current_storage_location = cleaned_data.get("current_storage_location")
        current_location = cleaned_data.get("current_location")
        if not current_storage_location and not current_location:
            raise forms.ValidationError("Debe indicar una ubicacion controlada o una ubicacion manual.")
        if self.instance and self.instance.pk:
            has_active_assignment = PyrotechnicAssignment.objects.filter(
                physical_item=self.instance, is_active=True
            ).exists()
            if has_active_assignment and operational_status in {"STOCK", "REMOVED", "DISCARDED", "CONSUMED"}:
                raise forms.ValidationError(
                    "Este material esta montado en un medio. Primero retire la asignacion antes de pasarlo a deposito, removido, consumido o baja."
                )
            if has_active_assignment and condition in {"UNSERVICEABLE", "QUARANTINE", "BLOCKED"}:
                raise forms.ValidationError(
                    "Este material esta montado en un medio. Primero retire la asignacion antes de marcarlo no operativo, en cuarentena o bloqueado."
                )
        return cleaned_data


class SurvivalMediumChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        label = f"{obj.identifier} - {obj.name}"
        details = []
        if obj.model:
            details.append(obj.model)
        if obj.unit:
            details.append(obj.unit.name)
        if details:
            label = f"{label} ({' / '.join(details)})"
        return label


class PyrotechnicPhysicalItemChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        identity = obj.serial_number or obj.lot_number or f"ID {obj.pk}"
        location = obj.current_storage_location or obj.current_location or "Sin ubicacion"
        quantity = f" | Cantidad {obj.lot_quantity}" if obj.lot_quantity else ""
        return (
            f"{obj.catalog_item.nomenclature} - {identity} | "
            f"Vence {obj.expiration_date:%d/%m/%Y} | "
            f"{obj.get_condition_display()} | {location}{quantity}"
        )


class PyrotechnicAssignmentForm(forms.ModelForm):
    medium = SurvivalMediumChoiceField(queryset=SurvivalMedium.objects.none(), label="Medio")
    physical_item = PyrotechnicPhysicalItemChoiceField(
        queryset=PyrotechnicPhysicalItem.objects.none(),
        label="Material fisico disponible",
        help_text="Solo se muestran materiales activos que no estan montados en otro medio.",
    )

    class Meta:
        model = PyrotechnicAssignment
        fields = ["medium", "physical_item", "installed_at", "position", "notes", "is_active", "removed_at"]
        labels = {
            "medium": "Medio",
            "physical_item": "Material fisico",
            "installed_at": "Fecha de montaje / asignacion",
            "position": "Posicion / ubicacion en el medio",
            "notes": "Observaciones",
            "is_active": "Activo / montado",
            "removed_at": "Fecha de retiro",
        }
        widgets = {
            "installed_at": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "removed_at": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "position": forms.TextInput(attrs={"placeholder": "Ej: ALOJAMIENTO DERECHO", "style": "text-transform: uppercase;"}),
            "notes": forms.Textarea(attrs={"rows": 3, "style": "text-transform: uppercase;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medium"].queryset = SurvivalMedium.objects.filter(is_active=True).order_by("identifier")
        assigned_assignments = PyrotechnicAssignment.objects.filter(is_active=True)
        if self.instance and self.instance.pk:
            assigned_assignments = assigned_assignments.exclude(physical_item_id=self.instance.physical_item_id)
        assigned_ids = assigned_assignments.values_list("physical_item_id", flat=True)
        self.fields["physical_item"].queryset = (
            PyrotechnicPhysicalItem.objects.filter(is_active=True)
            .exclude(id__in=assigned_ids)
            .select_related("catalog_item", "current_storage_location")
            .order_by("catalog_item__nomenclature", "serial_number", "lot_number")
        )
        if self.instance and self.instance.pk and self.instance.physical_item_id:
            current_item = PyrotechnicPhysicalItem.objects.filter(pk=self.instance.physical_item_id).select_related(
                "catalog_item", "current_storage_location"
            )
            self.fields["physical_item"].queryset = self.fields["physical_item"].queryset | current_item
        self.fields["medium"].empty_label = "Seleccione un medio"
        self.fields["physical_item"].empty_label = "Seleccione material disponible"
        self.fields["position"].required = False
        self.fields["notes"].required = False
        self.fields["removed_at"].required = False

    def clean(self):
        cleaned_data = super().clean()
        physical_item = cleaned_data.get("physical_item")
        is_active = cleaned_data.get("is_active")
        removed_at = cleaned_data.get("removed_at")
        if is_active and removed_at:
            raise forms.ValidationError("Una asignacion activa no debe tener fecha de retiro.")
        if physical_item and is_active:
            if not physical_item.is_active:
                raise forms.ValidationError("No se puede montar/asignar material inactivo.")
            if physical_item.is_expired:
                raise forms.ValidationError("No se puede montar/asignar material vencido.")
            if physical_item.condition != "SERVICEABLE":
                raise forms.ValidationError("Solo se puede montar/asignar material con condicion Operativo.")
            if physical_item.operational_status in {"DISCARDED", "CONSUMED"}:
                raise forms.ValidationError("No se puede montar/asignar material consumido o dado de baja.")
            duplicate = PyrotechnicAssignment.objects.filter(physical_item=physical_item, is_active=True)
            if self.instance and self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError("Ese material fisico ya esta activo en otro medio.")
        return cleaned_data


class PyrotechnicItemTypeForm(forms.ModelForm):
    class Meta:
        model = PyrotechnicItemType
        fields = ["code", "name", "part_number", "nsn", "alternate_part_number"]
        labels = {
            "code": "NOMENCLATURA",
            "name": "SISTEMA",
            "part_number": "N° / PARTE",
            "nsn": "N.S.N",
            "alternate_part_number": "NUMERO DE PARTE ALTERNATIVO",
        }


class PyrotechnicRequirementForm(forms.ModelForm):
    aircraft = AircraftChoiceField(queryset=Aircraft.objects.none(), label="Aeronave")
    variant = AircraftVariantChoiceField(queryset=AircraftVariant.objects.none(), label="Modelo", required=False)
    item_type = PyrotechnicItemTypeChoiceField(queryset=PyrotechnicItemType.objects.none(), label="Tipo de elemento")

    class Meta:
        model = PyrotechnicRequirement
        fields = [
            "aircraft",
            "variant",
            "item_type",
            "year",
            "month",
            "quantity",
            "status",
            "tender_process",
            "reference",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aircraft"].queryset = Aircraft.objects.filter(is_active=True).order_by("code")
        self.fields["variant"].queryset = AircraftVariant.objects.filter(is_active=True).select_related("aircraft").order_by("aircraft__code", "name")
        self.fields["variant"].required = False
        self.fields["item_type"].queryset = PyrotechnicItemType.objects.filter(is_active=True).order_by("code")
        self.fields["tender_process"].queryset = TenderProcess.objects.filter(is_active=True).select_related("unit").order_by("-year", "process_number")
        self.fields["tender_process"].required = False
        self.fields["reference"].required = False
        self.fields["notes"].required = False
        self.fields["is_active"].label = "Mostrar en seguimiento activo"
