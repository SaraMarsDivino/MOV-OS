from decimal import Decimal, ROUND_HALF_UP
import datetime
from django.utils import timezone
from django.db.models import Sum, F, Count
from django.db.models import DateField
from django.db.models.functions import Cast
from django.core.cache import cache
from cashier.models import Venta, VentaDetalle
import hashlib

def _safe_cache_key(prefix: str, *parts) -> str:
    """Genera una clave de caché segura para backends como memcached.
    Combina prefix + hash SHA1 de los componentes serializados.
    """
    raw = '|'.join(str(p) for p in parts)
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()  # corto y seguro
    return f"{prefix}:{digest}"
from sucursales.models import Sucursal

# Nota: Mantener lógica alineada con reports/views.py advanced_reports.

def compute_analytics(fecha_inicio, fecha_fin, cajero_filter='todos', sucursal_filter='todos', limit_rentabilidad=50):
    """Computa todos los datasets y KPIs usados en advanced_reports.
    Retorna diccionario con claves idénticas a las usadas en el contexto.
    """
    ventas_qs = Venta.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
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

    # Aggregates principales
    agg_ventas = ventas_qs.aggregate(ingreso_total=Sum('total'), num_transacciones=Count('id'))
    ingreso_total = agg_ventas.get('ingreso_total') or Decimal('0.00')
    num_transacciones = agg_ventas.get('num_transacciones') or 0

    agg_unidades = VentaDetalle.objects.filter(venta__in=ventas_qs).aggregate(total_unidades=Sum('cantidad'))
    total_unidades = agg_unidades.get('total_unidades') or 0

    agg_cmv = VentaDetalle.objects.filter(venta__in=ventas_qs).aggregate(
        cmv=Sum(F('cantidad') * F('producto__precio_compra'))
    )
    cmv_val = agg_cmv.get('cmv') or 0
    cmv = Decimal(str(cmv_val))

    ganancia_bruta = ingreso_total - cmv
    ticket_promedio = (ingreso_total / num_transacciones) if num_transacciones > 0 else Decimal('0.00')
    unidades_promedio = (total_unidades / num_transacciones) if num_transacciones > 0 else 0

    best_selling = VentaDetalle.objects.filter(venta__in=ventas_qs) \
        .values('producto__nombre') \
        .annotate(total_cantidad=Sum('cantidad')) \
        .order_by('-total_cantidad') \
        .first()
    best_selling_product = best_selling['producto__nombre'] if best_selling else "N/A"
    best_selling_quantity = best_selling['total_cantidad'] if best_selling else 0

    sales_by_payment_type = ventas_qs.values('forma_pago').annotate(total_monto=Sum('total'))
    sales_by_payment = []
    sales_by_payment_chart = []
    for item in sales_by_payment_type:
        monto = item['total_monto'] or 0
        sales_by_payment.append({'forma_pago': item['forma_pago'], 'total_monto_raw': monto})
        sales_by_payment_chart.append({'forma_pago': item['forma_pago'], 'total_monto': float(monto)})

    if ingreso_total > 0:
        ingreso_sin_iva = (ingreso_total / Decimal('1.19')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        iva_total_calc = ingreso_total - ingreso_sin_iva
    else:
        ingreso_sin_iva = Decimal('0.00')
        iva_total_calc = Decimal('0.00')

    cost_net = (cmv / Decimal('1.19')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if cmv else Decimal('0.00')
    ganancia_neta = ingreso_sin_iva - cost_net
    margen = ((ganancia_neta / ingreso_sin_iva) * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if ingreso_sin_iva > 0 else Decimal('0.00')

    # Serie diaria (cacheada) - usar Cast(DateField) en lugar de SQL raw para mayor compatibilidad
    cache_key_daily = _safe_cache_key("daily_series", fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    daily_series = cache.get(cache_key_daily)
    if daily_series is None:
        daily_series_qs = ventas_qs.annotate(day=Cast('fecha', DateField())).values('day').annotate(ingreso=Sum('total')).order_by('day')
        daily_series = list(daily_series_qs)
        cache.set(cache_key_daily, daily_series, 300)
    daily_chart = []
    # Para obtener costo por día usamos un único queryset agregado por fecha para evitar loops por detalle
    # Agrupamos VentaDetalle por fecha de venta y sumamos cantidad*precio_compra
    detalle_por_dia = VentaDetalle.objects.filter(venta__in=ventas_qs).annotate(day=Cast('venta__fecha', DateField())).values('day').annotate(costo=Sum(F('cantidad') * F('producto__precio_compra')))
    detalle_map = {d['day']: d['costo'] or 0 for d in detalle_por_dia}
    for row in daily_series:
        day_raw = row.get('day')
        if not day_raw:
            continue
        ingreso_dia = row.get('ingreso') or Decimal('0.00')
        costo_dia = Decimal(str(detalle_map.get(day_raw, 0)))
        ingreso_sin_iva_dia = (ingreso_dia / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_dia else Decimal('0.00')
        costo_sin_iva_dia = (costo_dia / Decimal('1.19')).quantize(Decimal('0.01')) if costo_dia else Decimal('0.00')
        ganancia_neta_dia = ingreso_sin_iva_dia - costo_sin_iva_dia
        day_str = day_raw.strftime('%Y-%m-%d') if isinstance(day_raw, datetime.date) else str(day_raw)
        daily_chart.append({'day': day_str, 'ingreso': float(ingreso_dia), 'ganancia_neta': float(ganancia_neta_dia)})

    # Comparación por sucursal (cacheada)
    cache_key_branch = _safe_cache_key("branch_comp", fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    branch_comparison = cache.get(cache_key_branch)
    if branch_comparison is None:
        branch_comparison = []
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
            branch_comparison.append({'sucursal': suc.nombre, 'ingreso': float(ingreso_suc), 'ganancia_neta': float(ganancia_neta_suc)})
        cache.set(cache_key_branch, branch_comparison, 300)

    # Distribución horaria y heatmap
    hourly_distribution = [{'hora': h, 'ventas': 0, 'ingreso': 0.0} for h in range(24)]
    heatmap_matrix = [[{'ventas':0,'ingreso':0.0} for _ in range(24)] for _ in range(7)]
    for v in ventas_qs:
        h = v.fecha.hour
        hourly_distribution[h]['ventas'] += 1
        hourly_distribution[h]['ingreso'] += float(v.total or 0)
        dow = v.fecha.weekday()
        cell = heatmap_matrix[dow][h]
        cell['ventas'] += 1
        cell['ingreso'] += float(v.total or 0)

    # Rentabilidad productos (cacheada parcialmente)
    cache_key_rent = _safe_cache_key("rentabilidad", fecha_inicio, fecha_fin, cajero_filter, sucursal_filter)
    rentabilidad_productos = cache.get(cache_key_rent)
    if rentabilidad_productos is None:
        detalles_rango = VentaDetalle.objects.filter(venta__in=ventas_qs).select_related('producto')
        tmp = {}
        for det in detalles_rango:
            pid = det.producto_id
            venta_unit = det.precio_unitario or Decimal('0.00')
            compra_unit = det.producto.precio_compra or Decimal('0.00')
            venta_sin_iva_unit = (venta_unit / Decimal('1.19')).quantize(Decimal('0.01')) if venta_unit else Decimal('0.00')
            compra_sin_iva_unit = (compra_unit / Decimal('1.19')).quantize(Decimal('0.01')) if compra_unit else Decimal('0.00')
            ganancia_neta_unit = venta_sin_iva_unit - compra_sin_iva_unit
            entry = tmp.get(pid)
            if not entry:
                entry = {'producto': det.producto.nombre or det.producto.producto_id, 'cantidad':0,'ingreso_neto_total':Decimal('0.00'),'costo_neto_total':Decimal('0.00'),'ganancia_neta_total':Decimal('0.00')}
            entry['cantidad'] += det.cantidad
            entry['ingreso_neto_total'] += venta_sin_iva_unit * det.cantidad
            entry['costo_neto_total'] += compra_sin_iva_unit * det.cantidad
            entry['ganancia_neta_total'] += ganancia_neta_unit * det.cantidad
            tmp[pid] = entry
        rentabilidad_productos = []
        for _, data in tmp.items():
            porcentaje = Decimal('0.00')
            if data['ingreso_neto_total'] > 0:
                porcentaje = (data['ganancia_neta_total'] / data['ingreso_neto_total'] * Decimal('100')).quantize(Decimal('0.01'))
            rentabilidad_productos.append({
                'producto': data['producto'],
                'cantidad': data['cantidad'],
                'ingreso_neto_total': float(data['ingreso_neto_total']),
                'costo_neto_total': float(data['costo_neto_total']),
                'ganancia_neta_total': float(data['ganancia_neta_total']),
                'porcentaje_ganancia': float(porcentaje)
            })
        rentabilidad_productos.sort(key=lambda x: x['ganancia_neta_total'], reverse=True)
        cache.set(cache_key_rent, rentabilidad_productos, 300)

    ranking_cajeros_map = {}
    for v in ventas_qs.select_related('empleado'):
        uid = v.empleado_id
        entry = ranking_cajeros_map.get(uid)
        if not entry:
            entry = {'usuario': v.empleado.username, 'ventas_count':0, 'ingreso_total':Decimal('0.00')}
        entry['ventas_count'] += 1
        entry['ingreso_total'] += v.total or Decimal('0.00')
        ranking_cajeros_map[uid] = entry
    ranking_cajeros = []
    for _, data in ranking_cajeros_map.items():
        ticket_prom = (data['ingreso_total'] / data['ventas_count']).quantize(Decimal('0.01')) if data['ventas_count'] else Decimal('0.00')
        ranking_cajeros.append({'usuario': data['usuario'], 'ventas_count': data['ventas_count'], 'ingreso_total': float(data['ingreso_total']), 'ticket_promedio': float(ticket_prom)})
    ranking_cajeros.sort(key=lambda x: x['ingreso_total'], reverse=True)

    # Wave últimos 6 meses (ganancia neta mensual)
    months_wave = []
    gains_wave = []
    today = timezone.now().date().replace(day=1)
    for i in range(5, -1, -1):
        start_month = (today - datetime.timedelta(days=30*i))
        first_day = start_month.replace(day=1)
        next_month = (first_day + datetime.timedelta(days=32)).replace(day=1)
        last_day = next_month - datetime.timedelta(days=1)
        ventas_mes = ventas_qs.filter(fecha__date__gte=first_day, fecha__date__lte=last_day)
        ingreso_mes = ventas_mes.aggregate(t=Sum('total'))['t'] or Decimal('0.00')
        detalles_mes = VentaDetalle.objects.filter(venta__in=ventas_mes)
        costo_mes = Decimal('0.00')
        for det in detalles_mes:
            costo_mes += (det.producto.precio_compra or Decimal('0.00')) * det.cantidad
        ingreso_sin_iva_mes = (ingreso_mes / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_mes else Decimal('0.00')
        costo_sin_iva_mes = (costo_mes / Decimal('1.19')).quantize(Decimal('0.01')) if costo_mes else Decimal('0.00')
        ganancia_neta_mes = ingreso_sin_iva_mes - costo_sin_iva_mes
        months_wave.append(first_day.strftime('%b %Y'))
        gains_wave.append(float(ganancia_neta_mes))

    # Periodo anterior comparativo
    rango_dias = (fecha_fin - fecha_inicio).days + 1
    prev_fin = fecha_inicio - datetime.timedelta(days=1)
    prev_inicio = prev_fin - datetime.timedelta(days=rango_dias - 1)
    ventas_prev = Venta.objects.filter(fecha__gte=prev_inicio, fecha__lte=prev_fin)
    ingreso_prev = ventas_prev.aggregate(t=Sum('total'))['t'] or Decimal('0.00')
    detalles_prev = VentaDetalle.objects.filter(venta__in=ventas_prev)
    cmv_prev_val = detalles_prev.aggregate(cmv_prev=Sum(F('cantidad') * F('producto__precio_compra')))['cmv_prev'] or 0
    cmv_prev = Decimal(str(cmv_prev_val))
    ingreso_sin_iva_prev = (ingreso_prev / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_prev else Decimal('0.00')
    costo_prev_net = (cmv_prev / Decimal('1.19')).quantize(Decimal('0.01')) if cmv_prev else Decimal('0.00')
    ganancia_neta_prev = ingreso_sin_iva_prev - costo_prev_net
    num_transacciones_prev = ventas_prev.count()

    def delta_pct(current: Decimal, previous: Decimal):
        delta = (current - previous)
        if previous == 0:
            pct = Decimal('100.00') if current > 0 else Decimal('0.00')
        else:
            pct = ((delta / previous) * Decimal('100')).quantize(Decimal('0.01'))
        return delta, pct

    ingreso_delta, ingreso_pct = delta_pct(ingreso_total, ingreso_prev)
    ganancia_neta_delta, ganancia_neta_pct = delta_pct(ganancia_neta, ganancia_neta_prev)
    transacciones_delta, transacciones_pct = delta_pct(Decimal(num_transacciones), Decimal(num_transacciones_prev))
    margen_prev = ((ganancia_neta_prev / ingreso_sin_iva_prev) * Decimal('100')).quantize(Decimal('0.01')) if ingreso_sin_iva_prev > 0 else Decimal('0.00')
    margen_delta, margen_pct = delta_pct(margen, margen_prev)

    return {
        'ingreso_total': ingreso_total,
        'ingreso_total_sin_iva': ingreso_sin_iva,
        'iva_total_calc': iva_total_calc,
        'ganancia_bruta': ganancia_bruta,
        'ganancia_neta': ganancia_neta,
        'margen': margen,
        'costo_total': cmv,
        'num_transacciones': num_transacciones,
        'ticket_promedio': ticket_promedio,
        'unidades_promedio': unidades_promedio,
        'best_selling_product': best_selling_product,
        'best_selling_quantity': best_selling_quantity,
        'sales_by_payment': sales_by_payment,
        'sales_by_payment_chart': sales_by_payment_chart,
        'daily_chart': daily_chart,
        'branch_comparison': branch_comparison,
        'hourly_distribution': hourly_distribution,
        'heatmap_matrix': heatmap_matrix,
        'rentabilidad_productos': rentabilidad_productos[:limit_rentabilidad],
        'ranking_cajeros': ranking_cajeros,
        'wave_labels': months_wave,
        'wave_gains': gains_wave,
        # Comparativos
        'prev_inicio': prev_inicio,
        'prev_fin': prev_fin,
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
    }
