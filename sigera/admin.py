from django.contrib import admin
from .models import ClothingType, ClothingSize, ClothingBatch, Personnel, ClothingAssignment, StockThreshold

@admin.register(ClothingType)
class ClothingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'nato_stock_number', 'shelf_life_months')
    search_fields = ('name', 'nato_stock_number')

@admin.register(ClothingSize)
class ClothingSizeAdmin(admin.ModelAdmin):
    list_display = ('clothing_type', 'size')
    list_filter = ('clothing_type',)
    search_fields = ('clothing_type__name', 'size')

@admin.register(ClothingBatch)
class ClothingBatchAdmin(admin.ModelAdmin):
    list_display = ('clothing_size', 'reception_date', 'initial_quantity', 'available_quantity', 'provider')
    list_filter = ('reception_date', 'provider')
    search_fields = ('clothing_size__clothing_type__name', 'provider', 'purchase_order')

@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'dni', 'rank', 'assigned_unit')
    list_filter = ('rank', 'assigned_unit')
    search_fields = ('last_name', 'first_name', 'dni')

@admin.register(ClothingAssignment)
class ClothingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('personnel', 'batch', 'assigned_date', 'quantity', 'returned')
    list_filter = ('returned', 'assigned_date')
    search_fields = ('personnel__last_name', 'personnel__first_name', 'batch__clothing_size__clothing_type__name')

@admin.register(StockThreshold)
class StockThresholdAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_quantity', 'max_quantity', 'color', 'order')
    list_editable = ('order',)
    ordering = ('order',)
