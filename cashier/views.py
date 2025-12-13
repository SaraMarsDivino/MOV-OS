from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
import json
import datetime
from decimal import Decimal

from .models import Venta, VentaDetalle, AperturaCierreCaja
from products.models import Product
from sucursales.models import Sucursal
from decimal import Decimal as _Decimal

def format_currency(value):
    try:
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except Exception:
        return value

def format_clp(value):
    try:
        pesos_val = float(value)
        if pesos_val == 0:
            return "0"
        if pesos_val.is_integer():
            formatted = "{:,.0f}".format(pesos_val)
        else:
            formatted = "{:,.2f}".format(pesos_val)
        formatted = formatted.replace(",", "temp").replace(".", ",").replace("temp", ".")
        return formatted
    except Exception:
        return value


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

# ==== Helper para resolver la caja abierta actual de forma consistente ====
def _parse_body_json(request):
    try:
        if request.body:
            return json.loads(request.body)
    except Exception:
        pass
    return {}

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

    # Solo puede operar sobre su propia caja y en su sucursal asignada
    if caja.vendedor_id != request.user.id:
        return None
    # Si el usuario tiene sucursal asignada, debe coincidir con la de la caja
    if hasattr(request.user, 'sucursal') and request.user.sucursal_id and caja.sucursal_id != request.user.sucursal_id:
        return None

    return caja
    # --- FIN DE LA CORRECCIÓN ---

