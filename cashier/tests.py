from django.test import TestCase, override_settings
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client
import threading, json, time

from tests.factories import (
	create_user, create_sucursal, create_product,
	open_caja, close_caja, make_sale
)
from cashier.models import Venta, VentaDetalle, AperturaCierreCaja, NotaCredito, Devolucion
from cashier.models import VentaPago
from django.db.models import Sum
from django.db import connection

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
		# Enviar el monto contado (igual al esperado) para que no haya descuadre en la prueba
		expected_ventas_efectivo = Venta.objects.filter(caja=caja, forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
		expected_efectivo_final = (caja.efectivo_inicial or Decimal('0.00')) + expected_ventas_efectivo
		payload = json.dumps({'caja_id': caja.id, 'efectivo_contado': str(expected_efectivo_final)})
		resp = self.client.post('/cashier/cerrar_caja/', data=payload, content_type='application/json')
		self.assertEqual(resp.status_code, 200)
		caja.refresh_from_db()
		# Calcular ventas en efectivo esperadas
		expected_ventas_efectivo = Venta.objects.filter(caja=caja, forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
		expected_efectivo_final = (caja.efectivo_inicial or Decimal('0.00')) + expected_ventas_efectivo
		self.assertEqual(caja.efectivo_final, expected_efectivo_final)
		# Como enviamos el efectivo contado igual al esperado, descuadre debe ser 0
		self.assertEqual(caja.descuadre, Decimal('0.00'))

	def test_abrir_caja_parses_clp_thousands_separator(self):
		self.client.force_login(self.user_admin)
		resp = self.client.post('/cashier/abrir-caja/', {
			'sucursal': str(self.sucursal.id),
			'efectivo_inicial': '10.000',
		}, follow=False)
		# redirect to cashier_dashboard on success
		self.assertIn(resp.status_code, (302, 303))
		caja = AperturaCierreCaja.objects.filter(vendedor=self.user_admin, sucursal=self.sucursal).order_by('-id').first()
		self.assertIsNotNone(caja)
		self.assertEqual(caja.efectivo_inicial, Decimal('10000'))

	def test_cerrar_caja_parses_clp_thousands_separator(self):
		"""El cierre de caja debe aceptar montos tipo '100.000' (CLP) sin interpretar 100.000 como 100."""
		prod = create_product("PCLP", "Producto CLP", precio_compra=Decimal('10'), precio_venta=Decimal('100000'))
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		make_sale(self.user_admin, self.sucursal, [(prod, 1)], forma_pago='efectivo', caja=caja)
		self.client.force_login(self.user_admin)
		payload = json.dumps({'caja_id': caja.id, 'efectivo_contado': '100.000'})
		resp = self.client.post('/cashier/cerrar_caja/', data=payload, content_type='application/json')
		self.assertEqual(resp.status_code, 200)
		caja.refresh_from_db()
		self.assertEqual(caja.efectivo_final, Decimal('100000'))
		self.assertEqual(caja.efectivo_contado, Decimal('100000'))
		self.assertEqual(caja.descuadre, Decimal('0.00'))

	@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
	def test_concurrent_sales_decrement_stock(self):
		"""Simula dos ventas concurrentes contra el mismo producto y valida stock final."""
		if connection.vendor == 'sqlite':
			self.skipTest('SQLite no soporta escrituras concurrentes de forma confiable para este test multi-hilo.')
		# Producto con stock 1 (legacy stock field)
		prod = create_product("PXC", "ConcurrentProd", precio_compra=Decimal('100'), precio_venta=Decimal('500'), stock=1)
		caja = open_caja(self.user_admin, self.sucursal)

		def worker(result_list, idx):
			try:
				client = Client()
				client.force_login(self.user_admin)
				body = {
					'caja_id': caja.id,
					'carrito': [{'producto_id': prod.id, 'cantidad': 1}],
					'tipo_venta': 'boleta',
					'forma_pago': 'efectivo',
					'cliente_paga': '500'
				}
				resp = client.post('/cashier/', data=json.dumps(body), content_type='application/json')
				payload = resp.json() if resp.status_code == 200 else resp.content.decode('utf-8')
			except Exception as e:
				result_list.append((idx, 500, f"EXCEPTION: {type(e).__name__}: {e}"))
				return
			result_list.append((idx, resp.status_code, payload))

		results = []
		t1 = threading.Thread(target=worker, args=(results, 1))
		t2 = threading.Thread(target=worker, args=(results, 2))
		t1.start(); t2.start()
		t1.join(); t2.join()
		prod.refresh_from_db()
		# Asegurarse que el stock no quedó negativo y que no hubo errores fatales
		self.assertGreaterEqual(prod.stock, 0)
		# Nota: la aserción fuerte de concurrencia se valida en TransactionTestCase (cashier/tests_concurrency.py)

	@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
	def test_multi_thread_sales_limit(self):
		"""Lanzar múltiples threads contra el mismo producto con stock limitado.
		Asegurar que no se vendan más unidades que el stock inicial.
		"""
		if connection.vendor == 'sqlite':
			self.skipTest('SQLite no soporta escrituras concurrentes de forma confiable para este test multi-hilo.')
		initial_stock = 3
		threads = 8
		prod = create_product("PXM", "MultiProd", precio_compra=Decimal('100'), precio_venta=Decimal('500'), stock=initial_stock, permitir_venta_sin_stock=False)
		caja = open_caja(self.user_admin, self.sucursal)

		results = []

		def worker(idx):
			try:
				client = Client()
				client.force_login(self.user_admin)
				body = {
					'caja_id': caja.id,
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
			except Exception:
				success = False
			results.append(success)

		ts = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
		for t in ts: t.start()
		for t in ts: t.join()

		prod.refresh_from_db()
		sold = sum(1 for r in results if r)
		# No se pueden vender más que initial_stock
		self.assertLessEqual(sold, initial_stock)
		self.assertEqual(prod.stock, max(0, initial_stock - sold))

	def test_nota_credito_can_be_redeemed_in_pos(self):
		"""Una venta puede pagarse con nota de crédito (store credit) si hay saldo suficiente."""
		prod = create_product("PNC", "Prod NC", precio_compra=Decimal('10'), precio_venta=Decimal('1000'), stock=10)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		nc = NotaCredito.objects.create(
			codigo='NC123TEST',
			sucursal=self.sucursal,
			monto_emitido=Decimal('5000'),
			saldo=Decimal('5000'),
			activa=True,
			creada_por=self.user_admin,
		)
		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()
		payload = {
			'carrito': [{'producto_id': prod.id, 'cantidad': 2}],
			'tipo_venta': 'boleta',
			'forma_pago': 'nota_credito',
			'cliente_paga': 2000,
			'numero_transaccion': nc.codigo,
			'banco': '',
		}
		resp = self.client.post('/cashier/', data=json.dumps(payload), content_type='application/json')
		self.assertEqual(resp.status_code, 200)
		nc.refresh_from_db()
		self.assertEqual(nc.saldo, Decimal('3000'))
		# La venta queda registrada
		self.assertTrue(Venta.objects.filter(forma_pago='nota_credito', numero_transaccion=nc.codigo).exists())

	def test_nota_credito_partial_and_pay_difference(self):
		"""Una venta puede usar nota de crédito parcial y pagar la diferencia con método normal."""
		prod = create_product("PNCP", "Prod NC Partial", precio_compra=Decimal('10'), precio_venta=Decimal('1000'), stock=10)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		nc = NotaCredito.objects.create(
			codigo='NC_PARTIAL_1',
			sucursal=self.sucursal,
			monto_emitido=Decimal('2000'),
			saldo=Decimal('2000'),
			activa=True,
			creada_por=self.user_admin,
		)
		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()

		# Total: 3 * 1000 = 3000. Nota cubre 2000. Diferencia: 1000 (débito).
		payload = {
			'carrito': [{'producto_id': prod.id, 'cantidad': 3}],
			'tipo_venta': 'boleta',
			'forma_pago': 'debito',
			'cliente_paga': 1000,
			'numero_transaccion': 'TX-DEB-123',
			'banco': '',
			'nota_credito_codigo': nc.codigo,
		}
		resp = self.client.post('/cashier/', data=json.dumps(payload), content_type='application/json')
		self.assertEqual(resp.status_code, 200)
		venta_id = resp.json().get('venta_id')
		self.assertIsNotNone(venta_id)

		nc.refresh_from_db()
		self.assertEqual(nc.saldo, Decimal('0'))

		venta = Venta.objects.get(id=venta_id)
		self.assertEqual(venta.forma_pago, 'debito')
		self.assertEqual(getattr(venta, 'nota_credito_usada', None), nc)
		self.assertEqual(getattr(venta, 'monto_nota_credito', Decimal('0')), Decimal('2000'))

		caja.refresh_from_db()
		self.assertEqual(caja.total_ventas_debito, Decimal('1000.00'))

	def test_devolucion_restock_and_close_caja_net_cash(self):
		"""La devolución en efectivo repone stock (si corresponde) y reduce el efectivo esperado al cerrar caja."""
		prod = create_product("PDEV", "Prod DEV", precio_compra=Decimal('10'), precio_venta=Decimal('2000'), stock=5, permitir_venta_sin_stock=False, sucursal=self.sucursal)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()
		# Venta: 2 unidades en efectivo
		payload_sale = {
			'carrito': [{'producto_id': prod.id, 'cantidad': 2}],
			'tipo_venta': 'boleta',
			'forma_pago': 'efectivo',
			'cliente_paga': 10000,
		}
		resp_sale = self.client.post('/cashier/', data=json.dumps(payload_sale), content_type='application/json')
		self.assertEqual(resp_sale.status_code, 200)
		venta_id = resp_sale.json().get('venta_id')
		self.assertIsNotNone(venta_id)
		prod.refresh_from_db()
		self.assertEqual(prod.stock, 3)
		# Devolución: 1 unidad vuelve a stock
		venta = Venta.objects.get(id=venta_id)
		det = venta.detalles.first()
		resp_dev = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'efectivo',
			f'qty_{det.id}': '1',
			f'destino_{det.id}': 'stock',
		}, follow=False)
		self.assertIn(resp_dev.status_code, (302, 303))
		self.assertTrue(Devolucion.objects.filter(venta_original=venta).exists())
		prod.refresh_from_db()
		self.assertEqual(prod.stock, 4)
		# Cerrar caja: efectivo esperado debe ser neto (venta - devolución)
		precio = Decimal('2000')
		expected_net_cash = precio  # vendió 2 (4000) y devolvió 1 (2000) => neto 2000
		resp_close = self.client.post('/cashier/cerrar_caja/', data=json.dumps({
			'caja_id': caja.id,
			'efectivo_contado': str(expected_net_cash),
		}), content_type='application/json')
		self.assertEqual(resp_close.status_code, 200)
		caja.refresh_from_db()
		self.assertEqual(caja.efectivo_final, expected_net_cash)

	def test_devolucion_debito_close_caja_nets_debito_only(self):
		"""Una devolución en débito no afecta el efectivo esperado; solo netea ventas débito y el total."""
		prod = create_product("PDEB", "Prod DEB", precio_compra=Decimal('10'), precio_venta=Decimal('2000'), stock=10, sucursal=self.sucursal)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		venta = make_sale(self.user_admin, self.sucursal, [(prod, 1)], forma_pago='debito', caja=caja)
		det = venta.detalles.first()

		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()

		resp_dev = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'debito',
			'numero_transaccion': 'TX-DEB-TEST',
			f'qty_{det.id}': '1',
			f'destino_{det.id}': 'merma',
		}, follow=False)
		self.assertIn(resp_dev.status_code, (302, 303))

		resp_close = self.client.post('/cashier/cerrar_caja/', data=json.dumps({
			'caja_id': caja.id,
			'efectivo_contado': '0',
		}), content_type='application/json')
		self.assertEqual(resp_close.status_code, 200)
		caja.refresh_from_db()
		self.assertEqual(caja.efectivo_final, Decimal('0.00'))
		self.assertEqual(caja.ventas_totales, Decimal('0.00'))
		self.assertEqual(caja.total_ventas_efectivo, Decimal('0.00'))
		self.assertEqual(caja.total_ventas_debito, Decimal('0.00'))


	def test_devolucion_credito_close_caja_nets_credito_only(self):
		"""Una devolución en crédito no afecta el efectivo esperado; solo netea ventas crédito y el total."""
		prod = create_product("PCRE", "Prod CRE", precio_compra=Decimal('10'), precio_venta=Decimal('2000'), stock=10, sucursal=self.sucursal)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		venta = make_sale(self.user_admin, self.sucursal, [(prod, 1)], forma_pago='credito', caja=caja)
		det = venta.detalles.first()

		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()

		resp_dev = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'credito',
			'numero_transaccion': 'TX-CRE-TEST',
			f'qty_{det.id}': '1',
			f'destino_{det.id}': 'merma',
		}, follow=False)
		self.assertIn(resp_dev.status_code, (302, 303))

		resp_close = self.client.post('/cashier/cerrar_caja/', data=json.dumps({
			'caja_id': caja.id,
			'efectivo_contado': '0',
		}), content_type='application/json')
		self.assertEqual(resp_close.status_code, 200)
		caja.refresh_from_db()
		self.assertEqual(caja.efectivo_final, Decimal('0.00'))
		self.assertEqual(caja.ventas_totales, Decimal('0.00'))
		self.assertEqual(caja.total_ventas_efectivo, Decimal('0.00'))
		self.assertEqual(caja.total_ventas_credito, Decimal('0.00'))

	def test_devolucion_transferencia_requires_bank_and_close_caja_nets_total(self):
		"""Transferencia exige banco + transacción; al cerrar caja netea el total sin afectar efectivo."""
		prod = create_product("PTR", "Prod TR", precio_compra=Decimal('10'), precio_venta=Decimal('2000'), stock=10, sucursal=self.sucursal)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		venta = make_sale(self.user_admin, self.sucursal, [(prod, 1)], forma_pago='transferencia', caja=caja)
		det = venta.detalles.first()

		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()

		# Sin banco debe fallar (redirige a formulario con error)
		resp_missing_bank = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'transferencia',
			'numero_transaccion': 'TX-TR-TEST',
			'banco': '',
			f'qty_{det.id}': '1',
			f'destino_{det.id}': 'merma',
		}, follow=False)
		self.assertIn(resp_missing_bank.status_code, (302, 303))
		self.assertFalse(Devolucion.objects.filter(venta_original=venta).exists())

		resp_dev = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'transferencia',
			'numero_transaccion': 'TX-TR-TEST',
			'banco': 'BancoTest',
			f'qty_{det.id}': '1',
			f'destino_{det.id}': 'merma',
		}, follow=False)
		self.assertIn(resp_dev.status_code, (302, 303))
		self.assertTrue(Devolucion.objects.filter(venta_original=venta).exists())

		resp_close = self.client.post('/cashier/cerrar_caja/', data=json.dumps({
			'caja_id': caja.id,
			'efectivo_contado': '0',
		}), content_type='application/json')
		self.assertEqual(resp_close.status_code, 200)
		caja.refresh_from_db()
		self.assertEqual(caja.efectivo_final, Decimal('0.00'))
		self.assertEqual(caja.ventas_totales, Decimal('0.00'))

	def test_devolucion_allows_other_products_but_blocks_same_product_twice(self):
		"""Se puede devolver otra línea en una devolución posterior, pero no el mismo producto dos veces."""
		prod_a = create_product("PRA", "Prod A", precio_compra=Decimal('10'), precio_venta=Decimal('2000'), stock=10, sucursal=self.sucursal)
		prod_b = create_product("PRB", "Prod B", precio_compra=Decimal('10'), precio_venta=Decimal('3000'), stock=10, sucursal=self.sucursal)
		caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		venta = make_sale(self.user_admin, self.sucursal, [(prod_a, 1), (prod_b, 1)], forma_pago='efectivo', caja=caja)

		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = caja.id
		s.save()

		det_a = venta.detalles.filter(producto=prod_a).first()
		det_b = venta.detalles.filter(producto=prod_b).first()
		self.assertIsNotNone(det_a)
		self.assertIsNotNone(det_b)

		# 1) Primera devolución: producto A
		resp_dev1 = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'efectivo',
			f'qty_{det_a.id}': '1',
			f'destino_{det_a.id}': 'stock',
		}, follow=False)
		self.assertIn(resp_dev1.status_code, (302, 303))
		self.assertEqual(Devolucion.objects.filter(venta_original=venta).count(), 1)

		# 2) Segunda devolución: producto B (debe permitirse)
		resp_dev2 = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'efectivo',
			f'qty_{det_b.id}': '1',
			f'destino_{det_b.id}': 'stock',
		}, follow=False)
		self.assertIn(resp_dev2.status_code, (302, 303))
		self.assertEqual(Devolucion.objects.filter(venta_original=venta).count(), 2)

		# 3) Intentar devolver A nuevamente (bloqueado)
		resp_dev3 = self.client.post(f'/cashier/devolucion/{venta.id}/', {
			'metodo_pago': 'efectivo',
			f'qty_{det_a.id}': '1',
			f'destino_{det_a.id}': 'stock',
		}, follow=False)
		self.assertIn(resp_dev3.status_code, (302, 303))
		self.assertEqual(Devolucion.objects.filter(venta_original=venta).count(), 2)


