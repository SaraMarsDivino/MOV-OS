#products/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('management/', views.product_management, name='product_management'),
    path('api/products/', views.api_products_list, name='api_products_list'),
    path('create/', views.create_or_edit_product, name='create_product'),
    path('edit/<int:product_id>/', views.create_or_edit_product, name='edit_product'),
    path('delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('set-active/<int:product_id>/', views.set_product_active, name='set_product_active'),
    path('upload/', views.upload_products, name='upload_products'),
    path('template/', views.download_template, name='download_template'),
    path('delete-all/', views.delete_all_products, name='delete_all_products'),
    path('bulk-delete/', views.bulk_delete_products, name='bulk_delete_products'),
    path('exportar/excel/', views.export_products_to_excel, name='export_products_to_excel'),
    path('bulk-assign/', views.bulk_assign_products, name='bulk_assign_products'),
    path('transfer/', views.transfer_stock, name='transfer_stock'),
    path('api/transfer/', views.api_do_transfer, name='api_do_transfer'),
    path('api/transfer/history/', views.api_transfer_history_json, name='api_transfer_history_json'),
    path('stock/availability/', views.stock_availability, name='stock_availability'),
    path('stock/allow-report/', views.allow_without_stock_report, name='allow_without_stock_report'),
    path('transfer/history/', views.transfer_history, name='transfer_history'),
    path('stock/adjust/', views.ajustar_stock, name='ajustar_stock'),
    path('stock/adjust/history/', views.adjust_history, name='adjust_history'),
]
