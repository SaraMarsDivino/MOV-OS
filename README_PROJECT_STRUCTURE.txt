Sistema POS - Estructura y funcionamiento del proyecto
=====================================================

Resumen general
---------------
Este proyecto es una aplicación POS construida sobre Django para el backend y un frontend React/Vite para la gestión avanzada de productos. Está empaquetada con Docker Compose para ejecución con contenedores.

Arquitectura principal
----------------------
- `manage.py`: punto de entrada Django.
- `Dockerfile` / `docker-compose.yml`: definición de contenedores web y base de datos.
- `requirements.txt`: dependencias Python.
- `frontend/pos-cashier/`: aplicación React/Vite para el panel de productos y estilo tipo cajero.
- `products/`: app Django que gestiona productos, carga Excel, edición, stock y exportación.
- `sucursales/`: app Django que gestiona sucursales.
- `reports/`: app Django para reportes y análisis.
- `users/`: app Django para gestión de usuarios (roles y permisos).

Modelo de datos clave
----------------------
- `products.models.Product`: producto con campos como `nombre`, `producto_id` (`CODIGO 1`), `codigo_alternativo` (`CODIGO 2`), `codigo_barras`, precios, stock, `sucursal`, `activo`.
- `products.models.StockSucursal`: inventario asociado a una sucursal.
- `products.models.AjusteStock`: historial de ajuste de stock.
- `products.models.TransferenciaStock`: historial de transferencias entre sucursales.
- `sucursales.models.Sucursal`: datos de sucursales.

Flujo de carga de Excel
-----------------------
- El endpoint Django es `products.views.upload_products`.
- El archivo Excel se carga desde `/products/upload/`.
- El importador normaliza encabezados:
  - `NOMBRE`, `CODIGO 1`, `CODIGO 2 (opcional)`, `CODIGO DE BARRAS (opcional)`, `PRECIO DE COMPRA`, `PRECIO DE VENTA`, etc.
  - Quita notas entre paréntesis y parsea columnas en mayúscula.
- `CODIGO 1` es tratado como identificador único.
- Si ya existe un producto con ese `producto_id`, el sistema lo actualiza en lugar de crear uno nuevo.
- Los valores no vacíos del Excel actualizan los campos existentes, evitando sobrescribir con cadenas vacías.
- El importador guarda un informe de resultados en sesión (`upload_products_report`) para mostrar resumen posterior.

UI de gestión de productos
--------------------------
- Página principal de gestión: `products/react_product_management.html` en modo React.
- React page: `frontend/pos-cashier/src/pages/ProductsManagementPage.tsx`.
- Componentes nuevos:
  - `UploadReportBanner.tsx`: muestra resumen de la última carga Excel desde `window.__UPLOAD_REPORT__`.
  - `AssignStockModal.tsx`: modal para asignar cantidades a una sucursal en bloque.
- La tabla de productos es sortable en columnas clave (`nombre`, `codigo1`, `stock`).
- La vista de edición de producto usa `products/templates/products/product_form.html` y muestra `codigo_alternativo` y `codigo_barras`.

API y asignación masiva de stock
--------------------------------
- Endpoint con JSON: `POST /products/bulk-assign/`.
- Se envía `{ sucursal_id, items: [{ codigo, cantidad }, ...] }`.
- Devuelve resumen con `assigned_count` y `failures`.
- Esto usa `Product.incrementar_stock_en` y crea/actualiza `StockSucursal`.

Estilos y temas
----------------
- Estilos globales en `static/css/` para cada módulo.
- Se aplicaron correcciones de contraste de texto, placeholders, selects y botones.
- Se creó `frontend/pos-cashier/src/styles/cashier_shared.css` para compartir la estética de caja.

Despliegue y ejecución
----------------------
Modo local (Python):
1. Crear entorno virtual.
2. `python -m pip install -r requirements.txt`
3. `python manage.py makemigrations && python manage.py migrate`
4. `python manage.py collectstatic --noinput`
5. `python manage.py runserver`

Modo Docker:
1. `docker-compose build`
2. `docker-compose up -d`

Uso principal
--------------
- Subir Excel: `http://<host>/products/upload/`
- Gestionar productos: `http://<host>/products/management/`
- Editar producto: `http://<host>/products/edit/<id>/`
- Descargar plantilla: `http://<host>/products/template/`
- Exportar productos: `http://<host>/products/exportar/excel/`

Notas importantes actuales
--------------------------
- Se solucionó el problema de que `CODIGO 2` y `CODIGO DE BARRAS` no se guardaban correctamente.
- El Excel ahora usa `CODIGO 1` como clave primaria lógica y actualiza el producto existente.
- La vista de edición está preparada para mostrar `codigo_alternativo` y `codigo_barras`.

Limitación actual
-----------------
Desde este entorno no pude ejecutar el commit Git directamente porque solo hay acceso a las herramientas de edición disponibles en el editor, no a comandos arbitrarios de shell.

Archivo creado:
- `README_PROJECT_STRUCTURE.txt`

