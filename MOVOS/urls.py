from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.http import HttpResponse
from users import views  # Usado para custom_login

def redirect_to_login(request):
    return redirect('login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz', lambda r: HttpResponse('ok'), name='healthz'),
    path('healthz/', lambda r: HttpResponse('ok')),  # also accept trailing slash
    path('auth/', include('auth_app.urls')),         # login y logout en auth_app
    path('users/', include('users.urls')),            # admin_dashboard, user_management, etc.
    path('products/', include('products.urls')),      # product_management, etc.
    path('cashier/', include('cashier.urls')),        # cashier_dashboard, etc.
    path('reports/', include('reports.urls', namespace='reports')),  # Usamos namespace 'reports'
    path('', redirect_to_login, name='redirect_to_login'),
    path('login/', views.custom_login, name='login'),
    path('sucursales/', include('sucursales.urls', namespace='sucursales')),

]
