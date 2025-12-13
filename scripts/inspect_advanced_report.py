import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','MOVOS.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from tests.factories import create_sucursal, create_product
from django.utils import timezone
from decimal import Decimal
from cashier.models import Venta, VentaDetalle
User = get_user_model()

# Create data
user = User.objects.create(username='inspect_user', is_staff=True)
suc = create_sucursal('InspectSucursal')
prod = create_product('PX','ProdX', precio_compra=Decimal('100'), precio_venta=Decimal('200'))
v = Venta.objects.create(empleado=user, sucursal=suc, fecha=timezone.now(), total=Decimal('200'), forma_pago='efectivo')
VentaDetalle.objects.create(venta=v, producto=prod, cantidad=1, precio_unitario=Decimal('200'))

c = Client()
c.force_login(user)
resp = c.get('/reports/advanced/')
print('STATUS:', resp.status_code)
html = resp.content.decode('utf-8')
print('LENGTH:', len(html))
start = html.find('data-promedio-ganancia-neta')
print('FOUND AT:', start)
if start!=-1:
    print(html[start-200:start+200])
else:
    print(html[:1000])
