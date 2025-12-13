from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client
import threading, json, time

from tests.factories import (
	create_user, create_sucursal, create_product,
	open_caja, close_caja, make_sale
)
from cashier.models import Venta, AperturaCierreCaja
from django.db.models import Sum

User = get_user_model()


class CashierFlowTests(TestCase):
	def setUp(self):
		self.sucursal = create_sucursal("Sucursal Central")
		self.user_admin = create_user("admin_user", is_staff=True)
		self.user_cajero = create_user("cajero_user", is_staff=False)
		self.prod_a = create_product("PX1", "Producto X", precio_compra=Decimal('1000'), precio_venta=Decimal('2500'))
		self.prod_b = create_product("PY1", "Producto Y", precio_compra=Decimal('700'), precio_venta=Decimal('2000'))

	def test_open_sale_close_caja_flow(self):
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('5000'))
		self.assertEqual(caja.estado, 'abierta')
		v1 = make_sale(self.user_admin, self.sucursal, [(self.prod_a, 2), (self.prod_b, 1)], forma_pago='efectivo', caja=caja)
		v2 = make_sale(self.user_admin, self.sucursal, [(self.prod_b, 3)], forma_pago='debito', caja=caja)
		self.assertGreater(v1.total, 0)
		self.assertGreater(v2.total, 0)
		close_caja(caja)
		caja.refresh_from_db()
		self.assertEqual(caja.estado, 'cerrada')
		total_ventas = sum(v.total for v in Venta.objects.filter(caja=caja))
		self.assertEqual(caja.ventas_totales, total_ventas)

	def test_ranking_cajeros_basic(self):
		caja1 = open_caja(self.user_admin, self.sucursal)
		# Solo una caja abierta por sucursal (constraint); ventas de cajero_user sin caja propia si no se puede abrir otra
		make_sale(self.user_admin, self.sucursal, [(self.prod_a, 1)], caja=caja1)
		make_sale(self.user_admin, self.sucursal, [(self.prod_b, 2)], caja=caja1)
		close_caja(caja1)
		self.client.force_login(self.user_admin)
		fi = (timezone.now() - timezone.timedelta(days=2)).strftime('%Y-%m-%d')
		ff = timezone.now().strftime('%Y-%m-%d')
		resp = self.client.get('/reports/advanced/data/', {
			'fecha_inicio': fi,
			'fecha_fin': ff
		})
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertIn('ranking_cajeros', data)
		self.assertTrue(len(data['ranking_cajeros']) >= 1)

	def test_permission_reports_denied_for_non_staff(self):
		caja = open_caja(self.user_cajero, self.sucursal)
		make_sale(self.user_cajero, self.sucursal, [(self.prod_a, 1)], caja=caja)
		self.client.force_login(self.user_cajero)
		resp = self.client.get('/reports/advanced/', follow=False)
		self.assertNotEqual(resp.status_code, 200, "Un usuario no staff no debería ver reports avanzados")

	def test_efectivo_final_calculation(self):
		# Abrir caja con efectivo inicial, crear ventas en efectivo y con tarjeta, cerrar caja vía endpoint
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('10000'))
		# Venta en efectivo 1
		v1 = make_sale(self.user_admin, self.sucursal, [(self.prod_a, 2)], forma_pago='efectivo', caja=caja)
		# Venta en efectivo 2 (con vuelto simulado por total > cliente_paga handled by view, but here we set total directly)
		v2 = make_sale(self.user_admin, self.sucursal, [(self.prod_b, 1)], forma_pago='efectivo', caja=caja)
		# Venta en tarjeta (no afecta efectivo final)
		v3 = make_sale(self.user_admin, self.sucursal, [(self.prod_b, 1)], forma_pago='debito', caja=caja)
		self.client.force_login(self.user_admin)
		resp = self.client.post('/cashier/cerrar_caja/', data='{"caja_id": %d}' % caja.id, content_type='application/json')
		self.assertEqual(resp.status_code, 200)
		caja.refresh_from_db()
		# Calcular ventas en efectivo esperadas
		expected_ventas_efectivo = Venta.objects.filter(caja=caja, forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
		expected_efectivo_final = (caja.efectivo_inicial or Decimal('0.00')) + expected_ventas_efectivo
		self.assertEqual(caja.efectivo_final, expected_efectivo_final)

	def test_concurrent_sales_decrement_stock(self):
		"""Simula dos ventas concurrentes contra el mismo producto y valida stock final."""
		# Producto con stock 1 (legacy stock field)
		prod = create_product("PXC", "ConcurrentProd", precio_compra=Decimal('100'), precio_venta=Decimal('500'), stock=1)
		caja = open_caja(self.user_admin, self.sucursal)

		def worker(result_list, idx):
			client = Client()
			client.force_login(self.user_admin)
			# establecer caja en sesión
			s = client.session
			s['caja_id'] = caja.id
			s.save()
			body = {
				'carrito': [{'producto_id': prod.id, 'cantidad': 1}],
				'tipo_venta': 'boleta',
				'forma_pago': 'efectivo',
				'cliente_paga': '500'
			}
			resp = client.post('/cashier/', data=json.dumps(body), content_type='application/json')
			result_list.append((idx, resp.status_code, resp.json() if resp.status_code==200 else resp.content.decode('utf-8')))

		results = []
		t1 = threading.Thread(target=worker, args=(results, 1))
		t2 = threading.Thread(target=worker, args=(results, 2))
		t1.start(); t2.start()
		t1.join(); t2.join()
		# DEBUG: mostrar resultados
		print("DEBUG concurrent results:", results)
		prod.refresh_from_db()
		print("DEBUG prod.stock after concurrent attempts:", prod.stock)
		# Asegurarse que el stock no quedó negativo y que no hubo errores fatales
		self.assertGreaterEqual(prod.stock, 0)
		# Registrar cuántas respuestas 200 obtuvimos (opcional)
		successes = [r for r in results if r[1] == 200]
		print("DEBUG successes_count:", len(successes))

	def test_multi_thread_sales_limit(self):
		"""Lanzar múltiples threads contra el mismo producto con stock limitado.
		Asegurar que no se vendan más unidades que el stock inicial.
		"""
		initial_stock = 3
		threads = 8
		prod = create_product("PXM", "MultiProd", precio_compra=Decimal('100'), precio_venta=Decimal('500'), stock=initial_stock, permitir_venta_sin_stock=False)
		caja = open_caja(self.user_admin, self.sucursal)

		results = []

		def worker(idx):
			client = Client()
			client.force_login(self.user_admin)
			s = client.session
			s['caja_id'] = caja.id
			s.save()
			body = {
				'carrito': [{'producto_id': prod.id, 'cantidad': 1}],
				'tipo_venta': 'boleta',
				'forma_pago': 'efectivo',
				'cliente_paga': '500'
			}
			resp = client.post('/cashier/', data=json.dumps(body), content_type='application/json')
			try:
				success = resp.status_code == 200 and resp.json().get('success')
			except Exception:
				success = resp.status_code == 200
			results.append(success)

		ts = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
		for t in ts: t.start()
		for t in ts: t.join()

		prod.refresh_from_db()
		sold = sum(1 for r in results if r)
		# No se pueden vender más que initial_stock
		self.assertLessEqual(sold, initial_stock)
		self.assertEqual(prod.stock, max(0, initial_stock - sold))