@transaction.atomic
@login_required
@ensure_csrf_cookie
def cashier_dashboard(request):
    caja_abierta = get_current_caja(request)
    if not caja_abierta:
        messages.error(request, "No tienes una caja abierta en tu sucursal o no tienes permisos para operar esta caja.")
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
        productos = Product.objects.filter(sucursal=caja_abierta.sucursal)
        return render(request, 'cashier/cashier.html', {
            'productos': productos,
            'caja_abierta': caja_abierta
        })
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            carrito = data.get('carrito', [])
            tipo_venta = data.get('tipo_venta', 'boleta')
            forma_pago = data.get('forma_pago', 'efectivo')
            cliente_paga = Decimal(str(data.get('cliente_paga', '0')))
            numero_transaccion = data.get('numero_transaccion', '').strip()
            banco = data.get('banco', '').strip() if forma_pago == "transferencia" else ""
            if forma_pago in ["debito", "credito", "transferencia"] and not numero_transaccion:
                return JsonResponse({
                    "error": "El número de transacción es obligatorio para pagos con tarjeta y transferencia."
                }, status=400)
            if forma_pago == "transferencia" and not banco:
                return JsonResponse({
                    "error": "Debe ingresar el nombre del banco para pagos por transferencia."
                }, status=400)
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
                products_qs = Product.objects.select_for_update().filter(id__in=product_ids)
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
                    pertenece_o_permitido = (
                        producto.sucursal_id == caja_abierta.sucursal_id or
                        (producto.sucursal_id is None and producto.permitir_venta_sin_stock)
                    )
                    if not pertenece_o_permitido:
                        return JsonResponse({"error": f"El producto '{producto.nombre}' no pertenece a la sucursal de la caja abierta."}, status=400)
                    disponible = producto.stock_en(caja_abierta.sucursal) if producto.sucursal_id else (producto.stock or 0)
                    if not producto.permitir_venta_sin_stock and disponible < cantidad:
                        return JsonResponse({"error": f"El producto '{producto.nombre}' no tiene suficiente stock. Disponible: {disponible}."}, status=400)
                    total += Decimal(str(cantidad)) * producto.precio_venta

                if forma_pago == 'efectivo' and cliente_paga < total:
                    return JsonResponse({
                        "error": f"Pago insuficiente. El total es ${format_currency(total)}, pero el cliente pagó ${format_currency(cliente_paga)}."
                    }, status=400)

                venta = Venta.objects.create(
                    empleado=request.user,
                    tipo_venta=tipo_venta,
                    forma_pago=forma_pago,
                    total=Decimal('0.00'),
                    cliente_paga=cliente_paga if forma_pago == "efectivo" else Decimal('0.00'),
                    vuelto_entregado=Decimal('0.00'),
                    numero_transaccion=numero_transaccion if forma_pago in ["debito", "credito", "transferencia"] else "",
                    banco=banco,
                    sucursal=caja_abierta.sucursal,
                    caja=caja_abierta
                )

                for item in carrito:
                    pid = int(item.get('producto_id'))
                    producto = products_map[pid]
                    cantidad = int(item.get('cantidad', 1))
                    if producto.sucursal_id:
                        producto.decrementar_stock_en(caja_abierta.sucursal, cantidad)
                    else:
                        # Legacy stock field: hemos bloqueado la fila con select_for_update, así que el decremento es seguro
                        try:
                            nuevo_stock = max(0, (producto.stock or 0) - cantidad)
                            if nuevo_stock != (producto.stock or 0):
                                producto.stock = nuevo_stock
                                producto.save(update_fields=['stock'])
                        except Exception:
                            pass
                    VentaDetalle.objects.create(
                        venta=venta,
                        producto=producto,
                        cantidad=cantidad,
                        precio_unitario=producto.precio_venta
                    )
                venta.total = total
                if forma_pago == "efectivo":
                    venta.vuelto_entregado = max(Decimal('0.00'), cliente_paga - total)
                venta.save()
            reporte_url = reverse('reporte_venta', args=[venta.id])
            return JsonResponse({
                "success": True,
                "mensaje": "Compra confirmada con éxito.",
                "reporte_url": reporte_url
            })
        except (json.JSONDecodeError, KeyError, ValueError, Product.DoesNotExist) as e:
            return JsonResponse({"error": f"Error en los datos enviados o producto no encontrado: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Ocurrió un error inesperado: {str(e)}"}, status=500)
    return JsonResponse({"error": "Método no permitido."}, status=405)

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
        caja_id = data.get('caja_id')
        if not caja_id:
            caja_id = request.session.get('caja_id')
        if caja_id:
            caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
            if not (request.user.is_superuser or request.user.is_staff or caja.vendedor_id == request.user.id):
                return JsonResponse({'error': 'No tienes una caja abierta en tu sucursal o no tienes permisos para operar esta caja.'}, status=403)
        else:
            caja = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').first()
            if not caja:
                return JsonResponse({'error': 'No tienes una caja abierta para cerrar.'}, status=400)
        if caja.estado == 'cerrada':
            return JsonResponse({'error': 'La caja ya está cerrada.'}, status=400)
        # Calcular totales del periodo de la caja
        fecha_fin = timezone.now()
        # Usar la relación explícita a la caja para evitar incluir ventas de otros periodos
        ventas_qs = Venta.objects.filter(caja=caja)
        total_ventas = ventas_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        ventas_efectivo = ventas_qs.filter(forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        ventas_debito = ventas_qs.filter(forma_pago='debito').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        ventas_credito = ventas_qs.filter(forma_pago='credito').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        vuelto_total = ventas_qs.aggregate(total=Sum('vuelto_entregado'))['total'] or Decimal('0.00')
        # Nota: el efectivo final no debe restar el vuelto. Para una venta en efectivo,
        # el neto que queda en caja es exactamente el total de la venta, independientemente
        # de cuánto se recibió y cuánto vuelto se entregó (cliente_paga - vuelto = total).
        # Por lo tanto, el efectivo final correcto es:
        efectivo_final = (caja.efectivo_inicial or Decimal('0.00')) + ventas_efectivo
        # Persistir estado y métricas básicas
        caja.cierre = fecha_fin
        caja.estado = 'cerrada'
        caja.ventas_totales = total_ventas
        caja.total_ventas_efectivo = ventas_efectivo
        caja.total_ventas_debito = ventas_debito
        caja.total_ventas_credito = ventas_credito
        caja.vuelto_entregado = vuelto_total
        caja.efectivo_final = efectivo_final
        caja.save()
        # Limpiar carrito al cerrar la caja
        try:
            request.session['carrito'] = []
            request.session.modified = True
        except Exception:
            pass
        detalle_url = reverse('detalle_caja', args=[caja.id])
        return JsonResponse({'success': True, 'detalle_url': detalle_url})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def detalle_caja(request, caja_id):
    caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
    # Si la caja está abierta y el usuario es admin, redirigir a la vista del cajero con esa caja
    if caja.estado == 'abierta' and request.user.is_superuser:
        return redirect(f"{reverse('cashier_dashboard')}?caja_id={caja.id}")
    # Establecemos el rango de ventas: desde la apertura hasta la fecha de cierre (o ahora si está abierta)
    # Consultar ventas ligadas a esta caja (más robusto que filtrar por empleado+fechas)
    ventas_qs = Venta.objects.filter(caja=caja)
    ventas_total = ventas_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_efectivo = ventas_qs.filter(forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_debito = ventas_qs.filter(forma_pago='debito').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_credito = ventas_qs.filter(forma_pago='credito').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_transferencia = ventas_qs.filter(forma_pago='transferencia').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    vuelto_total = ventas_qs.aggregate(total=Sum('vuelto_entregado'))['total'] or Decimal('0.00')
    # Igual que en el cierre: no restar 'vuelto_total' ya que el total en efectivo
    # ya representa el neto que queda en caja por cada venta.
    efectivo_final_calc = (caja.efectivo_inicial or Decimal('0.00')) + ventas_efectivo
    
    contexto = {
        'caja': caja,
        'formatted_efectivo_inicial': "$" + format_clp(caja.efectivo_inicial or Decimal('0.00')),
        'formatted_total_debito': "$" + format_clp(ventas_debito),
        'formatted_total_credito': "$" + format_clp(ventas_credito),
    'formatted_total_transferencia': "$" + format_clp(ventas_transferencia),
        'formatted_total_efectivo': "$" + format_clp(ventas_efectivo),
        'formatted_vuelto_entregado': "$" + format_clp(vuelto_total),
        'formatted_efectivo_final': "$" + format_clp(efectivo_final_calc),
        'formatted_total_ventas': "$" + format_clp(ventas_total)
    }
    return render(request, 'cashier/detalle_caja.html', contexto)

@login_required
def print_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    detalles_data = _build_detalles_data(venta)
    total_formatted = "$" + format_currency(venta.total or 0)
    cliente_paga_formatted = "$" + format_currency(venta.cliente_paga or 0)
    vuelto_formatted = "$" + format_currency(venta.vuelto_entregado or 0)
    ctx = {
        'venta': venta,
        'detalles': detalles_data,
        'formatted_total': total_formatted,
        'formatted_cliente_paga': cliente_paga_formatted,
        'formatted_vuelto_entregado': vuelto_formatted,
        'sucursal': venta.sucursal,
    }
    return render(request, 'cashier/print_venta.html', ctx)

@login_required
def print_caja(request, caja_id):
    caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
    # Usar ventas asociadas a la caja para el informe de impresión
    ventas_qs = Venta.objects.filter(caja=caja)
    ventas_total = ventas_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_efectivo = ventas_qs.filter(forma_pago='efectivo').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_debito = ventas_qs.filter(forma_pago='debito').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_credito = ventas_qs.filter(forma_pago='credito').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    ventas_transferencia = ventas_qs.filter(forma_pago='transferencia').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    vuelto_total = ventas_qs.aggregate(total=Sum('vuelto_entregado'))['total'] or Decimal('0.00')
    # El efectivo final debe ser efectivo_inicial + ventas_efectivo.
    # No restamos 'vuelto_total' porque las ventas en efectivo ya representan el neto que queda en caja.
    efectivo_final_calc = (caja.efectivo_inicial or Decimal('0.00')) + ventas_efectivo
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
    }
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
    base_qs = Product.objects.filter(
        Q(nombre__icontains=query) |
        Q(producto_id__icontains=query) |
        Q(codigo_barras__icontains=query) |
        Q(codigo_alternativo__icontains=query)
    )
    # Mostrar todos los productos que coincidan; el frontend indicará si se pueden agregar o no
    productos = base_qs
    # Calcular stock por sucursal cuando procede
    resultados = []
    for p in productos:
        # Determinar si el producto se puede vender desde la sucursal actual
        en_sucursal = True
        if caja_abierta and caja_abierta.sucursal_id:
            en_sucursal = (
                p.sucursal_id == caja_abierta.sucursal_id or
                (p.sucursal_id is None and p.permitir_venta_sin_stock)
            )
        # Calcular stock a mostrar
        if p.sucursal_id and caja_abierta and caja_abierta.sucursal_id:
            stock_val = p.stock_en(caja_abierta.sucursal)
        else:
            stock_val = p.stock or 0
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio_venta': str(p.precio_venta),
            'stock': stock_val,
            'permitir_venta_sin_stock': p.permitir_venta_sin_stock,
            'en_sucursal': en_sucursal
        })
    return JsonResponse({'productos': resultados})

