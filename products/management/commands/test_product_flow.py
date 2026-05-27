from django.core.management.base import BaseCommand
from uuid import uuid4

class Command(BaseCommand):
    help = 'Create test user/sucursales and attempt to access product management and create product'

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from django.test import Client
        from sucursales.models import Sucursal as SucursalSucursal
        from reports.models import Sucursal as SucursalReport
        from users.models import Vendedor
        from products.models import Product

        User = get_user_model()

        self.stdout.write('Starting product flow test')
        suffix = uuid4().hex[:8]
        s1 = SucursalReport.objects.create(nombre=f'PruebaRep-{suffix}')
        s2 = SucursalSucursal.objects.create(nombre=f'PruebaSuc-{suffix}')
        self.stdout.write(f'Created sucursales {s1.id} {s2.id}')

        u, created = User.objects.get_or_create(username='tester_prod', defaults={'email': 'tester@example.com'})
        if created:
            u.set_password('testpass')
        else:
            u.email = 'tester@example.com'
            u.set_password('testpass')
            u.save(update_fields=['email', 'password'])
        self.stdout.write(f'Created user {u.id}')

        v, _ = Vendedor.objects.get_or_create(user=u)
        v.sucursales_autorizadas.clear()
        v.sucursales_autorizadas.add(s2)
        self.stdout.write('Created vendedor and linked sucursal')

        try:
            u.sucursales_autorizadas.clear()
            u.sucursales_autorizadas.add(s1)
            self.stdout.write('Linked report sucursal to user')
        except Exception:
            self.stdout.write('User has no sucursales_autorizadas m2m')

        c = Client()
        c.defaults['HTTP_HOST'] = 'localhost'
        logged = c.login(username='tester_prod', password='testpass')
        self.stdout.write(f'logged {logged}')

        res = c.get('/products/management/')
        self.stdout.write(f'GET /products/management/ status_code {res.status_code}')
        if res.status_code in (301, 302):
            self.stdout.write(f'Redirected to: {res.url}')

        post_data = {
            'nombre': 'Prod Test',
            'producto_id': 'PT-001',
            'precio_compra': '1000',
            'precio_venta': '1500',
            'cantidad': '1',
            'stock': '10',
            'sucursal': str(s2.id),
        }
        res2 = c.post('/products/create/', post_data, follow=True)
        self.stdout.write(f'POST /products/create/ final status {res2.status_code}')
        if hasattr(res2, 'redirect_chain'):
            self.stdout.write(f'redirect chain: {res2.redirect_chain}')
        if hasattr(res2, 'context') and res2.context:
            form = res2.context.get('form') if isinstance(res2.context, dict) else None
            if form and form.errors:
                self.stdout.write(f'Form errors: {form.errors}')

        prod = Product.objects.filter(producto_id='PT-001').first()
        self.stdout.write(f'Product created? {bool(prod)} id={prod.id if prod else None}')
        self.stdout.write('Done')
