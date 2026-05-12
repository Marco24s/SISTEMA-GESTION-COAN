from django.urls import path
from . import views

app_name = 'sigera'

urlpatterns = [
    path('', views.home, name='home'),
    path('stock/', views.stock_list, name='stock_list'),
    path('stock/size/<int:size_id>/', views.size_batch_detail, name='size_batch_detail'),
    path('personnel/', views.personnel_list, name='personnel_list'),
    path('personnel/import/', views.personnel_import, name='personnel_import'),
    path('personnel/new/', views.personnel_create, name='personnel_create'),
    path('personnel/<int:pk>/edit/', views.personnel_edit, name='personnel_edit'),
    path('personnel/<int:pk>/delete/', views.personnel_delete, name='personnel_delete'),
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/new/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/return/', views.assignment_return_view, name='assignment_return'),
    path('catalog/', views.catalog_list, name='catalog_list'),
    path('catalog/new/', views.catalog_create, name='catalog_create'),
    path('catalog/size/new/', views.catalog_size_create, name='catalog_size_create'),
    path('catalog/size/<int:pk>/edit/', views.catalog_size_edit, name='catalog_size_edit'),
    path('catalog/size/<int:pk>/delete/', views.catalog_size_delete, name='catalog_size_delete'),
    path('batch/new/', views.batch_create, name='batch_create'),
    path('batch/<int:pk>/movements/', views.batch_movements, name='batch_movements'),
]
