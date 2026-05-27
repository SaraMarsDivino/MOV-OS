# scripts/test_product_flow.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MOVOS.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from sucursales.models import Sucursal as SucursalSucursal
from reports.models import Sucursal as SucursalReport
from users.models import Vendedor
from products.models import Product

User = get_user_model()

print('Starting product flow test')
# create report Sucursal and sucursales Sucursal
s1 = SucursalReport.objects.create(nombre='PruebaRep')
s2 = SucursalSucursal.objects.create(nombre='PruebaSuc')
print('Created sucursales', s1.id, s2.id)
# create user
u = User.objects.create_user('tester_prod','tester@example.com','testpass')
print('Created user', u.id)
# ensure Vendedor exists and link sucursal
v = Vendedor.objects.create(user=u)
v.sucursales_autorizadas.add(s2)
print('Created vendedor and linked sucursal')
# also link report sucursal to user.sucursales_autorizadas if field exists
try:
    u.sucursales_autorizadas.add(s1)
    print('Linked report sucursal to user')
except Exception:
    print('User has no sucursales_autorizadas m2m')

c = Client()
logged = c.login(username='tester_prod', password='testpass')
print('logged', logged)
res = c.get('/products/management/')
print('GET /products/management/ status_code', res.status_code)
print('Redirected to:', res.url if res.status_code in (301,302) else 'no')
# attempt to POST create product
post_data = {
    'nombre':'Prod Test',
    'producto_id':'PT-001',
    'precio_compra':'1000',
    'precio_venta':'1500',
    'cantidad':'1',
    'stock':'10',
    'sucursal': str(s2.id),
}
res2 = c.post('/products/create/', post_data, follow=True)
print('POST /products/create/ final status', res2.status_code)
if hasattr(res2, 'redirect_chain'):
    print('redirect chain:', res2.redirect_chain)
if hasattr(res2, 'context') and res2.context:
    # show form errors if present
    form = res2.context.get('form') if isinstance(res2.context, dict) else None
    if form and form.errors:
        print('Form errors:', form.errors)

# verify product created
prod = Product.objects.filter(producto_id='PT-001').first()
print('Product created?', bool(prod), 'id=', prod.id if prod else None)
print('Done')
