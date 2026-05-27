type Card = { title: string; desc: string; href: string };

const cards: Card[] = [
  { title: 'Gestión de Sucursales', desc: 'Administrar sucursales y productos por sede.', href: '/sucursales/' },
  { title: 'Gestión de Productos', desc: 'Administrar inventario, agregar y editar productos.', href: '/products/management/' },
  { title: 'Gestión de Usuarios', desc: 'Administrar permisos y roles de usuarios.', href: '/users/management/' },
  { title: 'Gestión de Ventas', desc: 'Ver y generar reportes de ventas.', href: '/reports/dashboard/' },
  { title: 'Modo Cajero', desc: 'Entrar al modo cajero (POS).', href: '/cashier/' },
];

function getReactContext() {
  // window.__MOVOS_REACT_CONTEXT__ is injected by Django when rendering React boot templates
  // Fallback to empty object if not present.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).__MOVOS_REACT_CONTEXT__ || {};
}

export default function AdminDashboardPage() {
  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h2 className="m-0 text-lg font-black text-slate-900">Panel de Administración</h2>
          <div className="mt-1 text-sm text-slate-900/80">Accesos rápidos.</div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(() => {
            const ctx = getReactContext();
            const user = ctx.user || {};
            const isStaff = Boolean(user.is_staff || user.is_superuser);
            const canManageProducts = Boolean(user.is_superuser || user.is_staff || user.can_add_products || user.can_edit_products);
            const canViewReports = Boolean(user.is_superuser || user.is_staff || user.can_view_analytics);

            return cards
              .filter((c) => {
                if (c.href === '/sucursales/') return isStaff;
                if (c.href === '/users/management/') return isStaff;
                if (c.href === '/products/management/') return canManageProducts;
                if (c.href === '/reports/dashboard/') return canViewReports;
                return true;
              })
              .map((c) => (
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
              ));
          })()}
        </div>
      </div>
    </div>
  );
}
