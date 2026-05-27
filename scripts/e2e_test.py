import os
import sys
import json
from decimal import Decimal
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MOVOS.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from sucursales.models import Sucursal
from products.models import Product, StockSucursal, TransferenciaStock, AjusteStock
from cashier.models import Venta, VentaDetalle, AperturaCierreCaja


PASS = 0
FAIL = 0

def check(label, cond, extra=None):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}")
        if extra:
            print(extra)
    return cond


def assert_status(label, resp, expected=200):
    return check(f"{label} -> HTTP {resp.status_code}", resp.status_code == expected, getattr(resp, 'content', b'')[:400])


def main():
    User = get_user_model()

    # Clean slate minimal (avoid cascade surprises in real DB)
    # Create base data
    admin, _ = User.objects.get_or_create(username="e2e_admin", defaults={"is_superuser": True, "is_staff": True, "email": "admin@e2e"})
    admin.set_password("admin"); admin.save()

    user, _ = User.objects.get_or_create(username="e2e_user", defaults={"is_superuser": False, "is_staff": False, "email": "user@e2e"})
    user.set_password("user"); user.save()

    s_central, _ = Sucursal.objects.get_or_create(nombre="Central", defaults={"direccion": "Dir 1"})
    s_norte, _ = Sucursal.objects.get_or_create(nombre="Norte", defaults={"direccion": "Dir 2"})

    # Vendedor profile uses users.Vendedor model, not on auth user
    try:
        from users.models import Vendedor
        vend, _ = Vendedor.objects.get_or_create(user=user, defaults={"is_admin": False})
        vend.sucursales_autorizadas.set([s_central.id])
    except Exception as e:
        print("[WARN] No se pudo configurar Vendedor para usuario no admin:", e)

    # Products
    p1, _ = Product.objects.get_or_create(
        producto_id="E2E-P1",
        defaults={
            "nombre": "Prod Central",
            "precio_compra": Decimal("100"),
            "precio_venta": Decimal("300"),
            "stock": 5,
            "permitir_venta_sin_stock": True,
            "sucursal": s_central,
        }
    )
    p2, _ = Product.objects.get_or_create(
        producto_id="E2E-P2",
        defaults={
            "nombre": "Prod Norte",
            "precio_compra": Decimal("100"),
            "precio_venta": Decimal("300"),
            "stock": 5,
            "permitir_venta_sin_stock": True,
            "sucursal": s_norte,
        }
    )
    p3, _ = Product.objects.get_or_create(
        producto_id="E2E-P3",
        defaults={
            "nombre": "Prod Libre",
            "precio_compra": Decimal("50"),
            "precio_venta": Decimal("200"),
            "stock": 0,
            "permitir_venta_sin_stock": True,
            "sucursal": None,
        }
    )
    p4, _ = Product.objects.get_or_create(
        producto_id="E2E-P4",
        defaults={
            "nombre": "Prod Libre NoPermitido",
            "precio_compra": Decimal("50"),
            "precio_venta": Decimal("200"),
            "stock": 3,
            "permitir_venta_sin_stock": False,
            "sucursal": None,
        }
    )

    c = Client()

    # Login as non-admin
    check("Login e2e_user", c.login(username="e2e_user", password="user"))

    # Abrir caja en Central
    r = c.get("/cashier/abrir-caja/")
    assert_status("GET abrir_caja", r, 200)
    r = c.post("/cashier/abrir-caja/", {"sucursal": str(s_central.id), "efectivo_inicial": "10000"})
    assert_status("POST abrir_caja", r, 302)

    # Dashboard y búsqueda de productos
    r = c.get("/cashier/")
    ok_dash = assert_status("GET cashier_dashboard", r, 200)
    if ok_dash:
        content = r.content.decode("utf-8", errors="ignore")
        check("Muestra sucursal activa en badge", "Sucursal:" in content and s_central.nombre in content)

    # Buscar producto libre (sin sucursal, permitido)
    r = c.get(f"/cashier/buscar-producto/?q={p3.producto_id}")
    assert_status("GET buscar_producto p3", r, 200)
    data = r.json()
    p3_item = next((x for x in data.get("productos", []) if x["id"] == p3.id), None)
    check("Producto sin sucursal permitido aparece y en_sucursal True", p3_item is not None and p3_item["en_sucursal"] is True)

    # Agregar p3 al carrito
    r = c.post("/cashier/agregar-al-carrito/", data=json.dumps({"producto_id": p3.id}), content_type="application/json")
    assert_status("POST agregar_al_carrito p3", r, 200)
    # Venta combinada p1 + p3
    payload = {
        "carrito": [
            {"producto_id": p1.id, "cantidad": 1, "nombre": p1.nombre, "precio": str(p1.precio_venta)},
            {"producto_id": p3.id, "cantidad": 1, "nombre": p3.nombre, "precio": str(p3.precio_venta)},
        ],
        "tipo_venta": "boleta",
        "forma_pago": "efectivo",
        "cliente_paga": float(p1.precio_venta + p3.precio_venta),
        "numero_transaccion": "",
        "banco": "",
    }
    r = c.post("/cashier/", data=json.dumps(payload), content_type="application/json")
    ok_sale = assert_status("POST confirmar venta p1+p3", r, 200)
    venta_id = None
    if ok_sale:
        resp = r.json()
        venta_id = int(resp.get("reporte_url", "/cashier/reporte/0/").rstrip("/").split("/")[-1])

    # Ver reporte de venta y que tenga volver correcto
    if venta_id:
        r = c.get(f"/cashier/reporte/{venta_id}/")
        ok = assert_status("GET reporte_venta caja", r, 200)
        if ok:
            html = r.content.decode("utf-8", errors="ignore")
            check(
                "Botón Volver apunta al destino correcto",
                ("/reports/sales/history/" in html or "Volver al Historial de Ventas" in html) # admin
                or ("/cashier/" in html or "Volver al Cajero" in html) # no-admin
            )

    # Cerrar caja y ver detalle (sin enlace de 'Ver versión de reporte')
    r = c.post("/cashier/cerrar_caja/", data=json.dumps({}), content_type="application/json")
    ok_close = assert_status("POST cerrar_caja", r, 200)
    if ok_close:
        detalle_url = r.json().get("detalle_url")
        r = c.get(detalle_url)
        ok = assert_status("GET detalle_caja", r, 200)
        if ok:
            html = r.content.decode("utf-8", errors="ignore")
            check("Detalle de caja NO muestra 'Ver versión de reporte'", "Ver versión de reporte" not in html)

    # Gestión de productos: crear producto
    # GET form
    r = c.get("/products/create/")
    assert_status("GET create_product", r, 200)
    # POST crear
    new_sku = f"E2E-NEW-{int(time.time())}"
    post_data = {
        'nombre': 'Nuevo Prod',
        'descripcion': 'desc',
        'producto_id': new_sku,
        'codigo_alternativo': 'ALT1',
    # proveedor eliminado del modelo
        'fecha_ingreso_producto': '2025-01-01',
        'precio_compra': '100',
        'precio_venta': '250',
        'cantidad': '0',
        'stock': '10',
        'codigo_barras': '123456789',
        'permitir_venta_sin_stock': 'on',
        'sucursal': str(s_central.id),
    }
    r = c.post("/products/create/", post_data, follow=False)
    assert_status("POST create_product", r, 302)
    check("Producto creado existe", Product.objects.filter(producto_id=new_sku).exists())

    # Bulk assign (reasignar a Norte y setear stock)
    new_ids = [str(Product.objects.get(producto_id=new_sku).id)]
    r = c.get("/products/bulk-assign/")
    assert_status("GET bulk_assign", r, 200)
    r = c.post("/products/bulk-assign/", {"products": new_ids, "sucursal": str(s_norte.id), "cantidad": "7"})
    assert_status("POST bulk_assign", r, 302)
    prod_new = Product.objects.get(producto_id='E2E-NEW-1')
    check("Bulk assign actualiza sucursal", prod_new.sucursal_id == s_norte.id)
    check("Bulk assign actualiza stock", prod_new.stock == 7)

    # Transferir stock p1 Central -> Norte
    r = c.get("/products/transfer/")
    assert_status("GET transfer_stock", r, 200)
    r = c.post("/products/transfer/", {
        'producto_id': str(p1.id),
        'sucursal_origen': str(s_central.id),
        'sucursal_destino': str(s_norte.id),
        'cantidad': '2'
    })
    assert_status("POST transfer_stock", r, 302)
    check("Transferencia registrada", TransferenciaStock.objects.filter(producto=p1, origen=s_central, destino=s_norte).exists())

    # Ajuste de stock p1 en Central (-1)
    r = c.post("/products/stock/adjust/", {
        'producto_id': str(p1.id),
        'sucursal_id': str(s_central.id),
        'delta': '-1',
        'motivo': 'e2e ajuste'
    })
    ok = assert_status("POST ajustar_stock", r, 200)
    if ok:
        j = r.json()
        check("Ajuste responde success", j.get('success') is True)

    # Historiales de transferencia y ajustes
    r = c.get("/products/transfer/history/")
    assert_status("GET transfer_history", r, 200)
    r = c.get("/products/stock/adjust/history/")
    assert_status("GET adjust_history", r, 200)

    # Productos por sucursal (Central)
    # Esta vista es solo para admin, cambiamos a admin y probamos
    c.logout()
    check("Login e2e_admin", c.login(username="e2e_admin", password="admin"))
    r = c.get(f"/sucursales/{s_central.id}/productos/")
    assert_status("GET sucursal_products (admin)", r, 200)

    # Historial de ventas y caja
    r = c.get("/reports/sales/history/")
    assert_status("GET reports sales_history", r, 200)
    r = c.get("/reports/cash/history/")
    assert_status("GET reports cash_history", r, 200)

    # Print endpoints (si tenemos IDs)
    venta = Venta.objects.order_by('-id').first()
    if venta:
        r = c.get(f"/cashier/print/venta/{venta.id}/")
        assert_status("GET print_venta", r, 200)
    caja = AperturaCierreCaja.objects.order_by('-id').first()
    if caja:
        r = c.get(f"/cashier/print/caja/{caja.id}/")
        assert_status("GET print_caja", r, 200)

    print(f"\nResumen: PASS={PASS}, FAIL={FAIL}")


if __name__ == "__main__":
    main()
