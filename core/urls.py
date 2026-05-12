from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal, name='portal'),
    path('sgap/', views.home, name='home'),
    
    # Units
    path('units/', views.UnitListView.as_view(), name='unit_list'),
    path('units/add/', views.UnitCreateView.as_view(), name='unit_create'),
    path('units/<int:pk>/edit/', views.UnitUpdateView.as_view(), name='unit_update'),
    path('units/<int:pk>/delete/', views.UnitDeleteView.as_view(), name='unit_delete'),
    
    # Measurement Units (Configuration)
    path('config/measurement-units/', views.MeasurementUnitListView.as_view(), name='measurementunit_list'),
    path('config/measurement-units/add/', views.MeasurementUnitCreateView.as_view(), name='measurementunit_create'),
    path('config/measurement-units/<int:pk>/edit/', views.MeasurementUnitUpdateView.as_view(), name='measurementunit_update'),
    path('config/measurement-units/<int:pk>/delete/', views.MeasurementUnitDeleteView.as_view(), name='measurementunit_delete'),
    
    # Aircraft Models
    path('aircrafts/', views.AircraftListView.as_view(), name='aircraft_list'),
    path('aircrafts/add/', views.AircraftCreateView.as_view(), name='aircraft_create'),
    path('aircrafts/<int:pk>/edit/', views.AircraftUpdateView.as_view(), name='aircraft_update'),
    path('aircrafts/<int:pk>/delete/', views.AircraftDeleteView.as_view(), name='aircraft_delete'),
    
    # Grease Types
    path('greases/', views.GreaseTypeListView.as_view(), name='grease_list'),
    path('greases/add/', views.GreaseTypeCreateView.as_view(), name='grease_create'),
    path('greases/<int:pk>/edit/', views.GreaseTypeUpdateView.as_view(), name='grease_update'),
    path('greases/<int:pk>/delete/', views.GreaseTypeDeleteView.as_view(), name='grease_delete'),
    path('greases/<int:pk>/prices/', views.GreaseReferencePriceListView.as_view(), name='grease_price_list'),
    path('greases/<int:pk>/prices/add/', views.GreaseReferencePriceCreateView.as_view(), name='grease_price_create'),
    path('greases/prices/<int:pk>/edit/', views.GreaseReferencePriceUpdateView.as_view(), name='grease_price_update'),
    path('greases/prices/<int:pk>/delete/', views.GreaseReferencePriceDeleteView.as_view(), name='grease_price_delete'),
    
    # Aircraft - Grease Associations
    path('associations/', views.AircraftGreaseListView.as_view(), name='association_list'),
    path('associations/add/', views.AircraftGreaseCreateView.as_view(), name='association_create'),
    path('associations/<int:pk>/edit/', views.AircraftGreaseUpdateView.as_view(), name='association_update'),
    path('associations/<int:pk>/delete/', views.AircraftGreaseDeleteView.as_view(), name='association_delete'),
    
    # Flight Plans
    path('flightplans/', views.FlightPlanListView.as_view(), name='flightplan_list'),
    path('flightplans/add/', views.FlightPlanCreateView.as_view(), name='flightplan_create'),
    path('flightplans/<int:pk>/edit/', views.FlightPlanUpdateView.as_view(), name='flightplan_update'),
    path('flightplans/<int:pk>/delete/', views.FlightPlanDeleteView.as_view(), name='flightplan_delete'),
    
    # Stock Management & Batches
    path('stock/', views.GreaseBatchListView.as_view(), name='batch_list'),
    path('stock/archived/', views.ArchivedBatchListView.as_view(), name='batch_archived_list'),
    path('stock/<int:pk>/archive/', views.ArchiveBatchView.as_view(), name='batch_archive'),
    path('stock/add/', views.GreaseBatchCreateView.as_view(), name='batch_create'),
    path('stock/<int:pk>/movements/', views.GreaseBatchDetailView.as_view(), name='batch_detail'),
    path('stock/<int:pk>/edit/', views.GreaseBatchUpdateView.as_view(), name='batch_update'),
    path('stock/<int:pk>/delete/', views.GreaseBatchDeleteView.as_view(), name='batch_delete'),
    path('stock/<int:pk>/start-retest/', views.StartRetestView.as_view(), name='batch_start_retest'),
    path('stock/<int:pk>/retest/', views.RetestBatchView.as_view(), name='batch_retest'),
    path('stock/consume/', views.ConsumeGreaseView.as_view(), name='consume_grease'),
    
    # Flight Hours Calculator
    path('tools/flight-hours/', views.FlightHoursCalculatorView.as_view(), name='flight_hours_calculator'),

    # Procurement Forecasting
    path('procurement/', views.ProcurementForecastingView.as_view(), name='procurement_forecast'),
    path('procurement/export/', views.export_procurement_forecast_csv, name='export_procurement_forecast_csv'),
    path('procurement/export/pdf/', views.export_procurement_forecast_pdf, name='export_procurement_forecast_pdf'),
    
    # Procurement Requirements
    path('procurement/requirements/', views.ProcurementRequirementListView.as_view(), name='requirement_list'),
    path('procurement/requirements/add/<int:grease_type_id>/', views.CreateRequirementFromForecastView.as_view(), name='requirement_create_from_forecast'),
    path('procurement/requirements/<int:pk>/edit/', views.ProcurementRequirementUpdateView.as_view(), name='requirement_update'),
    path('procurement/requirements/<int:pk>/delete/', views.ProcurementRequirementDeleteView.as_view(), name='requirement_delete'),
    path('procurement/requirements/export/', views.export_requirements_csv, name='export_requirements_csv'),
    
    # Exports
    path('stock/export/', views.export_grease_batches_csv, name='export_grease_batches_csv'),
    path('stock/export/pdf/', views.export_grease_batches_pdf, name='export_grease_batches_pdf'),
]
