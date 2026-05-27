import { useState, useCallback } from 'react';
import { apiGet } from '../lib/api';

// ─── types ───────────────────────────────────────────────────────────────────

type Sucursal = { id: number; nombre: string };

type Overview = {
  kpis: {
    venta_total_neta: number;
    utilidad_bruta_real: number;
    margen_ganancia_promedio_pct: number;
    ticket_promedio: number;
    ventas_count: number;
    articulos_por_ticket: number;
  };
  periods: { day: { total_monto: number }; week: { total_monto: number }; month: { total_monto: number } };
  top_product: { nombre: string; total_monto: number } | null;
  payment_methods: { forma_pago: string; total_monto: number; ventas_count: number }[];
};

type MonthlyRow = { month: string; total_monto: number; ventas_count: number; growth_pct: number | null };
type BranchRow = { sucursal_nombre: string; total_monto: number; ventas_count: number; ticket_promedio: number };
type ProductRow = { producto_nombre: string; cantidad: number; monto_total: number; ganancia_total: number; margen_pct: number };
type ParetoRow = { rank: number; producto_nombre: string; monto: number; cum_share_pct: number };
type ZombieRow = { producto_nombre: string; stock: number };
type HeatmapData = { matrix_count: number[][]; peak_hour: number | null; weekday_labels: string[] };
type WeekendData = {
  weekday: { total_monto: number; ventas_count: number; avg_ticket: number };
  weekend: { total_monto: number; ventas_count: number; avg_ticket: number };
};

type Data = {
  overview?: Overview;
  monthly?: MonthlyRow[];
  branches?: BranchRow[];
  topByAmount?: ProductRow[];
  topByGain?: ProductRow[];
  pareto?: ParetoRow[];
  zombies?: ZombieRow[];
  heatmap?: HeatmapData;
  weekend?: WeekendData;
};

// ─── helpers ─────────────────────────────────────────────────────────────────

function getCtx() {
  return (window as any).__MOVOS_REACT_CONTEXT__ || {};
}

const fmt = (n: number) =>
  '$' + Math.round(n).toLocaleString('es-CL');

function BarRow({ label, value, max, sub }: { label: string; value: number; max: number; sub?: string }) {
  const w = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 py-1">
      <div className="w-36 shrink-0 truncate text-xs font-bold text-slate-900" title={label}>{label}</div>
      <div className="flex-1 rounded-sm bg-slate-200 overflow-hidden" style={{ height: 14 }}>
        <div className="h-full rounded-sm bg-slate-800" style={{ width: `${w}%` }} />
      </div>
      <div className="w-28 shrink-0 text-right text-xs text-slate-900">
        {fmt(value)}
        {sub && <span className="ml-1 text-slate-500">{sub}</span>}
      </div>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
      <h3 className="mb-3 text-sm font-black uppercase tracking-wide text-slate-900">{title}</h3>
      {children}
    </div>
  );
}

function Spinner() {
  return <div className="flex items-center justify-center py-6 text-sm text-slate-500">Cargando…</div>;
}

// ─── heatmap ─────────────────────────────────────────────────────────────────

const DAY_LABELS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => (i < 10 ? '0' + i : '' + i));

function Heatmap({ data }: { data: HeatmapData }) {
  const matrix = data.matrix_count;
  const max = Math.max(1, ...matrix.flat());
  return (
    <div className="overflow-x-auto">
      <div className="inline-block min-w-full">
        <div className="flex gap-0.5 mb-1 ml-8">
          {HOUR_LABELS.map((h) => (
            <div key={h} className="w-5 shrink-0 text-center text-[9px] text-slate-500">{h}</div>
          ))}
        </div>
        {DAY_LABELS.map((day, di) => (
          <div key={day} className="flex items-center gap-0.5 mb-0.5">
            <div className="w-7 shrink-0 text-right text-[10px] font-bold text-slate-600 pr-1">{day}</div>
            {matrix[di]?.map((count, hi) => {
              const intensity = count / max;
              const bg = count === 0
                ? 'rgba(226,232,240,1)'
                : `rgba(15,23,42,${0.15 + intensity * 0.85})`;
              return (
                <div
                  key={hi}
                  title={`${day} ${HOUR_LABELS[hi]}h: ${count} ventas`}
                  className="w-5 h-5 shrink-0 rounded-sm border border-black/10 cursor-default"
                  style={{ backgroundColor: bg }}
                />
              );
            })}
          </div>
        ))}
        <div className="flex items-center gap-2 mt-2 ml-8">
          <span className="text-[10px] text-slate-500">Menos ventas</span>
          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <div key={v} className="w-4 h-4 rounded-sm border border-black/10"
              style={{ backgroundColor: v === 0 ? 'rgba(226,232,240,1)' : `rgba(15,23,42,${0.15 + v * 0.85})` }} />
          ))}
          <span className="text-[10px] text-slate-500">Más ventas</span>
        </div>
      </div>
    </div>
  );
}

