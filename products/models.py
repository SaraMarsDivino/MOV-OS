from django.db import models
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from django.core.validators import MinValueValidator
from sucursales.models import Sucursal

class StockSucursal(models.Model):
    """
    Inventario por Sucursal para un Producto específico.
    Permite manejar cantidades por sucursal y habilita transferencias parciales.
    """
    producto = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='stocks_por_sucursal')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='stocks_de_productos')
    cantidad = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Cantidad en Sucursal")
    permitir_venta_sin_stock = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Permitir Venta sin Stock",
        help_text="Si es null, usa el valor del producto"
    )

    class Meta:
        verbose_name = "Stock por Sucursal"
        verbose_name_plural = "Stocks por Sucursal"
        unique_together = ('producto', 'sucursal')

    def __str__(self):
        return f"{self.producto} @ {self.sucursal} = {self.cantidad}"

class TransferenciaStock(models.Model):
    """Historial de transferencias de stock entre sucursales."""
    producto = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='transferencias')
    origen = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='transferencias_salientes')
    destino = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='transferencias_entrantes')
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Transferencia de Stock'
        verbose_name_plural = 'Transferencias de Stock'

    def __str__(self):
        return f"{self.cantidad} x {self.producto} {self.origen} -> {self.destino} ({self.fecha:%Y-%m-%d %H:%M})"