@login_required
def reporte_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    embed_mode = request.GET.get('embed') == '1'
    detalles_data = _build_detalles_data(venta)
    total_formatted = "$" + format_currency(venta.total or 0)
    cliente_paga_formatted = "$" + format_currency(venta.cliente_paga or 0)
    vuelto_formatted = "$" + format_currency(venta.vuelto_entregado or 0)
    context = {
         'venta': venta,
         'detalles': detalles_data,
         'formatted_total': total_formatted,
         'formatted_cliente_paga': cliente_paga_formatted,
         'formatted_vuelto_entregado': vuelto_formatted,
         'sucursal': venta.sucursal  # Se asume que Venta tiene campo 'sucursal'
    }
    if embed_mode:
        return render(request, 'cashier/partials/reporte_venta_embed.html', context)
    return render(request, 'cashier/reporte_venta.html', context)

@login_required
def reporte_venta_embed(request, venta_id):
    """Versión embebible del detalle de venta para usar dentro del modal del cajero."""
    venta = get_object_or_404(Venta, id=venta_id)
    detalles_data = _build_detalles_data(venta)
    total_formatted = "$" + format_currency(venta.total or 0)
    cliente_paga_formatted = "$" + format_currency(venta.cliente_paga or 0)
    vuelto_formatted = "$" + format_currency(venta.vuelto_entregado or 0)
    context = {
         'venta': venta,
         'detalles': detalles_data,
         'formatted_total': total_formatted,
         'formatted_cliente_paga': cliente_paga_formatted,
         'formatted_vuelto_entregado': vuelto_formatted,
         'sucursal': venta.sucursal
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
        carrito = request.session.get('carrito', [])
        found = False
        for item in carrito:
            if item['producto_id'] == producto_id:
                found = True
                nueva_cantidad = item['cantidad'] + cambio_cantidad
                if nueva_cantidad <= 0:
                    carrito.remove(item)
                else:
                    item['cantidad'] = nueva_cantidad
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
        # Asegurar que el producto pertenezca a la sucursal de la caja o sea vendible sin sucursal
        pertenece_o_permitido = (
            producto.sucursal_id == caja_abierta.sucursal_id or
            (producto.sucursal_id is None and producto.permitir_venta_sin_stock)
        )
        if not pertenece_o_permitido:
            return JsonResponse({"error": "Este producto no pertenece a la sucursal de la caja abierta."}, status=400)
        # Determinar stock disponible
        disponible = producto.stock_en(caja_abierta.sucursal) if producto.sucursal_id else (producto.stock or 0)
        if not producto.permitir_venta_sin_stock and disponible < cantidad:
            return JsonResponse({"error": "Stock insuficiente para este producto."}, status=400)
        carrito = request.session.get('carrito', [])
        found = False
        for item in carrito:
            if item['producto_id'] == producto.id:
                # Si ya existe en el carrito, incrementar en 1
                try:
                    item['cantidad'] = int(item.get('cantidad', 0)) + 1
                except Exception:
                    item['cantidad'] = 1
                found = True
                break
        if not found:
            carrito.append({
                'producto_id': producto.id,
                'nombre': producto.nombre,
                'precio': str(producto.precio_venta),
                'cantidad': cantidad,
                'stock': disponible,
                'permitir_venta_sin_stock': producto.permitir_venta_sin_stock,
            })
        request.session['carrito'] = carrito
        request.session.modified = True
        return JsonResponse({'mensaje': 'Producto agregado al carrito', 'carrito': carrito})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def listar_carrito(request):
    carrito = request.session.get('carrito', [])
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
    # Si es admin/staff, puede elegir cualquier sucursal
    if request.user.is_superuser or request.user.is_staff:
        sucursales = Sucursal.objects.all()
        sucursal_fija = None
    else:
        # ManyToMany de sucursales autorizadas (relación en modelo Vendedor)
        vendedor = getattr(request.user, 'vendedor', None)
        if vendedor and hasattr(vendedor, 'sucursales_autorizadas') and vendedor.sucursales_autorizadas.exists():
            sucursales = vendedor.sucursales_autorizadas.all()
            sucursal_fija = sucursales[0]  # Toma la primera como predeterminada
        else:
            messages.error(request, "Tu cuenta no tiene sucursales autorizadas. Contacta a un administrador.")
            return redirect('home')

    if request.method == "POST":
        sucursal_id = request.POST.get('sucursal')
        efectivo_inicial_raw = request.POST.get('efectivo_inicial', '0')
        try:
            efectivo_inicial = Decimal(str(efectivo_inicial_raw))
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
            vendedor = getattr(request.user, 'vendedor', None)
            if not vendedor or not vendedor.sucursales_autorizadas.filter(id=sucursal.id).exists():
                messages.error(request, "No estás autorizado para abrir caja en esta sucursal.")
                return redirect('abrir_caja')
        
        try:
            with transaction.atomic():
                existente_en_sucursal = AperturaCierreCaja.objects.filter(sucursal=sucursal, estado='abierta').first()
                if existente_en_sucursal:
                    messages.warning(request, f"No se puede abrir caja: ya existe una caja abierta en la sucursal {sucursal.nombre} (Caja #{existente_en_sucursal.id}).")
                    context = {'sucursales': sucursales, 'sucursal_fija': sucursal_fija}
                    return render(request, 'cashier/abrir_caja.html', context)

                if not (request.user.is_superuser or request.user.is_staff):
                    abierta_usuario = AperturaCierreCaja.objects.filter(vendedor=request.user, estado='abierta').first()
                    if abierta_usuario:
                        messages.info(request, f"Ya tienes una caja abierta (Caja #{abierta_usuario.id}).")
                        context = {'sucursales': sucursales, 'sucursal_fija': sucursal_fija}
                        return render(request, 'cashier/abrir_caja.html', context)
                
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
        'sucursal_fija': sucursal_fija
    }
    return render(request, 'cashier/abrir_caja.html', context)
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
    sales_by_payment_type = Venta.objects.filter(
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).values('forma_pago').annotate(
        total_monto=Sum('total')
    )
    sales_by_payment = []
    sales_by_payment_chart = []
    for item in sales_by_payment_type:
        monto = item['total_monto'] or 0
        sales_by_payment.append({
            'forma_pago': item['forma_pago'],
            'total_monto': "$" + format_clp(monto)
        })
        sales_by_payment_chart.append({
            'forma_pago': item['forma_pago'],
            'total_monto': float(monto)
        })
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