from decimal import Decimal
import datetime
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from cashier.models import Venta, VentaDetalle
from cashier.views import format_clp
from products.models import Product
from sucursales.models import Sucursal
from tests.factories import create_sucursal, create_user, create_product, open_caja, make_sale

from .analytics import compute_analytics

User = get_user_model()


class ReportsPersistenceTests(TestCase):
    def setUp(self):
        self.sucursal = create_sucursal('Sucursal Test')
        self.admin = create_user('admin_reports', is_staff=True)
        self.prod = create_product('P1', 'Prod1', precio_compra=Decimal('100'), precio_venta=Decimal('1000'))

    def test_reports_use_persisted_efectivo_final(self):
        caja = open_caja(self.admin, self.sucursal, efectivo_inicial=Decimal('5000'))
        make_sale(self.admin, self.sucursal, [(self.prod, 2)], forma_pago='efectivo', caja=caja)
        make_sale(self.admin, self.sucursal, [(self.prod, 1)], forma_pago='debito', caja=caja)

        self.client.force_login(self.admin)
        payload = '{"caja_id": %d, "efectivo_contado": %s}' % (caja.id, str(caja.efectivo_final))
        resp = self.client.post('/cashier/cerrar_caja/', data=payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        caja.refresh_from_db()
        resp2 = self.client.get(f'/reports/caja/{caja.id}/reporte/')
        self.assertEqual(resp2.status_code, 200)

        expected = "$" + format_clp(caja.efectivo_final)
        self.assertIn(expected.encode('utf-8'), resp2.content)


class AnalyticsComputationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='tester', is_staff=True)
        self.suc = Sucursal.objects.create(nombre='Central')

        self.prod_a = Product.objects.create(
            producto_id='A1',
            nombre='Prod A',
            precio_compra=Decimal('1000'),
            precio_venta=Decimal('2000'),
        )
        self.prod_b = Product.objects.create(
            producto_id='B1',
            nombre='Prod B',
            precio_compra=Decimal('500'),
            precio_venta=Decimal('1500'),
        )

        now = timezone.now()
        v1 = Venta.objects.create(empleado=self.user, sucursal=self.suc, total=Decimal('2000'), forma_pago='efectivo')
        Venta.objects.filter(pk=v1.pk).update(fecha=now - datetime.timedelta(days=2))
        VentaDetalle.objects.create(venta=v1, producto=self.prod_a, cantidad=1, precio_unitario=Decimal('2000'))

        v2 = Venta.objects.create(empleado=self.user, sucursal=self.suc, total=Decimal('3000'), forma_pago='debito')
        Venta.objects.filter(pk=v2.pk).update(fecha=now - datetime.timedelta(days=1))
        VentaDetalle.objects.create(venta=v2, producto=self.prod_a, cantidad=1, precio_unitario=Decimal('2000'))
        VentaDetalle.objects.create(venta=v2, producto=self.prod_b, cantidad=2, precio_unitario=Decimal('500'))

        self.fecha_inicio = (now - datetime.timedelta(days=5)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.fecha_fin = now

    def test_basic_kpis(self):
        data = compute_analytics(self.fecha_inicio, self.fecha_fin, 'todos', 'todos')
        self.assertGreater(data['ingreso_total'], Decimal('0'))
        self.assertGreaterEqual(data['num_transacciones'], 1)
        self.assertIn('daily_chart', data)
        self.assertIn('rentabilidad_productos', data)
        self.assertIn(data['best_selling_product'], {'Prod A', 'Prod B'})

    def test_rentabilidad_structure(self):
        data = compute_analytics(self.fecha_inicio, self.fecha_fin)
        rent = data['rentabilidad_productos']
        self.assertTrue(len(rent) > 0)
        first = rent[0]
        self.assertIn('producto', first)
        self.assertIn('ganancia_neta_total', first)

    def test_comparativo_periodo(self):
        data = compute_analytics(self.fecha_inicio, self.fecha_fin)
        self.assertIn('ingreso_prev', data)
        self.assertIn('ingreso_delta', data)
        self.assertEqual(data['ingreso_delta'], data['ingreso_total'] - data['ingreso_prev'])

    def test_wave_chart(self):
        data = compute_analytics(self.fecha_inicio, self.fecha_fin)
        self.assertEqual(len(data['wave_labels']), 6)
        self.assertEqual(len(data['wave_gains']), 6)

    def test_json_endpoint_structure(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            '/reports/advanced/data/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
            },
        )
        self.assertEqual(resp.status_code, 200)

        payload = resp.json()
        self.assertIn('kpis', payload)
        self.assertIn('comparativo', payload)
        self.assertIn('series', payload)

        ingreso_fmt = payload['kpis']['ingreso_total_clp']
        self.assertTrue('.' in ingreso_fmt)
        self.assertFalse(',' in ingreso_fmt)

        self.assertIsInstance(payload['kpis']['ingreso_total'], int)

    def test_promedio_ganancia_neta_view(self):
        self.client.force_login(self.user)
        data = compute_analytics(self.fecha_inicio, self.fecha_fin)
        rent = data['rentabilidad_productos']

        manual_promedio = Decimal('0.00')
        if rent:
            manual_promedio = (
                sum(Decimal(str(r['ganancia_neta_total'])) for r in rent)
                / Decimal(str(len(rent)))
            ).quantize(Decimal('0.01'))

        resp = self.client.get(
            '/reports/advanced/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
            },
        )
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        m = re.search(r'data-promedio-ganancia-neta="([^"]+)"', content)
        self.assertIsNotNone(m, 'No se encontró el atributo data-promedio-ganancia-neta en el HTML')

        raw = (m.group(1) or '').strip().replace(',', '.')
        valor_html = Decimal(raw).quantize(Decimal('0.01'))
        self.assertEqual(
            valor_html,
            manual_promedio.quantize(Decimal('0.01')),
            'Promedio Ganancia Neta no coincide con cálculo esperado',
        )

    def test_top_productos_table_renders(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            '/reports/advanced/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
                'top': 5,
            },
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Top Productos Más Vendidos', content)
        self.assertIn('<table', content)
        self.assertIn('Cantidad Vendida', content)

    def test_custom_comparativo_range(self):
        self.client.force_login(self.user)
        custom_start = (self.fecha_inicio - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
        custom_end = (self.fecha_inicio - datetime.timedelta(days=5)).strftime('%Y-%m-%d')

        resp = self.client.get(
            '/reports/advanced/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
                'comparativo_inicio': custom_start,
                'comparativo_fin': custom_end,
            },
        )
        self.assertEqual(resp.status_code, 200)

        content = resp.content.decode('utf-8')
        self.assertIn('Comparando contra rango personalizado', content)
        self.assertIn(custom_start, content)
        self.assertIn(custom_end, content)

    def test_custom_comparativo_json_endpoint(self):
        self.client.force_login(self.user)
        custom_start = (self.fecha_inicio - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
        custom_end = (self.fecha_inicio - datetime.timedelta(days=5)).strftime('%Y-%m-%d')

        resp = self.client.get(
            '/reports/advanced/data/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
                'comparativo_inicio': custom_start,
                'comparativo_fin': custom_end,
            },
        )
        self.assertEqual(resp.status_code, 200)

        payload = resp.json()
        self.assertIn('comparativo_meta', payload)
        meta = payload['comparativo_meta']
        self.assertTrue(meta['comparativo_custom'])
        self.assertEqual(meta['comparativo_inicio'], custom_start)
        self.assertEqual(meta['comparativo_fin'], custom_end)

        self.assertIn('ingreso_delta', meta)
        self.assertIn('ganancia_neta_delta', meta)
        self.assertIn('transacciones_delta', meta)
        self.assertIn('margen_delta', meta)

    def test_top_products_json_param(self):
        self.client.force_login(self.user)

        resp = self.client.get(
            '/reports/advanced/data/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
                'top': 1,
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn('top_selling_products', payload)
        self.assertLessEqual(len(payload['top_selling_products']), 1)

        resp2 = self.client.get(
            '/reports/advanced/data/',
            {
                'fecha_inicio': self.fecha_inicio.strftime('%Y-%m-%d'),
                'fecha_fin': self.fecha_fin.strftime('%Y-%m-%d'),
                'top': 2,
            },
        )
        self.assertEqual(resp2.status_code, 200)
        payload2 = resp2.json()
        self.assertIn('top_selling_products', payload2)
        self.assertLessEqual(len(payload2['top_selling_products']), 2)
