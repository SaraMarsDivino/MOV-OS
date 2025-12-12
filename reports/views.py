import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.db.models import Q, Sum, F, Count
from django.db.models.functions import Cast
from django.utils import timezone
import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.http import JsonResponse
from django.http import HttpResponse
from django.core.cache import cache
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
import io
# aspose-pdf no está disponible en algunas plataformas (p.ej., ARM/OrangePi).
# Evitar fallo de import en inicio: intentar importar y degradar con bandera.
try:
    from aspose.pdf import Document as PdfDocument  # type: ignore
    from aspose.pdf import HtmlLoadOptions  # type: ignore
    ASPose_AVAILABLE = True
except Exception:
    PdfDocument = None  # type: ignore
    HtmlLoadOptions = None  # type: ignore
    ASPose_AVAILABLE = False
from docx import Document as DocxDocument

User = get_user_model()

from cashier.models import Venta, VentaDetalle, AperturaCierreCaja  
from sucursales.models import Sucursal  # Importar desde la app 'sucursales'

logger = logging.getLogger(__name__)

def format_clp(value):
    try:
        # No mostramos decimales y usamos punto como separador de miles
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except Exception:
        return value

def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@ensure_csrf_cookie
@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def report_dashboard(request):
    """Pantalla principal para la generación de reportes"""
    return render(request, 'reports/report_dashboard.html')

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def sales_dashboard(request):
    """Pantalla principal de Gestión de Ventas con opciones"""
    return render(request, 'reports/sales_dashboard.html')

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def sales_history(request):
    """Historial de Ventas"""
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    empleado_id = request.GET.get('empleado')
    page = request.GET.get('page', 1)

    ventas = Venta.objects.all().order_by('-fecha')

    if fecha_inicio:
        try:
            fecha_inicio_obj = timezone.make_aware(datetime.datetime.strptime(fecha_inicio, '%Y-%m-%d'))
            ventas = ventas.filter(fecha__gte=fecha_inicio_obj)
        except ValueError:
            ventas = Venta.objects.none()
    if fecha_fin:
        try:
            fecha_fin_obj = timezone.make_aware(datetime.datetime.strptime(fecha_fin, '%Y-%m-%d'))
            fecha_fin_obj += datetime.timedelta(days=1, seconds=-1)
            ventas = ventas.filter(fecha__lte=fecha_fin_obj)
        except ValueError:
            ventas = Venta.objects.none()
    if empleado_id:
        try:
            empleado_id = int(empleado_id)
            ventas = ventas.filter(empleado_id=empleado_id)
        except ValueError:
            ventas = Venta.objects.none()

    paginator = Paginator(ventas, 8)
    sales_page = paginator.get_page(page)
    for sale in sales_page:
        sale.display_total = "$" + format_clp(sale.total)
    empleados = User.objects.all()

    return render(request, 'reports/sales_history.html', {
        'sales': sales_page,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'empleado_id': empleado_id if empleado_id else None,
        'empleados': empleados,
    })

