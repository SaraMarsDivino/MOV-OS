#user/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from .forms import UserForm
from .models import Vendedor
from django.contrib.auth import get_user_model, authenticate, login, logout
from cashier.models import AperturaCierreCaja
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from MOVOS.react_ui import react_ui_enabled, vite_dev_server_url_if_up
from django.core.cache import cache
from django.contrib.auth.password_validation import validate_password, ValidationError as PasswordValidationError
import json
User = get_user_model()  # Importa el modelo de usuario personalizado

def _report_sucursal_model():
    from reports.models import Sucursal as ReportSucursal
    return ReportSucursal


def _legacy_sucursal_model():
    from sucursales.models import Sucursal as LegacySucursal
    return LegacySucursal


def _user_sucursal_ids(user):
    try:
        return list(user.sucursales_autorizadas.values_list('id', flat=True).order_by('id'))
    except Exception:
        return []


def _sync_user_sucursales(user, sucursales_ids):
    normalized = [int(sid) for sid in (sucursales_ids or [])]
    try:
        user.sucursales_autorizadas.set(normalized)
    except Exception:
        pass
    try:
        vendedor = Vendedor.objects.filter(user=user).first()
        if vendedor is None:
            vendedor = Vendedor.objects.create(user=user, is_admin=bool(getattr(user, 'is_superuser', False)))
        legacy_ids = []
        report_sucursales = _report_sucursal_model()
        legacy_sucursales = _legacy_sucursal_model()
        for report_sucursal in report_sucursales.objects.filter(id__in=normalized):
            matched = legacy_sucursales.objects.filter(nombre=report_sucursal.nombre).order_by('id').first()
            if matched:
                legacy_ids.append(matched.id)
        vendedor.sucursales_autorizadas.set(legacy_ids)
    except Exception:
        pass


def _wants_json(request) -> bool:
    ct = (request.content_type or '').lower()
    accept = (request.headers.get('Accept') or '').lower()
    return 'application/json' in ct or 'application/json' in accept


def is_admin(user):
    return user.is_authenticated and user.is_staff


