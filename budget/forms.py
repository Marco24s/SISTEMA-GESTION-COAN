from django import forms
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from .models import (
    BudgetFiscalYear, BudgetFF, BudgetSubprog, BudgetProg,
    BudgetPPPInc, BudgetPPInc, BudgetPreInc, BudgetIncisosAgrupado,
    BudgetInc, BudgetCredit, BudgetClassification, BudgetCreditType,
    BudgetAllocation, BudgetExecution, BudgetCompensacion, BudgetTipoGasto
)

class BudgetFiscalYearForm(forms.ModelForm):
    class Meta:
        model = BudgetFiscalYear
        fields = ['year', 'status', 'notes']

# --- Formularios de Catálogo ---

class BudgetFFForm(forms.ModelForm):
    class Meta:
        model = BudgetFF
        fields = ['code', 'name']

class BudgetSubprogForm(forms.ModelForm):
    class Meta:
        model = BudgetSubprog
        fields = ['code', 'name']

class BudgetProgForm(forms.ModelForm):
    class Meta:
        model = BudgetProg
        fields = ['code', 'name']

class BudgetPPPIncForm(forms.ModelForm):
    class Meta:
        model = BudgetPPPInc
        fields = ['code', 'name']

class BudgetPPIncForm(forms.ModelForm):
    class Meta:
        model = BudgetPPInc
        fields = ['code', 'name']

class BudgetPreIncForm(forms.ModelForm):
    class Meta:
        model = BudgetPreInc
        fields = ['code', 'name']

class BudgetIncisosAgrupadoForm(forms.ModelForm):
    class Meta:
        model = BudgetIncisosAgrupado
        fields = ['code', 'name']

class BudgetIncForm(forms.ModelForm):
    class Meta:
        model = BudgetInc
        fields = ['code', 'name']


class BudgetTipoGastoForm(forms.ModelForm):
    class Meta:
        model = BudgetTipoGasto
        fields = ['code', 'name']


class BudgetCreditForm(forms.ModelForm):
    class Meta:
        model = BudgetCredit
        fields = [
            'fiscal_year', 'credit_type', 'ff', 'programa', 'subprog', 'inc',
            'ppp_inc', 'pp_inc', 'pre_inc', 'incisos_agrupado',
            'q1_amount', 'q2_amount', 'q3_amount', 'q4_amount', 'notes'
        ]
        labels = {
            'fiscal_year': 'Ejercicio Económico',
            'credit_type': 'Tipo de Crédito',
            'ff': 'Fuente de Financiamiento (FF)',
            'programa': 'Programa',
            'subprog': 'Subprograma',
            'inc': 'INCISO',
            'ppp_inc': 'PPAL',
            'pp_inc': 'PARCIAL',
            'pre_inc': 'SUBPC',
            'incisos_agrupado': 'MONEDA',
            'q1_amount': 'Monto 1er Trimestre',
            'q2_amount': 'Monto 2do Trimestre',
            'q3_amount': 'Monto 3er Trimestre',
            'q4_amount': 'Monto 4to Trimestre',
            'notes': 'Observaciones'
        }
        widgets = {
            'q1_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q2_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q3_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q4_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
        }
        localized_fields = ('q1_amount', 'q2_amount', 'q3_amount', 'q4_amount')

class CreditChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        available = getattr(obj, 'available_amount', obj.total_amount)
        # Formato de puntos y comas. Reemplazando para evitar locale configs locales
        av_str = f"{available:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{obj} (Disponible para distribuir: ${av_str})"

class BudgetAllocationForm(forms.ModelForm):
    credit = CreditChoiceField(
        queryset=BudgetCredit.objects.none(),
        label="Crédito Origen",
        empty_label="--------- Seleccione un Crédito ---------"
    )
    
    class Meta:
        model = BudgetAllocation
        fields = [
            'credit', 'unit', 
            'q1_amount', 'q2_amount', 'q3_amount', 'q4_amount',
            'notes'
        ]
        labels = {
            'q1_amount': 'Monto 1er Trimestre (T1)',
            'q2_amount': 'Monto 2do Trimestre (T2)',
            'q3_amount': 'Monto 3er Trimestre (T3)',
            'q4_amount': 'Monto 4to Trimestre (T4)',
        }
        widgets = {
            'q1_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q2_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q3_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q4_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
        }
        localized_fields = ('q1_amount', 'q2_amount', 'q3_amount', 'q4_amount')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db import models
        # Annotate available_amount efficiently 
        self.fields['credit'].queryset = BudgetCredit.objects.annotate(
            allocated_total=Coalesce(Sum('allocations__allocated_amount'), 0, output_field=models.DecimalField())
        ).annotate(
            available_amount=F('total_amount') - F('allocated_total')
        ).order_by('-fiscal_year__year', 'ff__code')

class AllocationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        available = obj.available_amount
        av_str = f"{available:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        subpc = obj.credit.pre_inc.code if obj.credit.pre_inc else "00"
        return f"{obj.unit.name} - {subpc} - [Disp: ${av_str}]"

class BudgetExecutionCommitmentForm(forms.ModelForm):
    allocation = AllocationChoiceField(
        queryset=BudgetAllocation.objects.all(),
        label="Distribución / Techo Presupuestario",
        help_text="Seleccione la distribución de crédito contra la cual se imputará el gasto."
    )
    use_total_amount = forms.BooleanField(
        required=False, 
        label="¿Comprometer el total disponible?",
        help_text="Si se marca, el monto se completará automáticamente con el saldo restante."
    )
    class Meta:
        model = BudgetExecution
        fields = [
            'allocation', 'use_total_amount', 'reference_code', 'external_id', 
            'tipo_gasto', 'numero_obra',
            'commitment_amount', 'commitment_date'
        ]
        labels = {
            'allocation': 'Distribución / Techo Presupuestario',
            'reference_code': 'Número de Expediente / Comprobante',
            'external_id': 'ID de Control Único (Opcional)',
            'commitment_amount': 'Monto a Comprometer',
            'commitment_date': 'Fecha del Compromiso',
            'tipo_gasto': 'Tipo de Gasto (TG)',
            'numero_obra': 'Número de Obra',
        }
        help_texts = {
            'allocation': 'Seleccione la distribución de crédito contra la cual se imputará el gasto.',
            'reference_code': 'Ejemplo: Exp. 123/2026 o Nota Log. 45/26',
            'commitment_amount': 'Ingrese el monto bruto que se reserva para esta operación.',
            'external_id': 'Código único para prevenir registros duplicados.',
            'tipo_gasto': 'Requerido para Incisos 1, 2, 3 y 5.',
            'numero_obra': 'Requerido para Inciso 4 (5 dígitos).',
        }
        widgets = {
            'commitment_date': forms.DateInput(attrs={'type': 'date'}),
            'commitment_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'numero_obra': forms.TextInput(attrs={'maxlength': '5'}),
        }
        localized_fields = ('commitment_amount',)

    def clean(self):
        cleaned_data = super().clean()
        allocation = cleaned_data.get('allocation')
        tipo_gasto = cleaned_data.get('tipo_gasto')
        numero_obra = cleaned_data.get('numero_obra')

        if allocation and allocation.credit:
            credit = allocation.credit
            inc_code = credit.inc.code if credit.inc else ""
            ff_code = credit.ff.code if credit.ff else ""

            # Validaciones Inciso 4
            if inc_code == '4':
                if ff_code not in ['13', '99']:
                    if not numero_obra:
                        self.add_error('numero_obra', 'Para el Inciso 4 (sin FF 13/99), el Número de Obra es obligatorio.')
                    elif len(str(numero_obra)) != 5:
                        self.add_error('numero_obra', 'El Número de Obra debe tener exactamente 5 dígitos.')
                # Si es FF 13 o 99, será 99999 automáticamente, no necesita error de falta de numero
            else:
                # Validaciones Incisos 1, 2, 3, 5
                if not tipo_gasto:
                    self.add_error('tipo_gasto', f'Para el Inciso {inc_code}, el Tipo de Gasto es obligatorio.')
                if numero_obra:
                    self.add_error('numero_obra', f'El Número de Obra solo aplica al Inciso 4. Deje este campo en blanco.')

        return cleaned_data

class BudgetExecutionAccrualForm(forms.ModelForm):
    class Meta:
        model = BudgetExecution
        fields = ['accrued_amount', 'accrued_date']
        widgets = {
            'accrued_date': forms.DateInput(attrs={'type': 'date'}),
            'accrued_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
        }
        localized_fields = ('accrued_amount',)

