from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger 
from django.db.models import Q 
from .models import Product, StockSucursal, TransferenciaStock, AjusteStock
from .utils import build_product_search_q
from .forms import ProductForm
from django.contrib import messages
from django.http import HttpResponse
from django.http import JsonResponse
from openpyxl import Workbook, load_workbook
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, date
from django.utils.dateparse import parse_date 
from sucursales.models import Sucursal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json

def product_management(request):
    """
    Vista para la gestión y listado de productos, incluyendo búsqueda, paginación y ordenamiento.
    """
    query = request.GET.get('search', '')
    
    # Obtener parámetros de ordenamiento
    sort_by = request.GET.get('sort_by', 'nombre')
    order = request.GET.get('order', 'asc')

    # Filtrar productos
    products = Product.objects.filter(build_product_search_q(query))

    # Lista de campos permitidos para ordenar
    allowed_sort_fields = {
        'nombre': 'nombre',
        'descripcion': 'descripcion',
        'codigo1': 'producto_id',
        'codigo_barras': 'codigo_barras',
        'fecha_ingreso': 'fecha_ingreso_producto',
        'precio_compra': 'precio_compra',
        'precio_venta': 'precio_venta',
        'cantidad': 'cantidad',
        'stock': 'stock',
    }

    # Aplicar ordenamiento
    if sort_by in allowed_sort_fields:
        field_to_sort = allowed_sort_fields[sort_by]
        if order == 'desc':
            field_to_sort = '-' + field_to_sort
        products = products.order_by(field_to_sort)
    else:
        products = products.order_by('nombre') 

    total_products_count = products.count()
    per_page_options = [10, 25, 50, 100] 
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10 
    
    if per_page not in per_page_options:
        per_page = 10 

    paginator = Paginator(products, per_page) 
    page = request.GET.get('page', 1) 
    
    try:
        products_page = paginator.page(page) 
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    return render(request, 'products/product_management.html', {
        'products': products_page,
        'total_products_count': total_products_count,
        'search_query': query,
        'per_page': per_page, 
        'per_page_options': per_page_options, 
        'sort_by': sort_by, 
        'order': order,
        # Filtrado de mensajes para evitar mostrar avisos de caja aquí
        'messages': [m for m in messages.get_messages(request) if not (
            str(m).startswith('Ya existe una caja abierta') or str(m).startswith('Caja abierta en sucursal') or str(m).startswith('Ya tienes una caja abierta')
        )]
    })

def create_or_edit_product(request, product_id=None):
    """
    Vista para crear un nuevo producto o editar uno existente.
    """
    product = get_object_or_404(Product, id=product_id) if product_id else None
    form = ProductForm(request.POST or None, instance=product, user=request.user)
    title = 'Editar Producto' if product_id else 'Crear Producto'

    if request.method == 'POST' and form.is_valid():
        product_instance = form.save() 
        messages.success(request, 'Los cambios se guardaron con éxito.')
        if 'save_and_list' in request.POST:
            return redirect('product_management')
        return redirect('edit_product', product_instance.id)
    # Construir resumen de stock por sucursal (si existe el producto)
    stocks = []
    if product and product.id:
        registros = StockSucursal.objects.select_related('sucursal').filter(producto=product)
        for r in registros:
            stocks.append({ 'sucursal': r.sucursal, 'cantidad': r.cantidad })
        # Fallback al stock legado si no hay registros por sucursal
        if not registros.exists() and product.sucursal_id:
            try:
                suc = Sucursal.objects.get(id=product.sucursal_id)
                stocks.append({ 'sucursal': suc, 'cantidad': product.stock })
            except Sucursal.DoesNotExist:
                pass
    return render(request, 'products/product_form.html', {
        'form': form, 
        'title': title, 
        'product': product,
        'stocks_sucursal': stocks
    })

def delete_product(request, product_id):
    """
    Vista para eliminar un producto.
    """
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Producto eliminado exitosamente.')
        return redirect('product_management')
    return render(request, 'products/delete_product.html', {'product': product})

