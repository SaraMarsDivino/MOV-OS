# auth_app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse

def login_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_admin:  # O el atributo de rol que tengas
                return redirect('admin_dashboard')
            return redirect('cashier_dashboard')
        else:
            return render(request, 'auth_app/login.html', {'error': 'Credenciales incorrectas'})
    return render(request, 'auth_app/login.html')

def custom_logout(request):
    logout(request)
    return redirect('login')
