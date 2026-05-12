from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, 
    Unit, 
    AircraftModel, 
    GreaseType, 
    AircraftGrease, 
    FlightPlan, 
    GreaseBatch, 
    StockMovement
)

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'unit', 'is_staff']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Asignación de Unidad', {'fields': ('unit',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Asignación de Unidad', {'fields': ('unit',)}),
    )

admin.site.register(CustomUser, CustomUserAdmin)

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(AircraftModel)
class AircraftModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'total_aircraft', 'is_active')
    list_filter = ('is_active', 'unit')
    search_fields = ('name',)

@admin.register(GreaseType)
class GreaseTypeAdmin(admin.ModelAdmin):
    list_display = ('nomenclatura', 'unidad', 'nne_nsn', 'sibys', 'nato', 'normas_mil_otras')
    list_filter = ('recertification_allowed',)
    search_fields = ('nomenclatura', 'nne_nsn', 'nato')

@admin.register(AircraftGrease)
class AircraftGreaseAdmin(admin.ModelAdmin):
    list_display = ('aircraft_model', 'grease_type', 'hourly_consumption_rate')
    list_filter = ('aircraft_model', 'grease_type')

@admin.register(FlightPlan)
class FlightPlanAdmin(admin.ModelAdmin):
    list_display = ('aircraft_model', 'period_type', 'period_start_date', 'planned_hours')
    list_filter = ('period_type', 'period_start_date', 'aircraft_model')

@admin.register(GreaseBatch)
class GreaseBatchAdmin(admin.ModelAdmin):
    list_display = ('grease_type', 'batch_number', 'expiration_date', 'status', 'initial_quantity', 'available_quantity')
    list_filter = ('status', 'grease_type')
    search_fields = ('batch_number', 'grease_type__nomenclatura')

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('batch', 'movement_type', 'quantity_changed', 'movement_date', 'user')
    list_filter = ('movement_type', 'movement_date')
    search_fields = ('batch__batch_number', 'reference', 'reason')
    
    # Make default admin interface strictly read-only for audit history
    readonly_fields = [f.name for f in StockMovement._meta.fields]
    
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
