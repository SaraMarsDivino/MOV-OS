# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Django backend
```bash
# Local dev (SQLite by default, create MOVOS/local_settings.py to override)
python manage.py runserver

# Run all tests
python manage.py test

# Run tests for a single app
python manage.py test cashier
python manage.py test cashier.tests_concurrency

# Migrations
python manage.py makemigrations
python manage.py migrate
```

### React frontend (`frontend/pos-cashier/`)
```bash
npm run dev        # Vite dev server at :5173 (proxies to Django at :8000)
npm run build      # Production build → static/pos-cashier/
npm run typecheck  # TypeScript type-check only
```

### Docker (production-like)
```bash
docker compose up          # Postgres + gunicorn, port 8000
docker compose -f docker-compose.local.yml up   # local variant
```

## Architecture

### Stack overview
Django 5 (Python 3.12) backend with a React 18 + TypeScript + Tailwind CSS frontend. Django serves all routes; the React UI is embedded in Django templates. No DRF ViewSets — all API endpoints are plain Django views returning JSON.

### Django apps
| App | Purpose |
|---|---|
| `auth_app` | Custom `User` model extending `AbstractUser` with `is_admin` / `is_employee` flags |
| `users` | `Vendedor` profile (one-to-one with User), middleware (AutoLogout, CanonicalHost, RedirectOn404) |
| `sucursales` | `Sucursal` (branch) model — referenced by almost every other app |
| `products` | `Product`, `StockSucursal` (per-branch inventory), `TransferenciaStock`, `AjusteStock` |
| `cashier` | POS core: `Venta`, `VentaDetalle`, `VentaPago`, `AperturaCierreCaja`, `Devolucion`, `NotaCredito` |
| `reports` | Sales analytics views, plus `Conversation`/`Message` for the AI assistant feature |

### Frontend entry points
Vite builds two bundles, both output to `static/pos-cashier/`:
- `src/main.tsx` — full POS cashier (`/cashier/`)
- `src/movos-pages.tsx` — admin/management pages, routed via `window.__MOVOS_REACT_PAGE__` injected by Django templates

Django templates set `window.__MOVOS_REACT_PAGE__` to a string key (e.g. `"admin-dashboard"`) and mount `#root`; `AppRouter` in `movos-pages.tsx` picks the right page component.

### React UI toggle
`MOVOS/react_ui.py::react_ui_enabled()` always returns `True`; legacy Django-template views are effectively disabled. In development with `DEBUG=True`, if the Vite dev server is detected on `:5173`, templates load assets from there. Otherwise they use the built `static/pos-cashier/` files.

### Cart is server-side
The POS cart lives in the Django session (`request.session['carrito']`). The React frontend calls JSON endpoints (`/cashier/agregar-al-carrito/`, `/cashier/ajustar-cantidad/`, etc.) and re-renders from the returned cart array — there is no client-side cart store.

### Stock model (two-tier)
- `StockSucursal` (preferred): per-product per-branch quantity.
- `Product.stock` (legacy fallback): used when no `StockSucursal` row exists and `product.sucursal == current_sucursal`.
- Use `product.stock_en(sucursal)`, `product.decrementar_stock_en()`, `product.incrementar_stock_en()` — never manipulate raw fields directly.

### Money / CLP
All monetary amounts are Chilean Pesos (integer, no cents). Use `MOVOS/money.py` utilities:
- `parse_clp_decimal(value)` — parses "100.000" / "100,000" strings to `Decimal`
- `to_clp_pesos(value)` — rounds to integer `Decimal`
- `parse_clp_pesos(value)` — parse + round in one call
- The `|clp` template filter (from `cashier/templatetags/money_filters.py`) is registered globally.

### Mixed payments
A `Venta` can have multiple payment methods. `VentaPago` rows hold each split; the legacy `Venta.forma_pago` is set to `"mixto"` when there are multiple rows. `Venta.nota_credito_usada` / `Venta.monto_nota_credito` hold store-credit (nota de crédito) usage.

### User authorization flow
1. Login → `auth_app` or `users.views.custom_login`
2. Admin users (`is_admin=True`) → `/users/admin-dashboard/`; employees → `/cashier/`
3. Branch access: `Vendedor.sucursales_autorizadas` (M2M to `Sucursal`) controls which branches a user can open caja at. Superusers see all branches.

### Local settings
Create `MOVOS/local_settings.py` (git-ignored) to override anything for local dev, e.g.:
```python
DEBUG = True
DATABASES = { 'default': { 'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3' } }
VITE_DEV_SERVER_URL = 'http://localhost:5173'
```
