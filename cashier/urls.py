#cashier/views.py
from django.urls import path
from . import views
from cashier.views import reporte_venta, cerrar_caja

urlpatterns = [
    path('', views.cashier_dashboard, name='cashier_dashboard'),
    path('historial-ventas/', views.cashier_sales_history, name='cashier_sales_history'),
    path('api/bootstrap/', views.cashier_bootstrap, name='cashier_bootstrap'),
    path('api/nota-credito/validar/', views.validar_nota_credito, name='validar_nota_credito'),
    path('abrir-caja/', views.abrir_caja, name='abrir_caja'),
    path('cerrar_caja/', views.cerrar_caja, name='cerrar_caja'),
    path('buscar-producto/', views.buscar_producto, name='buscar_producto'),
    path('ajustar-cantidad/', views.ajustar_cantidad, name='ajustar_cantidad'),
    path('agregar-al-carrito/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('listar-carrito/', views.listar_carrito, name='listar_carrito'),
    path('limpiar-carrito/', views.limpiar_carrito, name='limpiar_carrito'),
    path('detalle-caja/<int:caja_id>/', views.detalle_caja, name='detalle_caja'),
    path('reporte/<int:venta_id>/', views.reporte_venta, name='reporte_venta'),
    path('reporte/embed/<int:venta_id>/', views.reporte_venta_embed, name='reporte_venta_embed'),
    path('print/venta/<int:venta_id>/', views.print_venta, name='print_venta'),
    path('print/devolucion/<int:devolucion_id>/', views.print_devolucion, name='print_devolucion'),
    path('print/caja/<int:caja_id>/', views.print_caja, name='print_caja'),
    path('devolucion/<int:venta_id>/', views.devolver_venta, name='devolver_venta'),
    path('devolucion/reporte/<int:devolucion_id>/', views.reporte_devolucion, name='reporte_devolucion'),
    path('borrar-historial-caja/', views.delete_all_sales_and_cash_history, name='delete_all_sales_and_cash_history'),
    path('api/heartbeat/', views.offline_heartbeat, name='offline_heartbeat'),
    path('api/offline/catalog-snapshot/', views.offline_catalog_snapshot, name='offline_catalog_snapshot'),
    path('api/offline/sync-sale/', views.offline_sync_sale, name='offline_sync_sale'),
]
