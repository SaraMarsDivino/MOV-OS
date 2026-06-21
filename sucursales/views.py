import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.conf import settings
from .forms import SucursalForm
from .models import Sucursal
from products.views import sucursal_products as _sucursal_products_view
from MOVOS.react_ui import react_ui_enabled, vite_dev_server_url_if_up

def is_admin(user):
    return user.is_authenticated and user.is_staff


def _sync_to_report_sucursal(legacy):
    """Crea o actualiza la entrada espejo en reports.Sucursal para que
    aparezca disponible al asignar permisos de sucursal a usuarios."""
    try:
        from reports.models import Sucursal as ReportSucursal
        ReportSucursal.objects.update_or_create(
            nombre=legacy.nombre,
            defaults={
                'direccion': legacy.direccion or '',
                'telefono': legacy.telefono or '',
            },
        )
    except Exception:
        pass


@login_required
@user_passes_test(is_admin)
def create_sucursal(request):
    """Vista para crear una nueva sucursal (solo para admin)."""
    if react_ui_enabled():
        ctx = {'react_context': {}}
        vite_url = vite_dev_server_url_if_up()
        if vite_url:
            ctx['vite_dev_server_url'] = vite_url
        return render(request, 'sucursales/react_create_sucursal.html', ctx)
    if request.method == 'POST':
        form = SucursalForm(request.POST)
        if form.is_valid():
            legacy = form.save()
            _sync_to_report_sucursal(legacy)
            messages.success(request, "Sucursal creada exitosamente.")
            return redirect('sucursales:sucursal_list')
    else:
        form = SucursalForm()
    return render(request, 'sucursales/create_sucursal.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def sucursal_list(request):
    """Vista para listar todas las sucursales (solo para admin)."""
    if react_ui_enabled():
        ctx = {}
        if getattr(settings, 'DEBUG', False):
            vite_url = vite_dev_server_url_if_up()
            if vite_url:
                ctx['vite_dev_server_url'] = vite_url
        return render(request, 'sucursales/react_sucursal_list.html', ctx)

    sucursales = Sucursal.objects.all()
    return render(request, 'sucursales/sucursal_list.html', {'sucursales': sucursales})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_sucursales_list(request):
    items = []
    for s in Sucursal.objects.all().order_by('id'):
        items.append({
            'id': s.id,
            'nombre': s.nombre or '',
            'direccion': s.direccion or '',
            'telefono': s.telefono or '',
            'activo': s.activo,
        })
    return JsonResponse({'items': items, 'total': len(items)})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def api_sucursal_toggle_activo(request, pk):
    s = get_object_or_404(Sucursal, pk=pk)
    s.activo = not s.activo
    s.save(update_fields=['activo'])
    return JsonResponse({'ok': True, 'activo': s.activo})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def api_sucursal_delete(request, pk):
    s = get_object_or_404(Sucursal, pk=pk)
    from django.db.models import Q
    from products.models import StockSucursal, TransferenciaStock, AjusteStock
    from cashier.models import Venta, AperturaCierreCaja

    from products.models import Product
    from cashier.models import NotaCredito
    blockers = []
    if StockSucursal.objects.filter(sucursal=s).exists():
        blockers.append('registros de stock')
    if TransferenciaStock.objects.filter(Q(origen=s) | Q(destino=s)).exists():
        blockers.append('transferencias de stock')
    if AjusteStock.objects.filter(sucursal=s).exists():
        blockers.append('ajustes de stock')
    if Product.objects.filter(sucursal=s).exists():
        blockers.append('productos asignados')
    if Venta.objects.filter(sucursal=s).exists():
        blockers.append('ventas')
    if NotaCredito.objects.filter(sucursal=s).exists():
        blockers.append('notas de crédito')
    if AperturaCierreCaja.objects.filter(sucursal=s).exists():
        blockers.append('aperturas/cierres de caja')

    if blockers:
        return JsonResponse({
            'ok': False,
            'error': f'No se puede eliminar "{s.nombre}" porque tiene: {", ".join(blockers)}. Use "Deshabilitar" en su lugar.',
        }, status=400)

    nombre = s.nombre
    s.delete()
    return JsonResponse({'ok': True, 'mensaje': f'Sucursal "{nombre}" eliminada.'})

@login_required
@user_passes_test(is_admin)
def edit_sucursal(request, pk):
    """Vista para editar una sucursal existente (solo para admin)."""
    sucursal = get_object_or_404(Sucursal, pk=pk)
    if react_ui_enabled():
        ctx = {'react_context': {'sucursal_id': pk}}
        vite_url = vite_dev_server_url_if_up()
        if vite_url:
            ctx['vite_dev_server_url'] = vite_url
        return render(request, 'sucursales/react_edit_sucursal.html', ctx)
    form = SucursalForm(request.POST or None, instance=sucursal)
    if request.method == 'POST' and form.is_valid():
        legacy = form.save()
        _sync_to_report_sucursal(legacy)
        messages.success(request, "Sucursal actualizada exitosamente.")
        return redirect('sucursales:sucursal_list')
    return render(request, 'sucursales/edit_sucursal.html', {'form': form, 'sucursal': sucursal})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def api_sucursal_detail(request, pk):
    s = get_object_or_404(Sucursal, pk=pk)
    return JsonResponse({'item': {
        'id': s.id,
        'nombre': s.nombre or '',
        'direccion': s.direccion or '',
        'telefono': s.telefono or '',
        'low_stock_threshold': s.low_stock_threshold,
    }})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def api_sucursal_update(request, pk):
    s = get_object_or_404(Sucursal, pk=pk)
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    nombre = (body.get('nombre') or '').strip()
    if not nombre:
        return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)
    if Sucursal.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists():
        return JsonResponse({'error': f'Ya existe una sucursal llamada "{nombre}".'}, status=400)
    s.nombre = nombre
    s.direccion = (body.get('direccion') or '').strip()
    s.telefono = (body.get('telefono') or '').strip()
    try:
        s.low_stock_threshold = max(0, int(body.get('low_stock_threshold') or 0))
    except (ValueError, TypeError):
        s.low_stock_threshold = 0
    s.save()
    _sync_to_report_sucursal(s)
    return JsonResponse({'ok': True})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def api_sucursal_create(request):
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    nombre = (body.get('nombre') or '').strip()
    if not nombre:
        return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)
    if Sucursal.objects.filter(nombre__iexact=nombre).exists():
        return JsonResponse({'error': f'Ya existe una sucursal llamada "{nombre}".'}, status=400)
    s = Sucursal.objects.create(
        nombre=nombre,
        direccion=(body.get('direccion') or '').strip(),
        telefono=(body.get('telefono') or '').strip(),
        low_stock_threshold=max(0, int(body.get('low_stock_threshold') or 0)),
    )
    _sync_to_report_sucursal(s)
    return JsonResponse({'ok': True, 'id': s.id})

@login_required
@user_passes_test(is_admin)
def sucursal_products(request, sucursal_id):
    """Proxy a la vista de listado de productos por sucursal."""
    return _sucursal_products_view(request, sucursal_id)
