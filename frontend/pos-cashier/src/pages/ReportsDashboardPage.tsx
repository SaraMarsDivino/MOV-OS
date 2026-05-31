type Quadrant = {
  title: string;
  desc: string;
  href: string;
  icon: string;
  accent: string;
  accentText: string;
  tag: string;
};

const quadrants: Quadrant[] = [
  {
    title: 'Historial de Ventas',
    desc: 'Consulta el detalle de cada transacción: productos, montos, métodos de pago y cajero.',
    href: '/reports/sales/history/',
    icon: '🧾',
    accent: 'bg-slate-800',
    accentText: 'text-white',
    tag: 'Transacciones',
  },
  {
    title: 'Historial de Caja',
    desc: 'Revisa las aperturas y cierres de caja: efectivo inicial, final, diferencias y cuadratura.',
    href: '/reports/cash/history/',
    icon: '🏦',
    accent: 'bg-slate-700',
    accentText: 'text-white',
    tag: 'Caja',
  },
  {
    title: 'Historial de Devoluciones',
    desc: 'Listado de devoluciones: parciales y totales, reembolsos en efectivo y notas de crédito emitidas.',
    href: '/reports/returns/history/',
    icon: '↩',
    accent: 'bg-slate-600',
    accentText: 'text-white',
    tag: 'Devoluciones',
  },
  {
    title: 'Análisis de Mercado',
    desc: 'BI completo: KPIs, heatmap de ventas, productos top, tendencias, Pareto 80/20 y más.',
    href: '/reports/market/',
    icon: '📈',
    accent: 'bg-slate-900',
    accentText: 'text-white',
    tag: 'Inteligencia de negocio',
  },
];

export default function ReportsDashboardPage() {
  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-3">
      <div className="mx-auto max-w-5xl">

        {/* Header compacto */}
        <div className="mb-3">
          <h1 className="text-base font-black text-slate-900 tracking-tight">Reportes</h1>
        </div>

        {/* 2×2 quadrant grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {quadrants.map((q) => (
            <a
              key={q.href}
              href={q.href}
              className="group flex flex-col rounded-2xl border-2 border-black bg-white shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all duration-150 overflow-hidden"
            >
              {/* Accent strip — más delgado */}
              <div className={`${q.accent} px-4 py-2 flex items-center justify-between`}>
                <span className={`text-[10px] font-black uppercase tracking-widest ${q.accentText} opacity-70`}>
                  {q.tag}
                </span>
                <span className="text-lg">{q.icon}</span>
              </div>

              {/* Body compacto */}
              <div className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <h2 className="text-sm font-black text-slate-900 leading-snug">{q.title}</h2>
                  <p className="text-xs text-slate-500 leading-snug mt-0.5 line-clamp-2">{q.desc}</p>
                </div>
                <span className="shrink-0 inline-flex items-center rounded-xl border-2 border-black bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-900 shadow group-hover:bg-slate-900 group-hover:text-white transition-colors">
                  Ir →
                </span>
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
