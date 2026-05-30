from django.urls import path

from . import views

app_name = "licitaciones"

urlpatterns = [
    path("", views.TenderDashboardView.as_view(), name="dashboard"),
    path("procesos/", views.TenderProcessListView.as_view(), name="process_list"),
    path("nuevo/", views.TenderProcessCreateView.as_view(), name="process_create"),
    path("importar/", views.TenderImportView.as_view(), name="process_import"),
    path("<int:pk>/editar/", views.TenderProcessUpdateView.as_view(), name="process_update"),
]
