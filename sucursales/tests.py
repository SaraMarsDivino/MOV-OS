from django.test import TestCase
from django.urls import reverse
from tests.factories import create_sucursal, create_user, create_product


class SucursalViewsTests(TestCase):
    def test_sucursal_products_page_renders_with_text_dark(self):
        admin = create_user(username='admin_test', is_staff=True)
        self.client.force_login(admin)
        sucursal = create_sucursal(nombre='Sucursal Central')
        create_product(producto_id='P001', nombre='Producto 1', sucursal=sucursal)

        response = self.client.get(reverse('sucursales:sucursal_products', args=[sucursal.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Productos en Sucursal Central')
        self.assertContains(response, 'text-dark')
