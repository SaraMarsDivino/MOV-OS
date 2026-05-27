from django.test import Client
from django.contrib.auth import get_user_model
import re

User = get_user_model()
username = 'tmpadmin_for_check'
password = 'tmp_password'
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, 'tmp@local', password)

c = Client()
logged = c.login(username=username, password=password)
print('logged_in:', logged)
resp = c.get('/products/edit/8/')
print('status_code:', resp.status_code)
if resp.status_code == 200:
    content = resp.content.decode('utf-8')
    m1 = re.search(r'name="codigo_alternativo"[^>]*value="([^"]*)"', content)
    m2 = re.search(r'name="codigo_barras"[^>]*value="([^"]*)"', content)
    print('codigo_alternativo:', m1.group(1) if m1 else None)
    print('codigo_barras:', m2.group(1) if m2 else None)
else:
    print('Could not render edit page; content length', len(resp.content))
