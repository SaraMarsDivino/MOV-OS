from decimal import Decimal, ROUND_HALF_UP
import datetime
from django.utils import timezone
from django.db.models import Sum, F, Count
from django.db.models import DateField
from django.db.models.functions import Cast, ExtractHour, ExtractWeekDay
from django.core.cache import cache
from cashier.models import Venta, VentaDetalle
import hashlib
import calendar

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
    # DEBUG: contar ventas en rango para diagnosticar tests intermitentes
    try:
        print(f"DEBUG compute_analytics ventas_count={ventas_qs.count()} rango={fecha_inicio} - {fecha_fin}")
    except Exception:
        pass
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
    # Series diaria: agregación directa (no cache para evitar inconsistencias en tests)
    daily_series_qs = ventas_qs.annotate(day=Cast('fecha', DateField())).values('day').annotate(ingreso=Sum('total')).order_by('day')
    daily_series = list(daily_series_qs)
    # Rellenar la serie diaria para todos los días en el rango (incluir días con 0)
    daily_chart = []
    detalle_por_dia = VentaDetalle.objects.filter(venta__in=ventas_qs).annotate(day=Cast('venta__fecha', DateField())).values('day').annotate(costo=Sum(F('cantidad') * F('producto__precio_compra')))
    detalle_map = {d['day']: d['costo'] or 0 for d in detalle_por_dia}
    # Construir mapa de ingreso por día desde daily_series
    ingresos_map = {row.get('day'): row.get('ingreso') or Decimal('0.00') for row in daily_series}
    # Iterar todos los días del rango
    current = fecha_inicio.date() if isinstance(fecha_inicio, datetime.datetime) else fecha_inicio
    end_date = fecha_fin.date() if isinstance(fecha_fin, datetime.datetime) else fecha_fin
    while current <= end_date:
        ingreso_dia = ingresos_map.get(current, Decimal('0.00'))
        costo_dia = Decimal(str(detalle_map.get(current, 0)))
        ingreso_sin_iva_dia = (ingreso_dia / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso_dia else Decimal('0.00')
        costo_sin_iva_dia = (costo_dia / Decimal('1.19')).quantize(Decimal('0.01')) if costo_dia else Decimal('0.00')
        ganancia_neta_dia = ingreso_sin_iva_dia - costo_sin_iva_dia
        day_str = current.strftime('%Y-%m-%d')
        daily_chart.append({'day': day_str, 'ingreso': float(ingreso_dia), 'ganancia_neta': float(ganancia_neta_dia)})
        current = current + datetime.timedelta(days=1)

    # Comparación por sucursal (cacheada)
    # Comparación por sucursal (sin cache para evitar inconsistencias durante tests)
    ingresos_qs = ventas_qs.values('sucursal__id').annotate(ingreso=Sum('total'))
    ingresos_map = {row['sucursal__id']: row.get('ingreso') or Decimal('0.00') for row in ingresos_qs}
    costos_qs = VentaDetalle.objects.filter(venta__in=ventas_qs).annotate(suc_id=F('venta__sucursal_id')).values('suc_id').annotate(costo=Sum(F('cantidad') * F('producto__precio_compra')))
    costos_map = {row['suc_id']: row.get('costo') or 0 for row in costos_qs}
    branch_comparison = []
    for suc in Sucursal.objects.all():
        ingreso = ingresos_map.get(suc.id, Decimal('0.00'))
        costo_val = costos_map.get(suc.id, 0)
        costo = Decimal(str(costo_val))
        ingreso_sin_iva_suc = (ingreso / Decimal('1.19')).quantize(Decimal('0.01')) if ingreso else Decimal('0.00')
        costo_sin_iva_suc = (costo / Decimal('1.19')).quantize(Decimal('0.01')) if costo else Decimal('0.00')
        ganancia_neta_suc = ingreso_sin_iva_suc - costo_sin_iva_suc
        branch_comparison.append({'sucursal': suc.nombre, 'ingreso': float(ingreso), 'ganancia_neta': float(ganancia_neta_suc)})

    # Distribución horaria y heatmap (usar agregaciones en DB)
    hourly_distribution = [{'hora': h, 'ventas': 0, 'ingreso': 0.0} for h in range(24)]
    heatmap_matrix = [[{'ventas':0,'ingreso':0.0} for _ in range(24)] for _ in range(7)]
    # Agregar por hora
    hours_qs = ventas_qs.annotate(hour=ExtractHour('fecha')).values('hour').annotate(ventas=Count('id'), ingreso=Sum('total'))
    for row in hours_qs:
        h = int(row['hour']) if row.get('hour') is not None else None
        if h is not None and 0 <= h < 24:
            hourly_distribution[h]['ventas'] = int(row['ventas'])
            hourly_distribution[h]['ingreso'] = float(row['ingreso'] or 0)
    # Agregar por weekday+hour para heatmap
    heat_qs = ventas_qs.annotate(weekday=ExtractWeekDay('fecha'), hour=ExtractHour('fecha')).values('weekday','hour').annotate(ventas=Count('id'), ingreso=Sum('total'))
    for row in heat_qs:
        # ExtractWeekDay returns 1-7 (Sunday=1). Convert to 0-6 Monday=0
        wk = int(row['weekday'])
        # Convert to Python weekday where Monday=0
        py_wk = (wk - 2) % 7
        h = int(row['hour']) if row.get('hour') is not None else None
        if 0 <= py_wk < 7 and h is not None and 0 <= h < 24:
            heatmap_matrix[py_wk][h]['ventas'] = int(row['ventas'])
            heatmap_matrix[py_wk][h]['ingreso'] = float(row['ingreso'] or 0)

    # Rentabilidad productos (cacheada parcialmente)
    # Rentabilidad productos (sin cache para coherencia durante tests)
    # Construir clave de caché única para rentabilidad (si se desea cachear)
    cache_key_rent = _safe_cache_key('rentabilidad', getattr(fecha_inicio, 'isoformat', lambda: str(fecha_inicio))(), getattr(fecha_fin, 'isoformat', lambda: str(fecha_fin))(), cajero_filter or '', sucursal_filter or '')

    # Intentar recuperar rentabilidad desde cache antes de computar (clave segura por rango y filtros)
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
                entry = {'producto': det.producto.nombre or det.producto.producto_id, 'cantidad': 0, 'ingreso_neto_total': Decimal('0.00'), 'costo_neto_total': Decimal('0.00'), 'ganancia_neta_total': Decimal('0.00')}
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
        # Only cache non-empty results to avoid returning stale empty lists
        try:
            if rentabilidad_productos:
                cache.set(cache_key_rent, rentabilidad_productos, 300)
        except Exception:
            pass
    else:
        try:
            print(f"DEBUG compute_analytics: cache HIT for key={cache_key_rent} len={len(rentabilidad_productos)}")
        except Exception:
            pass

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
    # Wave últimos 6 meses (ganancia neta mensual) — generar meses correctamente
    months_wave = []
    gains_wave = []
    ref = timezone.now().date().replace(day=1)
    for m in range(5, -1, -1):
        # calcular year/month retrocediendo m meses
        year = ref.year
        month = ref.month - m
        while month <= 0:
            month += 12
            year -= 1
        first_day = datetime.date(year, month, 1)
        last_day = datetime.date(year, month, calendar.monthrange(year, month)[1])
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
