from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from sucursales.models import Sucursal
from products.models import Product
from cashier.models import Venta, VentaDetalle, AperturaCierreCaja

User = get_user_model()

def create_sucursal(nombre="Sucursal Test"):
    return Sucursal.objects.create(nombre=nombre)

def create_user(username="user_test", is_staff=True, sucursal=None, **extra):
    user = User.objects.create(username=username, is_staff=is_staff, **extra)
    # Si el modelo User tuviera relación directa a sucursal (no vista aquí), se asignaría.
    return user

def create_product(producto_id="PTEST", nombre="Producto Test", precio_compra=Decimal('1000'), precio_venta=Decimal('2000'), **extra):
    return Product.objects.create(producto_id=producto_id, nombre=nombre, precio_compra=precio_compra, precio_venta=precio_venta, **extra)

def open_caja(vendedor, sucursal, efectivo_inicial=Decimal('0')):
    return AperturaCierreCaja.objects.create(vendedor=vendedor, sucursal=sucursal, efectivo_inicial=efectivo_inicial, estado='abierta')

def close_caja(caja, ventas_totales=None):
    if ventas_totales is None:
        # Recalcular suma de ventas ligadas a la caja
        total = Decimal('0.00')
        for v in caja.ventas.all():
            total += v.total or Decimal('0.00')
        ventas_totales = total
    caja.ventas_totales = ventas_totales
    caja.estado = 'cerrada'
    caja.cierre = timezone.now()
    caja.save(update_fields=['ventas_totales','estado','cierre'])
    return caja

def make_sale(empleado, sucursal, items, forma_pago='efectivo', fecha=None, caja=None):
    """Crea una venta con lista de items [(product, cantidad, precio_unitario_optional)]
    Retorna instancia de Venta.
    """
    if fecha is None:
        fecha = timezone.now()
    total = Decimal('0.00')
    venta = Venta.objects.create(empleado=empleado, sucursal=sucursal, fecha=fecha, total=Decimal('0.00'), forma_pago=forma_pago, caja=caja)
    for it in items:
        if len(it) == 2:
            product, cantidad = it
            precio_unit = product.precio_venta
        else:
            product, cantidad, precio_unit = it
        VentaDetalle.objects.create(venta=venta, producto=product, cantidad=cantidad, precio_unitario=precio_unit)
        total += precio_unit * cantidad
    venta.total = total
    venta.save(update_fields=['total'])
    return venta
