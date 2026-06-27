from django.urls import path

from . import views

app_name = "licitaciones"

urlpatterns = [
    path("", views.TenderTypeSelectionView.as_view(), name="type_selection"),
    path("nacional/", views.TenderDashboardView.as_view(), name="dashboard"),
    path("procesos/", views.TenderProcessListView.as_view(), name="process_list"),
    path("historial/", views.TenderProcessHistoryView.as_view(), name="process_history"),
    path("nuevo/", views.TenderProcessCreateView.as_view(), name="process_create"),
    path("<int:pk>/", views.TenderProcessDetailView.as_view(), name="process_detail"),
    path("<int:pk>/editar/", views.TenderProcessUpdateView.as_view(), name="process_update"),
    path("exterior/", views.ForeignTenderDashboardView.as_view(), name="foreign_dashboard"),
    path("exterior/procesos/", views.ForeignTenderProcessListView.as_view(), name="foreign_list"),
    path("exterior/nuevo/", views.ForeignTenderProcessCreateView.as_view(), name="foreign_create"),
    path("exterior/<int:pk>/", views.ForeignTenderProcessDetailView.as_view(), name="foreign_detail"),
    path("exterior/<int:pk>/editar/", views.ForeignTenderProcessUpdateView.as_view(), name="foreign_update"),
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
]
