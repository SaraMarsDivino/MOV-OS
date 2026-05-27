import os
import sys
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MOVOS.settings')
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import django
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from products.models import Product
from products import views
from django.contrib.sessions.middleware import SessionMiddleware

User = get_user_model()

# Create or get a test user
user, created = User.objects.get_or_create(username='test_integration_user')
if created:
    user.set_password('testpass')
    user.is_staff = True
    user.save()
print('User:', user.id, 'created?', created)

c = Client()
logged = c.login(username='test_integration_user', password='testpass')
print('Logged in via Client:', logged)

from django.conf import settings
# Ensure test client host is allowed
try:
    if 'testserver' not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append('testserver')
except Exception:
    pass

# Create a temporary product
p = Product.objects.create(nombre='TEMP TEST PROD', producto_id='TMP123' + str(int(Product.objects.count())), precio_venta=1000, precio_compra=500)
print('Created product id=', p.id)

# Test bulk delete via view using RequestFactory (bypass CSRF)
rf = RequestFactory()
req = rf.post('/products/bulk-delete/', data=json.dumps({'product_ids': [p.id]}), content_type='application/json')
# attach user and session
req.user = user
middleware = SessionMiddleware(get_response=lambda r: None)
middleware.process_request(req)
req.session.save()

resp = views.bulk_delete_products(req)
print('bulk_delete response status_code:', getattr(resp, 'status_code', None), 'content:', getattr(resp, 'content', b'')[:200])

# Verify product deleted
exists = Product.objects.filter(id=p.id).exists()
print('Product exists after delete?', exists)

# Test cashier add to cart and adjust quantity using client
# Find any existing product to add
prod = Product.objects.exclude(id=p.id).first()
if not prod:
    prod = Product.objects.create(nombre='ANOTHER TEMP', producto_id='TMP456', precio_venta=2000, precio_compra=1000)
print('Using product', prod.id)

# Ensure there is an open caja for the user so cashier endpoints allow operations
from sucursales.models import Sucursal
from cashier.models import AperturaCierreCaja
try:
    suc = Sucursal.objects.first() or Sucursal.objects.create(nombre='Sucursal Test')
    caja_obj = AperturaCierreCaja.objects.filter(vendedor=user, estado='abierta').first()
    if not caja_obj:
        caja_obj = AperturaCierreCaja.objects.filter(estado='abierta').first()
    if not caja_obj:
        caja_obj = AperturaCierreCaja.objects.create(vendedor=user, sucursal=suc, efectivo_inicial=0, estado='abierta')
    print('Using caja:', caja_obj.id)
except Exception as e:
    print('Could not create caja:', e)

resp = c.post('/cashier/agregar-al-carrito/', json.dumps({'producto_id': prod.id, 'caja_id': caja_obj.id}), content_type='application/json', HTTP_HOST='testserver')
print('/cashier/agregar-al-carrito/ status:', resp.status_code, 'resp snippet:', resp.content[:200])

# Adjust quantity to 400 via ajustar-cantidad (delta semantics). First increase by 399 (initial qty 1)
resp2 = c.post('/cashier/ajustar-cantidad/', json.dumps({'producto_id': prod.id, 'cantidad': 399, 'caja_id': caja_obj.id}), content_type='application/json', HTTP_HOST='testserver')
print('/cashier/ajustar-cantidad/ status:', resp2.status_code, 'resp snippet:', resp2.content[:400])

# Parse response and find quantity
try:
    data = resp2.json()
    carrito = data.get('carrito', [])
    qty = None
    for it in carrito:
        if it.get('producto_id') == prod.id:
            qty = it.get('cantidad')
    print('Quantity after adjust (should be 400):', qty)
except Exception as e:
    print('Error parsing ajustar-cantidad response:', e)

# Cleanup temp product if still exists
Product.objects.filter(producto_id__startswith='TMP').delete()
print('Cleanup done')