def _can_access_admin(user):
    """Usuarios que pueden entrar al panel de administración: staff/superuser o
    usuarios con al menos un permiso granular (productos o analíticas)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    return bool(
        getattr(user, 'can_add_products', False)
        or getattr(user, 'can_edit_products', False)
        or getattr(user, 'can_view_analytics', False)
    )


@login_required
def home(request):
    if _can_access_admin(request.user):
        return redirect('admin_dashboard')
    return redirect('cashier_dashboard')


@user_passes_test(_can_access_admin, login_url='cashier_dashboard')
@login_required
def admin_dashboard(request):
    if react_ui_enabled():
        ctx = {}
        if getattr(settings, 'DEBUG', False):
            vite_url = vite_dev_server_url_if_up()
            if vite_url:
                ctx['vite_dev_server_url'] = vite_url
        # expose current user permissions to React
        try:
            ctx['react_context'] = {
                'user': {
                    'id': request.user.id,
                    'username': getattr(request.user, 'username', ''),
                    'is_staff': bool(getattr(request.user, 'is_staff', False)),
                    'is_superuser': bool(getattr(request.user, 'is_superuser', False)),
                    'can_add_products': bool(getattr(request.user, 'can_add_products', False)),
                    'can_edit_products': bool(getattr(request.user, 'can_edit_products', False)),
                    'can_view_analytics': bool(getattr(request.user, 'can_view_analytics', False)),
                }
            }
        except Exception:
            ctx['react_context'] = {}
        return render(request, 'users/react_admin_dashboard.html', ctx)
    return render(request, 'users/admin_dashboard.html')


## Nota: cashier_dashboard es provisto por la app 'cashier'.


def custom_login(request):
    # Si ya está autenticado y vuelve a /login, redirigir según rol/estado de caja
    if request.user.is_authenticated:
        if _can_access_admin(request.user):
            return redirect('admin_dashboard')
        tiene_caja = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').exists()
        return redirect('cashier_dashboard' if tiene_caja else 'abrir_caja')

    if request.method == 'POST':
        ip = (request.META.get('HTTP_X_FORWARDED_FOR', '') or request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        rate_key = f'login_attempts_{ip}'
        attempts = cache.get(rate_key, 0)
        if attempts >= 10:
            messages.error(request, "Demasiados intentos fallidos. Espera 15 minutos antes de intentarlo de nuevo.")
            return render(request, 'users/login.html')

        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            cache.delete(rate_key)
            login(request, user)
            sv = getattr(settings, 'SESSION_VERSION', None)
            if sv is not None:
                request.session['_sv'] = sv
            if _can_access_admin(user):
                return redirect('admin_dashboard')
            tiene_caja = AperturaCierreCaja.objects.filter(vendedor=user, estado='abierta').exists()
            return redirect('cashier_dashboard' if tiene_caja else 'abrir_caja')
        else:
            cache.set(rate_key, attempts + 1, 15 * 60)  # bloqueo de 15 min tras 10 intentos
            messages.error(request, "Credenciales incorrectas.")
            return render(request, 'users/login.html')
    return render(request, 'users/login.html')


@login_required
def profile(request):
    return render(request, 'users/profile.html', {'user': request.user})


from django.contrib.auth import logout
from django.contrib import messages

def logout_view(request):
    logout(request)
    # Consumir (vaciar) los mensajes
    list(messages.get_messages(request))
    return redirect('login')


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
def user_management(request):
    if react_ui_enabled():
        ctx = {}
        if getattr(settings, 'DEBUG', False):
            vite_url = vite_dev_server_url_if_up()
            if vite_url:
                ctx['vite_dev_server_url'] = vite_url
        try:
            ctx['react_context'] = {
                'user': {
                    'id': request.user.id,
                    'username': getattr(request.user, 'username', ''),
                    'is_staff': bool(getattr(request.user, 'is_staff', False)),
                    'is_superuser': bool(getattr(request.user, 'is_superuser', False)),
                    'can_add_products': bool(getattr(request.user, 'can_add_products', False)),
                    'can_edit_products': bool(getattr(request.user, 'can_edit_products', False)),
                    'can_view_analytics': bool(getattr(request.user, 'can_view_analytics', False)),
                }
            }
        except Exception:
            ctx['react_context'] = {}
        return render(request, 'users/react_user_management.html', ctx)

    users = User.objects.all()
    print("Usuarios encontrados:", users.count())
    return render(request, 'users/user_management.html', {'users': users})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
@require_http_methods(["GET"])
def api_users_list(request):
    users = User.objects.all().order_by('id')
    items = []
    for u in users:
        items.append({
            'id': u.id,
            'username': getattr(u, 'username', '') or '',
            'email': getattr(u, 'email', '') or '',
            'is_superuser': bool(getattr(u, 'is_superuser', False)),
            'is_staff': bool(getattr(u, 'is_staff', False)),
            'is_active': bool(getattr(u, 'is_active', True)),
        })
    return JsonResponse({'items': items, 'total': len(items)})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
@require_http_methods(["GET"])
def api_user_sucursales_list(request):
    Sucursal = _report_sucursal_model()
    LegacySucursal = _legacy_sucursal_model()
    items = []
    # Always expose the legacy sucursales list (created via Sucursales screen)
    # and ensure the report sucursal exists for permissions storage.
    for legacy in LegacySucursal.objects.all().order_by('nombre', 'id'):
        report, _ = Sucursal.objects.update_or_create(
            nombre=legacy.nombre,
            defaults={
                'direccion': legacy.direccion or '',
                'telefono': legacy.telefono or '',
            },
        )
        items.append({
            'id': report.id,
            'nombre': legacy.nombre or '',
            'display_name': legacy.nombre or '',
            'direccion': legacy.direccion or '',
            'telefono': legacy.telefono or '',
        })
    return JsonResponse({'items': items, 'total': len(items)})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
@require_http_methods(["GET"]) 
def api_user_detail(request, user_id):
    u = get_object_or_404(User, id=user_id)
    data = {
        'id': u.id,
        'username': getattr(u, 'username', '') or '',
        'email': getattr(u, 'email', '') or '',
        'is_superuser': bool(getattr(u, 'is_superuser', False)),
        'is_staff': bool(getattr(u, 'is_staff', False)),
        'is_active': bool(getattr(u, 'is_active', True)),
        'can_add_products': bool(getattr(u, 'can_add_products', False)),
        'can_edit_products': bool(getattr(u, 'can_edit_products', False)),
        'can_view_analytics': bool(getattr(u, 'can_view_analytics', False)),
        'sucursales_autorizadas': _user_sucursal_ids(u),
    }
    return JsonResponse({'item': data})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
@require_http_methods(["POST"])
def api_user_update(request, user_id):
    target = get_object_or_404(User, id=user_id)
    # Only JSON payload supported for this API
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'error': 'Payload inválido'}, status=400)
    # Prevent non-superuser from editing superuser
    if getattr(target, 'is_superuser', False) and not getattr(request.user, 'is_superuser', False):
        return JsonResponse({'error': 'No tienes permisos para modificar un superusuario.'}, status=403)
    changed = False
    if 'email' in payload:
        target.email = payload.get('email') or ''
        changed = True
    if 'is_superuser' in payload:
        target.is_superuser = bool(payload.get('is_superuser'))
        target.is_staff = bool(payload.get('is_superuser'))
        changed = True
    for flag in ('can_add_products', 'can_edit_products', 'can_view_analytics'):
        if flag in payload:
            setattr(target, flag, bool(payload.get(flag)))
            changed = True
    new_password = payload.get('password') or ''
    if new_password:
        try:
            validate_password(new_password, target)
        except PasswordValidationError as e:
            return JsonResponse({'error': ' '.join(e.messages)}, status=400)
        target.set_password(new_password)
        changed = True
    if changed:
        target.save()
    if 'sucursales_autorizadas' in payload:
        _sync_user_sucursales(target, payload.get('sucursales_autorizadas') or [])
    return JsonResponse({'success': True, 'id': target.id})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
@require_http_methods(["POST"])
def api_user_create(request):
    # Create user from JSON payload
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'error': 'Payload inválido'}, status=400)
    username = payload.get('username')
    password = payload.get('password')
    email = payload.get('email') or ''
    if not username or not password:
        return JsonResponse({'error': 'username y password son requeridos'}, status=400)
    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({'error': 'Ya existe un usuario con ese nombre.'}, status=400)
    is_super = bool(payload.get('is_superuser', False))
    user = User(username=username, email=email, is_superuser=is_super, is_staff=is_super)
    try:
        validate_password(password, user)
    except PasswordValidationError as e:
        return JsonResponse({'error': ' '.join(e.messages)}, status=400)
    user.set_password(password)
    # flags
    user.can_add_products = bool(payload.get('can_add_products', False))
    user.can_edit_products = bool(payload.get('can_edit_products', False))
    user.can_view_analytics = bool(payload.get('can_view_analytics', False))
    user.save()
    _sync_user_sucursales(user, payload.get('sucursales_autorizadas') or [])
    return JsonResponse({'success': True, 'id': user.id})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
@require_http_methods(["POST"])
def set_user_active(request, user_id):
    """Activa/desactiva un usuario sin eliminarlo (evita romper reportes/historial).

    - HTML form: POST active=1/0 -> redirect con mensaje.
    - JSON: POST {"active": true/false} -> JSON.
    """

    target = get_object_or_404(User, id=user_id)

    # No permitir deshabilitarse a sí mismo (evita lockout)
    if target.id == request.user.id:
        msg = 'No puedes deshabilitar tu propio usuario.'
        if _wants_json(request):
            return JsonResponse({'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('user_management')

    # Sólo superuser puede tocar cuentas superuser
    if getattr(target, 'is_superuser', False) and not getattr(request.user, 'is_superuser', False):
        msg = 'No tienes permisos para modificar un superusuario.'
        if _wants_json(request):
            return JsonResponse({'error': msg}, status=403)
        messages.error(request, msg)
        return redirect('user_management')

    try:
        if (request.content_type or '').lower().startswith('application/json'):
            payload = json.loads(request.body.decode('utf-8') or '{}')
            desired = payload.get('active')
        else:
            desired = request.POST.get('active')
        active = bool(desired) if isinstance(desired, bool) else str(desired).strip().lower() in ('1', 'true', 'yes', 'on')
    except Exception:
        if _wants_json(request):
            return JsonResponse({'error': 'Payload inválido'}, status=400)
        messages.error(request, 'Payload inválido.')
        return redirect('user_management')

    if bool(getattr(target, 'is_active', True)) == active:
        msg = 'El usuario ya estaba activo.' if active else 'El usuario ya estaba deshabilitado.'
        if _wants_json(request):
            return JsonResponse({'success': True, 'id': target.id, 'is_active': bool(getattr(target, 'is_active', True)), 'message': msg})
        messages.info(request, msg)
        return redirect('user_management')

    target.is_active = active
    target.save(update_fields=['is_active'])
    msg = 'Usuario habilitado correctamente.' if active else 'Usuario deshabilitado correctamente.'
    if _wants_json(request):
        return JsonResponse({'success': True, 'id': target.id, 'is_active': bool(target.is_active), 'message': msg})
    messages.success(request, msg)
    return redirect('user_management')


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
def create_user(request):
    if react_ui_enabled():
        ctx = {}
        vite_url = vite_dev_server_url_if_up()
        if vite_url:
            ctx['vite_dev_server_url'] = vite_url
        ctx['react_context'] = {}
        return render(request, 'users/react_create_user.html', ctx)
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Crear usuario básico usando el modelo personalizado
                    username = form.cleaned_data['username']
                    email = form.cleaned_data['email']
                    password = form.cleaned_data['password']
                    is_superuser = form.cleaned_data.get('is_superuser', False)
                    user = User(
                        username=username,
                        email=email,
                        is_superuser=is_superuser,
                        is_staff=is_superuser
                    )
                    user.set_password(password)
                    # Asignar permisos granulares desde el formulario
                    user.can_add_products = bool(form.cleaned_data.get('can_add_products', False))
                    user.can_edit_products = bool(form.cleaned_data.get('can_edit_products', False))
                    user.can_view_analytics = bool(form.cleaned_data.get('can_view_analytics', False))
                    user.save()
                    sucursales = form.cleaned_data.get('sucursales_autorizadas') or []
                    _sync_user_sucursales(user, [s.pk for s in sucursales])
                messages.success(request, "Usuario creado exitosamente.")
                return redirect("user_management")
            except Exception as e:
                print("Error al crear usuario:", e)
                messages.error(request, f"Error al crear el usuario: {e}")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = UserForm()
    return render(request, 'users/create_user.html', {'form': form})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
def edit_user(request, user_id):
    if react_ui_enabled():
        ctx = {}
        vite_url = vite_dev_server_url_if_up()
        if vite_url:
            ctx['vite_dev_server_url'] = vite_url
        ctx['react_context'] = {'user_id': user_id}
        return render(request, 'users/react_edit_user.html', ctx)
    user_obj = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user_obj)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user_obj.email = form.cleaned_data['email']
                    user_obj.is_superuser = form.cleaned_data.get('is_superuser', False)
                    user_obj.is_staff = form.cleaned_data.get('is_superuser', False)

                    new_password = form.cleaned_data.get('password')
                    if new_password:
                        user_obj.set_password(new_password)

                    user_obj.save()
                    user_obj.can_add_products = bool(form.cleaned_data.get('can_add_products', False))
                    user_obj.can_edit_products = bool(form.cleaned_data.get('can_edit_products', False))
                    user_obj.can_view_analytics = bool(form.cleaned_data.get('can_view_analytics', False))
                    user_obj.save()
                    sucursales = form.cleaned_data.get('sucursales_autorizadas') or []
                    _sync_user_sucursales(user_obj, [s.pk for s in sucursales])
                messages.success(request, "Usuario actualizado exitosamente.")
                return redirect("user_management")
            except Exception as e:
                messages.error(request, f"Error al actualizar el usuario: {e}")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = UserForm(instance=user_obj)
    return render(request, 'users/edit_user.html', {'form': form, 'user': user_obj})


@user_passes_test(is_admin, login_url='cashier_dashboard')
@login_required
def delete_user(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    # Mantener endpoint por compatibilidad, pero evitar borrado real.
    if request.method == 'POST':
        # Reutilizar lógica: deshabilitar
        if user_obj.id == request.user.id:
            messages.error(request, 'No puedes deshabilitar tu propio usuario.')
            return redirect('user_management')
        if getattr(user_obj, 'is_superuser', False) and not getattr(request.user, 'is_superuser', False):
            messages.error(request, 'No tienes permisos para modificar un superusuario.')
            return redirect('user_management')
        user_obj.is_active = False
        user_obj.save(update_fields=['is_active'])
        messages.success(request, 'Usuario deshabilitado correctamente.')
        return redirect('user_management')
    messages.info(request, 'Para seguridad, los usuarios se deshabilitan (no se eliminan).')
    return redirect('user_management')
