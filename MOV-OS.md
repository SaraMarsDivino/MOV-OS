# MOV-OS — Guía de contexto para Claude

Repositorio: `D:\PROYECTOS PROGRAMADOR\MOV-OS-main`  
Stack: Django 5 · Python 3.12 · React 18 · TypeScript · Tailwind CSS · Bootstrap 5 · PostgreSQL (prod) / SQLite (dev)  
Versión actual: **0.8**

---

## Comandos rápidos

```bash
# Backend
python manage.py runserver          # dev con SQLite
python manage.py test               # todos los tests
python manage.py makemigrations && python manage.py migrate

# Frontend (frontend/pos-cashier/)
npm run build      # → static/pos-cashier/  (siempre hacer antes de push)
npm run dev        # Vite :5173, proxea a Django :8000
npm run typecheck

# Docker (producción)
docker compose up
# Después de cualquier cambio:
git pull && docker compose restart web
```

---

## Arquitectura

### Apps Django

| App | Propósito |
|---|---|
| `auth_app` | Login/logout, modelo `User` (extiende `AbstractUser`) con flags `is_admin`, `is_employee`, `can_add_products`, `can_edit_products`, `can_view_analytics` |
| `users` | Perfil `Vendedor` (one-to-one con User), middleware AutoLogout / CanonicalHost / RedirectOn404, gestión de usuarios (admin UI) |
| `sucursales` | Modelo `Sucursal` (nombre, dirección, teléfono, umbral bajo stock) |
| `products` | `Product`, `StockSucursal`, `TransferenciaStock`, `AjusteStock` |
| `cashier` | POS core: `Venta`, `VentaDetalle`, `VentaPago`, `AperturaCierreCaja`, `Devolucion`, `NotaCredito` |
| `reports` | Analítica de ventas, `Conversation`/`Message` para asistente IA |

### Frontend — dos bundles Vite

- `src/main.tsx` → POS cajero (`/cashier/`)
- `src/movos-pages.tsx` → páginas admin/gestión, enrutadas via `window.__MOVOS_REACT_PAGE__`

**Patrón de routing React:**  
Django templates inyectan `window.__MOVOS_REACT_PAGE__ = 'nombre-pagina'` y montan `#root`. `AppRouter` en `movos-pages.tsx` elige el componente.

**Contexto Django → React:**  
`window.__MOVOS_REACT_CONTEXT__ = { products: [...], sucursales: [...], ... }` — datos que Django pasa al template y React lee.

---

## Reglas críticas (NO olvidar)

### URLs y namespaces
- App `cashier` → **SIN namespace**. Usar `{% url 'reporte_venta' v.id %}`, NOT `cashier:reporte_venta`
- App `reports` → namespace `reports`. Usar `{% url 'reports:historial_caja' %}`
- App `sucursales` → namespace `sucursales`. Usar `{% url 'sucursales:sucursal_list' %}`

### Templates React vs. Bootstrap
Cualquier template que monte React **debe** override los bloques del wrapper para evitar la caja blanca de Bootstrap:
```html
{% block page_wrapper_start %}{% endblock %}
{% block page_wrapper_end %}{% endblock %}
```
Sin esto, el contenido React queda dentro de `.card.page-card.p-4`.

### CSS — problema de la hoja global
`static/css/styles.css` tiene una regla global destructiva:
```css
h1,h2,h3,h4,h5 { color: var(--accent-cyan); text-transform: uppercase; }
```
Esto tiñe de cyan claro TODOS los h1-h5. Para páginas específicas, siempre sobreescribir con `!important` en el bloque `{% block extra_styles %}`:
```css
.mi-titulo { color: #000 !important; text-transform: none !important; font-family: 'Roboto', sans-serif !important; }
```

### UI theme en páginas Django (no-React)
- Fondo oscuro global: `pos_design_system.css` — usar `body { background: #e2e8f0; color: #0f172a; }` en extra_styles para páginas claras
- Tarjetas claras: clases `.card-header-dark` + `.info-card` (definidas inline en los templates)
- Para páginas tipo "admin shell": incluir `theme_react_shell.css` en `{% block site_theme_styles %}`

### Dinero / CLP
Todos los montos son pesos chilenos (enteros, sin centavos).
- `parse_clp_decimal(v)` — parsea "100.000" / "100,000" → Decimal
- `to_clp_pesos(v)` — redondea a entero Decimal
- `parse_clp_pesos(v)` — parse + redondeo en uno
- Filtro `|clp` en templates (de `cashier/templatetags/money_filters.py`)

