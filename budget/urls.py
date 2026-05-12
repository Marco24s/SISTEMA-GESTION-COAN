from django.urls import path
from . import views

app_name = 'budget'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('statistics/', views.budget_statistics, name='statistics'),
    
    # Ejercicios
    path('fiscal-years/', views.fiscal_year_list, name='fiscal_year_list'),
    path('fiscal-years/create/', views.fiscal_year_create, name='fiscal_year_create'),
    path('fiscal-years/<int:pk>/edit/', views.fiscal_year_update, name='fiscal_year_update'),
    path('fiscal-years/<int:pk>/close/', views.fiscal_year_close, name='fiscal_year_close'),
    
    # Créditos (AA.PP.)
    path('credits/', views.credit_list, name='credit_list'),
    path('credits/create/', views.credit_create, name='credit_create'),
    path('credits/type-log/', views.credit_type_log, name='credit_type_log'),
    path('credits/<int:pk>/unassign-type/', views.credit_unassign_type, name='credit_unassign_type'),
    path('credits/<int:pk>/detail/', views.credit_detail, name='credit_detail'),
    path('credits/<int:pk>/adjust/', views.credit_adjust, name='credit_adjust'),
    path('credits/<int:pk>/delete/', views.credit_delete, name='credit_delete'),
    path('credits/bulk-delete/', views.credit_bulk_delete, name='credit_bulk_delete'),
    
    # Distribución (UU.CC.)
    path('allocations/', views.allocation_list, name='allocation_list'),
    path('allocations/create/', views.allocation_create, name='allocation_create'),
    path('allocations/<int:pk>/delete/', views.allocation_delete, name='allocation_delete'),
    path('allocations/bulk-delete/', views.allocation_bulk_delete, name='allocation_bulk_delete'),
    
    # Ejecución (Flujo Secuencial)
    path('executions/', views.execution_list, name='execution_list'),
    path('executions/commitment/', views.execution_step_commitment, name='execution_commitment'),
    path('executions/<int:pk>/accrual/', views.execution_step_accrual, name='execution_accrual'),
    path('executions/<int:pk>/payment/', views.execution_step_payment, name='execution_payment'),
    path('executions/<int:pk>/detail/', views.execution_detail, name='execution_detail'),
    path('executions/<int:pk>/release-surplus/', views.execution_release_surplus, name='execution_release_surplus'),
    path('executions/<int:pk>/delete/', views.execution_delete, name='execution_delete'),
    path('executions/export/rendicion/', views.export_rendicion_csv, name='export_rendicion_csv'),
    
    # Configuración / Nomencladores
    path('config/', views.nomenclature_dashboard, name='nomenclature_dashboard'),
    path('config/<str:catalog_type>/', views.nomenclature_list, name='nomenclature_list'),
    path('config/<str:catalog_type>/add/', views.nomenclature_create, name='nomenclature_create'),
    path('config/<str:catalog_type>/<int:pk>/edit/', views.nomenclature_update, name='nomenclature_update'),
    path('config/<str:catalog_type>/<int:pk>/delete/', views.nomenclature_delete, name='nomenclature_delete'),
    path('config-seed/tipo-gasto/', views.seed_tipo_gasto, name='seed_tipo_gasto'),
    
    # Clasificaciones Personalizadas
    path('classifications/', views.classification_list, name='classification_list'),
    path('classifications/create/', views.classification_create, name='classification_create'),
    path('classifications/<int:pk>/edit/', views.classification_update, name='classification_update'),
    path('classifications/<int:pk>/delete/', views.classification_delete, name='classification_delete'),
    path('classifications/<int:pk>/assign/', views.classification_assign, name='classification_assign'),
    path('classifications/<int:pk>/detail/', views.classification_detail, name='classification_detail'),

    # Compensaciones de Partidas
    path('compensaciones/', views.compensacion_list, name='compensacion_list'),
    path('compensaciones/create/', views.compensacion_create, name='compensacion_create'),
    path('compensaciones/<int:pk>/approve/', views.compensacion_approve, name='compensacion_approve'),
]
