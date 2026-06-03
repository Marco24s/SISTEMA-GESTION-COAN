from django import forms

from core.models import Unit

from .models import TenderProcess


class TenderProcessForm(forms.ModelForm):
    is_active = forms.BooleanField(
        label="Mostrar en procesos activos",
        required=False,
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
