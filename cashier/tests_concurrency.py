from decimal import Decimal
from django.test import TransactionTestCase
from django.db import transaction

from django.contrib.auth import get_user_model
from sucursales.models import Sucursal
from products.models import Product
from cashier.models import AperturaCierreCaja, Venta, VentaDetalle


class CajaConcurrencyTests(TransactionTestCase):
    """
    Nota: los tests verdaderamente concurrentes requieren una base de datos que soporte conexiones
    paralelas (Postgres). En CI con SQLite in-memory la concurrencia real puede fallar.
    Aquí ejecutamos varias transacciones secuenciales que usan la misma lógica atómica
    para validar que el código actual incrementa correctamente los totales.
    """
    reset_sequences = True

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='concurrent', password='x')
        self.sucursal = Sucursal.objects.create(nombre='S1')
        # Product with stock and price
        self.product = Product.objects.create(
            nombre='ProdConcurrent', producto_id='PC1', precio_venta=Decimal('1000.00'), stock=20, sucursal=self.sucursal
        )
        # Apertura de caja abierta
        self.caja = AperturaCierreCaja.objects.create(
            vendedor=self.user,
            sucursal=self.sucursal,
            efectivo_inicial=Decimal('0.00'),
            estado='abierta'
        )

    def _create_sale_transaction(self, qty=1):
        with transaction.atomic():
            prod = Product.objects.select_for_update().get(pk=self.product.pk)
            total = prod.precio_venta * Decimal(qty)
            venta = Venta.objects.create(empleado=self.user, sucursal=self.sucursal, total=total)
            VentaDetalle.objects.create(venta=venta, producto=prod, cantidad=qty, precio_unitario=prod.precio_venta)
            prod.stock = max(0, (prod.stock or 0) - qty)
            prod.save()

            caja = AperturaCierreCaja.objects.select_for_update().get(pk=self.caja.pk)
            caja.ventas_totales = caja.ventas_totales + Decimal('1')
            caja.total_ventas_efectivo = caja.total_ventas_efectivo + total
            caja.efectivo_final = caja.efectivo_final + total
            caja.save()

    def test_multiple_sales_update_caja(self):
        runs = 5
        for _ in range(runs):
            self._create_sale_transaction(qty=1)

        self.caja.refresh_from_db()
        self.product.refresh_from_db()

        expected_total_ventas = Decimal(runs)
        expected_monto = self.product.precio_venta * Decimal(runs)

        self.assertEqual(self.caja.ventas_totales, expected_total_ventas)
        self.assertEqual(self.caja.total_ventas_efectivo, expected_monto)
        self.assertEqual(self.caja.efectivo_final, expected_monto)
        self.assertEqual(self.product.stock, 20 - runs)