def download_template(request):
    """
    Vista para descargar una plantilla Excel con los encabezados de los productos, 
    incluyendo los nuevos campos calculados.
    """
    from openpyxl import Workbook
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="plantilla_productos.xlsx"'

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Productos'

    # Nuevos encabezados que incluyen los cálculos
    headers = [
        'NOMBRE', 'DESCRIPCION', 'CODIGO 1', 'CODIGO DE BARRAS',
        'FECHA DE INGRESO', 'PRECIO DE COMPRA', 'PRECIO DE VENTA',
        'PRECIO COMPRA SIN IVA', 'PRECIO VENTA SIN IVA',
        'GANANCIA NETA', 'PORCENTAJE DE GANANCIA'
    ]
    sheet.append(headers)

    workbook.save(response)
    return response

def upload_products(request):
    """
    Vista para subir productos desde un archivo Excel.
    """
    if request.method == 'POST':
        dry_run = 'dry_run' in request.POST  # Permite previsualización sin escribir
        if 'file' not in request.FILES:
            messages.error(request, 'No se subió ningún archivo.')
            return redirect('upload_products')

        file = request.FILES['file']
        if not file.name.lower().endswith('.xlsx'):
            messages.error(request, 'Formato inválido. Se requiere un .xlsx')
            return redirect('upload_products')

        try:
            # Use read_only streaming mode to reduce memory usage on low-RAM instances
            workbook = load_workbook(file, read_only=True, data_only=True)
            sheet = workbook.active

            # In read_only mode, avoid random access like sheet[1]; iterate the first row instead
            first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
            header_row_values = [str(v).strip() for v in (first_row or [])]
            header_map = {header: idx for idx, header in enumerate(header_row_values) if header}
            minimal_headers = ['NOMBRE', 'CODIGO 1', 'PRECIO DE COMPRA', 'PRECIO DE VENTA']
            missing = [h for h in minimal_headers if h not in header_map]
            if missing:
                messages.error(request, f'Faltan encabezados obligatorios: {", ".join(missing)}')
                return redirect('upload_products')

            # Pre-cargar productos existentes para minimizar queries repetidas
            existing_map = {p.producto_id: p for p in Product.objects.filter(producto_id__isnull=False)}

            # Acumuladores
            warnings = []
            errors = []
            # parsed_map mantiene la última fila leída por producto_id (el último valor gana)
            parsed_map = {}

            def safe_decimal(val):
                if val is None or (isinstance(val, str) and str(val).strip() == ''):
                    return Decimal('0.00')
                try:
                    return Decimal(str(val).strip().replace(',', '.'))
                except (ValueError, TypeError, InvalidOperation):
                    return Decimal('0.00')

            for row_idx, row_values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                # Salta filas completamente vacías
                if not any(v for v in row_values if v is not None and str(v).strip() != ''):
                    continue

                def get_val(header_name):
                    idx = header_map.get(header_name)
                    if idx is not None and idx < len(row_values):
                        return row_values[idx]
                    return None

                try:
                    producto_id_excel = get_val('CODIGO 1')
                    if producto_id_excel is None or str(producto_id_excel).strip() == '':
                        warnings.append(f'Fila {row_idx}: CODIGO 1 vacío. Saltada.')
                        continue
                    producto_id_excel = str(producto_id_excel).strip()

                    if producto_id_excel in parsed_map:
                        # Ya hubo una fila anterior con este código; reemplazamos con la nueva fila
                        warnings.append(f'Fila {row_idx}: Código duplicado en archivo ({producto_id_excel}). Se usa la última aparición para actualizar/crear.')
                    # Guardar/actualizar la última representación encontrada en el archivo
                    parsed_map[producto_id_excel] = {
                        'nombre': nombre,
                        'descripcion': descripcion or None,
                        'codigo_barras': (codigo_barras_excel or None),
                        'fecha_ingreso_producto': fecha_ingreso_producto,
                        'precio_compra': precio_compra,
                        'precio_venta': precio_venta,
                        'permitir_venta_sin_stock': True,
                    }

                    nombre = str(get_val('NOMBRE')).strip() if get_val('NOMBRE') is not None else ''
                    descripcion = str(get_val('DESCRIPCION')).strip() if get_val('DESCRIPCION') is not None else ''
                    # Migración: tratar CODIGO 2 del archivo como código de barras principal cuando esté presente
                    codigo_barras_excel = None
                    if 'CODIGO DE BARRAS' in header_map:
                        codigo_barras_excel = str(get_val('CODIGO DE BARRAS')).strip() if get_val('CODIGO DE BARRAS') is not None else ''
                    # Compatibilidad hacia atrás: si sólo existe CODIGO 2, úsalo como código de barras
                    if not codigo_barras_excel and 'CODIGO 2' in header_map:
                        val_alt = get_val('CODIGO 2')
                        codigo_barras_excel = str(val_alt).strip() if val_alt is not None else ''
                    codigo_alternativo = None  # deprecado como entrada de import

                    fecha_ingreso_producto = None
                    fecha_raw = get_val('FECHA DE INGRESO')
                    if fecha_raw:
                        if isinstance(fecha_raw, (datetime, date)):
                            fecha_ingreso_producto = fecha_raw.date() if isinstance(fecha_raw, datetime) else fecha_raw
                        else:
                            try:
                                fecha_ingreso_producto = parse_date(str(fecha_raw).split(' ')[0].strip())
                            except Exception:
                                warnings.append(f'Fila {row_idx}: Fecha inválida "{fecha_raw}" -> se asigna nulo.')

                    precio_compra = safe_decimal(get_val('PRECIO DE COMPRA'))
                    precio_venta = safe_decimal(get_val('PRECIO DE VENTA'))

                    # Nota: el almacenamiento real (crear/actualizar) se hará después de procesar todo el archivo,
                    # usando `parsed_map` para que la última fila con el mismo código sobrescriba las anteriores.
                    # Aquí solo acumulamos en parsed_map (hecho más arriba).
                except Exception as e:
                    errors.append(f'Fila {row_idx}: Error inesperado -> {e}')

            # Construir listas finales de creación/actualización a partir de parsed_map
            to_create = []
            to_update = []
            for codigo, defaults in parsed_map.items():
                if codigo in existing_map:
                    prod = existing_map[codigo]
                    has_change = any(getattr(prod, k) != v for k, v in defaults.items())
                    if has_change:
                        to_update.append((prod, defaults))
                else:
                    to_create.append(Product(producto_id=codigo, **defaults))

            created_count = 0
            updated_count = 0
            if not dry_run:
                from django.db import transaction
                try:
                    with transaction.atomic():
                        if to_create:
                            Product.objects.bulk_create(to_create, batch_size=500)
                            created_count = len(to_create)
                        for prod, defaults in to_update:
                            for k, v in defaults.items():
                                setattr(prod, k, v)
                        if to_update:
                            Product.objects.bulk_update([p for p, _ in to_update], [
                                'nombre','descripcion','codigo_alternativo','codigo_barras','fecha_ingreso_producto','precio_compra','precio_venta','permitir_venta_sin_stock'
                            ], batch_size=500)
                            updated_count = len(to_update)
                except Exception as e:
                    messages.error(request, f'Error de transacción: {e}')
                    return redirect('upload_products')
            else:
                created_count = len(to_create)
                updated_count = len(to_update)

            # Close workbook explicitly to free resources early
            try:
                workbook.close()
            except Exception:
                pass

            total_processed = created_count + updated_count
            if dry_run:
                messages.info(request, f'Dry-run: {total_processed} filas procesables (Nuevos: {created_count}, Modificados: {updated_count}).')
            else:
                messages.success(request, f'Productos creados: {created_count}, actualizados: {updated_count}. Total: {total_processed}.')

            # Compactar warnings y errores para no saturar UI
            if warnings:
                messages.warning(request, f'{len(warnings)} advertencias. Ejemplo: {warnings[0]}')
            if errors:
                messages.error(request, f'{len(errors)} errores. Ejemplo: {errors[0]}')

            # Guardar detalle en sesión para descarga opcional futura
            request.session['upload_products_report'] = {
                'warnings': warnings[:200],  # Limitar
                'errors': errors[:200],
                'created': created_count,
                'updated': updated_count,
                'dry_run': dry_run,
            }

            # Redirigir a gestión si se ejecutó realmente
            if not dry_run:
                return redirect('product_management')
            return redirect('upload_products')
        except Exception as e:
            messages.error(request, f'Error general procesando el archivo: {e}')
            return redirect('upload_products')

    return render(request, 'products/upload_products.html')

