import { useEffect, useMemo, useRef, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';
import UploadReportBanner from '../components/UploadReportBanner';
import AssignStockModal from '../components/AssignStockModal';
import { formatCLP } from '../components/utils';

type SucursalStock = { sucursal: string; cantidad: number };

type ProductItem = {
  id: number;
  nombre: string;
  producto_id: string;
  codigo_barras: string;
  precio_compra: string;
  precio_venta: string;
  stock: number;
  cantidad: number;
  stock_minimo: number;
  stocks_por_sucursal: SucursalStock[];
  permitir_venta_sin_stock: boolean;
  activo: boolean;
};

type ProductsResponse = {
  items: ProductItem[];
  page: number;
  num_pages: number;
  total: number;
  per_page: number;
  search: string;
};

function getReactContext() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).__MOVOS_REACT_CONTEXT__ || {};
}

function stockStatus(stocks: SucursalStock[], minimo: number) {
  if (!stocks.length) return null;
  const min = Math.min(...stocks.map((s) => s.cantidad));
  if (min === 0) return { label: 'Sin stock', cls: 'bg-red-100 text-red-700' };
  if (minimo > 0 && min < minimo) return { label: 'Bajo', cls: 'bg-amber-100 text-amber-700' };
  return { label: 'Normal', cls: 'bg-emerald-100 text-emerald-700' };
}

