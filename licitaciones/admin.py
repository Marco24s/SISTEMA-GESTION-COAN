from django.contrib import admin

from .models import ProcurementDestination, TenderProcess


@admin.register(ProcurementDestination)
class ProcurementDestinationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(TenderProcess)
class TenderProcessAdmin(admin.ModelAdmin):
    list_display = (
        "process_number",
        "unit",
        "destination",
        "year",
        "status",
        "process_type",
        "amount_ars",
        "has_oca",
        "opening_date",
    )
    list_filter = ("year", "unit", "destination", "status", "process_type", "has_oca")
    search_fields = ("process_number", "expediente", "name")
    readonly_fields = ("created_at", "updated_at", "created_by")