def delete_all_products(request):
    """
    Vista para eliminar todos los productos.
    """
    if request.method == 'POST':
        try:
            count, _ = Product.objects.all().delete()
            messages.success(request, f'¡Se eliminaron {count} productos exitosamente!')
            return redirect('product_management')
        except Exception as e:
            messages.error(request, f'Error al intentar eliminar productos: {str(e)}')
            return redirect('product_management')
    return render(request, 'products/delete_all_products_confirm.html')


def bulk_delete_products(request):
    """
    Endpoint para eliminar varios productos a la vez desde la vista de gestión.
    Espera un POST con JSON: { "product_ids": [1,2,3] }
    Devuelve JSON con el número de eliminados.
    """
    if request.method == 'POST':
        try:
            # admitir tanto application/json como form data
            if request.content_type == 'application/json':
                payload = json.loads(request.body.decode('utf-8') or '{}')
                ids = payload.get('product_ids', [])
            else:
                ids = request.POST.getlist('product_ids')
            # Normalizar IDs a enteros
            ids = [int(x) for x in ids if x]
            qs = Product.objects.filter(id__in=ids)
            count = qs.count()
            qs.delete()
            try:
                messages.success(request, f'Se eliminaron {count} productos correctamente.')
            except Exception:
                # En entornos de prueba RequestFactory puede no tener MessageMiddleware
                pass
            return JsonResponse({'success': True, 'deleted': count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

def export_products_to_excel(request):
    """
    Vista para exportar todos los productos a un archivo Excel.
    Se utiliza el formateo definido en el modelo, incluyendo los nuevos cálculos.
    """
    from openpyxl import Workbook
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="export_productos.xlsx"'

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Productos'

    # Encabezados actualizados
    headers = [
        'NOMBRE', 'DESCRIPCION', 'CODIGO 1', 'CODIGO DE BARRAS',
        'FECHA DE INGRESO', 'PRECIO DE COMPRA', 'PRECIO DE VENTA',
        'PRECIO COMPRA SIN IVA', 'PRECIO VENTA SIN IVA',
        'GANANCIA NETA', 'PORCENTAJE DE GANANCIA'
    ]
    sheet.append(headers)

    products = Product.objects.all().order_by('nombre')
    for product in products:
        row_data = [
            product.nombre,
            product.descripcion,
            product.producto_id,
            product.codigo_barras,
            product.fecha_ingreso_producto,
            product.formatted_precio_compra,
            product.formatted_precio_venta,
            product.formatted_precio_compra_sin_iva,
            product.formatted_precio_venta_sin_iva,
            product.formatted_ganancia_neta,
            product.porcentaje_ganancia  # O, si se tiene formateado: product.formatted_porcentaje_ganancia
        ]
        sheet.append(row_data)

    workbook.save(response)
    return response

@property
def precio_compra_sin_iva(self):
    if not self.precio_compra:
        return Decimal('0.00')
    return (self.precio_compra / Decimal('1.19')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

@property
def formatted_precio_compra_sin_iva(self):
    return self._format_currency(self.precio_compra_sin_iva)

@property
def precio_venta_sin_iva(self):
    if not self.precio_venta:
        return Decimal('0.00')
    return (self.precio_venta / Decimal('1.19')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

@property
def formatted_precio_venta_sin_iva(self):
    return self._format_currency(self.precio_venta_sin_iva)

@property
def ganancia_neta(self):
    # Ganancia neta = Venta sin IVA - Compra sin IVA
    return (self.precio_venta_sin_iva - self.precio_compra_sin_iva).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

@property
def formatted_ganancia_neta(self):
    return self._format_currency(self.ganancia_neta)

@property
def porcentaje_ganancia(self):
    if self.precio_venta_sin_iva == Decimal('0.00'):
        return Decimal('0.00')
    porcentaje = (self.ganancia_neta / self.precio_venta_sin_iva) * Decimal('100')
    return porcentaje.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def get_page_range(page_obj, block_size=20):
    total_pages = page_obj.paginator.num_pages
    current = page_obj.number
    start = ((current - 1) // block_size) * block_size + 1
    end = min(start + block_size - 1, total_pages)
    return range(start, end + 1)

def bulk_assign_products(request):
    """
    Vista para asignar de forma masiva productos a una sucursal.
    """
    # Filtros
    search_query = request.GET.get('search', '')
    per_page_options = [10, 20, 30, 50, 100]
    try:
        per_page = int(request.GET.get('per_page', 10))
    except ValueError:
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10

    # Queryset de productos filtrados
    products_qs = Product.objects.all()
    if search_query:
        products_qs = products_qs.filter(build_product_search_q(search_query))
    # Asegurar orden determinístico antes de paginar para evitar UnorderedObjectListWarning
    products_qs = products_qs.order_by('nombre', 'id')
    
    paginator = Paginator(products_qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    block_range = get_page_range(page_obj, 20)

    if request.method == "POST":
        # Obtener IDs de los productos marcados y la sucursal seleccionada
        product_ids = request.POST.getlist('products')
        sucursal_id = request.POST.get('sucursal')
        cantidad_str = request.POST.get('cantidad', '').strip()
        if not product_ids or not sucursal_id:
            messages.error(request, "Debe seleccionar al menos un producto y una sucursal.")
        else:
            # Asignar sucursal y opcionalmente establecer stock a la cantidad indicada
            qs = Product.objects.filter(id__in=product_ids)
            qs.update(sucursal_id=sucursal_id)
            if cantidad_str:
                try:
                    cantidad_val = int(cantidad_str)
                    if cantidad_val < 0:
                        raise ValueError("La cantidad no puede ser negativa.")
                    qs.update(stock=cantidad_val)
                except ValueError:
                    messages.warning(request, "La cantidad ingresada no es válida. Se ignoró la actualización de stock.")
            messages.success(request, "Productos asignados exitosamente a la sucursal.")
            return redirect('product_management')

    context = {
        'page_obj': page_obj,
        'block_range': block_range,
        'search_query': search_query,
        'per_page_options': per_page_options,
        'per_page': per_page,
        'sucursales': Sucursal.objects.all(),
    }
    return render(request, 'products/bulk_assign_products.html', context)

def transfer_stock(request):
    """Transferir cantidad de un producto desde una sucursal origen a una sucursal destino."""
    productos = Product.objects.all().order_by('nombre')
    sucursales = Sucursal.objects.all().order_by('nombre')
    # Pre-selección desde query params
    pre_producto = request.GET.get('producto')
    pre_origen = request.GET.get('sucursal_origen')
    context = { 'productos': productos, 'sucursales': sucursales, 'pre_producto': pre_producto, 'pre_origen': pre_origen }
    if request.method == 'POST':
        try:
            producto_id = int(request.POST.get('producto_id'))
            origen_id = int(request.POST.get('sucursal_origen'))
            destino_id = int(request.POST.get('sucursal_destino'))
            cantidad = int(request.POST.get('cantidad'))
        except (TypeError, ValueError):
            messages.error(request, 'Datos inválidos en el formulario.')
            return render(request, 'products/transfer_stock.html', context)
        if origen_id == destino_id:
            messages.error(request, 'La sucursal de origen y destino no pueden ser la misma.')
            return render(request, 'products/transfer_stock.html', context)
        if cantidad <= 0:
            messages.error(request, 'La cantidad debe ser mayor a cero.')
            return render(request, 'products/transfer_stock.html', context)
        producto = get_object_or_404(Product, id=producto_id)
        suc_origen = get_object_or_404(Sucursal, id=origen_id)
        suc_destino = get_object_or_404(Sucursal, id=destino_id)
        # Validar stock disponible en origen
        disp = producto.stock_en(suc_origen)
        if disp < cantidad and not producto.permitir_venta_sin_stock:
            messages.error(request, f'Stock insuficiente en sucursal origen. Disponible: {disp}.')
            return render(request, 'products/transfer_stock.html', context)
        # Descontar en origen
        ss_origen, _ = StockSucursal.objects.get_or_create(producto=producto, sucursal=suc_origen, defaults={'cantidad': 0})
        ss_origen.cantidad = max(0, (ss_origen.cantidad or 0) - cantidad)
        ss_origen.save()
        # Aumentar en destino
        ss_destino, _ = StockSucursal.objects.get_or_create(producto=producto, sucursal=suc_destino, defaults={'cantidad': 0})
        ss_destino.cantidad = (ss_destino.cantidad or 0) + cantidad
        ss_destino.save()
        # Registrar historial
        TransferenciaStock.objects.create(
            producto=producto,
            origen=suc_origen,
            destino=suc_destino,
            cantidad=cantidad,
            usuario=request.user if request.user.is_authenticated else None
        )
        messages.success(request, f'Transferencia realizada: {cantidad} unidades de "{producto.nombre}" de {suc_origen.nombre} a {suc_destino.nombre}.')
        return redirect('transfer_stock')
    return render(request, 'products/transfer_stock.html', context)

def transfer_history(request):
    """Historial simple de transferencias con filtros básicos."""
    productos = Product.objects.all().order_by('nombre')
    sucursales = Sucursal.objects.all().order_by('nombre')
    qs = TransferenciaStock.objects.select_related('producto', 'origen', 'destino', 'usuario').all()
    prod = request.GET.get('producto')
    suc = request.GET.get('sucursal')
    # Paginación
    per_page_options = [10, 20, 30, 50]
    try:
        per_page = int(request.GET.get('per_page', 10))
    except ValueError:
        per_page = 10
    if per_page not in per_page_options:
        per_page = 10
    if prod:
        qs = qs.filter(producto_id=prod)
    if suc:
        qs = qs.filter(Q(origen_id=suc) | Q(destino_id=suc))
    # Ordenar descendente por fecha (más recientes primero)
    qs = qs.order_by('-fecha')
    # Construir paginador
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'products/transfer_history.html', {
        'page_obj': page_obj,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'productos': productos,
        'sucursales': sucursales,
        'producto_sel': prod,
        'sucursal_sel': suc,
    })

def ajustar_stock(request):
    """Endpoint POST para ajustar stock por sucursal (incremento o decremento)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        producto_id = int(request.POST.get('producto_id'))
        sucursal_id = int(request.POST.get('sucursal_id'))
        delta = int(request.POST.get('delta'))
        motivo = (request.POST.get('motivo') or '').strip()
        producto = get_object_or_404(Product, id=producto_id)
        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
        ss, _ = StockSucursal.objects.get_or_create(producto=producto, sucursal=sucursal, defaults={'cantidad': 0})
        ss.cantidad = max(0, (ss.cantidad or 0) + delta)
        ss.save()
        AjusteStock.objects.create(
            producto=producto,
            sucursal=sucursal,
            cantidad_delta=delta,
            motivo=motivo or None,
            usuario=request.user if request.user.is_authenticated else None
        )
        return JsonResponse({'success': True, 'nueva_cantidad': ss.cantidad})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def adjust_history(request):
    """Historial de ajustes de stock con filtros por producto y sucursal."""
    productos = Product.objects.all().order_by('nombre')
    sucursales = Sucursal.objects.all().order_by('nombre')
    qs = AjusteStock.objects.select_related('producto', 'sucursal', 'usuario').all()
    prod = request.GET.get('producto')
    suc = request.GET.get('sucursal')
    q_text = (request.GET.get('q') or '').strip()
    if prod:
        qs = qs.filter(producto_id=prod)
    if suc:
        qs = qs.filter(sucursal_id=suc)
    if q_text:
        qs = qs.filter(
            Q(producto__nombre__icontains=q_text) |
            Q(producto__producto_id__icontains=q_text) |
            Q(producto__codigo_alternativo__icontains=q_text)
        )
    # Ordenar por fecha descendente para mostrar primero los ajustes más recientes
    qs = qs.order_by('-fecha')
    return render(request, 'products/adjust_history.html', {
        'ajustes': qs[:200],
        'productos': productos,
        'sucursales': sucursales,
        'producto_sel': prod,
        'sucursal_sel': suc,
        'q_text': q_text,
    })

def sucursal_products(request, sucursal_id):
    """
    Listado de productos de una sucursal con paginación y tamaño de página configurable.
    """
    sucursal = get_object_or_404(Sucursal, id=sucursal_id)
    search_query = request.GET.get('search', '').strip()
    stock_filter = request.GET.get('stock', '').strip()  # '', 'low', 'out'
    try:
        per_page = int(request.GET.get('per_page', 10))
    except ValueError:
        per_page = 10
    if per_page not in [10, 20, 30, 50]:
        per_page = 10
    # Incluir productos asociados por FK y/o que tengan stock registrado en esta sucursal
    productos_fk = Product.objects.filter(sucursal_id=sucursal_id)
    productos_stock = Product.objects.filter(stocks_por_sucursal__sucursal_id=sucursal_id)
    productos_qs = (productos_fk | productos_stock).distinct().prefetch_related('stocks_por_sucursal')
    if search_query:
        productos_qs = productos_qs.filter(build_product_search_q(search_query))
    # Determinar umbral ahora para posible filtrado por stock
    threshold = None  # será resuelto abajo usando sucursal o settings
    # Filtrado por estado de stock si corresponde (antes de paginar)
    if stock_filter in ('low', 'out'):
        # Resolver threshold preliminar (si sucursal tiene 0, luego usaremos el global)
        threshold = sucursal.low_stock_threshold if getattr(sucursal, 'low_stock_threshold', 0) and sucursal.low_stock_threshold > 0 else getattr(settings, 'LOW_STOCK_THRESHOLD', 2)
        ids_keep = []
        for p in productos_qs:
            s_val = 0
            try:
                s_val = p.stock_en(sucursal)
            except Exception:
                s_val = p.stock or 0
            if stock_filter == 'out' and s_val <= 0:
                ids_keep.append(p.id)
            elif stock_filter == 'low' and s_val > 0 and s_val <= threshold:
                ids_keep.append(p.id)
        productos_qs = productos_qs.filter(id__in=ids_keep)
    productos_qs = productos_qs.order_by('nombre')
    paginator = Paginator(productos_qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Adjuntar stock por sucursal a cada producto de la página
    for p in page_obj.object_list:
        try:
            p.stock_sucursal = p.stock_en(sucursal)
        except Exception:
            p.stock_sucursal = p.stock
    # Determinar umbral: usar el de la sucursal si > 0; en caso contrario, el global
    if threshold is None:
        threshold = sucursal.low_stock_threshold if getattr(sucursal, 'low_stock_threshold', 0) and sucursal.low_stock_threshold > 0 else getattr(settings, 'LOW_STOCK_THRESHOLD', 2)
    return render(request, 'sucursales/sucursal_products.html', {
        'sucursal': sucursal,
        'page_obj': page_obj,
        'per_page': per_page,
        'per_page_options': [10, 20, 30, 50],
        'search_query': search_query,
        'low_stock_threshold': threshold,
        'stock_filter': stock_filter
    })