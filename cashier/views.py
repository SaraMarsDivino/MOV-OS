from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import quote
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.conf import settings
from django.middleware.csrf import get_token
import json
import datetime
import socket
import uuid as _uuid_module
from urllib.parse import urlparse
from decimal import Decimal, ROUND_HALF_UP

from MOVOS.react_ui import react_ui_enabled
from MOVOS.money import parse_clp_decimal as _parse_clp_decimal_shared, to_clp_pesos as _to_clp_pesos_shared

from .models import Venta, VentaDetalle, VentaPago, AperturaCierreCaja, NotaCredito, Devolucion, DevolucionDetalle
from products.models import Product
from sucursales.models import Sucursal
from decimal import Decimal as _Decimal


def _legacy_sucursal_from_report(report_sucursal):
    """Map a reports.Sucursal to the legacy sucursales.Sucursal used by caja.

    We reuse an existing legacy sucursal with the same name when possible.
    If none exists, create one so the user can still open caja.
    """
    legacy = Sucursal.objects.filter(nombre=report_sucursal.nombre).order_by('id').first()
    if legacy:
        return legacy
    return Sucursal.objects.create(
        nombre=report_sucursal.nombre,
        direccion=getattr(report_sucursal, 'direccion', None) or '',
        telefono=getattr(report_sucursal, 'telefono', None) or '',
    )


def _authorized_sucursales_for_user(user):
    if user.is_superuser or user.is_staff:
        return Sucursal.objects.all()

    sucursales = []
    vendedor = getattr(user, 'vendedor', None)
    if vendedor and hasattr(vendedor, 'sucursales_autorizadas'):
        sucursales.extend(list(vendedor.sucursales_autorizadas.all()))

    if not sucursales and hasattr(user, 'sucursales_autorizadas'):
        try:
            for report_sucursal in user.sucursales_autorizadas.all():
                sucursales.append(_legacy_sucursal_from_report(report_sucursal))
        except Exception:
            pass

    seen = set()
    ordered = []
    for sucursal in sucursales:
        if sucursal.id not in seen:
            seen.add(sucursal.id)
            ordered.append(sucursal)
    return Sucursal.objects.filter(id__in=[s.id for s in ordered]).order_by('nombre', 'id')


def _vite_dev_server_is_up(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except Exception:
        return False

def format_currency(value):
    try:
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except Exception:
        return value

def format_clp(value):
    try:
        val = _to_clp_pesos(value)
        formatted = "{:,.0f}".format(int(val))
        return formatted.replace(",", ".")
    except Exception:
        return value


def _compute_caja_financials(caja: AperturaCierreCaja):
    """Compute gross and net (ventas - devoluciones) totals for a caja.

    Important:
    - Cash expected (efectivo_final_calc) uses net cash sales.
    - Refunds in cash reduce expected cash.
    """

    ventas_qs = Venta.objects.filter(caja=caja)
    devoluciones_qs = Devolucion.objects.filter(caja=caja)

    ventas_total_brutas = _to_clp_pesos(ventas_qs.aggregate(total=Sum('total'))['total'] or Decimal('0'))

    # Prefer `VentaPago` when present, but keep legacy fallback for older rows.
    legacy_ventas_qs = ventas_qs.filter(pagos__isnull=True)
    pagos_qs = VentaPago.objects.filter(venta__caja=caja)

    pagos_agg = pagos_qs.values('metodo').annotate(total=Sum('monto'))
    pagos_map = {row['metodo']: _to_clp_pesos(row.get('total') or Decimal('0')) for row in pagos_agg}

    nc_expr = Coalesce(F('monto_nota_credito'), Decimal('0.00'))
    # Amount that actually goes through the selected payment method (excludes store credit portion).
    metodo_expr = (Coalesce(F('total'), Decimal('0.00')) - nc_expr)

    legacy_efectivo = _to_clp_pesos(legacy_ventas_qs.filter(forma_pago='efectivo').aggregate(total=Sum(metodo_expr))['total'] or Decimal('0'))
    legacy_debito = _to_clp_pesos(legacy_ventas_qs.filter(forma_pago='debito').aggregate(total=Sum(metodo_expr))['total'] or Decimal('0'))
    legacy_credito = _to_clp_pesos(legacy_ventas_qs.filter(forma_pago='credito').aggregate(total=Sum(metodo_expr))['total'] or Decimal('0'))
    legacy_transferencia = _to_clp_pesos(legacy_ventas_qs.filter(forma_pago='transferencia').aggregate(total=Sum(metodo_expr))['total'] or Decimal('0'))
    legacy_nota_credito = _to_clp_pesos(legacy_ventas_qs.aggregate(total=Sum(nc_expr))['total'] or Decimal('0'))

    ventas_efectivo_brutas = _to_clp_pesos(pagos_map.get('efectivo', Decimal('0')) + legacy_efectivo)
    ventas_debito_brutas = _to_clp_pesos(pagos_map.get('debito', Decimal('0')) + legacy_debito)
    ventas_credito_brutas = _to_clp_pesos(pagos_map.get('credito', Decimal('0')) + legacy_credito)
    ventas_transferencia_brutas = _to_clp_pesos(pagos_map.get('transferencia', Decimal('0')) + legacy_transferencia)
    ventas_nota_credito_brutas = _to_clp_pesos(pagos_map.get('nota_credito', Decimal('0')) + legacy_nota_credito)
    vuelto_total = _to_clp_pesos(ventas_qs.aggregate(total=Sum('vuelto_entregado'))['total'] or Decimal('0'))

    devol_total = _to_clp_pesos(devoluciones_qs.aggregate(total=Sum('total'))['total'] or Decimal('0'))
    devol_efectivo = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0'))
    devol_debito = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='debito').aggregate(total=Sum('total'))['total'] or Decimal('0'))
    devol_credito = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='credito').aggregate(total=Sum('total'))['total'] or Decimal('0'))
    devol_transferencia = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='transferencia').aggregate(total=Sum('total'))['total'] or Decimal('0'))
    devol_nota_credito = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='nota_credito').aggregate(total=Sum('total'))['total'] or Decimal('0'))

    ventas_total_netas = _to_clp_pesos(ventas_total_brutas - devol_total)
    ventas_efectivo_netas = _to_clp_pesos(ventas_efectivo_brutas - devol_efectivo)
    ventas_debito_netas = _to_clp_pesos(ventas_debito_brutas - devol_debito)
    ventas_credito_netas = _to_clp_pesos(ventas_credito_brutas - devol_credito)
    ventas_transferencia_netas = _to_clp_pesos(ventas_transferencia_brutas - devol_transferencia)
    ventas_nota_credito_netas = _to_clp_pesos(ventas_nota_credito_brutas - devol_nota_credito)

    efectivo_final_calc = _to_clp_pesos((caja.efectivo_inicial or Decimal('0')) + ventas_efectivo_netas)

    return {
        'ventas_qs': ventas_qs,
        'ventas_total': ventas_total_netas,
        'ventas_efectivo': ventas_efectivo_netas,
        'ventas_debito': ventas_debito_netas,
        'ventas_credito': ventas_credito_netas,
        'ventas_transferencia': ventas_transferencia_netas,
        'ventas_nota_credito': ventas_nota_credito_netas,
        'vuelto_total': vuelto_total,
        'efectivo_final_calc': efectivo_final_calc,
        'devol_total': devol_total,
        'devol_efectivo': devol_efectivo,
        'devol_debito': devol_debito,
        'devol_credito': devol_credito,
        'devol_transferencia': devol_transferencia,
        'devol_nota_credito': devol_nota_credito,
    }