### Stock — modelo de dos niveles
- **Preferido**: `StockSucursal` (por producto × sucursal)
- **Fallback legacy**: `Product.stock` (cuando no existe StockSucursal y `product.sucursal == current_sucursal`)
- **SIEMPRE** usar: `product.stock_en(sucursal)`, `product.decrementar_stock_en()`, `product.incrementar_stock_en()`
- **NUNCA** manipular campos raw directamente
- `Product.stock_minimo` — umbral de alerta por producto (default 5). El endpoint `/products/api/low-stock/` devuelve todos los `StockSucursal` donde `cantidad < stock_minimo`. Se muestra en el Admin Dashboard.

### Ajuste de stock (ficha de producto)
- El formulario inline en `product_form.html` usa `name="nueva_cantidad"` (valor absoluto, no delta).
- El view detecta `'_stock_adjust' in request.POST`, calcula `delta = nueva_cantidad - stock_actual` y lo registra en `AjusteStock`.
- Redirige a `edit_product + ?stock_ok=1#stock-section` tras guardar.

### Permisos de productos
```python
def _can_manage_products(user):
    if not getattr(user, 'is_authenticated', False): return False
    if user.is_staff or user.is_superuser: return True
    return bool(getattr(user, 'can_add_products', False)) or bool(getattr(user, 'can_edit_products', False))
```
Los cajeros con `sucursales_autorizadas` NO tienen acceso a productos (antes lo tenían — bug corregido en v0.7).

### Pagos mixtos
Una `Venta` puede tener múltiples métodos de pago. `VentaPago` guarda cada tramo. `Venta.forma_pago` se pone `"mixto"` cuando hay más de un tramo. `Venta.nota_credito_usada` / `Venta.monto_nota_credito` para crédito de tienda.

---

## Módulos y funcionalidades actuales

### POS / Cajero (`/cashier/`)
- Búsqueda de productos por nombre, código 1, código 2, código de barras
- Carrito de compras con ajuste de cantidad
- Métodos de pago: efectivo, débito, crédito, transferencia, nota de crédito (NC), mixto
- Cálculo automático de vuelto
- Validación de nota de crédito por código
- Generar e imprimir boleta electrónica / factura electrónica
- Apertura y cierre de caja con efectivo inicial/final
- Detalle de caja con 4 cuadrantes: información, ventas por método, devoluciones, cuadratura
- Impresión cierre de caja formato 80mm térmico

### Devoluciones
- Devolución total o parcial de productos
- Reembolso en efectivo o emisión de nota de crédito
- Items devueltos a stock o marcados como merma
- Historial de devoluciones con reporte
- **Admin sin caja**: usuarios `is_staff`/`is_superuser` pueden procesar devoluciones sin caja abierta. La sucursal se toma de la venta original. Las métricas de caja no se actualizan (no hay caja). El stock sí se ajusta normalmente.

### Inventario / Productos (`/products/`)
- CRUD de productos con precio compra/venta, IVA automático (19%)
- Stock por sucursal (`StockSucursal`)
- Transferencia de stock entre sucursales (UI React 2 columnas, stock en tiempo real, historial)
- Ajuste manual de stock por valor absoluto (registra delta en `AjusteStock`)
- `stock_minimo` por producto: define el umbral de alerta de stock bajo
- Lista de productos: columna Stock con estado (Normal/Bajo/Sin stock) + tooltip por sucursal al hover; filtro "Solo activos" persistente en `localStorage`; ordenamiento por nombre y código con indicadores ↑↓
- Importación masiva desde Excel (template descargable)
- Exportación a Excel
- Activar/desactivar productos
- Configurar venta sin stock por producto

### Sucursales (`/sucursales/`)
- CRUD de sucursales (nombre, dirección, teléfono, umbral bajo stock)
- Asignación de productos a sucursales
- Umbral de alerta de bajo stock configurable por sucursal

### Usuarios (`/users/`)
- CRUD de usuarios con roles: superadmin, staff, empleado
- Permisos granulares: `can_add_products`, `can_edit_products`, `can_view_analytics`
- Asignación de sucursales autorizadas (cajeros)
- Activar/desactivar usuarios
- Dashboard admin con acceso a todos los módulos

### Reportes (`/reports/`)
- Dashboard principal de reportes
- Historial de ventas con detalle por transacción
- Historial de cajas (apertura/cierre)
- Historial de devoluciones
- Reportes avanzados con filtros por fecha, sucursal, producto
- Exportación: CSV, PDF, DOCX

