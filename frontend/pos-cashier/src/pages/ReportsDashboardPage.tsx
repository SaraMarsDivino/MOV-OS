type Card = { title: string; desc: string; href: string };

const cards: Card[] = [
  {
    title: 'Historial de Ventas',
    desc: 'Consulta el historial detallado de ventas realizadas.',
    href: '/reports/sales/history/',
  },
  {
    title: 'Historial de Caja',
    desc: 'Revisa registros de apertura y cierre de caja.',
    href: '/reports/cash/history/',
  },
  {
    title: 'Historial de Devoluciones',
    desc: 'Listado de todas las devoluciones realizadas, con detalle de productos y si se emitió nota de crédito.',
    href: '/reports/returns/history/',
  },
  {
    title: 'Análisis de Mercado',
    desc: 'Inteligencia de negocios: KPIs, tendencias, productos top, heatmap de ventas y asistente IA.',
    href: '/reports/market/',
  },

];

export default function ReportsDashboardPage() {
  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h2 className="m-0 text-lg font-black text-slate-900">Dashboard de Reportes</h2>
          <div className="mt-1 text-sm text-slate-900/80">Acceso rápido a reportes clave.</div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c) => (
            <a
              key={c.href}
              href={c.href}
              className={
                'block rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg ' +
                (c.href === '#' ? 'cursor-not-allowed opacity-80' : 'hover:bg-slate-200')
              }
              onClick={(ev) => {
                if (c.href === '#') ev.preventDefault();
              }}
            >
              <div className="text-base font-black text-slate-900">{c.title}</div>
              <div className="mt-1 text-sm text-slate-900/80">{c.desc}</div>
              <div className="mt-3 inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-bold text-slate-900 shadow">
                {c.href === '#' ? 'Próximamente' : 'Ir'}
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
