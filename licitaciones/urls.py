from django.urls import path

from . import views

app_name = "licitaciones"

urlpatterns = [
    path("", views.TenderTypeSelectionView.as_view(), name="type_selection"),
    path("nacional/", views.TenderDashboardView.as_view(), name="dashboard"),
    path("procesos/", views.TenderProcessListView.as_view(), name="process_list"),
    path("historial/", views.TenderProcessHistoryView.as_view(), name="process_history"),
    path("procesos/nuevo/", views.TenderProcessCreateView.as_view(), name="process_create"),
    path("procesos/exportar/csv/", views.export_national_tenders_csv, name="process_export_csv"),
    path("procesos/<int:pk>/", views.TenderProcessDetailView.as_view(), name="process_detail"),
    path("procesos/<int:pk>/editar/", views.TenderProcessUpdateView.as_view(), name="process_update"),
    path("procesos/<int:pk>/etapas/", views.TenderStageManageView.as_view(), name="tender_stages"),
    path("etapas/<int:pk>/editar/", views.TenderStageUpdateView.as_view(), name="stage_update"),
    path("exterior/", views.ForeignTenderDashboardView.as_view(), name="foreign_dashboard"),
    path("exterior/procesos/", views.ForeignTenderProcessListView.as_view(), name="foreign_list"),
    path("exterior/historial/", views.ForeignTenderProcessHistoryView.as_view(), name="foreign_history"),
    path("exterior/nuevo/", views.ForeignTenderProcessCreateView.as_view(), name="foreign_create"),
    path("exterior/<int:pk>/", views.ForeignTenderProcessDetailView.as_view(), name="foreign_detail"),
    path("exterior/<int:pk>/editar/", views.ForeignTenderProcessUpdateView.as_view(), name="foreign_update"),
    path("exterior/<int:pk>/archivo/", views.ForeignTenderArchiveToggleView.as_view(), name="foreign_archive_toggle"),
    path(
        "exterior/<int:process_pk>/requerimientos/nuevo/",
        views.ForeignTenderRequirementCreateView.as_view(),
        name="foreign_requirement_create",
    ),
    path(
        "exterior/requerimientos/<int:pk>/editar/",
        views.ForeignTenderRequirementUpdateView.as_view(),
        name="foreign_requirement_update",
    ),
    path(
        "exterior/<int:process_pk>/novedades/nueva/",
        views.ForeignTenderUpdateCreateView.as_view(),
        name="foreign_update_create",
    ),
    path(
        "exterior/novedades/<int:pk>/editar/",
        views.ForeignTenderUpdateUpdateView.as_view(),
        name="foreign_update_update",
    ),
    path(
        "exterior/<int:process_pk>/ordenes/nueva/",
        views.ForeignTenderPurchaseOrderCreateView.as_view(),
        name="foreign_purchase_order_create",
    ),
    path(
        "exterior/ordenes/<int:pk>/editar/",
        views.ForeignTenderPurchaseOrderUpdateView.as_view(),
        name="foreign_purchase_order_update",
    ),
    path(
        "exterior/ordenes/<int:order_pk>/sp/nueva/",
        views.ForeignProvisionRequestCreateView.as_view(),
        name="foreign_provision_request_create",
    ),
    path(
        "exterior/sp/<int:pk>/editar/",
        views.ForeignProvisionRequestUpdateView.as_view(),
        name="foreign_provision_request_update",
    ),
    path(
        "exterior/borrar/<str:model_type>/<int:pk>/",
        views.ForeignTenderDeleteView.as_view(),
        name="foreign_delete",
    ),
    path("notificacion/<int:pk>/leer/", views.mark_notification_read, name="notification_read"),
]