class CashierMixedPaymentsDisplayTests(TestCase):
	def setUp(self):
		self.sucursal = create_sucursal("Sucursal Display")
		self.user_admin = create_user("admin_display", is_staff=True)
		self.prod = create_product(
			"PD1",
			"Producto Display",
			precio_compra=Decimal('100'),
			precio_venta=Decimal('1000'),
			stock=50,
			sucursal=self.sucursal,
		)
		self.caja = open_caja(self.user_admin, self.sucursal, efectivo_inicial=Decimal('0'))
		self.client.force_login(self.user_admin)
		s = self.client.session
		s['caja_id'] = self.caja.id
		s.save()

	def _create_sale_with_detail(self, *, forma_pago: str, total: Decimal):
		venta = Venta.objects.create(
			empleado=self.user_admin,
			sucursal=self.sucursal,
			caja=self.caja,
			total=total,
			forma_pago=forma_pago,
			cliente_paga=Decimal('0.00'),
			vuelto_entregado=Decimal('0.00'),
		)
		VentaDetalle.objects.create(venta=venta, producto=self.prod, cantidad=1, precio_unitario=total)
		return venta

	def test_cashier_reporte_venta_renders_mixed_breakdown(self):
		venta = self._create_sale_with_detail(forma_pago='mixto', total=Decimal('3000.00'))
		VentaPago.objects.create(venta=venta, metodo='debito', monto=Decimal('1000.00'), numero_transaccion='TX-123')
		VentaPago.objects.create(venta=venta, metodo='efectivo', monto=Decimal('2000.00'))

		resp = self.client.get(f'/cashier/reporte/{venta.id}/')
		self.assertEqual(resp.status_code, 200)
		html = resp.content.decode('utf-8')
		self.assertIn('Mixta', html)
		self.assertIn('Detalle de pago', html)
		self.assertIn('Tarjeta de Débito', html)
		self.assertIn('$1.000', html)
		self.assertIn('TX-123', html)
		self.assertIn('$2.000', html)

	def test_cashier_reporte_venta_legacy_partial_nc_shows_breakdown(self):
		nc = NotaCredito.objects.create(
			codigo='NC-DISP-1',
			sucursal=self.sucursal,
			monto_emitido=Decimal('2000.00'),
			saldo=Decimal('0.00'),
			activa=False,
			creada_por=self.user_admin,
		)
		venta = self._create_sale_with_detail(forma_pago='debito', total=Decimal('3000.00'))
		venta.nota_credito_usada = nc
		venta.monto_nota_credito = Decimal('2000.00')
		venta.numero_transaccion = 'TX-LEG-1'
		venta.save(update_fields=['nota_credito_usada', 'monto_nota_credito', 'numero_transaccion'])

		resp = self.client.get(f'/cashier/reporte/{venta.id}/')
		self.assertEqual(resp.status_code, 200)
		html = resp.content.decode('utf-8')
		self.assertIn('Detalle de pago', html)
		# Breakdown should include NC code and remaining debito amount.
		self.assertIn('NC-DISP-1', html)
		self.assertIn('$2.000', html)
		self.assertIn('$1.000', html)
		# When breakdown is shown, template should not repeat the separate NC-applied line.
		self.assertNotIn('Nota de crédito aplicada', html)
		self.assertIn('Total a pagar', html)

	def test_print_caja_hides_cheque_and_added_and_marks_subtractions(self):
		resp = self.client.get(f'/cashier/print/caja/{self.caja.id}/')
		self.assertEqual(resp.status_code, 200)
		html = resp.content.decode('utf-8')
		self.assertNotIn('Cheque', html)
		self.assertNotIn('Añadido a caja', html)
		# Subtractive markers should be present for vueltos and devoluciones.
		self.assertIn('(-)', html)

	def test_detalle_caja_hides_cheque_and_added_and_marks_subtractions(self):
		resp = self.client.get(f'/cashier/detalle-caja/{self.caja.id}/')
		self.assertEqual(resp.status_code, 200)
		html = resp.content.decode('utf-8')
		self.assertNotIn('Cheque', html)
		self.assertNotIn('Añadido a caja', html)
		self.assertIn('(-)', html)