@login_required
def cashier_sales_history(request):
    """Búsqueda de ventas para devoluciones (cajeros).

    UX: muestra un listado paginado de ventas (solo del usuario/caja/sucursal actual)
    y permite buscar por ID o Nº transacción. Si encuentra una venta única (o se
    selecciona por ID), muestra el detalle + formulario de devolución.
    """

    caja_abierta = get_current_caja(request)
    if not caja_abierta:
        messages.error(request, 'Debes tener una caja abierta para ver el historial de ventas.')
        return redirect('abrir_caja')

    venta_id_raw = (request.GET.get('venta_id') or '').strip()
    numero_transaccion = (request.GET.get('numero_transaccion') or '').strip()
    per_page_raw = (request.GET.get('per_page') or '10').strip()

    venta = None
    lineas = []
    found = False
    message_added = False

    try:
        per_page = int(per_page_raw)
    except Exception:
        per_page = 10
    if per_page not in (10, 25):
        per_page = 10

    venta_id = None
    if venta_id_raw:
        try:
            venta_id = int(venta_id_raw)
        except Exception:
            venta_id = None
            messages.error(request, 'El ID de venta debe ser numérico.')
            message_added = True

    list_base_qs = Venta.objects.select_related('sucursal', 'caja', 'empleado').filter(
        sucursal=caja_abierta.sucursal
    )
    # "Solo ventas del usuario abierto": por defecto, restringimos al usuario actual.
    # Admin/staff puede ver todas en la sucursal.
    if not (request.user.is_staff or request.user.is_superuser):
        list_base_qs = list_base_qs.filter(empleado=request.user)

    list_qs = list_base_qs
    if numero_transaccion:
        list_qs = list_qs.filter(
            Q(numero_transaccion__icontains=numero_transaccion)
            | Q(pagos__numero_transaccion__icontains=numero_transaccion)
        ).distinct()
    if venta_id is not None:
        list_qs = list_qs.filter(id=venta_id)

    list_qs = list_qs.order_by('-fecha')
    paginator = Paginator(list_qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    if venta_id is not None or numero_transaccion:
        found = True
        detail_base_qs = list_base_qs.prefetch_related('detalles__producto')

        if venta_id is not None:
            venta = detail_base_qs.filter(id=venta_id).first()
        else:
            qs = detail_base_qs.filter(numero_transaccion__icontains=numero_transaccion).order_by('-fecha')
            c = qs.count()
            if c == 1:
                venta = qs.first()
            elif c == 0:
                venta = None
            else:
                venta = None
                messages.info(request, f'Se encontraron {c} ventas con ese Nº de transacción. Selecciona una desde el listado o ingresa el ID.')
                message_added = True

        if venta is None and not message_added:
            messages.info(request, 'No se encontró una venta con esos datos en la sucursal actual.')

    if venta:
        venta.display_total = "$" + format_clp(venta.total)
        detalles = list(venta.detalles.all())
        devueltos_por_producto = {
            row['producto_id']: int(row['total'] or 0)
            for row in (
                DevolucionDetalle.objects.filter(devolucion__venta_original=venta)
                .values('producto_id')
                .annotate(total=Sum('cantidad'))
            )
        }

        for d in detalles:
            ya = devueltos_por_producto.get(d.producto_id, 0)
            # Regla UX: permitir devoluciones múltiples por venta, pero no permitir
            # devolver el mismo producto más de una vez.
            max_ret = 0 if ya > 0 else max(0, int(d.cantidad) - ya)
            lineas.append({
                'detalle': d,
                'max_returnable': max_ret,
                'ya_devuelto': ya,
            })

    query_params = request.GET.copy()
    query_params.pop('page', None)
    base_query = query_params.urlencode()

    return render(request, 'cashier/sales_history.html', {
        'venta_id': venta_id_raw,
        'numero_transaccion': numero_transaccion,
        'per_page': per_page,
        'venta': venta,
        'lineas': lineas,
        'found': found,
        'caja_abierta': caja_abierta,
        'page_obj': page_obj,
        'base_query': base_query,
    })


def _build_detalles_data(venta):
    detalles = venta.detalles.all()
    detalles_data = []
    for d in detalles:
        subtotal = d.cantidad * d.precio_unitario
        detalles_data.append({
            'producto': d.producto,
            'cantidad': d.cantidad,
            'precio_unitario': d.precio_unitario,
            'formatted_subtotal': "$" + format_currency(subtotal)
        })
    return detalles_data


def _payment_method_display(method_code: str) -> str:
    # Keep labels consistent with VentaPago choices.
    return {
        'efectivo': 'Efectivo',
        'debito': 'Tarjeta de Débito',
        'credito': 'Tarjeta de Crédito',
        'transferencia': 'Transferencia',
        'nota_credito': 'Nota de crédito',
    }.get(method_code, method_code or '-')


def _build_payment_breakdown(venta: Venta):
    """Return a normalized breakdown of how a sale was paid.

    Prefers VentaPago rows when present; falls back to legacy Venta fields.
    Amounts are rounded to CLP pesos (no decimals).
    """

    pagos = list(venta.pagos.all().order_by('id'))
    breakdown = []

    if pagos:
        for p in pagos:
            monto = _to_clp_pesos(p.monto or Decimal('0'))
            breakdown.append({
                'metodo': p.metodo,
                'metodo_display': getattr(p, 'get_metodo_display', None)() if hasattr(p, 'get_metodo_display') else _payment_method_display(p.metodo),
                'monto': monto,
                'formatted_monto': "$" + format_currency(monto),
                'numero_transaccion': (p.numero_transaccion or '').strip() or None,
                'banco': (p.banco or '').strip() or None,
                'nota_credito_codigo': (getattr(p.nota_credito, 'codigo', None) if p.metodo == 'nota_credito' else None),
            })
        return breakdown

    # Legacy fallback (single method + optional partial nota de crédito)
    total = _to_clp_pesos(venta.total or Decimal('0'))
    monto_nc = _to_clp_pesos(getattr(venta, 'monto_nota_credito', None) or Decimal('0'))
    restante = _to_clp_pesos(total - monto_nc)

    if monto_nc > 0:
        breakdown.append({
            'metodo': 'nota_credito',
            'metodo_display': _payment_method_display('nota_credito'),
            'monto': monto_nc,
            'formatted_monto': "$" + format_currency(monto_nc),
            'numero_transaccion': None,
            'banco': None,
            'nota_credito_codigo': getattr(getattr(venta, 'nota_credito_usada', None), 'codigo', None),
        })

    if restante > 0 or not breakdown:
        breakdown.append({
            'metodo': venta.forma_pago,
            'metodo_display': _payment_method_display(venta.forma_pago),
            'monto': restante if monto_nc > 0 else total,
            'formatted_monto': "$" + format_currency(restante if monto_nc > 0 else total),
            'numero_transaccion': (venta.numero_transaccion or '').strip() or None,
            'banco': (venta.banco or '').strip() or None,
            'nota_credito_codigo': None,
        })

    return breakdown

# ==== Helper para resolver la caja abierta actual de forma consistente ====
def _parse_body_json(request):
    try:
        if request.body:
            return json.loads(request.body)
    except Exception:
        pass
    return {}


def _parse_clp_decimal(value):
    return _parse_clp_decimal_shared(value)


def _to_clp_pesos(value):
    try:
        return _to_clp_pesos_shared(value)
    except Exception:
        return Decimal('0')

def get_current_caja(request):
    """
    Devuelve la caja abierta actual para el usuario autenticado.
    - Admins/staff pueden operar cualquier caja.
    - Vendedores normales solo pueden operar su propia caja y solo en su sucursal asignada.
    """
    caja_id = request.GET.get('caja_id')
    if not caja_id and request.method in ("POST", "PUT", "PATCH"):
        data = _parse_body_json(request)
        caja_id = data.get('caja_id') or caja_id
    if not caja_id:
        caja_id = request.session.get('caja_id')

    caja = None
    if caja_id:
        try:
            caja = AperturaCierreCaja.objects.get(id=caja_id)
            if caja.estado != 'abierta':
                caja = None
        except AperturaCierreCaja.DoesNotExist:
            caja = None
    if not caja:
        caja = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').first()

    if not caja:
        return None

    # Permisos:
    if request.user.is_superuser or request.user.is_staff:
        return caja  # Admins pueden ver cualquier caja

    # Solo puede operar sobre su propia caja
    if caja.vendedor_id != request.user.id:
        return None

    # Nota operativa:
    # Si un admin cambia/desasigna la sucursal del usuario durante una caja abierta,
    # igual debemos permitir que el cajero termine (cierre) su caja actual.
    # Las restricciones por sucursal deben aplicarse al abrir una nueva caja.

    return caja
    # --- FIN DE LA CORRECCIÓN ---

@transaction.atomic
@login_required
@ensure_csrf_cookie
def cashier_dashboard(request):
    caja_abierta = get_current_caja(request)
    if not caja_abierta:
        # Redirigir a abrir caja sin generar un mensaje de error persistente
        # (el mensaje anterior causaba que al entrar a la vista de apertura
        #  siempre apareciera un toast; preferimos mostrar información
        #  contextual en la propia vista si es necesario).
        return redirect('abrir_caja')
    # Persistir selección en sesión para que endpoints AJAX usen la misma caja
    prev_caja_id = request.session.get('caja_id')
    request.session['caja_id'] = caja_abierta.id
    # Si cambió la caja o no existía, reiniciar carrito para evitar arrastres
    if prev_caja_id != caja_abierta.id or request.session.get('carrito') is None:
        request.session['carrito'] = []
    request.session.modified = True
    if request.method == 'GET':
        # Mostrar productos de la sucursal de la caja abierta (vista inicial)
        # Resetear carrito para iniciar una nueva venta sin arrastrar ítems previos
        try:
            request.session['carrito'] = []
            request.session.modified = True
        except Exception:
            pass
        # POS React (dev: Vite dev server; prod: assets build via manifest).
        if react_ui_enabled():
            ctx = {
                'caja_abierta': caja_abierta,
            }
            if getattr(settings, 'DEBUG', False):
                vite_url = getattr(settings, 'VITE_DEV_SERVER_URL', 'http://localhost:5173')
                if _vite_dev_server_is_up(vite_url):
                    ctx['vite_dev_server_url'] = vite_url
            return render(request, 'cashier/react_cashier.html', ctx)

        productos = Product.objects.filter(sucursal=caja_abierta.sucursal, activo=True)
        return render(request, 'cashier/cashier.html', {
            'productos': productos,
            'caja_abierta': caja_abierta,
        })
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            carrito = data.get('carrito', [])
            tipo_venta = data.get('tipo_venta', 'boleta')
            forma_pago = data.get('forma_pago', 'efectivo')
            pagos_payload = data.get('pagos')
            nota_credito_codigo = (data.get('nota_credito_codigo') or '').strip()
            # Normalizar a pesos CLP enteros (acepta '10.000' / '10.000,00')
            try:
                cliente_paga = _to_clp_pesos(_parse_clp_decimal(data.get('cliente_paga', '0')))
            except Exception:
                cliente_paga = Decimal('0')
            numero_transaccion = data.get('numero_transaccion', '').strip()
            banco = data.get('banco', '').strip() if forma_pago == "transferencia" else ""
            if not carrito:
                return JsonResponse({"error": "El carrito está vacío."}, status=400)

            # Consolidar product ids y bloquear filas para evitar condiciones de carrera (Postgres). Esto evita N+1.
            product_ids = []
            for item in carrito:
                try:
                    product_ids.append(int(item.get('producto_id')))
                except Exception:
                    return JsonResponse({"error": "ID de producto inválido en carrito."}, status=400)

            with transaction.atomic():
                products_qs = Product.objects.select_for_update().filter(id__in=product_ids, activo=True)
                products_map = {p.id: p for p in products_qs}
                missing = [str(pid) for pid in set(product_ids) if pid not in products_map]
                if missing:
                    return JsonResponse({"error": f"Productos no encontrados: {', '.join(missing)}"}, status=400)

                total = Decimal('0.00')
                # Validaciones y cálculo de total usando objetos en memoria
                for item in carrito:
                    pid = int(item.get('producto_id'))
                    producto = products_map[pid]
                    cantidad = int(item.get('cantidad', 1))
                    allow_without_stock = producto.permitir_venta_sin_stock_en(caja_abierta.sucursal)
                    pertenece_o_permitido = (
                        producto.asignado_a_sucursal(caja_abierta.sucursal) or allow_without_stock
                    )
                    if not pertenece_o_permitido:
                        return JsonResponse({"error": f"El producto '{producto.nombre}' no pertenece a la sucursal de la caja abierta."}, status=400)
                    if caja_abierta and caja_abierta.sucursal_id:
                        disponible = producto.stock_en(caja_abierta.sucursal)
                    else:
                        disponible = producto.stock or 0
                    if not allow_without_stock and disponible < cantidad:
                        return JsonResponse({"error": f"El producto '{producto.nombre}' no tiene suficiente stock. Disponible: {disponible}."}, status=400)
                    # Total en pesos enteros; precio_venta debe tratarse como CLP (sin centavos)
                    total += _to_clp_pesos(Decimal(str(cantidad)) * (producto.precio_venta or Decimal('0')))

                # === Pagos mixtos (nuevo payload: pagos[]) ===
                if isinstance(pagos_payload, list) and len(pagos_payload) > 0:
                    def _parse_pago_monto(val):
                        try:
                            return _to_clp_pesos(_parse_clp_decimal(val))
                        except Exception:
                            try:
                                return _to_clp_pesos(Decimal(str(val)))
                            except Exception:
                                return Decimal('0')

                    allowed_methods = {'efectivo', 'debito', 'credito', 'transferencia', 'nota_credito'}
                    parsed_pagos = []
                    for idx, raw in enumerate(pagos_payload, start=1):
                        if not isinstance(raw, dict):
                            return JsonResponse({"error": f"Pago inválido en posición {idx}."}, status=400)
                        metodo = (raw.get('metodo') or raw.get('forma_pago') or '').strip()
                        if metodo not in allowed_methods:
                            return JsonResponse({"error": f"Método de pago inválido: {metodo or '(vacío)'}"}, status=400)
                        monto = _parse_pago_monto(raw.get('monto'))
                        if monto <= Decimal('0'):
                            return JsonResponse({"error": f"Monto inválido para el pago {idx}."}, status=400)
                        tx = (raw.get('numero_transaccion') or '').strip()
                        bank = (raw.get('banco') or '').strip() if metodo == 'transferencia' else ''
                        codigo_nc = (raw.get('nota_credito_codigo') or raw.get('codigo') or '').strip()

                        if metodo in ('debito', 'credito', 'transferencia') and not tx:
                            return JsonResponse({
                                "error": "El número de transacción es obligatorio para pagos con tarjeta y transferencia."
                            }, status=400)
                        if metodo == 'transferencia' and not bank:
                            return JsonResponse({
                                "error": "Debe ingresar el nombre del banco para pagos por transferencia."
                            }, status=400)
                        if metodo == 'nota_credito' and not (codigo_nc or nota_credito_codigo):
                            return JsonResponse({
                                "error": "Debe ingresar el código de la nota de crédito para usarla como pago."
                            }, status=400)

                        parsed_pagos.append({
                            'metodo': metodo,
                            'monto': monto,
                            'numero_transaccion': tx,
                            'banco': bank,
                            'nota_credito_codigo': codigo_nc,
                        })

                    nota_rows = [p for p in parsed_pagos if p['metodo'] == 'nota_credito']
                    if len(nota_rows) > 1:
                        return JsonResponse({"error": "Solo se permite una nota de crédito por venta."}, status=400)
                    cash_rows = [p for p in parsed_pagos if p['metodo'] == 'efectivo']
                    if len(cash_rows) > 1:
                        return JsonResponse({"error": "Solo se permite un pago en efectivo por venta."}, status=400)

                    nota_credito_obj = None
                    monto_nota_credito = Decimal('0.00')
                    nc_code = ''
                    if nota_rows:
                        nc_code = (nota_rows[0].get('nota_credito_codigo') or nota_credito_codigo).strip()
                        nota_credito_obj = NotaCredito.objects.select_for_update().filter(codigo=nc_code, activa=True).first()
                        if not nota_credito_obj:
                            return JsonResponse({"error": "Nota de crédito no encontrada o inactiva."}, status=400)
                        if nota_credito_obj.sucursal_id != caja_abierta.sucursal_id:
                            return JsonResponse({"error": "La nota de crédito no corresponde a esta sucursal."}, status=400)
                        saldo = _to_clp_pesos(nota_credito_obj.saldo or Decimal('0'))
                        monto_nota_credito = _to_clp_pesos(min(nota_rows[0]['monto'], total))
                        if monto_nota_credito > saldo:
                            return JsonResponse({"error": "Saldo insuficiente en la nota de crédito."}, status=400)
                    elif nota_credito_codigo:
                        nc_code = nota_credito_codigo.strip()
                        nota_credito_obj = NotaCredito.objects.select_for_update().filter(codigo=nc_code, activa=True).first()
                        if not nota_credito_obj:
                            return JsonResponse({"error": "Nota de crédito no encontrada o inactiva."}, status=400)
                        if nota_credito_obj.sucursal_id != caja_abierta.sucursal_id:
                            return JsonResponse({"error": "La nota de crédito no corresponde a esta sucursal."}, status=400)
                        saldo = _to_clp_pesos(nota_credito_obj.saldo or Decimal('0'))
                        monto_nota_credito = _to_clp_pesos(min(saldo, total))

                    total_a_pagar = _to_clp_pesos(total - monto_nota_credito)
                    otros_pagos = [p for p in parsed_pagos if p['metodo'] != 'nota_credito']
                    suma_otros = _to_clp_pesos(sum((p['monto'] for p in otros_pagos), Decimal('0')))

                    if total_a_pagar <= Decimal('0'):
                        if suma_otros != Decimal('0'):
                            return JsonResponse({"error": "La nota de crédito cubre el total; elimina los otros pagos."}, status=400)
                    else:
                        if suma_otros != total_a_pagar:
                            return JsonResponse({
                                "error": f"La suma de pagos debe ser exactamente ${format_currency(total_a_pagar)}."
                            }, status=400)

                    efectivo_monto = cash_rows[0]['monto'] if cash_rows else Decimal('0')
                    cliente_paga_final = cliente_paga if efectivo_monto > 0 else Decimal('0.00')
                    if efectivo_monto > 0 and cliente_paga_final < efectivo_monto:
                        return JsonResponse({
                            "error": f"Pago en efectivo insuficiente. Debe ser al menos ${format_currency(efectivo_monto)}."
                        }, status=400)
                    vuelto = _to_clp_pesos(max(Decimal('0'), cliente_paga_final - efectivo_monto)) if efectivo_monto > 0 else Decimal('0.00')

                    # Apply store credit deduction if any
                    if nota_credito_obj and monto_nota_credito > Decimal('0'):
                        nota_credito_obj.saldo = _to_clp_pesos((nota_credito_obj.saldo or Decimal('0')) - monto_nota_credito)
                        if nota_credito_obj.saldo <= Decimal('0'):
                            nota_credito_obj.saldo = Decimal('0.00')
                            nota_credito_obj.activa = False
                            nota_credito_obj.save(update_fields=['saldo', 'activa'])
                        else:
                            nota_credito_obj.save(update_fields=['saldo'])

                    metodos_usados = [p['metodo'] for p in otros_pagos if p['monto'] > 0]
                    if monto_nota_credito > Decimal('0'):
                        metodos_usados.append('nota_credito')
                    metodos_distintos = sorted(set(metodos_usados))
                    if len(metodos_distintos) == 1:
                        forma_pago_final = metodos_distintos[0]
                    else:
                        forma_pago_final = 'mixto'

                    numero_transaccion_final = ''
                    banco_final = ''
                    if forma_pago_final == 'nota_credito':
                        numero_transaccion_final = nc_code
                    elif forma_pago_final in ('debito', 'credito', 'transferencia'):
                        p = next((x for x in otros_pagos if x['metodo'] == forma_pago_final), None)
                        if p:
                            numero_transaccion_final = p.get('numero_transaccion') or ''
                            banco_final = p.get('banco') or ''

                    venta = Venta.objects.create(
                        empleado=request.user,
                        tipo_venta=tipo_venta,
                        forma_pago=forma_pago_final,
                        total=Decimal('0.00'),
                        cliente_paga=cliente_paga_final,
                        vuelto_entregado=vuelto,
                        numero_transaccion=numero_transaccion_final,
                        banco=banco_final,
                        sucursal=caja_abierta.sucursal,
                        caja=caja_abierta,
                        nota_credito_usada=nota_credito_obj if (nota_credito_obj and monto_nota_credito > Decimal('0')) else None,
                        monto_nota_credito=monto_nota_credito,
                    )

                    # Persist payment breakdown
                    if monto_nota_credito > Decimal('0') and nota_credito_obj:
                        VentaPago.objects.create(
                            venta=venta,
                            metodo='nota_credito',
                            monto=monto_nota_credito,
                            numero_transaccion=nc_code,
                            banco='',
                            nota_credito=nota_credito_obj,
                        )
                    for p in otros_pagos:
                        VentaPago.objects.create(
                            venta=venta,
                            metodo=p['metodo'],
                            monto=p['monto'],
                            numero_transaccion=p.get('numero_transaccion') or '',
                            banco=p.get('banco') or '',
                            nota_credito=None,
                        )

                    for item in carrito:
                        pid = int(item.get('producto_id'))
                        producto = products_map[pid]
                        cantidad = int(item.get('cantidad', 1))
                        producto.decrementar_stock_en(caja_abierta.sucursal, cantidad)
                        VentaDetalle.objects.create(
                            venta=venta,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=producto.precio_venta
                        )
                    venta.total = _to_clp_pesos(total)
                    venta.save(update_fields=['total'])

                    # Update caja aggregates (best-effort)
                    try:
                        caja_locked = AperturaCierreCaja.objects.select_for_update().get(id=caja_abierta.id)
                        caja_locked.ventas_totales = (caja_locked.ventas_totales or Decimal('0.00')) + total
                        caja_locked.total_ventas_efectivo = (caja_locked.total_ventas_efectivo or Decimal('0.00')) + efectivo_monto
                        caja_locked.total_ventas_debito = (caja_locked.total_ventas_debito or Decimal('0.00')) + _to_clp_pesos(sum((x['monto'] for x in otros_pagos if x['metodo'] == 'debito'), Decimal('0')))
                        caja_locked.total_ventas_credito = (caja_locked.total_ventas_credito or Decimal('0.00')) + _to_clp_pesos(sum((x['monto'] for x in otros_pagos if x['metodo'] == 'credito'), Decimal('0')))
                        caja_locked.vuelto_entregado = (caja_locked.vuelto_entregado or Decimal('0.00')) + (vuelto or Decimal('0.00'))
                        caja_locked.efectivo_final = (caja_locked.efectivo_inicial or Decimal('0.00')) + (caja_locked.total_ventas_efectivo or Decimal('0.00'))
                        caja_locked.save(update_fields=['ventas_totales', 'total_ventas_efectivo', 'total_ventas_debito', 'total_ventas_credito', 'vuelto_entregado', 'efectivo_final'])
                    except Exception:
                        pass

                    reporte_url = reverse('reporte_venta', args=[venta.id])
                    return JsonResponse({
                        "success": True,
                        "mensaje": "Compra confirmada con éxito.",
                        "venta_id": venta.id,
                        "reporte_url": reporte_url
                    })

                # Store credit: allow partial usage. If forma_pago='nota_credito', it must cover full total.
                nota_credito_obj = None
                monto_nota_credito = Decimal('0.00')
                nc_code = (nota_credito_codigo or (numero_transaccion if forma_pago == 'nota_credito' else '')).strip()
                if nc_code:
                    nota_credito_obj = NotaCredito.objects.select_for_update().filter(codigo=nc_code, activa=True).first()
                    if not nota_credito_obj:
                        return JsonResponse({"error": "Nota de crédito no encontrada o inactiva."}, status=400)
                    if nota_credito_obj.sucursal_id != caja_abierta.sucursal_id:
                        return JsonResponse({"error": "La nota de crédito no corresponde a esta sucursal."}, status=400)
                    saldo = _to_clp_pesos(nota_credito_obj.saldo or Decimal('0'))
                    monto_nota_credito = _to_clp_pesos(min(saldo, total))
                    if forma_pago == 'nota_credito' and monto_nota_credito < total:
                        return JsonResponse({"error": "Saldo insuficiente en la nota de crédito."}, status=400)

                total_a_pagar = _to_clp_pesos(total - monto_nota_credito)

                # If store credit covers the whole amount, force payment method to nota_credito.
                forma_pago_final = forma_pago
                numero_transaccion_final = numero_transaccion
                banco_final = banco
                cliente_paga_final = cliente_paga

                if total_a_pagar <= Decimal('0'):
                    forma_pago_final = 'nota_credito'
                    numero_transaccion_final = nc_code
                    banco_final = ''
                    cliente_paga_final = Decimal('0.00')
                else:
                    # Card/transfer validations only apply if there is a remaining amount to pay.
                    if forma_pago_final == 'nota_credito':
                        return JsonResponse({
                            "error": "La nota de crédito no cubre el total. Selecciona un método de pago para la diferencia."
                        }, status=400)
                    if forma_pago_final in ["debito", "credito", "transferencia"] and not numero_transaccion_final:
                        return JsonResponse({
                            "error": "El número de transacción es obligatorio para pagos con tarjeta y transferencia."
                        }, status=400)
                    if forma_pago_final == "transferencia" and not banco_final:
                        return JsonResponse({
                            "error": "Debe ingresar el nombre del banco para pagos por transferencia."
                        }, status=400)
                    if forma_pago_final == 'efectivo' and cliente_paga_final < total_a_pagar:
                        return JsonResponse({
                            "error": f"Pago insuficiente. El total a pagar es ${format_currency(total_a_pagar)}, pero el cliente pagó ${format_currency(cliente_paga_final)}."
                        }, status=400)

                # Apply store credit deduction if any
                if nota_credito_obj and monto_nota_credito > Decimal('0'):
                    nota_credito_obj.saldo = _to_clp_pesos((nota_credito_obj.saldo or Decimal('0')) - monto_nota_credito)
                    if nota_credito_obj.saldo <= Decimal('0'):
                        nota_credito_obj.saldo = Decimal('0.00')
                        nota_credito_obj.activa = False
                        nota_credito_obj.save(update_fields=['saldo', 'activa'])
                    else:
                        nota_credito_obj.save(update_fields=['saldo'])

                venta = Venta.objects.create(
                    empleado=request.user,
                    tipo_venta=tipo_venta,
                    forma_pago=forma_pago_final,
                    total=Decimal('0.00'),
                    cliente_paga=cliente_paga_final if forma_pago_final == "efectivo" else Decimal('0.00'),
                    vuelto_entregado=Decimal('0.00'),
                    numero_transaccion=numero_transaccion_final if forma_pago_final in ["debito", "credito", "transferencia", "nota_credito"] else "",
                    banco=banco_final,
                    sucursal=caja_abierta.sucursal,
                    caja=caja_abierta,
                    nota_credito_usada=nota_credito_obj if (nota_credito_obj and monto_nota_credito > Decimal('0')) else None,
                    monto_nota_credito=monto_nota_credito,
                )

                for item in carrito:
                    pid = int(item.get('producto_id'))
                    producto = products_map[pid]
                    cantidad = int(item.get('cantidad', 1))
                    producto.decrementar_stock_en(caja_abierta.sucursal, cantidad)
                    VentaDetalle.objects.create(
                        venta=venta,
                        producto=producto,
                        cantidad=cantidad,
                        precio_unitario=producto.precio_venta
                    )
                venta.total = _to_clp_pesos(total)
                if forma_pago_final == "efectivo":
                    venta.vuelto_entregado = _to_clp_pesos(max(Decimal('0'), cliente_paga_final - total_a_pagar))
                venta.save()

                # Persist payment breakdown (legacy payload compatibility)
                try:
                    if nota_credito_obj and monto_nota_credito > Decimal('0'):
                        VentaPago.objects.create(
                            venta=venta,
                            metodo='nota_credito',
                            monto=monto_nota_credito,
                            numero_transaccion=nc_code,
                            banco='',
                            nota_credito=nota_credito_obj,
                        )
                    if total_a_pagar > Decimal('0'):
                        VentaPago.objects.create(
                            venta=venta,
                            metodo=forma_pago_final,
                            monto=total_a_pagar,
                            numero_transaccion=numero_transaccion_final if forma_pago_final in ["debito", "credito", "transferencia"] else '',
                            banco=banco_final if forma_pago_final == 'transferencia' else '',
                            nota_credito=None,
                        )
                except Exception:
                    pass
                # Actualizar métricas de la caja de forma atómica y consistente
                try:
                    # Reobtener caja con bloqueo para evitar condiciones de carrera entre ventas
                    caja_locked = AperturaCierreCaja.objects.select_for_update().get(id=caja_abierta.id)
                    caja_locked.ventas_totales = (caja_locked.ventas_totales or Decimal('0.00')) + total
                    if forma_pago_final == 'efectivo':
                        caja_locked.total_ventas_efectivo = (caja_locked.total_ventas_efectivo or Decimal('0.00')) + total_a_pagar
                    elif forma_pago_final == 'debito':
                        caja_locked.total_ventas_debito = (caja_locked.total_ventas_debito or Decimal('0.00')) + total_a_pagar
                    elif forma_pago_final == 'credito':
                        caja_locked.total_ventas_credito = (caja_locked.total_ventas_credito or Decimal('0.00')) + total_a_pagar
                    # Sumar los vueltos entregados (si aplica)
                    caja_locked.vuelto_entregado = (caja_locked.vuelto_entregado or Decimal('0.00')) + (venta.vuelto_entregado or Decimal('0.00'))
                    # Recalcular efectivo_final (efectivo inicial + ventas en efectivo acumuladas)
                    caja_locked.efectivo_final = (caja_locked.efectivo_inicial or Decimal('0.00')) + (caja_locked.total_ventas_efectivo or Decimal('0.00'))
                    caja_locked.save(update_fields=['ventas_totales', 'total_ventas_efectivo', 'total_ventas_debito', 'total_ventas_credito', 'vuelto_entregado', 'efectivo_final'])
                except Exception:
                    # Si ocurre algo al actualizar la caja, seguir (la transacción aún asegura consistencia en la DB)
                    pass
            reporte_url = reverse('reporte_venta', args=[venta.id])
            return JsonResponse({
                "success": True,
                "mensaje": "Compra confirmada con éxito.",
                "venta_id": venta.id,
                "reporte_url": reporte_url
            })
        except (json.JSONDecodeError, KeyError, ValueError, Product.DoesNotExist) as e:
            return JsonResponse({"error": f"Error en los datos enviados o producto no encontrado: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Ocurrió un error inesperado: {str(e)}"}, status=500)
    return JsonResponse({"error": "Método no permitido."}, status=405)


@login_required
def validar_nota_credito(request):
    codigo = ''
    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
        except Exception:
            data = {}
        codigo = (data.get('codigo') or '').strip()

    if not codigo:
        codigo = (request.GET.get('codigo') or '').strip()

    if not codigo:
        return JsonResponse({'ok': False, 'error': 'Debe ingresar un código.'}, status=400)

    caja_abierta = get_current_caja(request)
    if not caja_abierta:
        return JsonResponse({'ok': False, 'error': 'Debes tener una caja abierta.'}, status=400)

    nc = NotaCredito.objects.filter(codigo=codigo, activa=True).first()
    if not nc:
        return JsonResponse({'ok': False, 'error': 'Nota de crédito no encontrada o inactiva.'}, status=404)
    if nc.sucursal_id != caja_abierta.sucursal_id:
        return JsonResponse({'ok': False, 'error': 'La nota de crédito no corresponde a esta sucursal.'}, status=400)
    saldo = _to_clp_pesos(nc.saldo or Decimal('0'))
    return JsonResponse({'ok': True, 'codigo': nc.codigo, 'saldo': float(saldo)})


@login_required
@transaction.atomic
def devolver_venta(request, venta_id):
    venta = get_object_or_404(
        Venta.objects.select_related('sucursal', 'caja', 'empleado').prefetch_related('detalles__producto'),
        id=venta_id,
    )

    def _safe_next_url(default_name: str = 'cashier_dashboard'):
        candidate = (request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER') or '').strip()
        if candidate and url_has_allowed_host_and_scheme(
            url=candidate,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return candidate
        return reverse(default_name)

    def _redirect_to_devolver_with_next():
        next_url = _safe_next_url('cashier_dashboard')
        devolver_url = reverse('devolver_venta', kwargs={'venta_id': venta.id})
        return redirect(f"{devolver_url}?next={quote(next_url, safe='')}")

    next_url = _safe_next_url('cashier_dashboard')

    caja_abierta = get_current_caja(request)
    is_admin = request.user.is_staff or request.user.is_superuser

    if not caja_abierta:
        if not is_admin:
            messages.error(request, 'Debes tener una caja abierta para procesar devoluciones.')
            return redirect('cashier_dashboard')
        # Admin sin caja: usar la sucursal de la venta directamente
        if not venta.sucursal:
            messages.error(request, 'Esta venta no tiene sucursal asignada y no se puede procesar la devolución sin caja abierta.')
            return redirect(_safe_next_url('reports:sales_history'))
        sucursal_devolucion = venta.sucursal
        admin_sin_caja = True
    else:
        # Con caja abierta: verificar misma sucursal
        if venta.sucursal_id and caja_abierta.sucursal_id != venta.sucursal_id:
            messages.warning(request, 'La devolución debe realizarse en la misma sucursal de la venta.')
            return redirect(_safe_next_url('cashier_dashboard'))
        sucursal_devolucion = caja_abierta.sucursal
        admin_sin_caja = False

    detalles = list(venta.detalles.all())
    devueltos_por_producto = {
        row['producto_id']: int(row['total'] or 0)
        for row in DevolucionDetalle.objects.filter(devolucion__venta_original=venta)
        .values('producto_id')
        .annotate(total=Sum('cantidad'))
    }

    lineas = []
    for d in detalles:
        ya = devueltos_por_producto.get(d.producto_id, 0)
        max_ret = 0 if ya > 0 else max(0, int(d.cantidad) - ya)
        lineas.append({
            'detalle': d,
            'max_returnable': max_ret,
            'ya_devuelto': ya,
        })

    if request.method == 'GET':
        return render(request, 'cashier/devolver_venta.html', {
            'venta': venta,
            'lineas': lineas,
            'caja_abierta': caja_abierta,
            'sucursal_devolucion': sucursal_devolucion,
            'admin_sin_caja': admin_sin_caja,
            'next_url': next_url,
        })

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    metodo_pago = (request.POST.get('metodo_pago') or 'efectivo').strip()
    numero_transaccion = (request.POST.get('numero_transaccion') or '').strip()
    banco = (request.POST.get('banco') or '').strip() if metodo_pago == 'transferencia' else ''

    if metodo_pago in ('debito', 'credito', 'transferencia') and not numero_transaccion:
        messages.error(request, 'El número de transacción es obligatorio para devoluciones con tarjeta/transferencia.')
        return _redirect_to_devolver_with_next()
    if metodo_pago == 'transferencia' and not banco:
        messages.error(request, 'Debe ingresar el banco para devoluciones por transferencia.')
        return _redirect_to_devolver_with_next()

    items = []
    total = Decimal('0.00')
    for row in lineas:
        d = row['detalle']
        max_ret = int(row['max_returnable'])
        ya_devuelto = int(row.get('ya_devuelto') or 0)
        raw_qty = (request.POST.get(f'qty_{d.id}') or '0').strip()
        try:
            qty = int(raw_qty)
        except Exception:
            qty = 0
        if qty <= 0:
            continue
        if ya_devuelto > 0:
            messages.error(request, f"'{d.producto.nombre}' ya tiene una devolución registrada. No se puede devolver el mismo producto más de una vez.")
            return _redirect_to_devolver_with_next()
        if qty > max_ret:
            messages.error(request, f"Cantidad inválida para '{d.producto.nombre}'. Máximo: {max_ret}.")
            return _redirect_to_devolver_with_next()
        destino = (request.POST.get(f'destino_{d.id}') or 'stock').strip()
        if destino not in ('stock', 'merma'):
            destino = 'stock'
        precio_unitario = d.precio_unitario or Decimal('0.00')
        subtotal = _to_clp_pesos(Decimal(str(qty)) * precio_unitario)
        total += subtotal
        items.append({
            'producto': d.producto,
            'cantidad': qty,
            'precio_unitario': precio_unitario,
            'destino': destino,
        })

    if not items:
        messages.error(request, 'Debes ingresar al menos un ítem para devolver.')
        return redirect('devolver_venta', venta_id=venta.id)

    total = _to_clp_pesos(total)
    devolucion = Devolucion.objects.create(
        venta_original=venta,
        empleado=request.user,
        sucursal=sucursal_devolucion,
        caja=caja_abierta,
        total=total,
        metodo_pago=metodo_pago,
        numero_transaccion=numero_transaccion if metodo_pago in ('debito', 'credito', 'transferencia') else '',
        banco=banco,
    )

    # Ajustar stock según destino por ítem (con bloqueo)
    product_ids = [it['producto'].id for it in items if it['destino'] == 'stock']
    if product_ids:
        Product.objects.select_for_update().filter(id__in=product_ids)

    for it in items:
        DevolucionDetalle.objects.create(
            devolucion=devolucion,
            producto=it['producto'],
            cantidad=it['cantidad'],
            precio_unitario=it['precio_unitario'],
            destino=it['destino'],
        )
        if it['destino'] == 'stock':
            try:
                it['producto'].incrementar_stock_en(sucursal_devolucion, int(it['cantidad']))
            except Exception:
                pass

    # Emisión de nota de crédito (store credit)
    if metodo_pago == 'nota_credito':
        codigo = None
        for _ in range(6):
            candidate = NotaCredito.generar_codigo()
            if not NotaCredito.objects.filter(codigo=candidate).exists():
                codigo = candidate
                break
        if not codigo:
            messages.error(request, 'No se pudo generar el código de nota de crédito. Intenta nuevamente.')
            raise RuntimeError('No se pudo generar código único de nota de crédito')

        nc = NotaCredito.objects.create(
            codigo=codigo,
            sucursal=sucursal_devolucion,
            monto_emitido=total,
            saldo=total,
            activa=True,
            creada_por=request.user,
        )
        devolucion.nota_credito = nc
        devolucion.save(update_fields=['nota_credito'])

    # Actualizar métricas de caja (netas) solo si hay caja abierta
    if caja_abierta:
        try:
            caja_locked = AperturaCierreCaja.objects.select_for_update().get(id=caja_abierta.id)
            caja_locked.ventas_totales = _to_clp_pesos((caja_locked.ventas_totales or Decimal('0.00')) - total)
            if metodo_pago == 'efectivo':
                caja_locked.total_ventas_efectivo = _to_clp_pesos((caja_locked.total_ventas_efectivo or Decimal('0.00')) - total)
            elif metodo_pago == 'debito':
                caja_locked.total_ventas_debito = _to_clp_pesos((caja_locked.total_ventas_debito or Decimal('0.00')) - total)
            elif metodo_pago == 'credito':
                caja_locked.total_ventas_credito = _to_clp_pesos((caja_locked.total_ventas_credito or Decimal('0.00')) - total)
            caja_locked.efectivo_final = _to_clp_pesos((caja_locked.efectivo_inicial or Decimal('0.00')) + (caja_locked.total_ventas_efectivo or Decimal('0.00')))
            caja_locked.save(update_fields=['ventas_totales', 'total_ventas_efectivo', 'total_ventas_debito', 'total_ventas_credito', 'efectivo_final'])
        except Exception:
            pass

    messages.success(request, 'Devolución registrada correctamente.')
    # Redirect to the reporte_devolucion view, preserving the caller's `next` if present
    redirect_url = reverse('reporte_devolucion', kwargs={'devolucion_id': devolucion.id})
    try:
        return redirect(f"{redirect_url}?next={quote(next_url, safe='')}")
    except Exception:
        return redirect(redirect_url)


@login_required
def reporte_devolucion(request, devolucion_id):
    devolucion = get_object_or_404(
        Devolucion.objects.select_related('venta_original', 'sucursal', 'empleado', 'nota_credito'),
        id=devolucion_id,
    )
    detalles = list(devolucion.detalles.select_related('producto').all())
    total_formatted = "$" + format_currency(devolucion.total or 0)

    # Determine a safe "back to history" URL. Prefer explicit `next` query param,
    # then the HTTP_REFERER, else fall back to the cashier sales history.
    candidate = (request.GET.get('next') or request.META.get('HTTP_REFERER') or '').strip()
    if candidate and url_has_allowed_host_and_scheme(url=candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        back_history_href = candidate
    else:
        back_history_href = reverse('cashier_sales_history')

    return render(request, 'cashier/reporte_devolucion.html', {
        'devolucion': devolucion,
        'detalles': detalles,
        'formatted_total': total_formatted,
        'back_history_href': back_history_href,
    })


@login_required
def print_devolucion(request, devolucion_id):
    devolucion = get_object_or_404(
        Devolucion.objects.select_related('venta_original', 'sucursal', 'empleado', 'caja'),
        id=devolucion_id,
    )
    detalles = list(devolucion.detalles.select_related('producto').all())
    detalles_data = []
    for d in detalles:
        subtotal = (d.cantidad or 0) * (d.precio_unitario or 0)
        detalles_data.append({
            'producto': d.producto,
            'cantidad': d.cantidad,
            'precio_unitario': d.precio_unitario,
            'formatted_subtotal': "$" + format_currency(subtotal),
        })

    total_formatted = "$" + format_currency(devolucion.total or 0)
    ctx = {
        'devolucion': devolucion,
        'detalles': detalles_data,
        'formatted_total': total_formatted,
        'sucursal': devolucion.sucursal,
    }
    return render(request, 'cashier/print_devolucion.html', ctx)


@login_required
@ensure_csrf_cookie
def cashier_bootstrap(request):
    """Bootstrap endpoint for the React/Vite cashier UI (local testing).

    - Ensures CSRF cookie exists.
    - Returns current authenticated user and current open caja (if any).
    - Mirrors the server-side session behavior used by legacy cashier template.
    """
    caja_abierta = get_current_caja(request)
    if caja_abierta:
        try:
            request.session['caja_id'] = caja_abierta.id
            request.session.modified = True
        except Exception:
            pass

    sucursal_nombre = None
    sucursal_id = None
    caja_id = None
    if caja_abierta:
        caja_id = caja_abierta.id
        if getattr(caja_abierta, 'sucursal', None):
            sucursal_nombre = caja_abierta.sucursal.nombre
            sucursal_id = caja_abierta.sucursal.id

    return JsonResponse({
        'user': {
            'username': getattr(request.user, 'username', ''),
        },
        'caja': {
            'id': caja_id,
            'sucursal': {
                'id': sucursal_id,
                'nombre': sucursal_nombre,
            } if caja_abierta else None,
        } if caja_abierta else None,
        'has_open_caja': bool(caja_abierta),
        'open_caja_url': reverse('abrir_caja'),
        'cashier_url': reverse('cashier_dashboard'),
    })

import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from .models import AperturaCierreCaja

@login_required
@csrf_protect
@transaction.atomic
def cerrar_caja(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        data = _parse_body_json(request)
        force_close = bool(data.get('force'))
        caja_id = data.get('caja_id') or request.session.get('caja_id')

        caja = None
        if caja_id:
            caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
            if not (request.user.is_superuser or request.user.is_staff or caja.vendedor_id == request.user.id):
                # Si el cliente envía un caja_id erróneo (por ejemplo, sesión vieja),
                # intentar cerrar la caja abierta real del usuario (si existe).
                caja = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').first()
                if not caja:
                    return JsonResponse({'error': 'No tienes permisos para operar esta caja.'}, status=403)
        else:
            caja = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').first()
            if not caja:
                return JsonResponse({'error': 'No tienes una caja abierta para cerrar.'}, status=400)
        if caja.estado == 'cerrada':
            return JsonResponse({'error': 'La caja ya está cerrada.'}, status=400)
        fecha_fin = timezone.now()
        # Usar la relación explícita a la caja para evitar incluir ventas de otros periodos
        ventas_qs = Venta.objects.filter(caja=caja)
        total_ventas_brutas = _to_clp_pesos(ventas_qs.aggregate(total=Sum('total'))['total'] or Decimal('0'))
        ventas_efectivo_brutas = _to_clp_pesos(ventas_qs.filter(forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0'))
        ventas_debito_brutas = _to_clp_pesos(ventas_qs.filter(forma_pago='debito').aggregate(total=Sum('total'))['total'] or Decimal('0'))
        ventas_credito_brutas = _to_clp_pesos(ventas_qs.filter(forma_pago='credito').aggregate(total=Sum('total'))['total'] or Decimal('0'))

        devoluciones_qs = Devolucion.objects.filter(caja=caja)
        total_devoluciones = _to_clp_pesos(devoluciones_qs.aggregate(total=Sum('total'))['total'] or Decimal('0'))
        devol_efectivo = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0'))
        devol_debito = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='debito').aggregate(total=Sum('total'))['total'] or Decimal('0'))
        devol_credito = _to_clp_pesos(devoluciones_qs.filter(metodo_pago='credito').aggregate(total=Sum('total'))['total'] or Decimal('0'))

        # Totales netos (ventas - devoluciones)
        total_ventas = _to_clp_pesos(total_ventas_brutas - total_devoluciones)
        ventas_efectivo = _to_clp_pesos(ventas_efectivo_brutas - devol_efectivo)
        ventas_debito = _to_clp_pesos(ventas_debito_brutas - devol_debito)
        ventas_credito = _to_clp_pesos(ventas_credito_brutas - devol_credito)
        vuelto_total = _to_clp_pesos(ventas_qs.aggregate(total=Sum('vuelto_entregado'))['total'] or Decimal('0'))
        # Efectivo final esperado (según transacciones): efectivo inicial + ventas en efectivo
        efectivo_final_esperado = _to_clp_pesos((caja.efectivo_inicial or Decimal('0')) + ventas_efectivo)

        # Efectivo contado (input del cajero).
        # Regla UX:
        # - En cierre normal (cashier), debe enviarse explícitamente.
        # - En cierres forzados (reports/admin), si no se envía, se asume el esperado.
        efectivo_contado_raw = data.get('efectivo_contado')
        if efectivo_contado_raw is None or str(efectivo_contado_raw).strip() == '':
            if force_close:
                efectivo_contado = efectivo_final_esperado
            else:
                return JsonResponse({'error': 'Debes ingresar el efectivo contado para cerrar la caja.'}, status=400)
        else:
            try:
                efectivo_contado = _to_clp_pesos(_parse_clp_decimal(efectivo_contado_raw))
            except Exception:
                return JsonResponse({'error': 'El monto contado no es un número válido.'}, status=400)
        if efectivo_contado < Decimal('0'):
            return JsonResponse({'error': 'El monto contado no puede ser negativo.'}, status=400)

        # Calcular descuadre: contado - esperado
        descuadre = _to_clp_pesos((efectivo_contado or Decimal('0')) - efectivo_final_esperado)
        # Persistir estado y métricas básicas
        caja.cierre = fecha_fin
        caja.estado = 'cerrada'
        caja.ventas_totales = total_ventas
        caja.total_ventas_efectivo = ventas_efectivo
        caja.total_ventas_debito = ventas_debito
        caja.total_ventas_credito = ventas_credito
        caja.vuelto_entregado = vuelto_total
        caja.efectivo_final = efectivo_final_esperado
        caja.efectivo_contado = efectivo_contado
        caja.descuadre = descuadre
        caja.save()
        # Limpiar carrito al cerrar la caja
        try:
            request.session['carrito'] = []
            request.session.modified = True
        except Exception:
            pass
        detalle_url = reverse('detalle_caja', args=[caja.id])

        # Resumen para UI
        try:
            if descuadre > Decimal('0.00'):
                desc_label = 'Efectivo Sobrante'
                desc_sign = 1
            elif descuadre < Decimal('0.00'):
                desc_label = 'Faltante'
                desc_sign = -1
            else:
                desc_label = 'Cuadrada'
                desc_sign = 0
            formatted_desc = "$" + format_clp(abs(descuadre))
        except Exception:
            desc_label = None
            desc_sign = None
            formatted_desc = None

        return JsonResponse({
            'success': True,
            'detalle_url': detalle_url,
            'descuadre_label': desc_label,
            'descuadre_sign': desc_sign,
            'formatted_descuadre_signed': formatted_desc,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def detalle_caja(request, caja_id):
    caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
    # Si la caja está abierta y el usuario es admin, redirigir a la vista del cajero con esa caja
    if caja.estado == 'abierta' and request.user.is_superuser:
        return redirect(f"{reverse('cashier_dashboard')}?caja_id={caja.id}")
    fin = _compute_caja_financials(caja)
    ventas_qs = fin['ventas_qs']
    ventas_total = fin['ventas_total']
    ventas_efectivo = fin['ventas_efectivo']
    ventas_debito = fin['ventas_debito']
    ventas_credito = fin['ventas_credito']
    ventas_transferencia = fin['ventas_transferencia']
    vuelto_total = fin['vuelto_total']
    efectivo_final_calc = fin['efectivo_final_calc']

    # Si la caja ya está cerrada y el cajero ingresó el `efectivo_contado`, mostrar
    # ese valor como el efectivo final visible y exponer el descuadre.
    if caja.estado == 'cerrada' and getattr(caja, 'efectivo_contado', None) is not None:
        efectivo_final_display = caja.efectivo_contado
        descuadre_val = caja.descuadre if getattr(caja, 'descuadre', None) is not None else Decimal('0.00')
        efectivo_contado_val = caja.efectivo_contado
        # detectar si el contado difiere del esperado
        efectivo_contado_differs = (_to_clp_pesos(efectivo_contado_val) != (efectivo_final_calc or Decimal('0')))
        # solo mostrar el descuadre si es negativo (faltante)
        descuadre_shown = (descuadre_val < Decimal('0.00'))
    else:
        efectivo_final_display = efectivo_final_calc
        descuadre_val = None
        efectivo_contado_val = None
        efectivo_contado_differs = False
        descuadre_shown = False
    
    contexto = {
        'caja': caja,
        'formatted_efectivo_inicial': "$" + format_clp(caja.efectivo_inicial or Decimal('0.00')),
        'formatted_total_debito': "$" + format_clp(ventas_debito),
        'formatted_total_credito': "$" + format_clp(ventas_credito),
        'formatted_total_transferencia': "$" + format_clp(ventas_transferencia),
        'formatted_total_efectivo': "$" + format_clp(ventas_efectivo),
        'formatted_vuelto_entregado': "$" + format_clp(vuelto_total),
        'formatted_efectivo_final': "$" + format_clp(efectivo_final_calc),
        'formatted_total_ventas': "$" + format_clp(ventas_total),
        # Devoluciones (para transparencia)
        'formatted_devoluciones_total': "$" + format_clp(fin['devol_total']),
        'formatted_devoluciones_efectivo': "$" + format_clp(fin['devol_efectivo']),
        'formatted_devoluciones_debito': "$" + format_clp(fin['devol_debito']),
        'formatted_devoluciones_credito': "$" + format_clp(fin['devol_credito']),
        'formatted_devoluciones_transferencia': "$" + format_clp(fin['devol_transferencia']),
        # valor numérico esperado de efectivo final (para autocompletar en cierres forzados)
        'efectivo_final_expected': str(efectivo_final_calc),
        # si la caja está cerrada y se contó el efectivo, mostrarlo y el descuadre
        'formatted_efectivo_final_display': "$" + format_clp(efectivo_final_display),
        'formatted_efectivo_contado': ("$" + format_clp(efectivo_contado_val)) if efectivo_contado_val is not None else None,
        'formatted_descuadre': ("$" + format_clp(abs(descuadre_val))) if descuadre_shown else None,
        'efectivo_contado_raw': str(efectivo_contado_val) if efectivo_contado_val is not None else None,
        'efectivo_contado_differs': efectivo_contado_differs,
        'descuadre_shown': descuadre_shown,
    }
    # Añadir lista simple de ventas para detalle (sin datos sensibles)
    ventas_list = []
    for v in ventas_qs.order_by('fecha'):
        ventas_list.append({
            'id': v.id,
            'fecha': v.fecha.strftime('%d/%m/%Y %H:%M') if getattr(v, 'fecha', None) else '',
            'forma_pago': v.forma_pago,
            'tipo_venta': v.tipo_venta,
            'formatted_total': "$" + format_currency(v.total or 0),
        })
    contexto['ventas_list'] = ventas_list
    # Calcular descuadre signed y etiqueta si existe efectivo contado
    if getattr(caja, 'efectivo_contado', None) is not None:
        try:
            diff = _to_clp_pesos(_to_clp_pesos(caja.efectivo_contado) - efectivo_final_calc)
            if diff > 0:
                label = 'Efectivo Sobrante'
            elif diff < 0:
                label = 'Faltante'
            else:
                label = 'Cuadrada'
            contexto['descuadre_label'] = label
            contexto['formatted_descuadre_signed'] = "$" + format_clp(abs(diff))
        except Exception:
            contexto['descuadre_label'] = None
            contexto['formatted_descuadre_signed'] = None
    return render(request, 'cashier/detalle_caja.html', contexto)

@login_required
def print_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    detalles_data = _build_detalles_data(venta)
    total_formatted = "$" + format_currency(venta.total or 0)
    monto_nc = _to_clp_pesos(getattr(venta, 'monto_nota_credito', None) or Decimal('0'))
    total_a_pagar = _to_clp_pesos((venta.total or Decimal('0')) - monto_nc)
    nota_credito_formatted = ("$" + format_currency(monto_nc)) if monto_nc > 0 else None
    total_a_pagar_formatted = ("$" + format_currency(total_a_pagar)) if monto_nc > 0 else None
    cliente_paga_formatted = "$" + format_currency(venta.cliente_paga or 0)
    vuelto_formatted = "$" + format_currency(venta.vuelto_entregado or 0)
    payment_breakdown = _build_payment_breakdown(venta)
    forma_pago_label = 'Mixta' if venta.forma_pago == 'mixto' else venta.get_forma_pago_display()
    ctx = {
        'venta': venta,
        'detalles': detalles_data,
        'formatted_total': total_formatted,
        'formatted_nota_credito': nota_credito_formatted,
        'formatted_total_a_pagar': total_a_pagar_formatted,
        'formatted_cliente_paga': cliente_paga_formatted,
        'formatted_vuelto_entregado': vuelto_formatted,
        'sucursal': venta.sucursal,
        'forma_pago_label': forma_pago_label,
        'payment_breakdown': payment_breakdown,
        'show_payment_breakdown': (venta.forma_pago == 'mixto' or len(payment_breakdown) > 1),
    }
    return render(request, 'cashier/print_venta.html', ctx)

@login_required
def print_caja(request, caja_id):
    caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
    fin = _compute_caja_financials(caja)
    ventas_qs = fin['ventas_qs']
    ventas_total = fin['ventas_total']
    ventas_efectivo = fin['ventas_efectivo']
    ventas_debito = fin['ventas_debito']
    ventas_credito = fin['ventas_credito']
    ventas_transferencia = fin['ventas_transferencia']
    vuelto_total = fin['vuelto_total']
    efectivo_final_calc = fin['efectivo_final_calc']
    # Determinar si se contó efectivo al cerrar
    if caja.estado == 'cerrada' and getattr(caja, 'efectivo_contado', None) is not None:
        efectivo_final_display = caja.efectivo_contado
        descuadre_val = caja.descuadre if getattr(caja, 'descuadre', None) is not None else Decimal('0.00')
        efectivo_contado_val = caja.efectivo_contado
        efectivo_contado_differs = (Decimal(str(efectivo_contado_val)) != (efectivo_final_calc or Decimal('0.00')))
        descuadre_shown = (descuadre_val < Decimal('0.00'))
    else:
        efectivo_final_display = efectivo_final_calc
        descuadre_val = None
        efectivo_contado_val = None
        efectivo_contado_differs = False
        descuadre_shown = False

    ctx = {
        'caja': caja,
        'formatted_efectivo_inicial': "$" + format_clp(caja.efectivo_inicial or Decimal('0.00')),
        'formatted_total_debito': "$" + format_clp(ventas_debito),
        'formatted_total_credito': "$" + format_clp(ventas_credito),
        'formatted_total_transferencia': "$" + format_clp(ventas_transferencia),
        'formatted_total_efectivo': "$" + format_clp(ventas_efectivo),
        'formatted_vuelto_entregado': "$" + format_clp(vuelto_total),
        'formatted_total_ventas': "$" + format_clp(ventas_total),
        'formatted_efectivo_final': "$" + format_clp(efectivo_final_calc),
        'formatted_efectivo_final_display': "$" + format_clp(efectivo_final_display),
        # Devoluciones (para transparencia)
        'formatted_devoluciones_total': "$" + format_clp(fin['devol_total']),
        'formatted_devoluciones_efectivo': "$" + format_clp(fin['devol_efectivo']),
        'formatted_devoluciones_debito': "$" + format_clp(fin['devol_debito']),
        'formatted_devoluciones_credito': "$" + format_clp(fin['devol_credito']),
        'formatted_devoluciones_transferencia': "$" + format_clp(fin['devol_transferencia']),
        'formatted_efectivo_contado': ("$" + format_clp(efectivo_contado_val)) if efectivo_contado_val is not None else None,
        'formatted_descuadre': ("$" + format_clp(abs(descuadre_val))) if descuadre_shown else None,
        'efectivo_contado_raw': str(efectivo_contado_val) if efectivo_contado_val is not None else None,
        'efectivo_contado_differs': efectivo_contado_differs,
        'descuadre_shown': descuadre_shown,
    }
    # Añadir lista simple de ventas para impresión (sin datos sensibles)
    ventas_list = []
    for v in ventas_qs.order_by('fecha'):
        ventas_list.append({
            'id': v.id,
            'fecha': v.fecha.strftime('%d/%m/%Y %H:%M') if getattr(v, 'fecha', None) else '',
            'forma_pago': v.forma_pago,
            'tipo_venta': v.tipo_venta,
            'formatted_total': "$" + format_currency(v.total or 0),
            'documento': v.tipo_venta,
        })
    ctx['ventas_list'] = ventas_list
    # Si existe efectivo contado, calcular diferencia (signed)
    if getattr(caja, 'efectivo_contado', None) is not None:
        try:
            diff = (Decimal(str(caja.efectivo_contado)) - efectivo_final_calc)
            if diff > 0:
                label = 'Efectivo Sobrante'
            elif diff < 0:
                label = 'Faltante'
            else:
                label = 'Cuadrada'
            ctx['descuadre_label'] = label
            ctx['formatted_descuadre_signed'] = "$" + format_clp(abs(diff))
        except Exception:
            ctx['descuadre_label'] = None
            ctx['formatted_descuadre_signed'] = None
    return render(request, 'cashier/print_caja.html', ctx)

@login_required
def historial_caja(request):
    historial_cajas = AperturaCierreCaja.objects.all().order_by('-apertura')
    return render(request, 'cashier/historial_caja.html', {'historial_cajas': historial_cajas})

@login_required
def buscar_producto(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'productos': []})
    # Resolver caja de forma consistente
    caja_abierta = get_current_caja(request)
    # Base query por texto
    base_qs = Product.objects.select_related('categoria').filter(
        Q(nombre__icontains=query) |
        Q(producto_id__icontains=query) |
        Q(codigo_barras__icontains=query) |
        Q(codigo_alternativo__icontains=query),
        activo=True,
    )
    # Mostrar todos los productos que coincidan; el frontend indicará si se pueden agregar o no
    productos = base_qs
    # Calcular stock por sucursal cuando procede
    resultados = []
    for p in productos:
        # Determinar si el producto se puede vender desde la sucursal actual
        en_sucursal = True
        allow_without_stock = p.permitir_venta_sin_stock_en(caja_abierta.sucursal) if (caja_abierta and caja_abierta.sucursal_id) else p.permitir_venta_sin_stock
        if caja_abierta and caja_abierta.sucursal_id:
            en_sucursal = p.asignado_a_sucursal(caja_abierta.sucursal) or allow_without_stock
        # Calcular stock a mostrar
        if caja_abierta and caja_abierta.sucursal_id:
            stock_val = p.stock_en(caja_abierta.sucursal)
        else:
            stock_val = p.stock or 0
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio_venta': str(p.precio_venta),
            'stock': stock_val,
            'permitir_venta_sin_stock': allow_without_stock,
            'en_sucursal': en_sucursal,
            'categoria_id': p.categoria_id,
            'categoria_nombre': p.categoria.nombre if p.categoria_id else None,
        })
    return JsonResponse({'productos': resultados})


# ---------------------------------------------------------------------------
# Offline-mode endpoints
# ---------------------------------------------------------------------------

@login_required
def offline_heartbeat(request):
    """Simple liveness check — frontend polls this to detect connectivity."""
    return JsonResponse({'ok': True})


@login_required
def offline_catalog_snapshot(request):
    """Returns all active products with stock for the user's current branch."""
    from products.models import Product as _Product

    caja_abierta = get_current_caja(request)
    if not caja_abierta or not caja_abierta.sucursal_id:
        return JsonResponse({'error': 'No hay caja abierta'}, status=400)

    sucursal = caja_abierta.sucursal
    products_qs = (
        _Product.objects
        .filter(activo=True, archivado=False)
        .select_related('categoria')
        .prefetch_related('stocks_por_sucursal')
    )

    items = []
    for p in products_qs:
        allow = p.permitir_venta_sin_stock_en(sucursal)
        en_sucursal = p.asignado_a_sucursal(sucursal) or allow
        items.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio_venta': int(_to_clp_pesos(p.precio_venta or Decimal('0'))),
            'stock': p.stock_en(sucursal),
            'permitir_venta_sin_stock': allow,
            'en_sucursal': en_sucursal,
            'categoria_id': p.categoria_id,
            'categoria_nombre': p.categoria.nombre if p.categoria_id else None,
        })

    return JsonResponse({
        'sucursal_id': sucursal.id,
        'sucursal_nombre': sucursal.nombre,
        'products': items,
        'timestamp': timezone.now().isoformat(),
    })


@login_required
@transaction.atomic
def offline_sync_sale(request):
    """
    Idempotent endpoint to persist a sale queued while offline.
    Accepts the same payload as POST /cashier/ plus offline_idempotency_key.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    data = _parse_body_json(request)
    if not data:
        return JsonResponse({'error': 'Payload inválido'}, status=400)

    # --- Idempotency check ---
    raw_key = data.get('offline_idempotency_key', '')
    if not raw_key:
        return JsonResponse({'error': 'offline_idempotency_key es requerido'}, status=400)
    try:
        idempotency_key = _uuid_module.UUID(str(raw_key))
    except (ValueError, AttributeError):
        return JsonResponse({'error': 'offline_idempotency_key inválido'}, status=400)

    existing = Venta.objects.filter(offline_idempotency_key=idempotency_key).first()
    if existing:
        return JsonResponse({'success': True, 'venta_id': existing.id, 'already_synced': True})

    # --- Resolve open caja ---
    caja_abierta = get_current_caja(request)
    if not caja_abierta:
        return JsonResponse({'error': 'No hay caja abierta. Abre una caja antes de sincronizar.'}, status=400)

    carrito = data.get('carrito', [])
    if not carrito:
        return JsonResponse({'error': 'Carrito vacío'}, status=400)

    tipo_venta = data.get('tipo_venta', 'boleta')
    if tipo_venta not in ('boleta', 'factura'):
        tipo_venta = 'boleta'

    # --- Validate and lock products ---
    product_ids = []
    for item in carrito:
        try:
            product_ids.append(int(item.get('producto_id')))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'producto_id inválido en carrito'}, status=400)

    products_qs = Product.objects.select_for_update().filter(id__in=product_ids, activo=True)
    products_map = {p.id: p for p in products_qs}
    if len(products_map) != len(set(product_ids)):
        return JsonResponse({'error': 'Uno o más productos no encontrados o inactivos'}, status=400)

    # Stock check
    total = Decimal('0.00')
    for item in carrito:
        pid = int(item.get('producto_id'))
        cantidad = int(item.get('cantidad', 1))
        producto = products_map[pid]
        stock_actual = producto.stock_en(caja_abierta.sucursal)
        if not producto.permitir_venta_sin_stock_en(caja_abierta.sucursal) and stock_actual < cantidad:
            return JsonResponse({
                'error': f'Stock insuficiente para "{producto.nombre}". Disponible: {stock_actual}.'
            }, status=400)
        total += _to_clp_pesos(producto.precio_venta or Decimal('0')) * cantidad
    total = _to_clp_pesos(total)

    # --- Parse payment info (same as cashier_dashboard) ---
    nota_credito_usada = None
    monto_nota_credito = Decimal('0.00')
    venta = None

    pagos_raw = data.get('pagos')
    if pagos_raw and isinstance(pagos_raw, list):
        # Mixed payment path
        parsed_pagos = []
        for p in pagos_raw:
            metodo = str(p.get('metodo', ''))
            if metodo not in ('efectivo', 'debito', 'credito', 'transferencia'):
                return JsonResponse({'error': f'Método de pago offline no soportado: {metodo}'}, status=400)
            try:
                monto = _to_clp_pesos(_parse_clp_decimal(str(p.get('monto', 0))))
            except Exception:
                return JsonResponse({'error': 'Monto de pago inválido'}, status=400)
            tx = str(p.get('numero_transaccion') or '').strip()
            bank = str(p.get('banco') or '').strip()
            if metodo in ('debito', 'credito', 'transferencia') and not tx:
                return JsonResponse({'error': 'Número de transacción requerido para pagos con tarjeta/transferencia.'}, status=400)
            if metodo == 'transferencia' and not bank:
                return JsonResponse({'error': 'Banco requerido para transferencia.'}, status=400)
            parsed_pagos.append({'metodo': metodo, 'monto': monto, 'numero_transaccion': tx, 'banco': bank})

        efectivo_row = next((p for p in parsed_pagos if p['metodo'] == 'efectivo'), None)
        metodos_distintos = sorted({p['metodo'] for p in parsed_pagos})
        forma_pago_final = metodos_distintos[0] if len(metodos_distintos) == 1 else 'mixto'
        efectivo_monto = efectivo_row['monto'] if efectivo_row else Decimal('0')
        cliente_paga_raw = data.get('cliente_paga', 0)
        try:
            cliente_paga_final = _to_clp_pesos(_parse_clp_decimal(str(cliente_paga_raw)))
        except Exception:
            cliente_paga_final = Decimal('0')
        vuelto = _to_clp_pesos(max(Decimal('0'), cliente_paga_final - efectivo_monto)) if efectivo_monto > 0 else Decimal('0')

        venta = Venta.objects.create(
            empleado=request.user,
            tipo_venta=tipo_venta,
            forma_pago=forma_pago_final,
            total=Decimal('0.00'),
            cliente_paga=cliente_paga_final if efectivo_monto > 0 else Decimal('0'),
            vuelto_entregado=vuelto,
            numero_transaccion='',
            banco='',
            sucursal=caja_abierta.sucursal,
            caja=caja_abierta,
            offline_idempotency_key=idempotency_key,
        )
        for p in parsed_pagos:
            VentaPago.objects.create(
                venta=venta, metodo=p['metodo'], monto=p['monto'],
                numero_transaccion=p.get('numero_transaccion') or '',
                banco=p.get('banco') or '', nota_credito=None,
            )
    else:
        # Simple payment path
        forma_pago = str(data.get('forma_pago', 'efectivo'))
        if forma_pago not in ('efectivo', 'debito', 'credito', 'transferencia'):
            return JsonResponse({'error': f'Método de pago offline no soportado: {forma_pago}'}, status=400)

        numero_transaccion = str(data.get('numero_transaccion') or '').strip()
        banco = str(data.get('banco') or '').strip()
        if forma_pago in ('debito', 'credito', 'transferencia') and not numero_transaccion:
            return JsonResponse({'error': 'Número de transacción requerido.'}, status=400)
        if forma_pago == 'transferencia' and not banco:
            return JsonResponse({'error': 'Banco requerido para transferencia.'}, status=400)

        cliente_paga_raw = data.get('cliente_paga', 0)
        try:
            cliente_paga_val = _to_clp_pesos(_parse_clp_decimal(str(cliente_paga_raw)))
        except Exception:
            cliente_paga_val = Decimal('0')

        if forma_pago == 'efectivo' and cliente_paga_val < total:
            return JsonResponse({'error': 'Pago en efectivo insuficiente.'}, status=400)

        vuelto = _to_clp_pesos(max(Decimal('0'), cliente_paga_val - total)) if forma_pago == 'efectivo' else Decimal('0')

        venta = Venta.objects.create(
            empleado=request.user,
            tipo_venta=tipo_venta,
            forma_pago=forma_pago,
            total=Decimal('0.00'),
            cliente_paga=cliente_paga_val if forma_pago == 'efectivo' else Decimal('0'),
            vuelto_entregado=vuelto,
            numero_transaccion=numero_transaccion if forma_pago in ('debito', 'credito', 'transferencia') else '',
            banco=banco if forma_pago == 'transferencia' else '',
            sucursal=caja_abierta.sucursal,
            caja=caja_abierta,
            offline_idempotency_key=idempotency_key,
        )
        if total > Decimal('0'):
            VentaPago.objects.create(
                venta=venta, metodo=forma_pago, monto=total,
                numero_transaccion=numero_transaccion if forma_pago in ('debito', 'credito', 'transferencia') else '',
                banco=banco if forma_pago == 'transferencia' else '',
                nota_credito=None,
            )

    # --- Create sale lines and decrement stock ---
    for item in carrito:
        pid = int(item.get('producto_id'))
        producto = products_map[pid]
        cantidad = int(item.get('cantidad', 1))
        producto.decrementar_stock_en(caja_abierta.sucursal, cantidad)
        VentaDetalle.objects.create(
            venta=venta, producto=producto, cantidad=cantidad,
            precio_unitario=producto.precio_venta,
        )

    venta.total = total
    venta.save(update_fields=['total'])

    # Best-effort caja aggregate update
    try:
        caja_locked = AperturaCierreCaja.objects.select_for_update().get(id=caja_abierta.id)
        efectivo_monto_agg = Decimal('0')
        debito_monto_agg = Decimal('0')
        credito_monto_agg = Decimal('0')
        for vp in venta.ventapago_set.all():
            if vp.metodo == 'efectivo':
                efectivo_monto_agg += vp.monto or Decimal('0')
            elif vp.metodo == 'debito':
                debito_monto_agg += vp.monto or Decimal('0')
            elif vp.metodo == 'credito':
                credito_monto_agg += vp.monto or Decimal('0')
        caja_locked.ventas_totales = (caja_locked.ventas_totales or Decimal('0')) + total
        caja_locked.total_ventas_efectivo = (caja_locked.total_ventas_efectivo or Decimal('0')) + efectivo_monto_agg
        caja_locked.total_ventas_debito = (caja_locked.total_ventas_debito or Decimal('0')) + debito_monto_agg
        caja_locked.total_ventas_credito = (caja_locked.total_ventas_credito or Decimal('0')) + credito_monto_agg
        caja_locked.vuelto_entregado = (caja_locked.vuelto_entregado or Decimal('0')) + (venta.vuelto_entregado or Decimal('0'))
        caja_locked.efectivo_final = (caja_locked.efectivo_inicial or Decimal('0')) + (caja_locked.total_ventas_efectivo or Decimal('0'))
        caja_locked.save(update_fields=['ventas_totales', 'total_ventas_efectivo', 'total_ventas_debito', 'total_ventas_credito', 'vuelto_entregado', 'efectivo_final'])
    except Exception:
        pass

    return JsonResponse({'success': True, 'venta_id': venta.id})


@login_required
def reporte_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    embed_mode = request.GET.get('embed') == '1'
    detalles_data = _build_detalles_data(venta)
    total_formatted = "$" + format_currency(venta.total or 0)
    monto_nc = _to_clp_pesos(getattr(venta, 'monto_nota_credito', None) or Decimal('0'))
    total_a_pagar = _to_clp_pesos((venta.total or Decimal('0')) - monto_nc)
    nota_credito_formatted = ("$" + format_currency(monto_nc)) if monto_nc > 0 else None
    total_a_pagar_formatted = ("$" + format_currency(total_a_pagar)) if monto_nc > 0 else None
    cliente_paga_formatted = "$" + format_currency(venta.cliente_paga or 0)
    vuelto_formatted = "$" + format_currency(venta.vuelto_entregado or 0)
    payment_breakdown = _build_payment_breakdown(venta)
    forma_pago_label = 'Mixta' if venta.forma_pago == 'mixto' else venta.get_forma_pago_display()
    context = {
        'venta': venta,
        'detalles': detalles_data,
        'formatted_total': total_formatted,
        'formatted_nota_credito': nota_credito_formatted,
        'formatted_total_a_pagar': total_a_pagar_formatted,
        'formatted_cliente_paga': cliente_paga_formatted,
        'formatted_vuelto_entregado': vuelto_formatted,
        'sucursal': venta.sucursal,
        'forma_pago_label': forma_pago_label,
        'payment_breakdown': payment_breakdown,
        'show_payment_breakdown': (venta.forma_pago == 'mixto' or len(payment_breakdown) > 1),
    }
    if embed_mode:
        return render(request, 'cashier/partials/reporte_venta_embed.html', context)
    return render(request, 'cashier/reporte_venta.html', context)

@login_required
@xframe_options_sameorigin
def reporte_venta_embed(request, venta_id):
    """Versión embebible del detalle de venta para usar dentro del modal del cajero."""
    venta = get_object_or_404(Venta, id=venta_id)
    detalles_data = _build_detalles_data(venta)
    total_formatted = "$" + format_currency(venta.total or 0)
    monto_nc = _to_clp_pesos(getattr(venta, 'monto_nota_credito', None) or Decimal('0'))
    total_a_pagar = _to_clp_pesos((venta.total or Decimal('0')) - monto_nc)
    nota_credito_formatted = ("$" + format_currency(monto_nc)) if monto_nc > 0 else None
    total_a_pagar_formatted = ("$" + format_currency(total_a_pagar)) if monto_nc > 0 else None
    cliente_paga_formatted = "$" + format_currency(venta.cliente_paga or 0)
    vuelto_formatted = "$" + format_currency(venta.vuelto_entregado or 0)
    payment_breakdown = _build_payment_breakdown(venta)
    forma_pago_label = 'Mixta' if venta.forma_pago == 'mixto' else venta.get_forma_pago_display()
    context = {
        'venta': venta,
        'detalles': detalles_data,
        'formatted_total': total_formatted,
        'formatted_nota_credito': nota_credito_formatted,
        'formatted_total_a_pagar': total_a_pagar_formatted,
        'formatted_cliente_paga': cliente_paga_formatted,
        'formatted_vuelto_entregado': vuelto_formatted,
        'sucursal': venta.sucursal,
        'forma_pago_label': forma_pago_label,
        'payment_breakdown': payment_breakdown,
        'show_payment_breakdown': (venta.forma_pago == 'mixto' or len(payment_breakdown) > 1),
    }
    return render(request, 'cashier/partials/reporte_venta_embed.html', context)

@login_required
def ajustar_cantidad(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido."}, status=405)
    try:
        data = json.loads(request.body)
        producto_id = int(data.get('producto_id'))
        cambio_cantidad = int(data.get('cantidad'))
        producto = get_object_or_404(Product, id=producto_id)
        # Validar caja abierta
        caja_abierta = get_current_caja(request)
        if not caja_abierta:
            return JsonResponse({'error': 'No tienes una caja abierta en tu sucursal o no tienes permisos para operar esta caja.'}, status=403)
        allow_without_stock = producto.permitir_venta_sin_stock_en(caja_abierta.sucursal)
        disponible = producto.stock_en(caja_abierta.sucursal)
        carrito = request.session.get('carrito', [])
        found = False
        for item in carrito:
            if item['producto_id'] == producto_id:
                found = True
                nueva_cantidad = item['cantidad'] + cambio_cantidad
                if not allow_without_stock and nueva_cantidad > disponible:
                    return JsonResponse({"error": f"El producto '{producto.nombre}' no tiene suficiente stock. Disponible: {disponible}."}, status=400)
                if nueva_cantidad <= 0:
                    carrito.remove(item)
                else:
                    item['cantidad'] = nueva_cantidad
                    item['stock'] = disponible
                    item['permitir_venta_sin_stock'] = allow_without_stock
                break
        if not found:
            return JsonResponse({"error": "Producto no encontrado en el carrito."}, status=404)
        request.session['carrito'] = carrito
        request.session.modified = True
        return JsonResponse({"mensaje": "Cantidad ajustada correctamente.", "carrito": carrito})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def agregar_al_carrito(request):
    caja_abierta = get_current_caja(request)
    if not caja_abierta:
        return JsonResponse({'error': 'No tienes una caja abierta en tu sucursal o no tienes permisos para operar esta caja.'}, status=403)
    if request.method != "POST":
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        producto_id = data.get("producto_id")
        cantidad = 1
        producto = get_object_or_404(Product, id=producto_id)
        # Asegurar que el producto pertenezca a la sucursal de la caja o sea vendible sin stock
        allow_without_stock = producto.permitir_venta_sin_stock_en(caja_abierta.sucursal)
        pertenece_o_permitido = (
            producto.asignado_a_sucursal(caja_abierta.sucursal) or allow_without_stock
        )
        if not pertenece_o_permitido:
            return JsonResponse({"error": "Este producto no pertenece a la sucursal de la caja abierta."}, status=400)
        # Determinar stock disponible
        if caja_abierta and caja_abierta.sucursal_id:
            disponible = producto.stock_en(caja_abierta.sucursal)
        else:
            disponible = producto.stock or 0
        if not allow_without_stock and disponible < cantidad:
            return JsonResponse({"error": "Stock insuficiente para este producto."}, status=400)
        carrito = request.session.get('carrito', [])
        found = False
        for item in carrito:
            if item['producto_id'] == producto.id:
                nueva_cantidad = int(item.get('cantidad', 0)) + 1
                if not allow_without_stock and nueva_cantidad > disponible:
                    return JsonResponse({"error": f"Stock insuficiente. Disponible: {disponible}."}, status=400)
                item['cantidad'] = nueva_cantidad
                item['stock'] = disponible
                item['permitir_venta_sin_stock'] = allow_without_stock
                found = True
                break
        if not found:
            carrito.append({
                'producto_id': producto.id,
                'nombre': producto.nombre,
                'precio': str(producto.precio_venta),
                'cantidad': cantidad,
                'stock': disponible,
                'permitir_venta_sin_stock': allow_without_stock,
            })
        request.session['carrito'] = carrito
        request.session.modified = True
        return JsonResponse({'mensaje': 'Producto agregado al carrito', 'carrito': carrito})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def listar_carrito(request):
    carrito = request.session.get('carrito', [])
    caja_abierta = get_current_caja(request)
    if caja_abierta and caja_abierta.sucursal_id and carrito:
        product_ids = [item['producto_id'] for item in carrito if 'producto_id' in item]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids, activo=True)}
        for item in carrito:
            pid = item.get('producto_id')
            if pid and pid in products:
                item['stock'] = products[pid].stock_en(caja_abierta.sucursal)
                item['permitir_venta_sin_stock'] = products[pid].permitir_venta_sin_stock_en(caja_abierta.sucursal)
    return JsonResponse({'carrito': carrito})

@login_required
def limpiar_carrito(request):
    request.session['carrito'] = []
    request.session.modified = True
    return JsonResponse({'mensaje': 'Carrito limpio con éxito'})

def delete_all_sales_and_cash_history(request):
    if request.method == 'POST':
        try:
            Venta.objects.all().delete()
            AperturaCierreCaja.objects.all().delete()
            messages.success(request, '¡Éxito! Todo el historial de ventas y caja ha sido eliminado.')
        except Exception as e:
            messages.error(request, f'Ocurrió un error al eliminar los datos: {e}')
    return redirect('products_management')

@login_required
def abrir_caja(request):
    template_name = 'cashier/abrir_caja.html'
    if react_ui_enabled():
        template_name = 'cashier/react_open_caja.html'

    def _render_open_cash(context):
        if template_name == 'cashier/react_open_caja.html':
            sucursales_ctx = context.get('sucursales') or []
            payload = {
                'csrfToken': get_token(request),
                'submitUrl': reverse('abrir_caja'),
                'sucursalFijaId': None,
                'sucursales': [
                    {'id': s.id, 'nombre': s.nombre}
                    for s in sucursales_ctx
                ],
            }
            context = {
                **context,
                'open_cash_payload': payload,
            }
            if getattr(settings, 'DEBUG', False):
                vite_url = getattr(settings, 'VITE_DEV_SERVER_URL', 'http://localhost:5173')
                if _vite_dev_server_is_up(vite_url):
                    context['vite_dev_server_url'] = vite_url
        return render(request, template_name, context)

    # Si es admin/staff, puede elegir cualquier sucursal
    sucursales = _authorized_sucursales_for_user(request.user)
    if not sucursales:
        messages.error(request, "Tu cuenta no tiene sucursales autorizadas. Contacta a un administrador.")
        return _render_open_cash({'sucursales': []})

    if request.method == "POST":
        sucursal_id = request.POST.get('sucursal')
        efectivo_inicial_raw = request.POST.get('efectivo_inicial', '0')
        try:
            efectivo_inicial = _to_clp_pesos(_parse_clp_decimal(efectivo_inicial_raw))
            if efectivo_inicial < 0:
                raise ValueError('efectivo_inicial negativo')
        except Exception:
            messages.error(request, "El monto de efectivo inicial no es válido.")
            return redirect('abrir_caja')

        if not sucursal_id:
            messages.error(request, "Seleccione una sucursal.")
            return redirect('abrir_caja')

        sucursal = get_object_or_404(Sucursal, id=sucursal_id)

        # Validar que el vendedor esté autorizado para esta sucursal
        if not (request.user.is_superuser or request.user.is_staff):
            autorizadas = _authorized_sucursales_for_user(request.user)
            if not autorizadas.filter(id=sucursal.id).exists():
                messages.error(request, "No estás autorizado para abrir caja en esta sucursal.")
                return redirect('abrir_caja')
        
        try:
            with transaction.atomic():
                existente_en_sucursal = AperturaCierreCaja.objects.filter(sucursal=sucursal, estado='abierta').first()
                if existente_en_sucursal:
                    messages.warning(request, f"No se puede abrir caja: ya existe una caja abierta en la sucursal {sucursal.nombre} (Caja #{existente_en_sucursal.id}).")
                    context = {'sucursales': sucursales}
                    return _render_open_cash(context)

                if not (request.user.is_superuser or request.user.is_staff):
                    abierta_usuario = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').first()
                    if abierta_usuario:
                        messages.info(request, f"Ya tienes una caja abierta (Caja #{abierta_usuario.id}).")
                        context = {'sucursales': sucursales}
                        return _render_open_cash(context)
                
                caja = AperturaCierreCaja.objects.create(
                    vendedor=request.user,
                    sucursal=sucursal,
                    efectivo_inicial=efectivo_inicial
                )
            messages.success(request, f"Caja abierta en sucursal {sucursal.nombre}.")
            return redirect('cashier_dashboard')
        
        except Exception as e:
            messages.error(request, f"Error al abrir caja: {e}")

    context = {
        'sucursales': sucursales,
    }
    return _render_open_cash(context)
    # --- FIN DE LA CORRECCIÓN ---


@login_required
def advanced_reports(request):
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    try:
        if fecha_inicio_str:
            fecha_inicio = datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            fecha_inicio = timezone.make_aware(fecha_inicio)
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')
            fecha_fin = timezone.make_aware(fecha_fin) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    ventas_qs = Venta.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
    agg_ventas = ventas_qs.aggregate(
        ingreso_total=Sum('total'),
        num_transacciones=Count('id')
    )
    ingreso_total = agg_ventas.get('ingreso_total') or Decimal('0.00')
    num_transacciones = agg_ventas.get('num_transacciones') or 0
    agg_unidades = VentaDetalle.objects.filter(venta__in=ventas_qs).aggregate(total_unidades=Sum('cantidad'))
    total_unidades = agg_unidades.get('total_unidades') or 0
    agg_cmv = VentaDetalle.objects.filter(venta__in=ventas_qs).aggregate(
        cmv=Sum(F('cantidad') * F('producto__precio_compra'))
    )
    cmv_val = agg_cmv.get('cmv') or 0
    cmv = Decimal(str(cmv_val))
    if ingreso_total > 0:
        ingreso_sin_iva = (ingreso_total / Decimal('1.19')).quantize(Decimal('0.01'))
        iva_total_calc = ingreso_total - ingreso_sin_iva
    else:
        ingreso_sin_iva = Decimal('0.00')
        iva_total_calc = Decimal('0.00')
    cmv_net = (cmv / Decimal('1.19')).quantize(Decimal('0.01')) if cmv else Decimal('0.00')
    ganancia_real = ingreso_sin_iva - cmv_net
    margen = ((ganancia_real / ingreso_sin_iva) * Decimal('100')).quantize(Decimal('0.01')) if ingreso_sin_iva > 0 else Decimal('0.00')
    ticket_promedio = (ingreso_total / num_transacciones) if num_transacciones > 0 else Decimal('0.00')
    unidades_promedio = (total_unidades / num_transacciones) if num_transacciones > 0 else 0
    promedio_ganancia_neta = Decimal('0.00')
    promedio_porcentaje_ganancia = Decimal('0.00')
    best_selling = VentaDetalle.objects.filter(venta__in=ventas_qs) \
                     .values('producto__nombre') \
                     .annotate(total_cantidad=Sum('cantidad')) \
                     .order_by('-total_cantidad') \
                     .first()
    best_selling_product = best_selling['producto__nombre'] if best_selling else "N/A"
    best_selling_quantity = best_selling['total_cantidad'] if best_selling else 0
    legacy_ventas_qs = ventas_qs.filter(pagos__isnull=True)
    nc_expr = Coalesce(F('monto_nota_credito'), Decimal('0.00'))
    metodo_expr = (Coalesce(F('total'), Decimal('0.00')) - nc_expr)

    pagos_agg = VentaPago.objects.filter(venta__in=ventas_qs).values('metodo').annotate(total_monto=Sum('monto'))
    totales_por_metodo = {row['metodo']: _to_clp_pesos(row.get('total_monto') or Decimal('0.00')) for row in pagos_agg}

    legacy_by_method = legacy_ventas_qs.values('forma_pago').annotate(total_monto=Sum(metodo_expr))
    for row in legacy_by_method:
        metodo = row.get('forma_pago')
        monto = _to_clp_pesos(row.get('total_monto') or Decimal('0.00'))
        if metodo:
            totales_por_metodo[metodo] = _to_clp_pesos(totales_por_metodo.get(metodo, Decimal('0.00')) + monto)
    legacy_nc_total = legacy_ventas_qs.aggregate(total=Sum(nc_expr)).get('total') or Decimal('0.00')
    totales_por_metodo['nota_credito'] = _to_clp_pesos(totales_por_metodo.get('nota_credito', Decimal('0.00')) + legacy_nc_total)

    sales_by_payment = []
    sales_by_payment_chart = []
    for metodo, monto in totales_por_metodo.items():
        if not metodo:
            continue
        sales_by_payment.append({'forma_pago': metodo, 'total_monto': "$" + format_clp(monto)})
        try:
            sales_by_payment_chart.append({'forma_pago': metodo, 'total_monto': float(monto)})
        except Exception:
            sales_by_payment_chart.append({'forma_pago': metodo, 'total_monto': 0.0})
    filtro_top = request.GET.get('top', 10)
    try:
        filtro_top = int(filtro_top)
    except ValueError:
        filtro_top = 10
    top_selling_products = VentaDetalle.objects.filter(
        venta__fecha__gte=fecha_inicio, venta__fecha__lte=fecha_fin
    ).values('producto__nombre').annotate(
        total_cantidad=Sum('cantidad')
    ).order_by('-total_cantidad')[:filtro_top]
    context = {
        'ingreso_total': "$" + format_clp(ingreso_total),
        'ingreso_total_sin_iva': "$" + format_clp(ingreso_sin_iva),
        'iva_total': "$" + format_clp(iva_total_calc),
        'ganancia_bruta': "$" + format_clp(ganancia_real),
        'ganancia_liquida': "$" + format_clp(ganancia_real),
        'margen': format_clp(margen) + "%",
        'costo_total': "$" + format_clp(cmv),
        'num_transacciones': num_transacciones,
        'ticket_promedio': "$" + format_clp(ticket_promedio),
        'unidades_promedio': format_clp(unidades_promedio),
        'best_selling_product': best_selling_product,
        'best_selling_quantity': best_selling_quantity,
        'sales_by_payment': sales_by_payment,
        'sales_by_payment_chart': sales_by_payment_chart,
        'top_selling_products': list(top_selling_products),
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'filtro_top_actual': filtro_top,
        'promedio_ganancia_neta': "$" + format_clp(promedio_ganancia_neta),
        'promedio_porcentaje_ganancia': format_clp(promedio_porcentaje_ganancia) + "%"
    }
    return render(request, 'reports/advanced_reports.html', context)