### Análisis de Mercado (`/reports/market/`)
BI completo con los siguientes paneles:
- KPIs generales (ventas totales, margen, ticket promedio, unidades)
- Mapa de calor (ventas por hora/día de semana)
- Comparativa de sucursales
- Tendencia mensual (MoM)
- Top productos por volumen y por margen
- Productos zombie (baja rotación)
- Análisis Pareto 80/20
- Fin de semana vs. día de semana
- Análisis de métodos de pago
- Desempeño por cajero
- Horas pico / densidad de ventas
- Volatilidad de demanda
- Elasticidad de precio
- Análisis de canasta (productos que se compran juntos)

---

## Archivos clave

### Backend
| Archivo | Contenido importante |
|---|---|
| `MOVOS/settings.py` | Config principal |
| `MOVOS/local_settings.py` | Override local (git-ignored), DEBUG, DB, VITE_DEV_SERVER_URL |
| `MOVOS/money.py` | Utilidades CLP |
| `MOVOS/react_ui.py` | `react_ui_enabled()` — siempre True |
| `cashier/views.py` | Vista `detalle_caja`, `cerrar_caja`, POS endpoints |
| `cashier/templatetags/money_filters.py` | Filtro `|clp` |
| `products/views.py` | `_can_manage_products()`, transfer stock, ajuste stock, `api_low_stock` |
| `reports/views.py` | Todos los endpoints de analítica |

### Frontend
| Archivo | Contenido |
|---|---|
| `frontend/pos-cashier/src/movos-pages.tsx` | Router principal de páginas admin (`window.__MOVOS_REACT_PAGE__`) |
| `frontend/pos-cashier/src/main.tsx` | Entry point POS cajero |
| `frontend/pos-cashier/src/pages/index.ts` | Re-exports de todas las páginas |
| `frontend/pos-cashier/src/components/CatalogPanel.tsx` | Panel búsqueda productos POS |
| `frontend/pos-cashier/src/components/CartPanel.tsx` | Carrito de compras |
| `frontend/pos-cashier/src/components/PaymentPanel.tsx` | Panel de pago (simple y mixto) |
| `frontend/pos-cashier/src/pages/TransferStockPage.tsx` | Transferencia de stock entre sucursales |
| `frontend/pos-cashier/src/pages/MarketAnalysisPage.tsx` | Dashboard BI |

### CSS
| Archivo | Uso |
|---|---|
| `static/css/pos_design_system.css` | Global — cargado en TODAS las páginas via base.html. Dark theme base + micro-interactions. CUIDADO: regla global `h1` cyan en styles.css |
| `static/css/theme_react_shell.css` | Admin shell light theme — incluir en `{% block site_theme_styles %}` en páginas tipo admin |
| `static/css/styles.css` | Legacy global — tiene regla destructiva `h1-h5 { color: cyan }`. No modificar sin cuidado |
| `frontend/pos-cashier/src/index.css` | Tailwind base para React |

### Templates
| Archivo | Propósito |
|---|---|
| `templates/base.html` | Layout base — navbar, footer, toasts, CSRF meta |
| `cashier/templates/cashier/detalle_caja.html` | Detalle de sesión de caja (4 cuadrantes) |
| `cashier/templates/cashier/print_caja.html` | Impresión cierre caja 80mm |
| `cashier/templates/cashier/print_venta.html` | Impresión ticket venta 80mm |
| `products/templates/products/react_transfer_stock.html` | Shell React para transferencia stock |
| `auth_app/templates/auth_app/login.html` | Pantalla de login con modal notas de parche |

---

## Patrones de código frecuentes

### Nuevo endpoint JSON (Django)
```python
@login_required
@user_passes_test(_can_manage_products)
def mi_endpoint(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        # ...
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)
```

### Nueva página React en movos-pages.tsx
```tsx
// 1. En pages/index.ts: export { default as MiPagina } from './MiPagina';
// 2. En movos-pages.tsx:
import { MiPagina } from './pages';
// En AppRouter:
if (page === 'mi-pagina') return <MiPagina />;
```

### Template shell para página React
```html
{% extends 'base.html' %}
{% block site_theme_styles %}
<link rel="stylesheet" href="/static/css/theme_react_shell.css">
{% endblock %}
{% block page_wrapper_start %}{% endblock %}
{% block page_wrapper_end %}{% endblock %}
{% block content %}
<div id="root"></div>
<script>
  window.__MOVOS_REACT_PAGE__ = 'mi-pagina';
  window.__MOVOS_REACT_CONTEXT__ = {{ react_context|safe }};
</script>
{% include 'pos_cashier_bundle.html' %}
{% endblock %}
```