@ensure_csrf_cookie
@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def cash_history(request):
    """Historial de Caja con filtros por ID, cajero y rango de fechas."""
    id_caja_filtro = request.GET.get('id_caja')
    cajero_filtro = request.GET.get('cajero')
    fecha_inicio_filtro = request.GET.get('fecha_inicio')
    fecha_fin_filtro = request.GET.get('fecha_fin')
    page = request.GET.get('page', 1)
    per_page_options = [5, 10, 15, 20]
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    # Se ordena por fecha de apertura (campo "apertura")
    cajas = AperturaCierreCaja.objects.all().order_by('-apertura')
    if id_caja_filtro:
        try:
            cajas = cajas.filter(id=int(id_caja_filtro))
        except ValueError:
            cajas = AperturaCierreCaja.objects.none()
    if cajero_filtro:
        # Filtramos por username del vendedor
        cajas = cajas.filter(vendedor__username__icontains=cajero_filtro)
    if fecha_inicio_filtro:
        try:
            fecha_inicio_obj = parse_date(fecha_inicio_filtro)
            if fecha_inicio_obj:
                cajas = cajas.filter(apertura__gte=fecha_inicio_obj)
        except ValueError:
            cajas = AperturaCierreCaja.objects.none()
    if fecha_fin_filtro:
        try:
            fecha_fin_obj = parse_date(fecha_fin_filtro)
            if fecha_fin_obj:
                cajas = cajas.filter(apertura__lte=fecha_fin_obj)
        except ValueError:
            cajas = AperturaCierreCaja.objects.none()

    paginator = Paginator(cajas, per_page)
    cash_page = paginator.get_page(page)
    # Para cada caja se recalcula el total de ventas (consultando las ventas registradas en el período)
    for caja in cash_page:
        ventas_total = Venta.objects.filter(
            empleado=caja.vendedor,
            fecha__gte=caja.apertura,
            fecha__lte=caja.cierre if caja.cierre else timezone.now()
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        caja.formatted_ventas_totales = "$" + format_clp(ventas_total)

    context = {
        'cajas': cash_page,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'id_caja_filtro': id_caja_filtro,
        'cajero_filtro': cajero_filtro,
        'fecha_inicio_filtro': fecha_inicio_filtro,
        'fecha_fin_filtro': fecha_fin_filtro,
    }
    return render(request, 'reports/cash_history.html', context)

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def sales_report(request, sale_id):
    """
    Reporte detallado de una venta. Verifica que la venta exista y que tenga detalles.
    Se calculan los valores formateados y se pasan al contexto sin asignarlos a la instancia.
    """
    try:
        venta = get_object_or_404(Venta, id=sale_id)
        detalles = venta.detalles.all()
        logger.info("Venta %s encontrada con %d detalle(s).", sale_id, detalles.count())

        formatted_total = "$" + format_clp(venta.total or 0)
        formatted_cliente_paga = "$" + format_clp(venta.cliente_paga or 0)
        formatted_vuelto_entregado = "$" + format_clp(venta.vuelto_entregado or 0)

        # En lugar de asignar a cada detalle, creamos una lista de diccionarios con los datos formateados
        detalles_formateados = []
        for detalle in detalles:
            subtotal = detalle.cantidad * detalle.precio_unitario
            detalles_formateados.append({
                'producto': detalle.producto,
                'cantidad': detalle.cantidad,
                'precio_unitario': detalle.precio_unitario,
                'formatted_subtotal': "$" + format_clp(subtotal)
            })

        context = {
            'venta': venta,
            'detalles': detalles_formateados,
            'formatted_total': formatted_total,
            'formatted_cliente_paga': formatted_cliente_paga,
            'formatted_vuelto_entregado': formatted_vuelto_entregado,
            'sucursal': venta.sucursal  # Se agrega la sucursal
        }
        return render(request, 'reports/sales_report.html', context)
    except Exception as e:
        logger.error("Error en sales_report (ID:%s): %s", sale_id, str(e))
        return render(request, 'reports/sales_report.html', {
            'error': str(e),
            'venta': None,
            'detalles': None
        })

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def advanced_reports(request):
    """JSON endpoint para recargar secciones vía AJAX sin renderizar HTML completo."""
    # Perfilado ligero para medir tiempos y cantidad de queries (solo primera sección JSON rápida)
    import time
    from django.db import connection
    start_total = time.perf_counter()
    start_queries = len(getattr(connection, 'queries', []))
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    ventas_qs = Venta.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
    t_filtrado = time.perf_counter()
    if cajero_filter and cajero_filter != 'todos':
        try:
            ventas_qs = ventas_qs.filter(empleado_id=int(cajero_filter))
        except ValueError:
            pass
    if sucursal_filter and sucursal_filter != 'todos':
        try:
            ventas_qs = ventas_qs.filter(sucursal_id=int(sucursal_filter))
        except ValueError:
            pass
    # Reutilizar partes ligeras (serie diaria, branch, hourly, rentabilidad, ranking, heatmap)
    daily = (
        ventas_qs.extra({'day': "DATE(fecha)"})
        .values('day')
        .annotate(ingreso=Sum('total'))
        .order_by('day')
    )
    t_daily = time.perf_counter()
    daily_chart = []
    for row in daily:
        day_raw = row['day']
        # Normalizar a date
        if isinstance(day_raw, datetime.datetime):
            day_date = day_raw.date()
        elif isinstance(day_raw, datetime.date):
            day_date = day_raw
        elif isinstance(day_raw, str):
            parsed = None
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
                try:
                    parsed = datetime.datetime.strptime(day_raw[:19], fmt).date()
                    break
                except ValueError:
                    continue
            if not parsed:
                # Si no se puede parsear se usa el string original para key y se salta cálculos detallados
                day_date = None
            else:
                day_date = parsed
        else:
            day_date = None

        ingreso_dia = row['ingreso'] or Decimal('0.00')
        ganancia_neta_dia = Decimal('0.00')
        if day_date:
            detalles_dia = VentaDetalle.objects.filter(venta__fecha__date=day_date, venta__in=ventas_qs)
            costo_dia = Decimal('0.00')
            for det in detalles_dia:
                costo_dia += (det.producto.precio_compra or Decimal('0.00')) * det.cantidad
            ingreso_sin_iva_dia = (ingreso_dia / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_dia else Decimal('0.00')
            costo_sin_iva_dia = (costo_dia / Decimal('1.19')).quantize(Decimal('0.01')) if costo_dia else Decimal('0.00')
            ganancia_neta_dia = ingreso_sin_iva_dia - costo_sin_iva_dia
        day_str = day_date.strftime('%Y-%m-%d') if day_date else (day_raw if isinstance(day_raw, str) else '')
        daily_chart.append({'day': day_str, 'ingreso': float(ingreso_dia), 'ganancia_neta': float(ganancia_neta_dia)})
    # Branch comparison
    branch_comp = []
    for suc in Sucursal.objects.all():
        ventas_suc = ventas_qs.filter(sucursal_id=suc.id)
        ingreso_suc = ventas_suc.aggregate(t=Sum('total'))['t'] or Decimal('0.00')
        detalles_suc = VentaDetalle.objects.filter(venta__in=ventas_suc)
        costo_suc = Decimal('0.00')
        for det in detalles_suc:
            costo_suc += (det.producto.precio_compra or Decimal('0.00')) * det.cantidad
        ingreso_sin_iva_suc = (ingreso_suc / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_suc else Decimal('0.00')
        costo_sin_iva_suc = (costo_suc / Decimal('1.19')).quantize(Decimal('0.01')) if costo_suc else Decimal('0.00')
        ganancia_neta_suc = ingreso_sin_iva_suc - costo_sin_iva_suc
        branch_comp.append({'sucursal': suc.nombre, 'ingreso': float(ingreso_suc), 'ganancia_neta': float(ganancia_neta_suc)})
    t_branch = time.perf_counter()
    # Hourly distribution
    hourly = [ {'hora': h, 'ventas': 0, 'ingreso': 0.0} for h in range(24) ]
    for v in ventas_qs:
        h = v.fecha.hour
        hourly[h]['ventas'] += 1
        hourly[h]['ingreso'] += float(v.total or 0)
    # Ranking cajeros
    rank_temp = {}
    for v in ventas_qs.select_related('empleado'):
        uid = v.empleado_id
        e = rank_temp.get(uid)
        if not e:
            e = {'usuario': v.empleado.username, 'ventas_count': 0, 'ingreso_total': Decimal('0.00')}
        e['ventas_count'] += 1
        e['ingreso_total'] += v.total or Decimal('0.00')
        rank_temp[uid] = e
    ranking = []
    for _, d in rank_temp.items():
        ticket_prom = (d['ingreso_total'] / d['ventas_count']).quantize(Decimal('0.01')) if d['ventas_count'] else Decimal('0.00')
        ranking.append({'usuario': d['usuario'], 'ventas_count': d['ventas_count'], 'ingreso_total': float(d['ingreso_total']), 'ticket_promedio': float(ticket_prom)})
    ranking.sort(key=lambda x: x['ingreso_total'], reverse=True)
    t_ranking = time.perf_counter()
    # Heatmap
    heatmap = [[{'ventas':0,'ingreso':0.0} for _ in range(24)] for _ in range(7)]
    for v in ventas_qs:
        dow = v.fecha.weekday(); hour = v.fecha.hour
        cell = heatmap[dow][hour]
        cell['ventas'] += 1
        cell['ingreso'] += float(v.total or 0)
    t_heatmap = time.perf_counter()
    profiling_json = {
        'ms_filtrado': round((t_filtrado - start_total)*1000,2),
        'ms_daily': round((t_daily - t_filtrado)*1000,2),
        'ms_branch': round((t_branch - t_daily)*1000,2),
        'ms_ranking': round((t_ranking - t_branch)*1000,2),
        'ms_heatmap': round((t_heatmap - t_ranking)*1000,2),
        'ms_total_json': round((time.perf_counter() - start_total)*1000,2),
        'queries_total_json': len(getattr(connection, 'queries', [])) - start_queries,
    }
    # Guardar profiling_json para contexto; no retornamos aquí para permitir render HTML completo
    # (Sección HTML completa) usar helper para generar contexto extendido
    from .analytics import compute_analytics
    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    # --- Custom comparison range override (only for comparativo section) ---
    comp_inicio_str = request.GET.get('comparativo_inicio')
    comp_fin_str = request.GET.get('comparativo_fin')
    custom_comparativo_used = False
    if comp_inicio_str and comp_fin_str:
        try:
            comp_inicio = timezone.make_aware(datetime.datetime.strptime(comp_inicio_str, '%Y-%m-%d'))
            comp_fin = timezone.make_aware(datetime.datetime.strptime(comp_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
            if comp_inicio <= comp_fin:
                # Recompute only comparative metrics for custom range
                ventas_prev_custom = Venta.objects.filter(fecha__gte=comp_inicio, fecha__lte=comp_fin)
                if cajero_filter and cajero_filter != 'todos':
                    try:
                        ventas_prev_custom = ventas_prev_custom.filter(empleado_id=int(cajero_filter))
                    except ValueError:
                        pass
                if sucursal_filter and sucursal_filter != 'todos':
                    try:
                        ventas_prev_custom = ventas_prev_custom.filter(sucursal_id=int(sucursal_filter))
                    except ValueError:
                        pass
                ingreso_prev = ventas_prev_custom.aggregate(t=Sum('total'))['t'] or Decimal('0.00')
                detalles_prev = VentaDetalle.objects.filter(venta__in=ventas_prev_custom)
                cmv_prev_val = detalles_prev.aggregate(cmv_prev=Sum(F('cantidad') * F('producto__precio_compra')))['cmv_prev'] or 0
                cmv_prev = Decimal(str(cmv_prev_val))
                ingreso_sin_iva_prev = (ingreso_prev / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_prev else Decimal('0.00')
                costo_prev_net = (cmv_prev / Decimal('1.19')).quantize(Decimal('0.01')) if cmv_prev else Decimal('0.00')
                ganancia_neta_prev = ingreso_sin_iva_prev - costo_prev_net
                num_transacciones_prev = ventas_prev_custom.count()
                margen_prev = ((ganancia_neta_prev / ingreso_sin_iva_prev) * Decimal('100')).quantize(Decimal('0.01')) if ingreso_sin_iva_prev > 0 else Decimal('0.00')
                def delta_pct(current: Decimal, previous: Decimal):
                    delta = (current - previous)
                    if previous == 0:
                        pct = Decimal('100.00') if current > 0 else Decimal('0.00')
                    else:
                        pct = ((delta / previous) * Decimal('100')).quantize(Decimal('0.01'))
                    return delta, pct
                ingreso_delta, ingreso_pct = delta_pct(analytics['ingreso_total'], ingreso_prev)
                ganancia_neta_delta, ganancia_neta_pct = delta_pct(analytics['ganancia_neta'], ganancia_neta_prev)
                transacciones_delta, transacciones_pct = delta_pct(Decimal(analytics['num_transacciones']), Decimal(num_transacciones_prev))
                margen_delta, margen_pct = delta_pct(analytics['margen'], margen_prev)
                # Override analytics comparative keys for context only
                analytics.update({
                    'prev_inicio': comp_inicio,
                    'prev_fin': comp_fin,
                    'ingreso_prev': ingreso_prev,
                    'ganancia_neta_prev': ganancia_neta_prev,
                    'num_transacciones_prev': num_transacciones_prev,
                    'margen_prev': margen_prev,
                    'ingreso_delta': ingreso_delta,
                    'ingreso_pct': ingreso_pct,
                    'ganancia_neta_delta': ganancia_neta_delta,
                    'ganancia_neta_pct': ganancia_neta_pct,
                    'transacciones_delta': transacciones_delta,
                    'transacciones_pct': transacciones_pct,
                    'margen_delta': margen_delta,
                    'margen_pct': margen_pct,
                    'participacion_ingreso': (ingreso_prev / analytics['ingreso_total'] * Decimal('100')).quantize(Decimal('0.01')) if analytics['ingreso_total'] else Decimal('0.00'),
                    'participacion_ganancia': (ganancia_neta_prev / analytics['ganancia_neta'] * Decimal('100')).quantize(Decimal('0.01')) if analytics['ganancia_neta'] else Decimal('0.00'),
                })
                custom_comparativo_used = True
        except ValueError:
            pass
    filtro_top = request.GET.get('top', 10)
    try:
        filtro_top = int(filtro_top)
    except ValueError:
        filtro_top = 10
    # Recalcular top_selling_products separado para mantener comportamiento previo
    ventas_full = Venta.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
    if cajero_filter and cajero_filter != 'todos':
        try:
            ventas_full = ventas_full.filter(empleado_id=int(cajero_filter))
        except ValueError:
            pass
    if sucursal_filter and sucursal_filter != 'todos':
        try:
            ventas_full = ventas_full.filter(sucursal_id=int(sucursal_filter))
        except ValueError:
            pass
    top_selling_products = VentaDetalle.objects.filter(venta__in=ventas_full).values('producto__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:filtro_top]

    def fmt_money(val: Decimal):
        return "$" + format_clp(val or 0)

    # Calcular promedios de rentabilidad (ganancia neta y porcentaje)
    promedio_ganancia_neta = Decimal('0.00')
    promedio_porcentaje_ganancia = Decimal('0.00')
    rent_list = analytics['rentabilidad_productos']
    if rent_list:
        total_gan_neta = sum(Decimal(str(r['ganancia_neta_total'])) for r in rent_list)
        promedio_ganancia_neta = (total_gan_neta / Decimal(str(len(rent_list)))).quantize(Decimal('0.01'))
        total_pct = sum(Decimal(str(r['porcentaje_ganancia'])) for r in rent_list)
        promedio_porcentaje_ganancia = (total_pct / Decimal(str(len(rent_list)))).quantize(Decimal('0.01'))
    context = {
        'ingreso_total': fmt_money(analytics['ingreso_total']),
        'ingreso_total_sin_iva': fmt_money(analytics['ingreso_total_sin_iva']),
        'iva_total': fmt_money(analytics['iva_total_calc']),
        'ganancia_bruta': fmt_money(analytics['ganancia_bruta']),
        'ganancia_neta': fmt_money(analytics['ganancia_neta']),
        'margen': format_clp(analytics['margen']) + '%',
        'costo_total': fmt_money(analytics['costo_total']),
        'num_transacciones': analytics['num_transacciones'],
        'ticket_promedio': fmt_money(analytics['ticket_promedio']),
        'unidades_promedio': format_clp(analytics['unidades_promedio']),
        'best_selling_product': analytics['best_selling_product'],
        'best_selling_quantity': analytics['best_selling_quantity'],
        'sales_by_payment': [ {'forma_pago': sp['forma_pago'], 'total_monto': fmt_money(sp['total_monto_raw']) } for sp in analytics['sales_by_payment'] ],
        'sales_by_payment_chart': analytics['sales_by_payment_chart'],
        'top_selling_products': list(top_selling_products),
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'filtro_top_actual': filtro_top,
        'promedio_ganancia_neta': fmt_money(promedio_ganancia_neta),
    'promedio_ganancia_neta_raw': float(promedio_ganancia_neta),
        'promedio_porcentaje_ganancia': format_clp(promedio_porcentaje_ganancia) + '%',
        'cajero_actual': cajero_filter,
        'sucursal_actual': sucursal_filter,
        'daily_chart': analytics['daily_chart'],
        'branch_comparison': analytics['branch_comparison'],
        'hourly_distribution': analytics['hourly_distribution'],
        'heatmap_matrix': analytics['heatmap_matrix'],
        'rentabilidad_productos': analytics['rentabilidad_productos'],
        'ranking_cajeros': analytics['ranking_cajeros'],
        'wave_labels': analytics['wave_labels'],
        'wave_gains': analytics['wave_gains'],
        'prev_inicio': analytics['prev_inicio'].strftime('%Y-%m-%d'),
        'prev_fin': analytics['prev_fin'].strftime('%Y-%m-%d'),
        'ingreso_prev': fmt_money(analytics['ingreso_prev']),
        'ganancia_neta_prev': fmt_money(analytics['ganancia_neta_prev']),
        'num_transacciones_prev': analytics['num_transacciones_prev'],
        'margen_prev': format_clp(analytics['margen_prev']) + '%',
        'ingreso_delta': fmt_money(analytics['ingreso_delta']),
        'ingreso_pct': format_clp(analytics['ingreso_pct']) + '%',
        'ganancia_neta_delta': fmt_money(analytics['ganancia_neta_delta']),
        'ganancia_neta_pct': format_clp(analytics['ganancia_neta_pct']) + '%',
        'transacciones_delta': format_clp(analytics['transacciones_delta']),
        'transacciones_pct': format_clp(analytics['transacciones_pct']) + '%',
        'margen_delta': format_clp(analytics['margen_delta']) + '%',
        'margen_pct': format_clp(analytics['margen_pct']) + '%',
    'participacion_ingreso': format_clp(analytics.get('participacion_ingreso', Decimal('0')))+'%',
    'participacion_ganancia': format_clp(analytics.get('participacion_ganancia', Decimal('0')))+'%',
        'profiling': profiling_json,
        'comparativo_custom': custom_comparativo_used,
        'comparativo_inicio_custom': comp_inicio_str if custom_comparativo_used else '',
        'comparativo_fin_custom': comp_fin_str if custom_comparativo_used else '',
    }
    
    return render(request, 'reports/advanced_reports.html', {
        "usuarios": User.objects.all(),
        "sucursales": Sucursal.objects.all(),
        **context
    })

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def advanced_reports_data(request):
    """Nuevo endpoint JSON completo usando compute_analytics sin renderizar HTML."""
    from .analytics import compute_analytics
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    comp_inicio_str = request.GET.get('comparativo_inicio')
    comp_fin_str = request.GET.get('comparativo_fin')
    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    # Parametro opcional para limitar Top de productos (default 10)
    filtro_top = request.GET.get('top', 10)
    try:
        filtro_top = int(filtro_top)
    except ValueError:
        filtro_top = 10
    comparativo_meta = {
        'comparativo_custom': False,
        'comparativo_inicio': analytics['prev_inicio'].strftime('%Y-%m-%d'),
        'comparativo_fin': analytics['prev_fin'].strftime('%Y-%m-%d'),
        'ingreso_prev': float(analytics['ingreso_prev']),
        'ganancia_neta_prev': float(analytics['ganancia_neta_prev']),
        'num_transacciones_prev': analytics['num_transacciones_prev'],
        'margen_prev': float(analytics['margen_prev']),
        'ingreso_delta': float(analytics['ingreso_delta']),
        'ingreso_pct': float(analytics['ingreso_pct']),
        'ganancia_neta_delta': float(analytics['ganancia_neta_delta']),
        'ganancia_neta_pct': float(analytics['ganancia_neta_pct']),
        'transacciones_delta': float(analytics['transacciones_delta']),
        'transacciones_pct': float(analytics['transacciones_pct']),
        'margen_delta': float(analytics['margen_delta']),
        'margen_pct': float(analytics['margen_pct']),
        'participacion_ingreso': float((analytics['ingreso_prev']/analytics['ingreso_total']*Decimal('100')).quantize(Decimal('0.01')) if analytics['ingreso_total'] else Decimal('0.00')),
        'participacion_ganancia': float((analytics['ganancia_neta_prev']/analytics['ganancia_neta']*Decimal('100')).quantize(Decimal('0.01')) if analytics['ganancia_neta'] else Decimal('0.00')),
    }
    if comp_inicio_str and comp_fin_str:
        try:
            comp_inicio = timezone.make_aware(datetime.datetime.strptime(comp_inicio_str, '%Y-%m-%d'))
            comp_fin = timezone.make_aware(datetime.datetime.strptime(comp_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
            if comp_inicio <= comp_fin:
                ventas_prev_custom = Venta.objects.filter(fecha__gte=comp_inicio, fecha__lte=comp_fin)
                if cajero_filter and cajero_filter != 'todos':
                    try: ventas_prev_custom = ventas_prev_custom.filter(empleado_id=int(cajero_filter))
                    except ValueError: pass
                if sucursal_filter and sucursal_filter != 'todos':
                    try: ventas_prev_custom = ventas_prev_custom.filter(sucursal_id=int(sucursal_filter))
                    except ValueError: pass
                ingreso_prev = ventas_prev_custom.aggregate(t=Sum('total'))['t'] or Decimal('0.00')
                detalles_prev = VentaDetalle.objects.filter(venta__in=ventas_prev_custom)
                cmv_prev_val = detalles_prev.aggregate(cmv_prev=Sum(F('cantidad') * F('producto__precio_compra')))['cmv_prev'] or 0
                cmv_prev = Decimal(str(cmv_prev_val))
                ingreso_sin_iva_prev = (ingreso_prev / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_prev else Decimal('0.00')
                costo_prev_net = (cmv_prev / Decimal('1.19')).quantize(Decimal('0.01')) if cmv_prev else Decimal('0.00')
                ganancia_neta_prev = ingreso_sin_iva_prev - costo_prev_net
                num_transacciones_prev = ventas_prev_custom.count()
                margen_prev = ((ganancia_neta_prev / ingreso_sin_iva_prev) * Decimal('100')).quantize(Decimal('0.01')) if ingreso_sin_iva_prev > 0 else Decimal('0.00')
                def delta_pct(current: Decimal, previous: Decimal):
                    delta = (current - previous)
                    if previous == 0:
                        pct = Decimal('100.00') if current > 0 else Decimal('0.00')
                    else:
                        pct = ((delta / previous) * Decimal('100')).quantize(Decimal('0.01'))
                    return delta, pct
                ingreso_delta, ingreso_pct = delta_pct(analytics['ingreso_total'], ingreso_prev)
                ganancia_neta_delta, ganancia_neta_pct = delta_pct(analytics['ganancia_neta'], ganancia_neta_prev)
                transacciones_delta, transacciones_pct = delta_pct(Decimal(analytics['num_transacciones']), Decimal(num_transacciones_prev))
                margen_delta, margen_pct = delta_pct(analytics['margen'], margen_prev)
                comparativo_meta.update({
                    'comparativo_custom': True,
                    'comparativo_inicio': comp_inicio.strftime('%Y-%m-%d'),
                    'comparativo_fin': comp_fin.strftime('%Y-%m-%d'),
                    'ingreso_prev': float(ingreso_prev),
                    'ganancia_neta_prev': float(ganancia_neta_prev),
                    'num_transacciones_prev': num_transacciones_prev,
                    'margen_prev': float(margen_prev),
                    'ingreso_delta': float(ingreso_delta),
                    'ingreso_pct': float(ingreso_pct),
                    'ganancia_neta_delta': float(ganancia_neta_delta),
                    'ganancia_neta_pct': float(ganancia_neta_pct),
                    'transacciones_delta': float(transacciones_delta),
                    'transacciones_pct': float(transacciones_pct),
                    'margen_delta': float(margen_delta),
                    'margen_pct': float(margen_pct),
                    'participacion_ingreso': float((ingreso_prev/analytics['ingreso_total']*Decimal('100')).quantize(Decimal('0.01')) if analytics['ingreso_total'] else Decimal('0.00')),
                    'participacion_ganancia': float((ganancia_neta_prev/analytics['ganancia_neta']*Decimal('100')).quantize(Decimal('0.01')) if analytics['ganancia_neta'] else Decimal('0.00')),
                })
        except ValueError:
            pass
    # Formateo monetario liviano en JSON (sin símbolos para facilitar consumo externo)
    def dec_to_float(d):
        if isinstance(d, Decimal):
            return float(d)
        return d
    def format_clp_plain(val):
        try:
            return "{:,.0f}".format(float(val)).replace(",", ".")
        except Exception:
            return str(val)
    json_payload = {
        'params': {
            'fecha_inicio': fecha_inicio_str,
            'fecha_fin': fecha_fin_str,
            'cajero': cajero_filter,
            'sucursal': sucursal_filter,
            'top': filtro_top,
        },
        'kpis': {
            'ingreso_total': dec_to_float(analytics['ingreso_total']),
            'ingreso_total_clp': format_clp_plain(analytics['ingreso_total']),
            'ingreso_total_sin_iva': dec_to_float(analytics['ingreso_total_sin_iva']),
            'ingreso_total_sin_iva_clp': format_clp_plain(analytics['ingreso_total_sin_iva']),
            'iva_total': dec_to_float(analytics['iva_total_calc']),
            'iva_total_clp': format_clp_plain(analytics['iva_total_calc']),
            'ganancia_bruta': dec_to_float(analytics['ganancia_bruta']),
            'ganancia_bruta_clp': format_clp_plain(analytics['ganancia_bruta']),
            'ganancia_neta': dec_to_float(analytics['ganancia_neta']),
            'ganancia_neta_clp': format_clp_plain(analytics['ganancia_neta']),
            'margen_pct': dec_to_float(analytics['margen']),
            'costo_total': dec_to_float(analytics['costo_total']),
            'costo_total_clp': format_clp_plain(analytics['costo_total']),
            'num_transacciones': analytics['num_transacciones'],
            'ticket_promedio': dec_to_float(analytics['ticket_promedio']),
            'ticket_promedio_clp': format_clp_plain(analytics['ticket_promedio']),
            'unidades_promedio': analytics['unidades_promedio'],
            'best_selling_product': analytics['best_selling_product'],
            'best_selling_quantity': analytics['best_selling_quantity'],
        },
        'comparativo': {
            'prev_inicio': analytics['prev_inicio'].strftime('%Y-%m-%d'),
            'prev_fin': analytics['prev_fin'].strftime('%Y-%m-%d'),
            'ingreso_prev': dec_to_float(analytics['ingreso_prev']),
            'ingreso_prev_clp': format_clp_plain(analytics['ingreso_prev']),
            'ganancia_neta_prev': dec_to_float(analytics['ganancia_neta_prev']),
            'ganancia_neta_prev_clp': format_clp_plain(analytics['ganancia_neta_prev']),
            'num_transacciones_prev': analytics['num_transacciones_prev'],
            'margen_prev': dec_to_float(analytics['margen_prev']),
            'ingreso_delta': dec_to_float(analytics['ingreso_delta']),
            'ingreso_delta_clp': format_clp_plain(analytics['ingreso_delta']),
            'ingreso_pct': dec_to_float(analytics['ingreso_pct']),
            'ganancia_neta_delta': dec_to_float(analytics['ganancia_neta_delta']),
            'ganancia_neta_delta_clp': format_clp_plain(analytics['ganancia_neta_delta']),
            'ganancia_neta_pct': dec_to_float(analytics['ganancia_neta_pct']),
            'transacciones_delta': dec_to_float(analytics['transacciones_delta']),
            'transacciones_pct': dec_to_float(analytics['transacciones_pct']),
            'margen_delta': dec_to_float(analytics['margen_delta']),
            'margen_pct': dec_to_float(analytics['margen_pct']),
        },
        'series': {
            'daily_chart': analytics['daily_chart'],
            'branch_comparison': analytics['branch_comparison'],
            'hourly_distribution': analytics['hourly_distribution'],
            'heatmap_matrix': analytics['heatmap_matrix'],
            'wave_labels': analytics['wave_labels'],
            'wave_gains': analytics['wave_gains'],
        },
        'rentabilidad_productos': analytics['rentabilidad_productos'],
        'ranking_cajeros': analytics['ranking_cajeros'],
        'comparativo_meta': comparativo_meta,
        # Top productos más vendidos (filtrado por parámetro 'top')
        'top_selling_products': list(
            VentaDetalle.objects.filter(
                venta__fecha__gte=fecha_inicio,
                venta__fecha__lte=fecha_fin,
                **({} if cajero_filter in (None, '', 'todos') else {'venta__empleado_id': cajero_filter}),
                **({} if sucursal_filter in (None, '', 'todos') else {'venta__sucursal_id': sucursal_filter}),
            ).values('producto__nombre')
             .annotate(total_cantidad=Sum('cantidad'))
             .order_by('-total_cantidad')[:filtro_top]
        ),
    }
    return JsonResponse(json_payload)

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_rentabilidad_csv(request):
    # Reutilizar rango de fechas principal
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    ventas_qs = Venta.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
    detalles_rango = VentaDetalle.objects.filter(venta__in=ventas_qs)
    rent_map = {}
    for det in detalles_rango.select_related('producto'):
        pid = det.producto_id
        venta_unit = det.precio_unitario or Decimal('0.00')
        compra_unit = det.producto.precio_compra or Decimal('0.00')
        venta_sin_iva = (venta_unit / Decimal('1.19')).quantize(Decimal('0.01')) if venta_unit else Decimal('0.00')
        compra_sin_iva = (compra_unit / Decimal('1.19')).quantize(Decimal('0.01')) if compra_unit else Decimal('0.00')
        ganancia_unit = venta_sin_iva - compra_sin_iva
        entry = rent_map.get(pid)
        if not entry:
            entry = {
                'producto': det.producto.nombre or det.producto.producto_id,
                'cantidad': 0,
                'ingreso': Decimal('0.00'),
                'costo': Decimal('0.00'),
                'ganancia': Decimal('0.00')
            }
        entry['cantidad'] += det.cantidad
        entry['ingreso'] += venta_sin_iva * det.cantidad
        entry['costo'] += compra_sin_iva * det.cantidad
        entry['ganancia'] += ganancia_unit * det.cantidad
        rent_map[pid] = entry
    rows = []
    for _, d in rent_map.items():
        pct = Decimal('0.00')
        if d['ingreso'] > 0:
            pct = (d['ganancia'] / d['ingreso'] * Decimal('100')).quantize(Decimal('0.01'))
        rows.append([d['producto'], d['cantidad'], d['ingreso'], d['costo'], d['ganancia'], pct])
    rows.sort(key=lambda r: r[4], reverse=True)
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=rentabilidad_productos.csv'
    # BOM para que Excel detecte UTF-8 correctamente
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Producto','Cantidad','Ingreso Neto','Costo Neto','Ganancia Neta','% Ganancia'])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5]])
    return response

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_ranking_cajeros_csv(request):
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    ventas_qs = Venta.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin).select_related('empleado')
    ranking_map = {}
    for v in ventas_qs:
        uid = v.empleado_id
        entry = ranking_map.get(uid)
        if not entry:
            entry = {'usuario': v.empleado.username, 'ventas': 0, 'ingreso': Decimal('0.00')}
        entry['ventas'] += 1
        entry['ingreso'] += v.total or Decimal('0.00')
        ranking_map[uid] = entry
    rows = []
    for _, d in ranking_map.items():
        ticket_prom = (d['ingreso'] / d['ventas']).quantize(Decimal('0.01')) if d['ventas'] else Decimal('0.00')
        rows.append([d['usuario'], d['ventas'], d['ingreso'], ticket_prom])
    rows.sort(key=lambda r: r[2], reverse=True)
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=ranking_cajeros.csv'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Usuario','Ventas','Ingreso Total','Ticket Promedio'])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3]])
    return response


@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_analytics_csv(request):
    """Exporta un CSV con KPIs principales y top productos para el rango solicitado."""
    from .analytics import compute_analytics
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()

    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter, limit_rentabilidad=100)
    # Top productos
    top_products = VentaDetalle.objects.filter(venta__fecha__gte=fecha_inicio, venta__fecha__lte=fecha_fin)
    if cajero_filter and cajero_filter != 'todos':
        try:
            top_products = top_products.filter(venta__empleado_id=int(cajero_filter))
        except ValueError:
            pass
    if sucursal_filter and sucursal_filter != 'todos':
        try:
            top_products = top_products.filter(venta__sucursal_id=int(sucursal_filter))
        except ValueError:
            pass
    top_list = list(top_products.values('producto__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:50])

    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=analytics_kpis.csv'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    # Escribir KPIs principales
    writer.writerow(['KPI','Valor'])
    writer.writerow(['Ingreso Total (CLP)', analytics['ingreso_total']])
    writer.writerow(['Ingreso Neto (sin IVA)', analytics['ingreso_total_sin_iva']])
    writer.writerow(['IVA Calculado', analytics['iva_total_calc']])
    writer.writerow(['Ganancia Bruta', analytics['ganancia_bruta']])
    writer.writerow(['Ganancia Neta', analytics['ganancia_neta']])
    writer.writerow(['Margen (%)', analytics['margen']])
    writer.writerow(['Numero Transacciones', analytics['num_transacciones']])
    writer.writerow(['Ticket Promedio', analytics['ticket_promedio']])
    writer.writerow([])
    writer.writerow(['Top Productos','Cantidad'])
    for p in top_list:
        writer.writerow([p.get('producto__nombre'), p.get('total_cantidad')])
    return response
    return response

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_daily_series_csv(request):
    """Exporta la serie diaria (ingreso y ganancia neta) en CSV."""
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    from .analytics import compute_analytics
    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    rows = analytics['daily_chart']
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=serie_diaria.csv'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Dia','Ingreso','GananciaNeta'])
    for r in rows:
        writer.writerow([r['day'], r['ingreso'], r['ganancia_neta']])
    return response

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_branch_comparison_csv(request):
    """Exporta comparación por sucursal (ingreso y ganancia neta) en CSV."""
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    from .analytics import compute_analytics
    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    rows = analytics['branch_comparison']
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=comparacion_sucursal.csv'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Sucursal','Ingreso','GananciaNeta'])
    for r in rows:
        writer.writerow([r['sucursal'], r['ingreso'], r['ganancia_neta']])
    return response

@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def caja_report(request, caja_id):
    """
    Vista para mostrar el detalle de una caja cerrada usando el template 'reporte_caja.html'.
    """
    caja = get_object_or_404(AperturaCierreCaja, id=caja_id)
    # Usar los totales persistidos en la caja cuando estén disponibles
    caja.formatted_efectivo_inicial = "$" + format_clp(caja.efectivo_inicial or 0)
    caja.formatted_total_ventas_debito = "$" + format_clp(caja.total_ventas_debito or 0)
    caja.formatted_total_ventas_credito = "$" + format_clp(caja.total_ventas_credito or 0)
    caja.formatted_total_ventas_efectivo = "$" + format_clp(caja.total_ventas_efectivo or 0)
    caja.formatted_vuelto_entregado = "$" + format_clp(caja.vuelto_entregado or 0)
    caja.formatted_efectivo_final = "$" + format_clp(caja.efectivo_final or caja.efectivo_inicial or 0)
    caja.formatted_ventas_totales = "$" + format_clp(caja.ventas_totales or 0)
    # Para transferencias mantenemos el cálculo puntual (no hay campo persistido para transferencias)
    ventas_transferencia = Venta.objects.filter(caja=caja, forma_pago='transferencia').aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    caja.formatted_total_ventas_transferencia = "$" + format_clp(ventas_transferencia)
    
    return render(request, 'reports/reporte_caja.html', {'caja': caja})

@csrf_exempt  # Solo para pruebas; luego usa tokens CSRF correctamente
@login_required
def limpiar_historial_ventas(request):
    if request.method == "POST":
        try:
            Venta.objects.all().delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

@csrf_exempt  # Solo para pruebas
@login_required
def limpiar_historial_caja(request):
    if request.method == "POST":
        AperturaCierreCaja.objects.all().delete()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Método no permitido.'}, status=405)


@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_advanced_pdf(request):
    """Exporta el reporte avanzado completo a PDF usando la misma data y un template html compacto."""
    # Fallback amigable cuando aspose-pdf no está instalado (p.ej., ARM)
    if not ASPose_AVAILABLE:
        return HttpResponse(
            (
                "Exportación a PDF no disponible en este servidor (falta dependencia aspose-pdf). "
                "Por favor use la opción 'Exportar Word'."
            ),
            content_type="text/plain",
            status=501,
        )
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    filtro_top = int(request.GET.get('top', 10) or 10)
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    from .analytics import compute_analytics
    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter, limit_rentabilidad=50)
    top_selling = list(
        VentaDetalle.objects.filter(
            venta__fecha__gte=fecha_inicio,
            venta__fecha__lte=fecha_fin,
            **({} if cajero_filter in (None, '', 'todos') else {'venta__empleado_id': cajero_filter}),
            **({} if sucursal_filter in (None, '', 'todos') else {'venta__sucursal_id': sucursal_filter}),
        ).values('producto__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:filtro_top]
    )
    context = {
        'fecha_inicio': fecha_inicio_str or (timezone.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin_str or timezone.now().strftime('%Y-%m-%d'),
        'ingreso_total': "$" + format_clp(analytics['ingreso_total']),
        'ingreso_total_sin_iva': "$" + format_clp(analytics['ingreso_total_sin_iva']),
        'iva_total': "$" + format_clp(analytics['iva_total_calc']),
        'ganancia_neta': "$" + format_clp(analytics['ganancia_neta']),
        'ganancia_bruta': "$" + format_clp(analytics['ganancia_bruta']),
        'costo_total': "$" + format_clp(analytics['costo_total']),
        'num_transacciones': analytics['num_transacciones'],
        'ticket_promedio': "$" + format_clp(analytics['ticket_promedio']),
        'unidades_promedio': analytics['unidades_promedio'],
        'ranking_cajeros': analytics['ranking_cajeros'],
        'rentabilidad_productos': analytics['rentabilidad_productos'],
        'top_selling_products': top_selling,
    }
    html = render_to_string('reports/export/advanced_pdf.html', context)
    load_opts = HtmlLoadOptions()
    pdf = PdfDocument(io.BytesIO(html.encode('utf-8')), load_opts)
    out = io.BytesIO()
    pdf.save(out)
    out.seek(0)
    resp = HttpResponse(out.read(), content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="reporte_avanzado.pdf"'
    return resp


@login_required
@user_passes_test(_is_admin, login_url='cashier_dashboard')
def export_advanced_docx(request):
    """Exporta un resumen del reporte avanzado a DOCX."""
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    cajero_filter = request.GET.get('cajero','todos')
    sucursal_filter = request.GET.get('sucursal','todos')
    filtro_top = int(request.GET.get('top', 10) or 10)
    try:
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(datetime.datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        else:
            fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    except ValueError:
        fecha_inicio = timezone.now() - datetime.timedelta(days=30)
    try:
        if fecha_fin_str:
            fecha_fin = timezone.make_aware(datetime.datetime.strptime(fecha_fin_str, '%Y-%m-%d')) + datetime.timedelta(days=1, seconds=-1)
        else:
            fecha_fin = timezone.now()
    except ValueError:
        fecha_fin = timezone.now()
    from .analytics import compute_analytics
    analytics = compute_analytics(fecha_inicio, fecha_fin, cajero_filter, sucursal_filter, limit_rentabilidad=50)
    top_selling = list(
        VentaDetalle.objects.filter(
            venta__fecha__gte=fecha_inicio,
            venta__fecha__lte=fecha_fin,
            **({} if cajero_filter in (None, '', 'todos') else {'venta__empleado_id': cajero_filter}),
            **({} if sucursal_filter in (None, '', 'todos') else {'venta__sucursal_id': sucursal_filter}),
        ).values('producto__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:filtro_top]
    )
    doc = DocxDocument()
    doc.add_heading('Reporte Avanzado', 0)
    doc.add_paragraph(f"Rango: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin.strftime('%Y-%m-%d')}")
    doc.add_heading('KPIs', level=1)
    doc.add_paragraph(f"Ingreso total: ${format_clp(analytics['ingreso_total'])}")
    doc.add_paragraph(f"Venta sin IVA: ${format_clp(analytics['ingreso_total_sin_iva'])}")
    doc.add_paragraph(f"IVA recaudado: ${format_clp(analytics['iva_total_calc'])}")
    doc.add_paragraph(f"Ganancia neta: ${format_clp(analytics['ganancia_neta'])}")
    doc.add_paragraph(f"Ganancia bruta: ${format_clp(analytics['ganancia_bruta'])}")
    doc.add_paragraph(f"Costo total (CMV): ${format_clp(analytics['costo_total'])}")
    doc.add_paragraph(f"Transacciones: {analytics['num_transacciones']}")
    doc.add_paragraph(f"Ticket promedio: ${format_clp(analytics['ticket_promedio'])}")
    doc.add_paragraph(f"Unidades promedio/venta: {analytics['unidades_promedio']}")
    doc.add_heading('Top Productos', level=1)
    for item in top_selling:
        doc.add_paragraph(f"{item['producto__nombre']}: {item['total_cantidad']}")
    doc.add_heading('Ranking de Cajeros', level=1)
    for r in analytics['ranking_cajeros']:
        doc.add_paragraph(f"{r['usuario']}: ventas={r['ventas_count']}, ingreso=${format_clp(r['ingreso_total'])}")
    doc.add_heading('Rentabilidad de Productos (Top 50)', level=1)
    for r in analytics['rentabilidad_productos']:
        doc.add_paragraph(f"{r['producto']}: ganancia_neta=${format_clp(r['ganancia_neta_total'])} ({r['porcentaje_ganancia']}%)")
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    resp = HttpResponse(out.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    resp['Content-Disposition'] = 'attachment; filename="reporte_avanzado.docx"'
    return resp

