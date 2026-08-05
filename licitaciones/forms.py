from django import forms

from core.models import Unit

from .models import (
    ForeignProvisionRequest,
    ForeignTenderProcess,
    ForeignTenderPurchaseOrder,
    ForeignTenderRequirement,
    ForeignTenderUpdate,
    TenderProcess,
    TenderStage,
)


class TenderProcessForm(forms.ModelForm):
    is_active = forms.BooleanField(
        label="Mostrar en procesos activos",
        required=False,
        initial=True,
        help_text="Si se desmarca, queda guardado en el historial.",
    )
    unit = forms.ModelChoiceField(
        queryset=Unit.objects.filter().order_by("name"),
        label="Destino requirente",
        required=True,
    )
    opening_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        label="Fecha de apertura",
    )
    exchange_rate_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="Fecha del tipo de cambio",
    )

    class Meta:
        model = TenderProcess
        fields = [
            "year",
            "unit",
            "process_number",
            "expediente",
            "name",
            "process_type",
            "classification",
            "opening_date",
            "status",
            "amount_ars",
            "currency",
            "foreign_amount",
            "exchange_rate",
            "exchange_rate_date",
            "has_oca",
            "source",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ForeignTenderProcessForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expediente"].required = True
        self.fields["expediente"].label = "Expediente (obligatorio)"
        self.fields["expediente"].help_text = (
            "Se carga al crear la licitacion y puede corregirse luego desde Editar proceso."
        )
        self.fields["expediente"].widget.attrs.update(
            {
                "placeholder": "Ej.: EX-2025-73889265-APN-DEDGMA#ARA",
                "class": "text-uppercase",
            }
        )

    class Meta:
        model = ForeignTenderProcess
        fields = [
            "year",
            "process_number",
            "expediente",
            "process_type",
            "has_oca",
            "status",
            "currency",
            "custom_currency",
            "evaluation_amount",
            "awarded_amount",
            "allocation_gfh",
            "incoterm",
            "received",
            "notes",
            "is_active",
        ]
        widgets = {
            "allocation_gfh": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "currency": "La misma moneda se aplicara a requerimientos, dictamen y adjudicacion.",
        }


class ForeignTenderRequirementForm(forms.ModelForm):
    unit = forms.ModelChoiceField(
        queryset=Unit.objects.filter().order_by("name"),
        label="Taller / destino",
        required=False,
    )

    class Meta:
        model = ForeignTenderRequirement
        fields = [
            "requirement_number",
            "requested_amount",
            "unit",
            "workshop",
            "aircraft",
            "description",
            "notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class ForeignTenderUpdateForm(forms.ModelForm):
    event_date = forms.DateField(
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="Fecha",
    )

    class Meta:
        model = ForeignTenderUpdate
        fields = [
            "event_date",
            "organization",
            "document_type",
            "document_number",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ForeignTenderPurchaseOrderForm(forms.ModelForm):
    issue_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="Fecha de emision",
    )
    expiration_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="Fecha de vencimiento",
    )

    class Meta:
        model = ForeignTenderPurchaseOrder
        fields = [
            "order_number",
            "amount",
            "issue_date",
            "expiration_date",
            "saimb_number",
        ]


class TenderStageUpdateForm(forms.ModelForm):
    class Meta:
        model = TenderStage
        fields = ["status", "start_date", "end_date", "responsible"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "responsible": forms.Select(attrs={"class": "form-select"}),
        }


class ForeignProvisionRequestForm(forms.ModelForm):
    class Meta:
        model = ForeignProvisionRequest
        fields = ["sp_number", "amount", "issue_date", "saimb_number"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }
