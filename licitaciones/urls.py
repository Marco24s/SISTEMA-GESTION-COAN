from django.urls import path

from . import views

app_name = "licitaciones"

urlpatterns = [
    path("", views.TenderDashboardView.as_view(), name="dashboard"),
    path("procesos/", views.TenderProcessListView.as_view(), name="process_list"),
    path("historial/", views.TenderProcessHistoryView.as_view(), name="process_history"),
    path("nuevo/", views.TenderProcessCreateView.as_view(), name="process_create"),
    path("<int:pk>/", views.TenderProcessDetailView.as_view(), name="process_detail"),
    path("<int:pk>/editar/", views.TenderProcessUpdateView.as_view(), name="process_update"),
]
