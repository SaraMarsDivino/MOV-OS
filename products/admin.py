from django.contrib import admin
from .models import Product, StockSucursal, TransferenciaStock, AjusteStock

admin.site.register(Product)
admin.site.register(StockSucursal)
admin.site.register(TransferenciaStock)
admin.site.register(AjusteStock)