class AjusteStock(models.Model):
    """Registro de ajustes directos de stock por sucursal (entradas/salidas)."""
    producto = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='ajustes_stock')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='ajustes_stock')
    cantidad_delta = models.IntegerField(verbose_name="Variación de Stock")
    motivo = models.CharField(max_length=255, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Ajuste de Stock'
        verbose_name_plural = 'Ajustes de Stock'

    def __str__(self):
        signo = '+' if (self.cantidad_delta or 0) >= 0 else ''
        return f"{self.producto} @ {self.sucursal}: {signo}{self.cantidad_delta} ({self.fecha:%Y-%m-%d %H:%M})"

class Product(models.Model):
    """
    Modelo simplificado para un producto.
    """
    # Campos solicitados
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Producto", blank=True, null=True)
    descripcion = models.TextField(verbose_name="Descripción", blank=True, null=True)
    producto_id = models.CharField(max_length=255, unique=True, verbose_name="Código 1")
    codigo_alternativo = models.CharField(max_length=255, verbose_name="Código 2", blank=True, null=True)
    fecha_ingreso_producto = models.DateField(verbose_name="Fecha de Ingreso", blank=True, null=True)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Compra", default=Decimal('0.00'))
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Venta", default=Decimal('0.00'))
    
    # Se agregan validadores para que no se acepten valores negativos.
    cantidad = models.IntegerField(
        verbose_name="Cantidad",
        default=0,
        validators=[MinValueValidator(0)]
    )
    stock = models.IntegerField(
        verbose_name="Stock",
        default=0,
        validators=[MinValueValidator(0)]
    )
    codigo_barras = models.CharField(max_length=255, verbose_name="Código de Barras", blank=True, null=True)
    stock_minimo = models.PositiveIntegerField(
        default=5,
        verbose_name="Stock mínimo (alerta)",
        help_text="Cantidad por sucursal por debajo de la cual se genera alerta de stock bajo"
    )
    permitir_venta_sin_stock = models.BooleanField(default=False, verbose_name="Permitir Venta sin Stock")
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='productos', blank=True, null=True)

    def __str__(self):
        return self.nombre if self.nombre else self.producto_id or f"Producto sin nombre ({self.pk})"

    def _format_currency(self, value):
        try:
            # Formatea sin decimales y usa el punto para separar miles
            return "{:,.0f}".format(int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))).replace(",", ".")
        except Exception:
            return value

    @property
    def formatted_precio_compra(self):
        return self._format_currency(self.precio_compra)

    @property
    def formatted_precio_venta(self):
        return self._format_currency(self.precio_venta)

    # Nuevas propiedades para trabajar con IVA:
    @property
    def precio_venta_sin_iva(self):
        """
        Calcula el precio de venta sin IVA.
        Fórmula: Precio total con IVA = Precio sin IVA * 1.19
        """
        if not self.precio_venta:
            return Decimal('0')
        return (self.precio_venta / Decimal('1.19')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    @property
    def formatted_precio_venta_sin_iva(self):
        return self._format_currency(self.precio_venta_sin_iva)

    @property
    def iva_recaudado(self):
        """
        Calcula el monto de IVA recaudado en la venta.
        """
        return self.precio_venta - self.precio_venta_sin_iva

    @property
    def formatted_iva_recaudado(self):
        return self._format_currency(self.iva_recaudado)

    # Nuevas propiedades para Reportes Avanzados:
    @property
    def precio_compra_sin_iva(self):
        """
        Calcula el costo neto (Precio de Compra sin IVA).
        Fórmula: Precio de Compra / 1.19
        """
        if not self.precio_compra:
            return Decimal('0')
        return (self.precio_compra / Decimal('1.19')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    @property
    def formatted_precio_compra_sin_iva(self):
        return self._format_currency(self.precio_compra_sin_iva)

    @property
    def ganancia_neta(self):
        """
        Calcula la ganancia real (utilidad neta) en base a los precios sin IVA.
        Fórmula: ganancia = Precio de Venta sin IVA – Precio de Compra sin IVA
        """
        if self.precio_venta_sin_iva == Decimal('0'):
            return Decimal('0')
        return (self.precio_venta_sin_iva - self.precio_compra_sin_iva).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    @property
    def formatted_ganancia_neta(self):
        return self._format_currency(self.ganancia_neta)

    @property
    def porcentaje_ganancia(self):
        """
        Calcula el porcentaje de ganancia basado en el precio de venta sin IVA.
        Fórmula: (ganancia neta / Precio de Venta sin IVA) * 100
        """
        if self.precio_venta_sin_iva == Decimal('0.00'):
            return Decimal('0.00')
        porcentaje = (self.ganancia_neta / self.precio_venta_sin_iva) * Decimal('100')
        return porcentaje.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def formatted_porcentaje_ganancia(self):
        return f"{self.porcentaje_ganancia}%"

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    # ===== Helpers de stock por sucursal (con fallback al campo 'stock') =====
    def stock_en(self, sucursal: Sucursal) -> int:
        """Cantidad disponible en una sucursal. Prefiere StockSucursal, si no existe, usa el campo 'stock' solo si el producto pertenece a esa sucursal."""
        if not sucursal:
            return 0
        ss = self.stocks_por_sucursal.filter(sucursal=sucursal).first()
        if ss:
            return ss.cantidad or 0
        # Fallback legado
        if self.sucursal_id == sucursal.id:
            return self.stock or 0
        return 0

    def decrementar_stock_en(self, sucursal: Sucursal, cantidad: int) -> None:
        """Disminuye el stock en la sucursal indicada respetando el modelo de inventario por sucursal o el campo legado."""
        if cantidad <= 0:
            return
        ss = self.stocks_por_sucursal.select_for_update().filter(sucursal=sucursal).first()
        if ss:
            ss.cantidad = max(0, (ss.cantidad or 0) - cantidad)
            ss.save()
            return
        # Fallback legado: solo si pertenece a la sucursal
        if self.sucursal_id == sucursal.id:
            self.stock = max(0, (self.stock or 0) - cantidad)
            self.save()

    def incrementar_stock_en(self, sucursal: Sucursal, cantidad: int) -> None:
        """Aumenta el stock en la sucursal indicada respetando StockSucursal o el campo legado."""
        if cantidad <= 0:
            return
        if not sucursal:
            return
        ss = self.stocks_por_sucursal.select_for_update().filter(sucursal=sucursal).first()
        if ss:
            ss.cantidad = (ss.cantidad or 0) + cantidad
            ss.save(update_fields=['cantidad'])
            return
        # Fallback legado: solo si pertenece a la sucursal
        if self.sucursal_id == sucursal.id:
            self.stock = (self.stock or 0) + cantidad
            self.save(update_fields=['stock'])

    def permitir_venta_sin_stock_en(self, sucursal: Sucursal) -> bool:
        """Devuelve si se permite vender sin stock en la sucursal indicada.

        Regla: si hay override por sucursal, se usa; si no, se usa el valor global del producto.
        """
        if not sucursal:
            return bool(self.permitir_venta_sin_stock)
        ss = self.stocks_por_sucursal.filter(sucursal=sucursal).first()
        if ss and ss.permitir_venta_sin_stock is not None:
            return bool(ss.permitir_venta_sin_stock)
        return bool(self.permitir_venta_sin_stock)

    def asignado_a_sucursal(self, sucursal: Sucursal) -> bool:
        """Indica si el producto esta asignado a la sucursal (FK o StockSucursal)."""
        if not sucursal:
            return False
        if self.sucursal_id == sucursal.id:
            return True
        return self.stocks_por_sucursal.filter(sucursal=sucursal).exists()