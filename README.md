MOV-OS (Sistema POS)
=====================

Descripción
-----------
MOV-OS es un sistema POS modular construido con Django (backend) y una interfaz React/Vite para el frontend del cajero. Maneja ventas, devoluciones, notas de crédito (store credit), gestión de sucursales, productos y reportes.

Resumen rápido — comandos útiles
--------------------------------

Requisitos locales
- Python 3.12
- Node.js (v18+ / compatible con Vite)
- Docker & Docker Compose (opcional para producción/local con contenedores)

Instalación y ejecución local (sin Docker)
-----------------------------------------
1. Crear y activar un entorno virtual (Windows PowerShell):

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias Python:

```powershell
python -m pip install -r requirements.txt
```

3. Ejecutar migraciones y crear un superusuario (si procede):

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

4. (Opcional) Ejecutar servidor de desarrollo Django:

```powershell
python manage.py runserver
```

Frontend (React / Vite)
----------------------
El frontend del cajero se encuentra en `frontend/pos-cashier`.

Modo desarrollo (Vite):

```bash
cd frontend/pos-cashier
npm ci
npm run dev
```

Build (para producción / collectstatic):

```bash
cd frontend/pos-cashier
npm ci
npm run build
cd ../..   # regresar al root del proyecto
python manage.py collectstatic --noinput
```

Docker (development / local container)
--------------------------------------
El `docker-compose.yml` está configurado para construir la imagen `web` que compila el frontend y ejecuta `collectstatic` durante la build.

Para levantar los servicios (rebuild incluido):

```powershell
docker compose up -d --build web
```

URLs importantes
- Dashboard de reportes (requiere usuario admin): http://localhost:8000/reports/dashboard/
- Historial de Devoluciones (nuevo): http://localhost:8000/reports/returns/history/
- Historial de Ventas (cajero): http://localhost:8000/cashier/historial-ventas/
- Comprobante de devolución (ejemplo): http://localhost:8000/cashier/devolucion/reporte/<devolucion_id>/

Pruebas (tests)
---------------
Ejecuta la suite de Django tests:

```powershell
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py check
python manage.py test -v 2
```

Notas de desarrollo importantes
------------------------------
- El nuevo "Historial de Devoluciones" (vista y plantilla) fue añadido en `reports` y está integrado en el dashboard React para mantener la estética.
- Al abrir un comprobante de devolución desde el listado de `reports`, la vista preserva el parámetro `next` para que el botón "Ir al historial" vuelva al listado correcto (reports o cajero), según el flujo de entrada.
- Rutas y ficheros clave:
  - Backend: `reports/views.py`, `cashier/views.py` (lógica de devoluciones + `reporte_devolucion`), `cashier/models.py` (modelos `Devolucion` y `DevolucionDetalle`).
  - Templates: `reports/templates/reports/returns_history.html`, `cashier/templates/cashier/reporte_devolucion.html`.
  - Frontend (React): `frontend/pos-cashier/src/pages/ReportsDashboardPage.tsx` (tarjetas del dashboard).

Sugerencias para despliegue en Docker
------------------------------------
- El servicio `web` reconstruye el frontend y ejecuta `collectstatic`. Si actualizas el repo remoto y quieres desplegar un contenedor nuevo desde esa rama principal, el flujo sería:

```powershell
# en el host/servidor
git pull origin main
docker compose up -d --build web
```

Contacto/soporte
----------------
Si encuentras tests fallando o problemas en UI, crea un issue con: pasos para reproducir, URL afectada y logs relevantes (`docker compose logs web` o salida de `python manage.py test`).

---
Archivo generado/actualizado automáticamente por el equipo al añadir el historial de devoluciones y ajustes de navegación.
