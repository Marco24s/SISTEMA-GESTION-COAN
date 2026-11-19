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
    classification = forms.CharField(
        label="Clasificacion",
        required=False,
        widget=forms.Select(),
    )
    new_classification = forms.CharField(
        label="➕ O crear nueva Clasificación",
        required=False,
        help_text="Escriba aquí solo si no encuentra la clasificación en la lista superior.",
    )
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
            "new_classification",
            "opening_date",
            "status",
            "amount_ars",
            "currency",
            "foreign_amount",
            "exchange_rate",
            "exchange_rate_date",
            "ipp",
            "has_oca",
            "source",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.status == "EN_APERTURA":
            self.initial["status"] = "EN_VISTA"
        default_keys = [c[0] for c in TenderProcess.CLASSIFICATION_CHOICES]
        existing_custom = (
            TenderProcess.objects.exclude(classification__in=default_keys)
            .exclude(classification__isnull=True)
            .exclude(classification="")
            .values_list("classification", flat=True)
            .distinct()
            .order_by("classification")
        )
        choices = list(TenderProcess.CLASSIFICATION_CHOICES)
        for c in existing_custom:
            if (c, c) not in choices:
                choices.append((c, c))
        if self.instance and self.instance.classification:
            choices_keys = [c[0] for c in choices]
            if self.instance.classification not in choices_keys:
                choices.append((self.instance.classification, self.instance.classification))
        self.fields["classification"].widget.choices = choices

    def clean(self):
        cleaned_data = super().clean()
        new_classification = cleaned_data.get("new_classification")
        if new_classification and new_classification.strip():
            cleaned_data["classification"] = new_classification.strip()
        return cleaned_data


class ForeignTenderProcessForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.has_oca:
            self.fields.pop("received", None)
        self.fields["expediente"].required = True
        self.fields["expediente"].label = "Objeto / Expediente (obligatorio)"
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

    def clean_requirement_number(self):
        req_number = self.cleaned_data.get("requirement_number")
        if req_number:
            req_number = req_number.upper().strip()
            process = getattr(self.instance, "process", None)
            process_id = getattr(self.instance, "process_id", None)
            if process or process_id:
                qs = ForeignTenderRequirement.objects.filter(
                    process_id=process_id or (process.pk if process else None),
                    requirement_number__iexact=req_number,
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError(
                        f"Ya existe un requerimiento con el número '{req_number}' en esta licitación."
                    )
        return req_number


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
            "supplier",
            "amount",
            "issue_date",
            "expiration_date",
            "saimb_number",
        ]

    def clean_order_number(self):
        order_number = self.cleaned_data.get("order_number")
        if order_number:
            order_number = order_number.upper().strip()
            process = getattr(self.instance, "process", None)
            process_id = getattr(self.instance, "process_id", None)
            if process or process_id:
                qs = ForeignTenderPurchaseOrder.objects.filter(
                    process_id=process_id or (process.pk if process else None),
                    order_number__iexact=order_number,
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError(
                        f"Ya existe una Orden de Compra con el número '{order_number}' en esta licitación."
                    )
        return order_number


class TenderStageUpdateForm(forms.ModelForm):
    class Meta:
        model = TenderStage
        fields = ["status", "start_date", "end_date", "responsible"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "end_date": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "responsible": forms.Select(attrs={"class": "form-select"}),
        }


class ForeignProvisionRequestForm(forms.ModelForm):
    class Meta:
        model = ForeignProvisionRequest
        fields = ["sp_number", "amount", "issue_date", "expiration_date", "saimb_number", "received"]
        widgets = {
            "issue_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "expiration_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "received": forms.Select(choices=[(None, "-"), (True, "SI"), (False, "NO")], attrs={"class": "form-select"}),
        }

    def clean_sp_number(self):
        sp_number = self.cleaned_data.get("sp_number")
        if sp_number:
            sp_number = sp_number.upper().strip()
            po = getattr(self.instance, "purchase_order", None)
            po_id = getattr(self.instance, "purchase_order_id", None)
            if po or po_id:
                qs = ForeignProvisionRequest.objects.filter(
                    purchase_order_id=po_id or (po.pk if po else None),
                    sp_number__iexact=sp_number,
                )
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError(
                        f"Ya existe una Solicitud de Provisión con el número '{sp_number}' en esta orden de compra."
                    )
        return sp_number
