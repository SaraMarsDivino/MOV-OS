# POS Cashier (React + Tailwind UI)

Este directorio contiene una **maqueta UI** (sin backend) para la vista de cajero estilo POS.

## Objetivo UX
- App-like: ocupa el 100% del viewport (`h-[100dvh]`) y el `body` no scrollea.
- Scroll solo en listas internas (catálogo y ticket).
- Desktop/Tablet: catálogo a la izquierda + columna derecha fija (ticket arriba, pago abajo).
- Móvil: catálogo full screen + barra inferior sticky y un drawer de checkout.

## Ejecutar
Desde `frontend/pos-cashier`:

- `npm install`
- `npm run dev`

Luego abre `http://localhost:5173`.

## Nota
Esto no toca ni reemplaza el template Django actual. Sirve como base para migrar la UI a React y luego integrar API/endpoints.
