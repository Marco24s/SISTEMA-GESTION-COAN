from django.contrib import admin

from .models import (
    ForeignTenderProcess,
    ForeignTenderPurchaseOrder,
    ForeignTenderRequirement,
    ForeignTenderUpdate,
    ProcurementDestination,
    TenderProcess,
)


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
        "classification",
        "amount_ars",
        "has_oca",
        "opening_date",
    )
    list_filter = ("year", "unit", "destination", "status", "process_type", "classification", "has_oca")
    search_fields = ("process_number", "expediente", "name")
    readonly_fields = ("created_at", "updated_at", "created_by")


class ForeignTenderRequirementInline(admin.TabularInline):
    model = ForeignTenderRequirement
    extra = 0


class ForeignTenderUpdateInline(admin.TabularInline):
    model = ForeignTenderUpdate
    extra = 0


class ForeignTenderPurchaseOrderInline(admin.TabularInline):
    model = ForeignTenderPurchaseOrder
    extra = 0


@admin.register(ForeignTenderProcess)
class ForeignTenderProcessAdmin(admin.ModelAdmin):
    list_display = ("process_number", "expediente", "year", "currency", "status", "has_oca", "evaluation_amount", "awarded_amount")
    list_filter = ("year", "currency", "status", "has_oca")
    search_fields = ("process_number", "expediente", "requirements__requirement_number", "requirements__description")
    readonly_fields = ("created_at", "updated_at", "created_by")
    inlines = (ForeignTenderRequirementInline, ForeignTenderPurchaseOrderInline, ForeignTenderUpdateInline)