// ─── main page ───────────────────────────────────────────────────────────────

export default function MarketAnalysisPage() {
  const ctx = getCtx();
  const sucursales: Sucursal[] = ctx.sucursales || [];

  const [startDate, setStartDate] = useState<string>(ctx.default_start_date || '');
  const [endDate, setEndDate] = useState<string>(ctx.default_end_date || '');
  const [sucursalId, setSucursalId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<Data | null>(null);
  const [activeTab, setActiveTab] = useState<'resumen' | 'actividad' | 'productos' | 'sucursales'>('resumen');
  const [prodLimit, setProdLimit] = useState<5 | 10 | 20 | 50>(10);

  const loadData = useCallback(async () => {
    if (!startDate || !endDate) { setError('Selecciona un rango de fechas.'); return; }
    setError('');
    setLoading(true);
    const q = `?start_date=${startDate}&end_date=${endDate}${sucursalId ? `&sucursal_id=${sucursalId}` : ''}`;
    try {
      const [overviewRes, monthlyRes, branchRes, topRes, paretoRes, zombieRes, heatmapRes, weekendRes] = await Promise.all([
        apiGet<any>(`/reports/market/overview/${q}`),
        apiGet<any>(`/reports/market/monthly-trend/${q}`),
        apiGet<any>(`/reports/market/branch-comparison/${q}`),
        apiGet<any>(`/reports/market/top-products/${q}&limit=50`),
        apiGet<any>(`/reports/market/pareto/${q}&limit=50`),
        apiGet<any>(`/reports/market/zombie-products/${q}`),
        apiGet<any>(`/reports/market/heatmap/${q}`),
        apiGet<any>(`/reports/market/weekend-vs-weekday/${q}`),
      ]);
      setData({
        overview: overviewRes,
        monthly: monthlyRes.monthly || [],
        branches: branchRes.branches || [],
        topByAmount: topRes.top_by_amount || [],
        topByGain: topRes.top_by_amount?.slice().sort((a: ProductRow, b: ProductRow) => b.ganancia_total - a.ganancia_total) || [],
        pareto: paretoRes.series || [],
        zombies: zombieRes.zombies || [],
        heatmap: heatmapRes,
        weekend: weekendRes,
      });
      setActiveTab('resumen');
    } catch (e: any) {
      setError(e?.message || 'Error cargando datos');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, sucursalId]);

  const tabs: { key: typeof activeTab; label: string }[] = [
    { key: 'resumen', label: 'Resumen' },
    { key: 'actividad', label: 'Actividad' },
    { key: 'productos', label: 'Productos' },
    { key: 'sucursales', label: 'Sucursales' },
  ];

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">

        {/* Header */}
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="m-0 text-lg font-black text-slate-900">Análisis de Mercado</h2>
              <p className="mt-0.5 text-sm text-slate-600">Inteligencia de negocio por período y sucursal.</p>
            </div>
            <a href="/reports/dashboard/" className="inline-flex shrink-0 items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-black text-slate-900 shadow hover:bg-slate-100">
              ← Volver
            </a>
          </div>
        </div>

        {/* Filtros */}
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-black text-slate-900">Desde</label>
              <input type="date" className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 outline-none"
                value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-black text-slate-900">Hasta</label>
              <input type="date" className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 outline-none"
                value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            {sucursales.length > 0 && (
              <div>
                <label className="mb-1 block text-xs font-black text-slate-900">Sucursal</label>
                <select className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 outline-none"
                  value={sucursalId} onChange={(e) => setSucursalId(e.target.value)}>
                  <option value="">Todas</option>
                  {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
                </select>
              </div>
            )}
            <button
              onClick={loadData}
              disabled={loading}
              className="rounded-xl border-2 border-black bg-slate-900 px-5 py-2 text-sm font-black text-white shadow disabled:opacity-50"
            >
              {loading ? 'Cargando…' : 'Cargar datos'}
            </button>
          </div>
          {error && <div className="mt-2 text-sm text-red-700">{error}</div>}
        </div>

        {/* Estado vacío */}
        {!data && !loading && (
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-8 text-center shadow-lg">
            <div className="text-slate-500 text-sm">Selecciona un período y presiona <strong>Cargar datos</strong> para ver el análisis.</div>
          </div>
        )}

        {loading && (
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-8 text-center shadow-lg">
            <Spinner />
          </div>
        )}

        {/* Contenido con tabs */}
        {data && !loading && (
          <>
            {/* Tab bar */}
            <div className="mb-3 flex flex-wrap gap-2">
              {tabs.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={`rounded-xl border-2 border-black px-4 py-2 text-sm font-black shadow transition-colors ${
                    activeTab === t.key ? 'bg-slate-900 text-white' : 'bg-slate-300 text-slate-900 hover:bg-slate-200'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* ── RESUMEN ─────────────────────────────────────────────── */}
            {activeTab === 'resumen' && data.overview && (() => {
              const kpis = data.overview!.kpis;
              const margin = kpis.margen_ganancia_promedio_pct;

              const periodDays = startDate && endDate
                ? Math.max(1, Math.round((new Date(endDate).getTime() - new Date(startDate).getTime()) / 86400000) + 1)
                : 30;
              const dailyAvg = kpis.venta_total_neta / periodDays;
              const todaySales = data.overview!.periods.day.total_monto;
              const todayDelta = dailyAvg > 0 ? ((todaySales - dailyAvg) / dailyAvg) * 100 : null;

              const lastMonthGrowth = data.monthly && data.monthly.length > 0
                ? (data.monthly[data.monthly.length - 1].growth_pct ?? null)
                : null;

              const topBranch = data.branches && data.branches.length > 0
                ? [...data.branches].sort((a, b) => b.total_monto - a.total_monto)[0]
                : null;
              const topPayment = data.overview!.payment_methods.length > 0
                ? [...data.overview!.payment_methods].sort((a, b) => b.total_monto - a.total_monto)[0]
                : null;

              // ▲▼→ trend badge
              const badge = (g: number | null) => {
                if (g === null) return null;
                if (Math.abs(g) < 2) return (
                  <span className="inline-flex items-center rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-black text-amber-700">→ {g.toFixed(1)}%</span>
                );
                if (g > 0) return (
                  <span className="inline-flex items-center rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-black text-emerald-700">▲ +{g.toFixed(1)}%</span>
                );
                return (
                  <span className="inline-flex items-center rounded-md bg-red-100 px-1.5 py-0.5 text-[10px] font-black text-red-600">▼ {g.toFixed(1)}%</span>
                );
              };

              // Alertas automáticas
              type AlertKind = 'danger' | 'warning' | 'success' | 'info';
              const alerts: { kind: AlertKind; icon: string; title: string; sub: string }[] = [];
              if (dailyAvg > 0 && todayDelta !== null) {
                if (todayDelta < -50)
                  alerts.push({ kind: 'danger', icon: '↓', title: 'Ventas bajas hoy', sub: `${fmt(todaySales)} · prom. diario ${fmt(Math.round(dailyAvg))}` });
                else if (todayDelta > 40)
                  alerts.push({ kind: 'success', icon: '↑', title: 'Excelente día de ventas', sub: `+${Math.round(todayDelta)}% sobre el promedio diario` });
                else
                  alerts.push({ kind: 'info', icon: '→', title: 'Ventas normales hoy', sub: fmt(todaySales) });
              }
              if (topBranch)
                alerts.push({ kind: 'info', icon: '★', title: `Mejor sucursal: ${topBranch.sucursal_nombre}`, sub: `${fmt(topBranch.total_monto)} · ${topBranch.ventas_count} ventas` });
              if (topPayment)
                alerts.push({ kind: 'info', icon: '◈', title: `Pago más usado: ${topPayment.forma_pago}`, sub: `${topPayment.ventas_count} ventas` });
              if (margin < 10)
                alerts.push({ kind: 'warning', icon: '!', title: 'Margen de ganancia bajo', sub: `${margin.toFixed(1)}% promedio en el período` });

              const alertBorder: Record<AlertKind, string> = {
                danger:  'bg-red-50 border-red-400',
                warning: 'bg-amber-50 border-amber-400',
                success: 'bg-emerald-50 border-emerald-500',
                info:    'bg-white border-black',
              };
              const alertIconBg: Record<AlertKind, string> = {
                danger:  'bg-red-500 text-white',
                warning: 'bg-amber-400 text-slate-900',
                success: 'bg-emerald-500 text-white',
                info:    'bg-slate-900 text-white',
              };

              const marginColor = margin >= 20 ? 'text-emerald-600' : margin >= 10 ? 'text-amber-600' : 'text-red-600';

              const totalWeekend = (data.weekend?.weekday.total_monto ?? 0) + (data.weekend?.weekend.total_monto ?? 0);
              const weekdayPct = totalWeekend > 0
                ? Math.round((data.weekend!.weekday.total_monto / totalWeekend) * 100)
                : 50;

              return (
                <div className="flex flex-col gap-3">

                  {/* ── Alertas automáticas */}
                  {alerts.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {alerts.map((a, i) => (
                        <div key={i} className={`flex items-start gap-2 rounded-xl border-2 px-3 py-2 shadow-sm ${alertBorder[a.kind]}`}>
                          <div className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-black ${alertIconBg[a.kind]}`}>
                            {a.icon}
                          </div>
                          <div>
                            <div className="text-xs font-black text-slate-900">{a.title}</div>
                            <div className="text-[11px] text-slate-600">{a.sub}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* ── KPIs principales */}
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">

                    {/* Ventas netas — acento oscuro, span completo en móvil */}
                    <div className="relative col-span-2 overflow-hidden rounded-2xl border-2 border-black bg-slate-900 p-4 shadow-lg md:col-span-1">
                      <div className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-xl font-black text-white">$</div>
                      <div className="text-xs font-black uppercase tracking-wide text-slate-400">Ventas netas</div>
                      <div className="mt-1 text-3xl font-black leading-tight text-white">{fmt(kpis.venta_total_neta)}</div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] text-slate-400">{kpis.ventas_count} transacciones</span>
                        {badge(lastMonthGrowth)}
                      </div>
                    </div>

                    {/* Ganancia bruta */}
                    <div className="relative overflow-hidden rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
                      <div className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-xl bg-black/10 text-lg text-slate-700">↑</div>
                      <div className="text-xs font-black uppercase tracking-wide text-slate-600">Ganancia bruta</div>
                      <div className="mt-1 text-2xl font-black leading-tight text-slate-900">{fmt(kpis.utilidad_bruta_real)}</div>
                      <div className="mt-1 text-[11px] text-slate-500">Período completo</div>
                    </div>

                    {/* Margen — color semántico */}
                    <div className="relative overflow-hidden rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
                      <div className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-xl bg-black/10 text-sm font-black text-slate-700">%</div>
                      <div className="text-xs font-black uppercase tracking-wide text-slate-600">Margen promedio</div>
                      <div className={`mt-1 text-2xl font-black leading-tight ${marginColor}`}>{margin.toFixed(1)}%</div>
                      <div className="mt-1 text-[11px] text-slate-500">
                        {margin >= 20 ? '✓ Saludable' : margin >= 10 ? 'Aceptable' : '⚠ Bajo'}
                      </div>
                    </div>

                    {/* Ticket promedio */}
                    <div className="relative overflow-hidden rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
                      <div className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-xl bg-black/10 text-lg text-slate-700">◎</div>
                      <div className="text-xs font-black uppercase tracking-wide text-slate-600">Ticket promedio</div>
                      <div className="mt-1 text-2xl font-black leading-tight text-slate-900">{fmt(kpis.ticket_promedio)}</div>
                      <div className="mt-1 text-[11px] text-slate-500">{kpis.articulos_por_ticket.toFixed(1)} artículos/ticket</div>
                    </div>
                  </div>

                  {/* ── Períodos rápidos */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
                      <div className="mb-1 text-xs font-black uppercase tracking-wide text-slate-600">Hoy</div>
                      <div className="text-xl font-black text-slate-900">{fmt(todaySales)}</div>
                      <div className="mt-1">{badge(todayDelta)}</div>
                    </div>
                    <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
                      <div className="mb-1 text-xs font-black uppercase tracking-wide text-slate-600">Últimos 7 días</div>
                      <div className="text-xl font-black text-slate-900">{fmt(data.overview!.periods.week.total_monto)}</div>
                    </div>
                    <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
                      <div className="mb-1 text-xs font-black uppercase tracking-wide text-slate-600">Este mes</div>
                      <div className="text-xl font-black text-slate-900">{fmt(data.overview!.periods.month.total_monto)}</div>
                    </div>
                  </div>

                  {/* ── Tendencia mensual + Medios de pago */}
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {data.monthly && data.monthly.length > 0 && (
                      <SectionCard title="Tendencia mensual">
                        {(() => {
                          const max = Math.max(1, ...data.monthly!.map((r) => r.total_monto));
                          return data.monthly!.map((r) => {
                            const w = max > 0 ? Math.round((r.total_monto / max) * 100) : 0;
                            return (
                              <div key={r.month} className="flex items-center gap-2 py-1">
                                <div className="w-14 shrink-0 text-[11px] font-bold text-slate-700">
                                  {r.month ? new Date(r.month + 'T12:00:00').toLocaleDateString('es-CL', { month: 'short', year: '2-digit' }) : ''}
                                </div>
                                <div className="flex-1 overflow-hidden rounded-sm bg-slate-200" style={{ height: 12 }}>
                                  <div className="h-full rounded-sm bg-slate-800" style={{ width: `${w}%` }} />
                                </div>
                                <div className="w-24 shrink-0 text-right text-xs font-bold text-slate-900">{fmt(r.total_monto)}</div>
                                <div className="w-16 shrink-0 text-right">{badge(r.growth_pct)}</div>
                              </div>
                            );
                          });
                        })()}
                      </SectionCard>
                    )}
                    {data.overview!.payment_methods.length > 0 && (
                      <SectionCard title="Medios de pago">
                        {(() => {
                          const max = Math.max(1, ...data.overview!.payment_methods.map((p) => p.total_monto));
                          return data.overview!.payment_methods.map((p) => (
                            <BarRow key={p.forma_pago} label={p.forma_pago} value={p.total_monto} max={max} sub={`${p.ventas_count} ventas`} />
                          ));
                        })()}
                      </SectionCard>
                    )}
                  </div>

                  {/* ── Semana vs Fin de semana */}
                  {data.weekend && totalWeekend > 0 && (
                    <SectionCard title="Semana vs Fin de semana">
                      <div className="mb-3 flex h-5 overflow-hidden rounded-lg border border-black/20">
                        <div className="bg-slate-900" style={{ width: `${weekdayPct}%` }} />
                        <div className="flex-1 bg-slate-400" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="mb-1 flex items-center gap-1.5">
                            <div className="h-3 w-3 shrink-0 rounded-sm bg-slate-900" />
                            <span className="text-xs font-black text-slate-900">Días de semana · {weekdayPct}%</span>
                          </div>
                          <div className="text-lg font-black text-slate-900">{fmt(data.weekend.weekday.total_monto)}</div>
                          <div className="text-[11px] text-slate-500">{data.weekend.weekday.ventas_count} ventas · ticket {fmt(data.weekend.weekday.avg_ticket)}</div>
                        </div>
                        <div>
                          <div className="mb-1 flex items-center gap-1.5">
                            <div className="h-3 w-3 shrink-0 rounded-sm bg-slate-400" />
                            <span className="text-xs font-black text-slate-900">Fin de semana · {100 - weekdayPct}%</span>
                          </div>
                          <div className="text-lg font-black text-slate-900">{fmt(data.weekend.weekend.total_monto)}</div>
                          <div className="text-[11px] text-slate-500">{data.weekend.weekend.ventas_count} ventas · ticket {fmt(data.weekend.weekend.avg_ticket)}</div>
                        </div>
                      </div>
                    </SectionCard>
                  )}

                </div>
              );
            })()}

            {/* ── ACTIVIDAD ───────────────────────────────────────────── */}
            {activeTab === 'actividad' && (
              <div className="flex flex-col gap-3">
                {data.heatmap && (
                  <SectionCard title="Mapa de calor — ventas por día y hora">
                    <Heatmap data={data.heatmap} />
                    {data.heatmap.peak_hour !== null && (
                      <div className="mt-3 text-sm text-slate-700">
                        Hora pico: <strong>{data.heatmap.peak_hour}:00 – {data.heatmap.peak_hour + 1}:00</strong>
                      </div>
                    )}
                  </SectionCard>
                )}
              </div>
            )}

            {/* ── PRODUCTOS ───────────────────────────────────────────── */}
            {activeTab === 'productos' && (
              <div className="flex flex-col gap-3">
                {/* Selector de cantidad */}
                <div className="flex flex-wrap items-center gap-2 rounded-2xl border-2 border-black bg-slate-300 px-4 py-3 shadow-lg">
                  <span className="text-xs font-black text-slate-700 shrink-0">Mostrar top:</span>
                  {([5, 10, 20, 50] as const).map((n) => (
                    <button
                      key={n}
                      onClick={() => setProdLimit(n)}
                      className={`rounded-xl border-2 border-black px-3 py-1 text-sm font-black shadow-sm transition-colors ${
                        prodLimit === n ? 'bg-slate-900 text-white' : 'bg-white text-slate-900 hover:bg-slate-200'
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {/* Top por ingresos */}
                  {data.topByAmount && data.topByAmount.length > 0 && (
                    <SectionCard title={`Top ${prodLimit} — Mayor ingreso`}>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b-2 border-black">
                              <th className="pb-1 text-left font-black text-slate-900">Producto</th>
                              <th className="pb-1 text-right font-black text-slate-900">Ingresos</th>
                              <th className="pb-1 text-right font-black text-slate-900">Margen</th>
                            </tr>
                          </thead>
                          <tbody>
                            {data.topByAmount.slice(0, prodLimit).map((p, i) => (
                              <tr key={i} className="border-b border-black/10">
                                <td className="py-1 font-bold text-slate-900 max-w-0 truncate" style={{ maxWidth: 160 }} title={p.producto_nombre}>{p.producto_nombre}</td>
                                <td className="py-1 text-right text-slate-900">{fmt(p.monto_total)}</td>
                                <td className={`py-1 text-right font-bold ${p.margen_pct >= 20 ? 'text-green-700' : p.margen_pct >= 0 ? 'text-slate-700' : 'text-red-600'}`}>
                                  {p.margen_pct.toFixed(1)}%
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </SectionCard>
                  )}

                  {/* Top por ganancia */}
                  {data.topByGain && data.topByGain.length > 0 && (
                    <SectionCard title={`Top ${prodLimit} — Mayor ganancia`}>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b-2 border-black">
                              <th className="pb-1 text-left font-black text-slate-900">Producto</th>
                              <th className="pb-1 text-right font-black text-slate-900">Ganancia</th>
                              <th className="pb-1 text-right font-black text-slate-900">Margen</th>
                            </tr>
                          </thead>
                          <tbody>
                            {data.topByGain.slice(0, prodLimit).map((p, i) => (
                              <tr key={i} className="border-b border-black/10">
                                <td className="py-1 font-bold text-slate-900 truncate" style={{ maxWidth: 160 }} title={p.producto_nombre}>{p.producto_nombre}</td>
                                <td className="py-1 text-right text-slate-900">{fmt(p.ganancia_total)}</td>
                                <td className={`py-1 text-right font-bold ${p.margen_pct >= 20 ? 'text-green-700' : p.margen_pct >= 0 ? 'text-slate-700' : 'text-red-600'}`}>
                                  {p.margen_pct.toFixed(1)}%
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </SectionCard>
                  )}
                </div>

                {/* Pareto */}
                {data.pareto && data.pareto.length > 0 && (
                  <SectionCard title={`Análisis Pareto — top ${prodLimit} productos por ingreso`}>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b-2 border-black">
                            <th className="pb-1 text-left font-black text-slate-900">#</th>
                            <th className="pb-1 text-left font-black text-slate-900">Producto</th>
                            <th className="pb-1 text-right font-black text-slate-900">Monto</th>
                            <th className="pb-1 text-right font-black text-slate-900">Acum.</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.pareto.slice(0, prodLimit).map((p) => (
                            <tr key={p.rank} className={`border-b border-black/10 ${p.cum_share_pct <= 80 ? 'bg-slate-900/5' : ''}`}>
                              <td className="py-1 font-bold text-slate-500">{p.rank}</td>
                              <td className="py-1 font-bold text-slate-900 truncate" style={{ maxWidth: 200 }} title={p.producto_nombre}>{p.producto_nombre}</td>
                              <td className="py-1 text-right text-slate-900">{fmt(p.monto)}</td>
                              <td className={`py-1 text-right font-bold ${p.cum_share_pct <= 80 ? 'text-slate-900' : 'text-slate-400'}`}>
                                {p.cum_share_pct.toFixed(1)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="mt-2 text-xs text-slate-500">Las filas sombreadas componen el 80% del ingreso total.</div>
                    </div>
                  </SectionCard>
                )}

                {/* Zombie products */}
                {data.zombies !== undefined && (
                  <SectionCard title={`Productos sin movimiento (últimos 30 días) — ${data.zombies.length} encontrados`}>
                    {data.zombies.length === 0 ? (
                      <p className="text-sm text-slate-600">Todos los productos tuvieron al menos una venta en el período. ✓</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b-2 border-black">
                              <th className="pb-1 text-left font-black text-slate-900">Producto</th>
                              <th className="pb-1 text-right font-black text-slate-900">Stock actual</th>
                            </tr>
                          </thead>
                          <tbody>
                            {data.zombies.map((z, i) => (
                              <tr key={i} className="border-b border-black/10">
                                <td className="py-1 font-bold text-slate-900">{z.producto_nombre}</td>
                                <td className={`py-1 text-right font-bold ${z.stock <= 0 ? 'text-red-600' : 'text-slate-700'}`}>{z.stock}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </SectionCard>
                )}
              </div>
            )}

            {/* ── SUCURSALES ──────────────────────────────────────────── */}
            {activeTab === 'sucursales' && data.branches && (
              <div className="flex flex-col gap-3">
                <SectionCard title="Comparación por sucursal">
                  {data.branches.length === 0 ? (
                    <p className="text-sm text-slate-600">Sin datos de sucursales para el período.</p>
                  ) : (
                    <>
                      {(() => {
                        const max = Math.max(1, ...data.branches!.map((b) => b.total_monto));
                        return data.branches!.map((b) => (
                          <div key={b.sucursal_nombre} className="mb-3">
                            <BarRow label={b.sucursal_nombre} value={b.total_monto} max={max} sub={`${b.ventas_count} ventas`} />
                            <div className="ml-38 text-xs text-slate-500 pl-36">Ticket prom.: {fmt(b.ticket_promedio)}</div>
                          </div>
                        ));
                      })()}
                    </>
                  )}
                </SectionCard>
              </div>
            )}

          </>
        )}
      </div>
    </div>
  );
}
