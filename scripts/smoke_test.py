import os
import sys
import json
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MOVOS.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from sucursales.models import Sucursal
from products.models import Product


def assert_status(label, resp, expected_status=200):
    ok = resp.status_code == expected_status
    print(f"[{'PASS' if ok else 'FAIL'}] {label} -> HTTP {resp.status_code}")
    if not ok:
        print(getattr(resp, 'content', b'')[:500])
    return ok


def main():
    User = get_user_model()
    # Create or get a superuser for testing
    user, _ = User.objects.get_or_create(username="smoke_super", defaults={
        "is_superuser": True,
        "is_staff": True,
        "email": "smoke@example.com",
    })

    # Ensure at least one sucursal
    sucursal, _ = Sucursal.objects.get_or_create(nombre="Central", defaults={
        "direccion": "Test 123",
    })

    # Create a product in that sucursal
    product, _ = Product.objects.get_or_create(
        producto_id="SKU-SMOKE-1",
        defaults={
            "nombre": "Producto Smoke",
            "precio_compra": Decimal("500"),
            "precio_venta": Decimal("1000"),
            "cantidad": 10,
            "stock": 10,
            "permitir_venta_sin_stock": True,
            "sucursal": sucursal,
        }
    )

    c = Client()
    c.force_login(user)

    # 1) GET abrir_caja page
    r = c.get("/cashier/abrir-caja/")
    assert_status("GET /cashier/abrir-caja/", r, 200)

    # 2) POST abrir_caja form (expect redirect 302)
    r = c.post("/cashier/abrir-caja/", {"sucursal": str(sucursal.id), "efectivo_inicial": "10000"})
    assert_status("POST /cashier/abrir-caja/", r, 302)

    # 3) GET cashier dashboard
    r = c.get("/cashier/")
    assert_status("GET /cashier/", r, 200)

    # 4) POST sale on cashier (efectivo)
    payload = {
        "carrito": [
            {"producto_id": product.id, "cantidad": 2, "nombre": product.nombre, "precio": str(product.precio_venta)}
        ],
        "tipo_venta": "boleta",
        "forma_pago": "efectivo",
        "cliente_paga": 2000,
        "numero_transaccion": "",
        "banco": "",
    }
    r = c.post("/cashier/", data=json.dumps(payload), content_type="application/json")
    ok = assert_status("POST /cashier/ (venta)", r, 200)
    reporte_url = None
    if ok:
        try:
            data = r.json()
            print("Respuesta venta:", data)
            reporte_url = data.get("reporte_url")
        except Exception as e:
            print("Error parseando JSON de venta:", e)

    # 5) GET reporte de venta
    if reporte_url:
        r = c.get(reporte_url)
        ok = assert_status(f"GET {reporte_url}", r, 200)
        if ok and b"Detalle de Venta" in r.content:
            print("[PASS] Contenido del reporte de venta parece correcto")
        else:
            print("[WARN] No se encontró el título esperado en el reporte de venta")

    # 6) GET advanced reports
    r = c.get("/reports/advanced/")
    ok = assert_status("GET /reports/advanced/", r, 200)
    if ok and b"Detalle de Ventas" in getattr(r, 'content', b''):
        print("[PASS] Advanced reports renderizado con sección de detalle de ventas")
    else:
        print("[INFO] Advanced reports OK (200); contenido específico no verificado")

    print("Smoke test finalizado.")


if __name__ == "__main__":
    main()
