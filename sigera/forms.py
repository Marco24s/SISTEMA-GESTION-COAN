from django import forms
from .models import Personnel, ClothingAssignment, ClothingBatch, ClothingType, ClothingSize
from core.models import Unit

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ['first_name', 'last_name', 'dni', 'rank', 'assigned_unit']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Nombres...', 'style': 'text-transform: uppercase;'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Apellidos...', 'style': 'text-transform: uppercase;'}),
            'dni': forms.TextInput(attrs={'placeholder': 'Matrícula de Revista', 'style': 'text-transform: uppercase;'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            is_admin = self.user.is_superuser or self.user.groups.filter(name__in=['Administrador', 'Logistica']).exists()
            if not is_admin and getattr(self.user, 'unit', None):
                self.fields['assigned_unit'].queryset = Unit.objects.filter(pk=self.user.unit.pk)
                self.fields['assigned_unit'].initial = self.user.unit
                # Optional: para mayor seguridad/claridad, podemos ocultarlo o no
                # pero con el queryset filtrado a una opción está seguro.


class ClothingAssignmentForm(forms.ModelForm):
    class Meta:
        model = ClothingAssignment
        # Se omiten 'issued_by', 'assigned_date', 'returned', 'return_date' porque los maneja la vista internamente
        fields = ['personnel', 'batch', 'quantity', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observaciones de la entrega...', 'style': 'text-transform: uppercase;'}),
            'quantity': forms.NumberInput(attrs={'min': '1', 'value': '1'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar solo los lotes de prendas que tengan cantidad disponible en pañol
        self.fields['batch'].queryset = ClothingBatch.objects.filter(available_quantity__gt=0).order_by('clothing_size__clothing_type__name')
        self.fields['batch'].label_from_instance = lambda obj: f"{obj.clothing_size.clothing_type.name} - Talle: {obj.clothing_size.size} (Disp: {obj.available_quantity})"

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        batch = self.cleaned_data.get('batch')
        
        if quantity and batch:
            if quantity > batch.available_quantity:
                raise forms.ValidationError(f"No hay stock suficiente. Solo quedan {batch.available_quantity} unidades en este lote.")
        
        if quantity and quantity <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a 0.")
            
        return quantity


class ClothingTypeForm(forms.ModelForm):
    class Meta:
        model = ClothingType
        fields = ['name', 'description', 'nato_stock_number', 'shelf_life_months', 'must_be_returned']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej: Mameluco de Vuelo', 'style': 'text-transform: uppercase;'}),
            'description': forms.Textarea(attrs={'rows': 2, 'style': 'text-transform: uppercase;'}),
            'nato_stock_number': forms.TextInput(attrs={'placeholder': 'NNE o NSN...', 'style': 'text-transform: uppercase;'}),
            'shelf_life_months': forms.NumberInput(attrs={'min': '1', 'value': '12'}),
            'must_be_returned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ClothingSizeForm(forms.ModelForm):
    class Meta:
        model = ClothingSize
        fields = ['clothing_type', 'size']
        widgets = {
            'size': forms.TextInput(attrs={'placeholder': 'Ej: M, L, XL, 42, 44', 'style': 'text-transform: uppercase;'}),
        }


class ClothingBatchForm(forms.ModelForm):
    clothing_type = forms.ModelChoiceField(
        queryset=ClothingType.objects.order_by('name'),
        label='Prenda',
        required=True,
        empty_label='Seleccionar prenda...',
        widget=forms.Select()
    )

    class Meta:
        model = ClothingBatch
        # available_quantity is handled in the view
        fields = ['clothing_type', 'clothing_size', 'reception_date', 'initial_quantity', 'provider', 'purchase_order', 'unit_price']
        widgets = {
            'clothing_size': forms.Select(),
            'reception_date': forms.DateInput(attrs={'type': 'date'}),
            'initial_quantity': forms.NumberInput(attrs={'min': '1', 'value': '1'}),
            'provider': forms.TextInput(attrs={'placeholder': 'Ej: Proveedor S.A.', 'style': 'text-transform: uppercase;'}),
            'purchase_order': forms.TextInput(attrs={'placeholder': 'N° de Remito/Factura', 'style': 'text-transform: uppercase;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clothing_size'].queryset = ClothingSize.objects.none()
        self.fields['clothing_size'].label = 'Talle'

        if self.instance and self.instance.pk and self.instance.clothing_size:
            clothing_type = self.instance.clothing_size.clothing_type
            self.fields['clothing_type'].initial = clothing_type
            self.fields['clothing_size'].queryset = ClothingSize.objects.filter(clothing_type=clothing_type).order_by('size')
            self.fields['clothing_size'].initial = self.instance.clothing_size
        elif self.data.get('clothing_type'):
            try:
                clothing_type_id = int(self.data.get('clothing_type'))
            except (TypeError, ValueError):
                clothing_type_id = None
            if clothing_type_id:
                self.fields['clothing_size'].queryset = ClothingSize.objects.filter(clothing_type_id=clothing_type_id).order_by('size')

    def clean(self):
        cleaned_data = super().clean()
        clothing_type = cleaned_data.get('clothing_type')
        clothing_size = cleaned_data.get('clothing_size')

        if clothing_type and clothing_size:
            if clothing_size.clothing_type != clothing_type:
                self.add_error('clothing_size', 'El talle seleccionado no corresponde a la prenda elegida.')

        return cleaned_data
