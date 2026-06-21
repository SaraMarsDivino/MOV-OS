from django.urls import path
from . import views

app_name = 'sucursales'

urlpatterns = [
    path('', views.sucursal_list, name='sucursal_list'),
    path('api/list/', views.api_sucursales_list, name='api_sucursales_list'),
    path('create/', views.create_sucursal, name='create_sucursal'),
    path('edit/<int:pk>/', views.edit_sucursal, name='edit_sucursal'),
    path('<int:sucursal_id>/productos/', views.sucursal_products, name='sucursal_products'),
    path('api/<int:pk>/', views.api_sucursal_detail, name='api_sucursal_detail'),
    path('api/<int:pk>/update/', views.api_sucursal_update, name='api_sucursal_update'),
    path('api/<int:pk>/toggle-activo/', views.api_sucursal_toggle_activo, name='api_sucursal_toggle_activo'),
    path('api/<int:pk>/delete/', views.api_sucursal_delete, name='api_sucursal_delete'),
    path('api/create/', views.api_sucursal_create, name='api_sucursal_create'),
]