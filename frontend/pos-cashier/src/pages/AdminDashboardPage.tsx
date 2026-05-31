import { useEffect, useState } from 'react';
import { apiGet } from '../lib/api';

type Card = { title: string; desc: string; href: string };

const cards: Card[] = [
  { title: 'Gestión de Sucursales', desc: 'Administrar sucursales y productos por sede.', href: '/sucursales/' },
  { title: 'Gestión de Productos', desc: 'Administrar inventario, agregar y editar productos.', href: '/products/management/' },
  { title: 'Gestión de Usuarios', desc: 'Administrar permisos y roles de usuarios.', href: '/users/management/' },
  { title: 'Gestión de Ventas', desc: 'Ver y generar reportes de ventas.', href: '/reports/dashboard/' },
  { title: 'Modo Cajero', desc: 'Entrar al modo cajero (POS).', href: '/cashier/' },
];

type LowStockAlert = {
  producto_id: number;
  nombre: string;
  sucursal: string;
  cantidad: number;
  stock_minimo: number;
  edit_url: string;
};

function getReactContext() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).__MOVOS_REACT_CONTEXT__ || {};
}

export default function AdminDashboardPage() {
  const ctx = getReactContext();
  const user = ctx.user || {};
  const isStaff = Boolean(user.is_staff || user.is_superuser);
  const canManageProducts = Boolean(user.is_superuser || user.is_staff || user.can_add_products || user.can_edit_products);
  const canViewReports = Boolean(user.is_superuser || user.is_staff || user.can_view_analytics);

  const [alerts, setAlerts] = useState<LowStockAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);

  useEffect(() => {
    if (!canManageProducts) return;
    setAlertsLoading(true);
    apiGet<{ alerts: LowStockAlert[] }>('/products/api/low-stock/')
      .then((d) => setAlerts(d.alerts || []))
      .catch(() => setAlerts([]))
      .finally(() => setAlertsLoading(false));
  }, []);

  const visibleCards = cards.filter((c) => {
    if (c.href === '/sucursales/') return isStaff;
    if (c.href === '/users/management/') return isStaff;
    if (c.href === '/products/management/') return canManageProducts;
    if (c.href === '/reports/dashboard/') return canViewReports;
    return true;
  });

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl space-y-4">

        {/* Header */}
        <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h2 className="m-0 text-lg font-black text-slate-900">Panel de Administración</h2>
          <div className="mt-1 text-sm text-slate-900/80">Accesos rápidos.</div>
        </div>

        {/* Alerta stock bajo */}
        {canManageProducts && (
          <div className="rounded-2xl border-2 border-black overflow-hidden shadow-lg">
            {/* Header strip */}
            <div className="flex items-center justify-between bg-amber-500 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">⚠</span>
                <span className="text-sm font-black text-amber-950 uppercase tracking-wide">
                  Alertas de stock bajo
                </span>
              </div>
              {!alertsLoading && (
                <span className="rounded-full bg-amber-900/20 px-2.5 py-0.5 text-xs font-black text-amber-950">
                  {alerts.length} {alerts.length === 1 ? 'producto' : 'productos'}
                </span>
              )}
            </div>

            {alertsLoading ? (
              <div className="bg-white px-4 py-4 text-sm text-slate-500">Cargando alertas…</div>
            ) : alerts.length === 0 ? (
              <div className="bg-white px-4 py-4 flex items-center gap-2 text-sm text-emerald-700 font-semibold">
                <span>✓</span> Todo el stock está sobre el mínimo definido.
              </div>
            ) : (
              <div className="bg-white divide-y divide-slate-100">
                {alerts.map((a, i) => (
                  <a
                    key={i}
                    href={a.edit_url}
                    className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-amber-50 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-slate-900 truncate">{a.nombre}</p>
                      <p className="text-xs text-slate-500">{a.sucursal}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-slate-500">
                        Mín. {a.stock_minimo}
                      </span>
                      <span className={`rounded-lg px-2.5 py-1 text-xs font-black tabular-nums ${
                        a.cantidad === 0
                          ? 'bg-red-100 text-red-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}>
                        {a.cantidad} u.
                      </span>
                      <span className="text-xs text-slate-400">Editar →</span>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Cards de módulos */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visibleCards.map((c) => (
            <a
              key={c.href}
              href={c.href}
              className="block rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg hover:bg-slate-200"
            >
              <div className="text-base font-black text-slate-900">{c.title}</div>
              <div className="mt-1 text-sm text-slate-900/80">{c.desc}</div>
              <div className="mt-3 inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-bold text-slate-900 shadow">
                Ir
              </div>
            </a>
          ))}
        </div>

      </div>
    </div>
  );
}
