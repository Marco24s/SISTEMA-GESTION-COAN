from django.urls import path

from . import views


app_name = "supervivencia"

urlpatterns = [
    path("", views.SupervivenciaDashboardView.as_view(), name="dashboard"),
    path("administracion/borrado/", views.SupervivenciaAdminDeleteView.as_view(), name="admin_delete"),
    path(
        "administracion/borrado/<str:model_type>/<int:pk>/",
        views.SupervivenciaAdminDeleteConfirmView.as_view(),
        name="admin_delete_confirm",
    ),
    path("medios/", views.SurvivalMediumListView.as_view(), name="medium_list"),
    path("medios/nuevo/", views.SurvivalMediumCreateView.as_view(), name="medium_create"),
    path("medios/<int:pk>/", views.SurvivalMediumDetailView.as_view(), name="medium_detail"),
    path("medios/<int:pk>/editar/", views.SurvivalMediumUpdateView.as_view(), name="medium_update"),
    path("medios/<int:pk>/eliminar/", views.medium_delete, name="medium_delete"),
    path("catalogo/", views.PyrotechnicCatalogListView.as_view(), name="catalog_list"),
    path("catalogo/nuevo/", views.PyrotechnicCatalogCreateView.as_view(), name="catalog_create"),
    path("catalogo/<int:pk>/editar/", views.PyrotechnicCatalogUpdateView.as_view(), name="catalog_update"),
    path("catalogo/<int:pk>/eliminar/", views.catalog_delete, name="catalog_delete"),
    path("material/", views.PyrotechnicPhysicalItemListView.as_view(), name="physical_item_list"),
    path("material/nuevo/", views.PyrotechnicPhysicalItemCreateView.as_view(), name="physical_item_create"),
    path("material/<int:pk>/", views.PyrotechnicPhysicalItemDetailView.as_view(), name="physical_item_detail"),
    path("material/<int:pk>/movimiento/", views.PyrotechnicPhysicalItemMovementView.as_view(), name="physical_item_movement"),
    path("material/<int:pk>/editar/", views.PyrotechnicPhysicalItemUpdateView.as_view(), name="physical_item_update"),
    path("material/<int:pk>/eliminar/", views.physical_item_delete, name="physical_item_delete"),
    path(
        "administracion/material/<int:pk>/borrado-forzado/",
        views.PyrotechnicPhysicalItemForceDeleteView.as_view(),
        name="physical_item_force_delete",
    ),
    path("asignaciones/", views.PyrotechnicAssignmentListView.as_view(), name="assignment_list"),
    path("asignaciones/nueva/", views.PyrotechnicAssignmentCreateView.as_view(), name="assignment_create"),
    path("asignaciones/<int:pk>/editar/", views.PyrotechnicAssignmentUpdateView.as_view(), name="assignment_update"),
    path("asignaciones/<int:pk>/eliminar/", views.assignment_delete, name="assignment_delete"),
    path("movimientos/", views.PyrotechnicMovementListView.as_view(), name="movement_list"),
    path("ubicaciones/", views.PyrotechnicStorageLocationListView.as_view(), name="location_list"),
    path("ubicaciones/nueva/", views.PyrotechnicStorageLocationCreateView.as_view(), name="location_create"),
    path("ubicaciones/<int:pk>/editar/", views.PyrotechnicStorageLocationUpdateView.as_view(), name="location_update"),
    path("ubicaciones/<int:pk>/eliminar/", views.location_delete, name="location_delete"),
]
