from django.contrib import admin

from .models import (
    ItemClassification,
    ItemSystem,
    PyrotechnicAssignment,
    PyrotechnicCatalogItem,
    PyrotechnicCatalogLifeRule,
    PyrotechnicMovement,
    PyrotechnicPhysicalItem,
    PyrotechnicStorageLocation,
    SupervivenciaDeletionLog,
    SurvivalMedium,
)

@admin.register(ItemClassification)
class ItemClassificationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)

@admin.register(ItemSystem)
class ItemSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "classification", "is_active")
    list_filter = ("classification", "is_active")
    search_fields = ("name", "classification__name")

@admin.register(SurvivalMedium)
class SurvivalMediumAdmin(admin.ModelAdmin):
    list_display = ("identifier", "name", "medium_type", "model", "unit", "is_active")
    list_filter = ("medium_type", "unit", "is_active")
    search_fields = ("identifier", "name", "model", "unit__name")


class PyrotechnicCatalogLifeRuleInline(admin.TabularInline):
    model = PyrotechnicCatalogLifeRule
    extra = 1


@admin.register(PyrotechnicCatalogItem)
class PyrotechnicCatalogItemAdmin(admin.ModelAdmin):
    list_display = ("nomenclature", "system", "part_number", "nsn", "is_active")
    list_filter = ("system__classification", "system", "is_active")
    search_fields = ("nomenclature", "system__name", "system__classification__name", "part_number", "nsn", "alternate_part_number", "alternate_nsn")
    inlines = [PyrotechnicCatalogLifeRuleInline]


@admin.register(PyrotechnicCatalogLifeRule)
class PyrotechnicCatalogLifeRuleAdmin(admin.ModelAdmin):
    list_display = ("catalog_item", "situation", "duration_value", "duration_unit")
    list_filter = ("situation", "duration_unit")
    search_fields = ("catalog_item__nomenclature", "catalog_item__system__name", "notes")


@admin.register(PyrotechnicPhysicalItem)
class PyrotechnicPhysicalItemAdmin(admin.ModelAdmin):
    list_display = (
        "catalog_item",
        "serial_number",
        "lot_number",
        "lot_quantity",
        "expiration_date",
        "condition",
        "operational_status",
        "current_storage_location",
        "current_location",
        "is_active",
    )
    list_filter = ("condition", "operational_status", "current_storage_location", "expiration_date", "is_active")
    search_fields = (
        "catalog_item__nomenclature",
        "catalog_item__system__name",
        "serial_number",
        "lot_number",
        "manufacturer",
        "current_location",
        "current_storage_location__code",
        "current_storage_location__name",
        "certificate_reference",
    )
    autocomplete_fields = ("catalog_item", "current_storage_location", "created_by")


@admin.register(PyrotechnicStorageLocation)
class PyrotechnicStorageLocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "unit", "is_restricted", "is_active")
    list_filter = ("name", "unit", "is_restricted", "is_active")
    search_fields = ("code", "name", "unit__name", "notes")


@admin.register(PyrotechnicAssignment)
class PyrotechnicAssignmentAdmin(admin.ModelAdmin):
    list_display = ("medium", "physical_item", "installed_at", "position", "is_active", "removed_at")
    list_filter = ("is_active", "installed_at", "removed_at", "medium")
    search_fields = (
        "medium__identifier",
        "medium__name",
        "physical_item__catalog_item__nomenclature",
        "physical_item__serial_number",
        "physical_item__lot_number",
        "position",
        "notes",
    )
    autocomplete_fields = ("medium", "physical_item", "created_by")


@admin.register(PyrotechnicMovement)
class PyrotechnicMovementAdmin(admin.ModelAdmin):
    list_display = ("movement_date", "movement_type", "physical_item", "medium", "from_reference", "to_reference")
    list_filter = ("movement_type", "movement_date", "medium")
    search_fields = (
        "physical_item__catalog_item__nomenclature",
        "physical_item__serial_number",
        "physical_item__lot_number",
        "medium__identifier",
        "medium__name",
        "from_reference",
        "to_reference",
        "notes",
    )
    autocomplete_fields = ("physical_item", "medium", "assignment", "created_by")


@admin.register(SupervivenciaDeletionLog)
class SupervivenciaDeletionLogAdmin(admin.ModelAdmin):
    list_display = ("deleted_at", "object_type", "object_id", "object_repr", "deleted_by")
    list_filter = ("object_type", "deleted_at")
    search_fields = ("object_type", "object_id", "object_repr", "deleted_by__username")
    readonly_fields = ("object_type", "object_id", "object_repr", "deleted_by", "deleted_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