function StockCell({ stocks, minimo }: { stocks: SucursalStock[]; minimo: number }) {
  const [pos, setPos] = useState<{ x: number; y: number; above: boolean } | null>(null);
  const status = stockStatus(stocks, minimo);
  if (!status) return <span className="text-slate-400 text-xs">—</span>;

  const handleEnter = (e: React.MouseEvent<HTMLSpanElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const above = rect.bottom > window.innerHeight - 160;
    setPos({
      x: rect.right,
      y: above ? rect.top : rect.bottom,
      above,
    });
  };

  return (
    <>
      <span
        className={`cursor-default rounded-md px-2 py-0.5 text-xs font-black ${status.cls}`}
        onMouseEnter={handleEnter}
        onMouseLeave={() => setPos(null)}
      >
        {status.label}
      </span>
      {pos && (
        <div
          className="fixed z-[9999] min-w-[170px] rounded-xl border-2 border-black bg-white shadow-2xl text-xs overflow-hidden"
          style={{
            right: `${window.innerWidth - pos.x}px`,
            ...(pos.above
              ? { bottom: `${window.innerHeight - pos.y}px` }
              : { top: `${pos.y + 4}px` }),
          }}
          onMouseEnter={() => {/* mantener visible si el cursor pasa al tooltip */}}
        >
          {stocks.map((s, i) => (
            <div
              key={i}
              className={`flex items-center justify-between gap-4 px-3 py-2 ${i === 0 ? 'bg-slate-50' : ''} ${i < stocks.length - 1 ? 'border-b border-slate-100' : ''}`}
            >
              <span className={`truncate ${i === 0 ? 'font-black text-slate-800' : 'text-slate-500'}`}>{s.sucursal}</span>
              <span className={`font-black tabular-nums shrink-0 ${
                s.cantidad === 0 ? 'text-red-600' :
                minimo > 0 && s.cantidad < minimo ? 'text-amber-600' :
                'text-emerald-600'
              }`}>{s.cantidad} u.</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function ProductsManagementPage() {
  const ctx = getReactContext();
  const user = ctx.user || {};
  const canAdd = Boolean(user.is_superuser || user.is_staff || user.can_add_products);
  const canEdit = Boolean(user.is_superuser || user.is_staff || user.can_edit_products);

  const [searchDraft, setSearchDraft] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [sortBy, setSortBy] = useState<string>('nombre');
  const [orderBy, setOrderBy] = useState<'asc'|'desc'>('asc');
  const [hideInactive, setHideInactive] = useState<boolean>(
    () => localStorage.getItem('products_hide_inactive') === '1'
  );
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const selectAllRef = useRef<HTMLInputElement | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const scannerTimerRef = useRef<number | null>(null);
  const scannerBurstRef = useRef<{ count: number; start: number; last: number }>({
    count: 0,
    start: 0,
    last: 0,
  });

  const load = async (nextPage: number, nextSearch: string, nextPerPage = perPage, nextSortBy = sortBy, nextOrder = orderBy, nextHideInactive = hideInactive) => {
    try {
      setLoading(true);
      setError('');
      const qs = new URLSearchParams({
        page: String(nextPage),
        per_page: String(nextPerPage),
        search: nextSearch,
        sort_by: String(nextSortBy || 'nombre'),
        order: String(nextOrder || 'asc'),
        hide_inactive: nextHideInactive ? '1' : '0',
      });
      const data = await apiGet<ProductsResponse>(`/products/api/products/?${qs.toString()}`);
      setItems(data.items || []);
      setPage(data.page || 1);
      setNumPages(data.num_pages || 1);
      setSelectedIds(new Set());
    } catch (e: any) {
      setError(e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1, '', perPage, sortBy, orderBy, hideInactive);
  }, []);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  const showToast = (kind: 'success' | 'error', message: string) => {
    setToast({ kind, message });
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2500);
  };

  const triggerSearch = (raw: string) => {
    const next = (raw || '').trim();
    setSearch(next);
    load(1, next, perPage);
  };

  // Helper to change sorting
  const changeSort = (field: string) => {
    const nextOrder = sortBy === field && orderBy === 'asc' ? 'desc' : 'asc';
    setSortBy(field);
    setOrderBy(nextOrder);
    load(1, search, perPage, field, nextOrder, hideInactive);
  };

  const sortIcon = (field: string) => {
    if (sortBy !== field) return <span className="ml-1 opacity-30">↕</span>;
    return <span className="ml-1">{orderBy === 'asc' ? '↑' : '↓'}</span>;
  };

  const toggleHideInactive = () => {
    const next = !hideInactive;
    setHideInactive(next);
    localStorage.setItem('products_hide_inactive', next ? '1' : '0');
    load(1, search, perPage, sortBy, orderBy, next);
  };

  const allSelected = useMemo(() => !!items.length && items.every((p) => selectedIds.has(p.id)), [items, selectedIds]);
  const someSelected = useMemo(() => items.some((p) => selectedIds.has(p.id)), [items, selectedIds]);

  useEffect(() => {
    if (!selectAllRef.current) return;
    selectAllRef.current.indeterminate = !allSelected && someSelected;
  }, [allSelected, someSelected]);

  const totalLabel = useMemo(() => (loading ? '…' : String(items.length)), [loading, items.length]);
  const selectedCount = selectedIds.size;

  const renderClp = (raw: string) => {
    const n = Number(raw);
    if (!Number.isFinite(n)) return '-';
    return `$${formatCLP(n)}`;
  };

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="m-0 text-lg font-black text-slate-900">Gestión de Productos</h2>
              <div className="mt-1 text-sm text-slate-900/80">Mostrando: {totalLabel}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {canAdd ? (
                <a
                  href="/products/create/"
                  className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-bold text-slate-900 shadow"
                >
                  Crear producto
                </a>
              ) : (
                <button
                  type="button"
                  disabled
                  title="No tienes permiso para crear productos"
                  className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-bold text-slate-900 shadow opacity-40 cursor-not-allowed"
                >
                  Crear producto
                </button>
              )}
              {canAdd ? (
                <a
                  href="/products/upload/"
                  className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-bold text-slate-900 shadow"
                >
                  Subir Excel
                </a>
              ) : (
                <button
                  type="button"
                  disabled
                  title="No tienes permiso para crear productos"
                  className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-bold text-slate-900 shadow opacity-40 cursor-not-allowed"
                >
                  Subir Excel
                </button>
              )}

              <a
                href="/products/transfer/"
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-bold text-slate-900 shadow"
              >
                Transferir stock
              </a>

              <a
                href="/products/stock/adjust/history/"
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-bold text-slate-900 shadow"
              >
                Historial de ajustes
              </a>

                <button
                  type="button"
                  disabled={selectedCount <= 0 || loading}
                  onClick={() => { if (selectedCount > 0) setAssignOpen(true); }}
                  className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-black text-slate-900 shadow disabled:opacity-50"
                >
                  Asignar stock ({selectedCount})
                </button>

              <button
                type="button"
                disabled={selectedCount <= 0 || loading}
                onClick={async () => {
                  if (selectedCount <= 0) return;
                  const ok = window.confirm(
                    `¿Seguro que quieres deshabilitar ${selectedCount} producto(s)?`,
                  );
                  if (!ok) return;
                  try {
                    setLoading(true);
                    setError('');
                    await apiPost<{ success: boolean; deleted: number }>(`/products/bulk-delete/`, {
                      product_ids: Array.from(selectedIds),
                    });
                    const nextPage = selectedCount >= items.length && page > 1 ? Math.max(1, page - 1) : page;
                    await load(nextPage, search, perPage);
                  } catch (e: any) {
                    setError(e?.message || 'Error');
                  } finally {
                    setLoading(false);
                  }
                }}
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-black text-rose-700 shadow disabled:opacity-50"
              >
                Deshabilitar seleccionados ({selectedCount})
              </button>
            </div>
          </div>

            <div className="mt-3 flex flex-wrap gap-2">
            <input
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              onKeyDown={(e) => {
                // Normal UX: Enter runs search
                if (e.key === 'Enter') {
                  e.preventDefault();
                  triggerSearch(searchDraft);
                  return;
                }

                // Barcode scanner UX: rapid key burst then short idle pause -> auto-search
                // (Some scanners don't send Enter.)
                if (e.key.length !== 1) return;
                const now = Date.now();
                const burst = scannerBurstRef.current;

                // If time between keys is large, start a new burst
                if (!burst.last || now - burst.last > 80) {
                  burst.count = 0;
                  burst.start = now;
                }
                burst.count += 1;
                burst.last = now;

                if (scannerTimerRef.current) {
                  window.clearTimeout(scannerTimerRef.current);
                }
                scannerTimerRef.current = window.setTimeout(() => {
                  const current = scannerBurstRef.current;
                  const duration = current.last - current.start;
                  const looksLikeScan = current.count >= 6 && duration <= 700;

                  // Reset burst
                  current.count = 0;
                  current.start = 0;
                  current.last = 0;

                  if (!looksLikeScan) return;
                  triggerSearch(searchDraft);
                }, 140);
              }}
              placeholder="Buscar productos…"
              className="w-full min-w-0 flex-1 rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none"
            />

            <select
              value={perPage}
              onChange={(e) => {
                const next = Number(e.target.value || 10);
                const normalized = next === 25 || next === 50 ? next : 10;
                setPerPage(normalized);
                load(1, search, normalized);
              }}
              aria-label="Elementos por página"
              className="min-w-[96px] rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>

            <button
              type="button"
              onClick={() => {
                triggerSearch(searchDraft);
              }}
              className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-4 py-2 text-sm font-black text-slate-900 shadow"
            >
              Buscar
            </button>

            <button
              type="button"
              onClick={toggleHideInactive}
              className={
                'inline-flex items-center justify-center rounded-xl border-2 border-black px-4 py-2 text-sm font-black shadow ' +
                (hideInactive
                  ? 'bg-slate-900 text-white'
                  : 'bg-white text-slate-900')
              }
              title={hideInactive ? 'Mostrando solo activos — clic para mostrar todos' : 'Clic para ocultar deshabilitados'}
            >
              {hideInactive ? 'Solo activos' : 'Mostrar todos'}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mb-3 rounded-2xl border-2 border-black bg-white p-3 text-sm text-red-700 shadow">{error}</div>
        ) : null}

        {toast ? (
          <div
            className={
              'mb-3 rounded-2xl border-2 border-black bg-white p-3 text-sm shadow ' +
              (toast.kind === 'success' ? 'text-emerald-800' : 'text-red-700')
            }
            role="status"
          >
            {toast.message}
          </div>
        ) : null}

        <div className="rounded-2xl border-2 border-black bg-slate-300 shadow-lg overflow-hidden">
          <div className="overflow-auto">
            <table className="min-w-full border-collapse text-sm text-slate-900">
              <thead className="bg-slate-200">
                <tr>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">
                    <input
                      ref={selectAllRef}
                      type="checkbox"
                      checked={allSelected}
                      onChange={(e) => {
                        const checked = !!e.target.checked;
                        if (!checked) {
                          setSelectedIds(new Set());
                          return;
                        }
                        setSelectedIds(new Set(items.map((p) => p.id)));
                      }}
                      aria-label="Seleccionar todo"
                    />
                  </th>
                  <th onClick={() => changeSort('nombre')} className="border-b-2 border-black px-3 py-2 text-left font-black cursor-pointer select-none">Nombre{sortIcon('nombre')}</th>
                  <th onClick={() => changeSort('codigo1')} className="border-b-2 border-black px-3 py-2 text-left font-black cursor-pointer select-none">Código{sortIcon('codigo1')}</th>
                  <th className="border-b-2 border-black px-3 py-2 text-right font-black">Stock</th>
                  <th className="border-b-2 border-black px-3 py-2 text-right font-black">Valor</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Estado</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="px-3 py-3" colSpan={7}>
                      Cargando…
                    </td>
                  </tr>
                ) : items.length ? (
                  items.map((p) => (
                    <tr key={p.id} className="odd:bg-white/20">
                      <td className="border-b border-black/20 px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(p.id)}
                          onChange={(e) => {
                            const checked = !!e.target.checked;
                            setSelectedIds((prev) => {
                              const next = new Set(prev);
                              if (checked) next.add(p.id);
                              else next.delete(p.id);
                              return next;
                            });
                          }}
                          aria-label={`Seleccionar ${p.nombre || 'producto'}`}
                        />
                      </td>
                      <td className="border-b border-black/20 px-3 py-2">{p.nombre || '-'}</td>
                      <td className="border-b border-black/20 px-3 py-2">{p.producto_id}</td>
                      <td className="border-b border-black/20 px-3 py-2 text-right">
                        <StockCell stocks={p.stocks_por_sucursal ?? []} minimo={p.stock_minimo ?? 0} />
                      </td>
                      <td className="border-b border-black/20 px-3 py-2 text-right">{renderClp(p.precio_venta)}</td>
                      <td className="border-b border-black/20 px-3 py-2">{p.activo ? 'Activo' : 'Deshabilitado'}</td>
                      <td className="border-b border-black/20 px-3 py-2">
                        <div className="flex flex-wrap gap-2">
                          {canEdit ? (
                            <a
                              href={`/products/edit/${p.id}/`}
                              className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-2.5 py-1.5 text-xs font-bold shadow"
                            >
                              Editar
                            </a>
                          ) : (
                            <button
                              type="button"
                              disabled
                              title="No tienes permiso para editar productos"
                              className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-2.5 py-1.5 text-xs font-bold shadow opacity-40 cursor-not-allowed"
                            >
                              Editar
                            </button>
                          )}
                          <button
                            type="button"
                            disabled={loading}
                            onClick={async () => {
                              const desired = !p.activo;
                              const label = desired ? 'habilitar' : 'deshabilitar';
                              const ok = window.confirm(`¿Está seguro que desea ${label} este producto?`);
                              if (!ok) return;
                              try {
                                setLoading(true);
                                setError('');
                                await apiPost<{ success: boolean; id: number; activo: boolean }>(
                                  `/products/set-active/${p.id}/`,
                                  { active: desired },
                                );
                                await load(page, search, perPage);
                              } catch (e: any) {
                                setError(e?.message || 'Error');
                              } finally {
                                setLoading(false);
                              }
                            }}
                            className={
                              'inline-flex items-center justify-center rounded-xl border-2 border-black px-2.5 py-1.5 text-xs font-bold shadow ' +
                              (p.activo ? 'bg-white' : 'bg-slate-200')
                            }
                          >
                            {p.activo ? 'Deshabilitar' : 'Habilitar'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3" colSpan={7}>
                      Sin resultados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between gap-2 border-t-2 border-black bg-slate-200 p-3">
            <div className="text-xs font-bold">Página {page} / {numPages}</div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1 || loading}
                onClick={() => load(Math.max(1, page - 1), search, perPage)}
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-xs font-black shadow disabled:opacity-50"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={page >= numPages || loading}
                onClick={() => load(Math.min(numPages, page + 1), search, perPage)}
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-xs font-black shadow disabled:opacity-50"
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>
      </div>

        <UploadReportBanner />
        <AssignStockModal
          open={assignOpen}
          onClose={() => setAssignOpen(false)}
          items={items.filter((p) => selectedIds.has(p.id))}
          onAssigned={async ({ assigned_count, failures }) => {
            await load(page, search, perPage);
            setSelectedIds(new Set());
            showToast(
              'success',
              `Productos asignados con éxito. Asignados: ${assigned_count}. Fallos: ${failures?.length || 0}`,
            );
          }}
        />
    </div>
  );
}