### Override de color h1 (siempre necesario en páginas claras)
```html
{% block extra_styles %}
<style>
  body { background: #e2e8f0; color: #0f172a; }
  .mi-titulo { color: #000 !important; text-transform: none !important; font-family: 'Roboto', sans-serif !important; }
</style>
{% endblock %}
```

---

## Flujo de despliegue

### Desde la máquina local (Windows)
```
1. Hacer cambios (backend .py o .html)
2. Si cambios en frontend/pos-cashier/src/:
   cd frontend/pos-cashier && npm run build
3. git add -p (selectivo, evitar .env o secrets)
4. git commit -m "mensaje"
5. git push
```

### En el servidor OrangePi (via SSH)
Conectarse desde una terminal normal de Windows (NO desde el ! de Claude Code — no soporta TTY interactivo):
```bash
ssh orangepi@192.168.1.22
# contraseña requerida (no se puede pasar por stdin sin sshpass)
```

Una vez dentro:
```bash
cd MOV-OS
```

**Si el repo divergió** (error "necesita especificar cómo reconciliar"):
```bash
git fetch origin && git reset --hard origin/main
```

**Si solo hay cambios de templates/CSS/Python (sin frontend nuevo):**
```bash
git pull
docker compose up --build -d
docker compose exec web python manage.py collectstatic --noinput
```

**Si hay cambios de frontend (src/ de React):**
El build ya viene incluido en el repo (`static/pos-cashier/` se commitea).
Los mismos 3 comandos de arriba aplican.

**Si hay migraciones nuevas** (hay archivos `*/migrations/*.py` nuevos en el pull):
```bash
docker compose exec web python manage.py migrate
```

### Por qué `restart web` solo NO alcanza
- El volumen `static_volume:/app/staticfiles` guarda los estáticos separado de la imagen.
- `restart` no reconstruye la imagen → el código Python/templates queda desactualizado.
- `up --build -d` reconstruye la imagen, pero el volumen sigue teniendo archivos viejos.
- `collectstatic --noinput` dentro del contenedor actualiza el volumen con los nuevos archivos.
- La base de datos está en el volumen `pgdata` — **ninguno de estos comandos la toca**.

### Verificar que actualizó
Hacer hard refresh en el navegador: **Ctrl + Shift + R**

---

## Historial de versiones

### v0.8 (Mayo 2026)
- Stock mínimo por producto: campo `stock_minimo` + alerta en Admin Dashboard (panel ámbar con lista de productos críticos)
- Lista de productos: columna Stock con estado semántico (Normal/Bajo/Sin stock) + tooltip hover por sucursal; filtro "Solo activos" persistente; ordenamiento con indicadores ↑↓; esquinas redondeadas corregidas
- Ajuste de stock: campo cambiado a valor absoluto (no delta) + confirmación antes de guardar
- Dashboard de reportes: rediseñado en cuadrantes 2×2 compactos
- Vista reporte de venta: rediseñada con cuadrantes y CSS consistente con el sistema
- Devoluciones: admins pueden procesar sin caja abierta (sucursal tomada de la venta)
- Formulario devolución: rediseñado con CSS consistente + banner de aviso para modo admin

### v0.7 (Mayo 2026)
- Transferencia de stock: nueva UI React (2 columnas, stock en tiempo real, historial)
- Seguridad productos: menú y vistas solo para usuarios con permisos explícitos
- Detalle de caja: rediseño con 4 cuadrantes, tipografía Roboto negra
- Impresión cierre caja: formato térmico 80mm (igual que tickets de venta)
- Análisis de mercado: corrección del botón Volver (era 404)
- Micro-interacciones system-wide: hover, transiciones, efecto press en toda la UI

### v0.6 y anteriores
- POS cajero React con carrito, pagos mixtos, nota de crédito
- Devoluciones con reembolso a efectivo o NC
- Análisis de mercado con múltiples paneles BI
- Gestión multi-sucursal completa
- Importación masiva de productos desde Excel
- Sistema de impresión térmica 80mm

---

## Deuda técnica conocida

- `styles.css` tiene CSS malformado (nesting no estándar) y la regla global `h1-h5 { color: cyan }` que rompe cualquier página clara — pendiente refactor
- Modelo `Vendedor` en `users` es legacy y coexiste con el `User` extendido de `auth_app` — hay lógica duplicada
- `pos_design_system.css` fuerza fondo oscuro globalmente en `body`, lo que requiere override explícito en páginas claras
- Las vistas del `cashier` app no tienen namespace — NO agregar `app_name` sin revisar todas las referencias de URL
