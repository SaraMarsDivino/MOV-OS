#cashier/models.py
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from products.models import Product
from sucursales.models import Sucursal
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

# Modelo de Venta
class Venta(models.Model):
    empleado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='ventas', blank=True, null=True)
    caja = models.ForeignKey('AperturaCierreCaja', on_delete=models.SET_NULL, related_name='ventas', blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    tipo_venta = models.CharField(
        max_length=20,
        choices=[('boleta', 'Boleta Electrónica'), ('factura', 'Factura Electrónica')],
        default='boleta'
    )
    forma_pago = models.CharField(
        max_length=20,
        choices=[
            ('efectivo', 'Efectivo'),
            ('debito', 'Tarjeta de Débito'),
            ('credito', 'Tarjeta de Crédito'),
            ('transferencia', 'Transferencia'),
            ('nota_credito', 'Nota de crédito'),
            ('mixto', 'Mixto')
        ],
        default='efectivo'
    )
    
    cliente_paga = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vuelto_entregado = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    numero_transaccion = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        verbose_name="Número de Transacción"
    )
    banco = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Banco"
    )

    # Store credit (nota de crédito) can be used as full or partial payment.
    nota_credito_usada = models.ForeignKey(
        'NotaCredito',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas',
    )
    monto_nota_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"Venta #{self.id} - Total: {self.total}"


class NotaCredito(models.Model):
    """Saldo interno (store credit) emitido por una devolución y canjeable en el POS."""

    codigo = models.CharField(max_length=32, unique=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='notas_credito')
    monto_emitido = models.DecimalField(max_digits=10, decimal_places=2)
    saldo = models.DecimalField(max_digits=10, decimal_places=2)
    activa = models.BooleanField(default=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota de crédito {self.codigo} - Saldo: {self.saldo}"

    @staticmethod
    def generar_codigo() -> str:
        return uuid.uuid4().hex[:10].upper()


class Devolucion(models.Model):
    """Devolución de una venta. No modifica la venta original."""

    venta_original = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='devoluciones')
    empleado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    caja = models.ForeignKey('AperturaCierreCaja', on_delete=models.SET_NULL, related_name='devoluciones', blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    metodo_pago = models.CharField(
        max_length=20,
        choices=[
            ('efectivo', 'Efectivo'),
            ('debito', 'Tarjeta de Débito'),
            ('credito', 'Tarjeta de Crédito'),
            ('transferencia', 'Transferencia'),
            ('nota_credito', 'Nota de crédito'),
        ],
        default='efectivo',
    )

    numero_transaccion = models.CharField(max_length=100, null=True, blank=True)
    banco = models.CharField(max_length=100, null=True, blank=True)
    nota_credito = models.OneToOneField(NotaCredito, on_delete=models.SET_NULL, null=True, blank=True, related_name='devolucion')

    def __str__(self):
        return f"Devolución #{self.id} - Venta #{self.venta_original_id} - Total: {self.total}"


class DevolucionDetalle(models.Model):
    devolucion = models.ForeignKey(Devolucion, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Product, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    destino = models.CharField(
        max_length=10,
        choices=[('stock', 'Vuelve a stock'), ('merma', 'Merma')],
        default='stock',
    )

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

# Modelo para el detalle de la venta
class VentaDetalle(models.Model):
    venta = models.ForeignKey(Venta, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ventadetalles')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class VentaPago(models.Model):
    """Detalle de pagos asociados a una venta.

    Permite pagos mixtos (múltiples métodos por una misma venta) sin romper
    compatibilidad con los campos legacy en `Venta`.
    """

    venta = models.ForeignKey(Venta, related_name='pagos', on_delete=models.CASCADE)

    metodo = models.CharField(
        max_length=20,
        choices=[
            ('efectivo', 'Efectivo'),
            ('debito', 'Tarjeta de Débito'),
            ('credito', 'Tarjeta de Crédito'),
            ('transferencia', 'Transferencia'),
            ('nota_credito', 'Nota de crédito'),
        ],
    )

    monto = models.DecimalField(max_digits=10, decimal_places=2)
    numero_transaccion = models.CharField(max_length=100, null=True, blank=True)
    banco = models.CharField(max_length=100, null=True, blank=True)
    nota_credito = models.ForeignKey(
        NotaCredito,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos',
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago Venta #{self.venta_id} - {self.metodo}: {self.monto}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['venta'],
                condition=Q(metodo='nota_credito'),
                name='unique_nota_credito_pago_per_venta',
            ),
            models.CheckConstraint(
                check=Q(monto__gte=0),
                name='venta_pago_monto_non_negative',
            ),
        ]

# Modelo de Apertura y Cierre de Caja (actualizado)
class AperturaCierreCaja(models.Model):
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        verbose_name='Vendedor'
    )
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    efectivo_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, default='abierta')  # valores: 'abierta' o 'cerrada'
    apertura = models.DateTimeField(auto_now_add=True)
    cierre = models.DateTimeField(null=True, blank=True)
    # Campos adicionales para el cierre de caja agregados
    ventas_totales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_ventas_efectivo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_ventas_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_ventas_debito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vuelto_entregado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    efectivo_final = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Monto contado físicamente al cerrar la caja (por el cajero)
    efectivo_contado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Diferencia entre lo contado y lo esperado (positivo = sobrante, negativo = faltante)
    descuadre = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"Caja {self.id} - {self.vendedor.username} - {self.estado}"

    class Meta:
        constraints = [
            # Garantiza que sólo exista una caja 'abierta' por sucursal a la vez
            models.UniqueConstraint(
                fields=['sucursal'],
                condition=Q(estado='abierta'),
                name='unique_open_caja_per_sucursal'
            )
        ]