class BudgetExecutionPaymentForm(forms.ModelForm):
    class Meta:
        model = BudgetExecution
        fields = ['paid_amount', 'paid_date']
        widgets = {
            'paid_date': forms.DateInput(attrs={'type': 'date'}),
            'paid_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
        }
        localized_fields = ('paid_amount',)

class BudgetCreditTypeForm(forms.ModelForm):
    class Meta:
        model = BudgetCreditType
        fields = ['code', 'name']
        labels = {'code': 'Código', 'name': 'Nombre / Descripción'}

class BudgetClassificationForm(forms.ModelForm):
    class Meta:
        model = BudgetClassification
        fields = ['name', 'notes']
        labels = {
            'name': 'Nombre de la Clasificación',
            'notes': 'Notas / Descripción'
        }

class BudgetAllocationMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        amount_str = f"{obj.allocated_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{obj.unit.name} — {obj.credit} [Total: ${amount_str}]"

class BudgetClassificationAssignForm(forms.Form):
    # This form is used from the classification perspective to pull allocations into itself
    allocations = BudgetAllocationMultipleChoiceField(
        queryset=BudgetAllocation.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Seleccionar Créditos Distribuidos"
    )

    def __init__(self, *args, **kwargs):
        self.classification = kwargs.pop('classification', None)
        super().__init__(*args, **kwargs)
        if self.classification:
            # Set initial checked instances (allocation items)
            self.fields['allocations'].initial = self.classification.allocations.all()
            
            self.fields['allocations'].queryset = BudgetAllocation.objects.all().select_related(
                'unit', 'credit__fiscal_year', 'credit__ff', 'credit__programa', 
                'credit__subprog', 'credit__inc', 'credit__ppp_inc', 'credit__pp_inc', 'credit__pre_inc'
            ).order_by('-credit__fiscal_year__year', 'unit__name')

class BudgetCompensacionForm(forms.ModelForm):
    class Meta:
        model = BudgetCompensacion
        fields = [
            'fiscal_year', 'programa', 'source_credit',
            'target_ff', 'target_subprog', 'target_inc', 'target_ppp_inc', 
            'target_pp_inc', 'target_pre_inc', 'target_incisos_agrupado',
            'q1_amount', 'q2_amount', 'q3_amount', 'q4_amount', 'notes'
        ]
        widgets = {
            'q1_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q2_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q3_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
            'q4_amount': forms.TextInput(attrs={'class': 'form-control currency-input', 'placeholder': '0,00'}),
        }
        localized_fields = ('q1_amount', 'q2_amount', 'q3_amount', 'q4_amount')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_credit'].queryset = BudgetCredit.objects.filter(total_amount__gt=0).order_by('programa__code', 'ff__code')
        self.fields['source_credit'].label = "Crédito de Origen (AA.PP.)"
        self.fields['programa'].help_text = "La compensación solo se permite entre partidas del mismo programa."


class BudgetCreditAdjustmentForm(forms.Form):
    q1_new = forms.DecimalField(max_digits=18, decimal_places=2, label="Nuevo Monto T1", required=False, localize=True)
    q2_new = forms.DecimalField(max_digits=18, decimal_places=2, label="Nuevo Monto T2", required=False, localize=True)
    q3_new = forms.DecimalField(max_digits=18, decimal_places=2, label="Nuevo Monto T3", required=False, localize=True)
    q4_new = forms.DecimalField(max_digits=18, decimal_places=2, label="Nuevo Monto T4", required=False, localize=True)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label="Motivo del Ajuste", help_text="Explique brevemente por qué se realiza esta modificación.")

    def __init__(self, *args, **kwargs):
        credit = kwargs.pop('credit', None)
        super().__init__(*args, **kwargs)
        if credit:
            self.fields['q1_new'].initial = credit.q1_amount
            self.fields['q2_new'].initial = credit.q2_amount
            self.fields['q3_new'].initial = credit.q3_amount
            self.fields['q4_new'].initial = credit.q4_amount
        
        for field in ['q1_new', 'q2_new', 'q3_new', 'q4_new']:
            # No sobreescribir la clase si ya tiene format-control del bootstrap
            self.fields[field].widget.attrs.update({'class': 'form-control currency-input', 'placeholder': '0,00'})
        self.fields['reason'].widget.attrs.update({'class': 'form-control'})
