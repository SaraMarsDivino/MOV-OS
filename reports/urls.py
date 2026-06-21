from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('dashboard/', views.report_dashboard, name='report_dashboard'),
    path('advanced/', views.advanced_reports, name='advanced_reports'),
    path('advanced/data/', views.advanced_reports_data, name='advanced_reports_data'),
    path('advanced/compute/', views.compute_analytics_api, name='compute_analytics_api'),
    path('sales/dashboard/', views.sales_dashboard, name='sales_dashboard'),
    path('sales/history/', views.sales_history, name='sales_history'),
    path('sales/history/export/', views.export_sales_history_excel, name='export_sales_history_excel'),
    path('returns/history/', views.returns_history, name='returns_history'),
    path('sales/<int:sale_id>/reporte/', views.sales_report, name='sales_report'),
    path('cash/history/', views.cash_history, name='historial_caja'),
    path('caja/<int:caja_id>/reporte/', views.caja_report, name='caja_report'),
    path('refresh-csrf/', views.refresh_csrf, name='refresh_csrf'),
    path('limpiar_historial/', views.limpiar_historial_caja, name='limpiar_historial_caja'),
    path('limpiar_historial_ventas/', views.limpiar_historial_ventas, name='limpiar_historial_ventas'),

    # Análisis de mercado
    path('market/', views.market_analysis, name='market_analysis'),
    path('market/overview/', views.market_overview_api, name='market_overview_api'),
    path('market/heatmap/', views.market_heatmap_api, name='market_heatmap_api'),
    path('market/branch-comparison/', views.market_branch_comparison_api, name='market_branch_comparison_api'),
    path('market/monthly-trend/', views.market_monthly_trend_api, name='market_monthly_trend_api'),
    path('market/top-products/', views.market_top_products_api, name='market_top_products_api'),
    path('market/top-margin/', views.market_top_margin_products_api, name='market_top_margin_products_api'),
    path('market/zombie-products/', views.market_zombie_products_api, name='market_zombie_products_api'),
    path('market/pareto/', views.market_pareto_api, name='market_pareto_api'),
    path('market/weekend-vs-weekday/', views.market_weekend_vs_weekday_api, name='market_weekend_vs_weekday_api'),


]
