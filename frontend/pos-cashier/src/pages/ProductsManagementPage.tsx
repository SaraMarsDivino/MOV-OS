import { useEffect, useMemo, useRef, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';
import UploadReportBanner from '../components/UploadReportBanner';
import AssignStockModal from '../components/AssignStockModal';
import { formatCLP } from '../components/utils';

type SucursalStock = { sucursal: string; cantidad: number };
type SucursalOption = { id: number; nombre: string };
type CategoriaOption = { id: number; nombre: string };

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
  archivado: boolean;
  fecha_ingreso: string | null;
  categoria_id: number | null;
  categoria_nombre: string | null;
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
    setPos({ x: rect.right, y: above ? rect.top : rect.bottom, above });
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

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: CURRENT_YEAR - 2019 }, (_, i) => CURRENT_YEAR - i);

export default function ProductsManagementPage() {
  const ctx = getReactContext();
  const user = ctx.user || {};
  const sucursales: SucursalOption[] = ctx.sucursales || [];
  const categorias: CategoriaOption[] = ctx.categorias || [];
  const isAdmin = Boolean(user.is_superuser || user.is_staff);
  const canAdd     = isAdmin || Boolean(user.can_add_products);
  const canEdit    = isAdmin || Boolean(user.can_edit_products);
  const canExport  = isAdmin || Boolean(user.can_export_products);
  const canDisable = isAdmin || Boolean(user.can_disable_products);
  const canArchive = isAdmin || Boolean(user.can_archive_products);
  const canTransfer = isAdmin || Boolean(user.can_transfer_stock);
  const canAssign  = isAdmin || Boolean(user.can_assign_stock);

  const [searchDraft, setSearchDraft] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [perPage, setPerPage] = useState(10);
  const [sortBy, setSortBy] = useState<string>('nombre');
  const [orderBy, setOrderBy] = useState<'asc'|'desc'>('asc');
  const [hideInactive, setHideInactive] = useState<boolean>(
    () => localStorage.getItem('products_hide_inactive') === '1'
  );
  const [showArchivados, setShowArchivados] = useState(false);
  const [filterYear, setFilterYear] = useState('');
  const [filterMonth, setFilterMonth] = useState('');
  const [exportSucursalId, setExportSucursalId] = useState<string>('');
  const [filterCategoria, setFilterCategoria] = useState<string>('');
  const [filterSucursal, setFilterSucursal] = useState<string>('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const selectAllRef = useRef<HTMLInputElement | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const scannerTimerRef = useRef<number | null>(null);
  const scannerBurstRef = useRef<{ count: number; start: number; last: number }>({ count: 0, start: 0, last: 0 });

  const load = async (
    nextPage: number,
    nextSearch: string,
    nextPerPage = perPage,
    nextSortBy = sortBy,
    nextOrder = orderBy,
    nextHideInactive = hideInactive,
    nextShowArchivados = showArchivados,
    nextYear = filterYear,
    nextMonth = filterMonth,
    nextCategoria = filterCategoria,
    nextSucursal = filterSucursal,
  ) => {
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
        show_archivados: nextShowArchivados ? '1' : '0',
        ...(nextYear ? { year: nextYear } : {}),
        ...(nextMonth ? { month: nextMonth } : {}),
        ...(nextCategoria ? { categoria: nextCategoria } : {}),
        ...(nextSucursal ? { sucursal: nextSucursal } : {}),
      });
      const data = await apiGet<ProductsResponse>(`/products/api/products/?${qs.toString()}`);
      setItems(data.items || []);
      setPage(data.page || 1);
      setNumPages(data.num_pages || 1);
      setTotal(data.total || 0);
      setSelectedIds(new Set());
    } catch (e: any) {
      setError(e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(1, '', perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
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
    load(1, next, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
  };

  const changeSort = (field: string) => {
    const nextOrder = sortBy === field && orderBy === 'asc' ? 'desc' : 'asc';
    setSortBy(field);
    setOrderBy(nextOrder);
    load(1, search, perPage, field, nextOrder, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
  };

  const sortIcon = (field: string) => {
    if (sortBy !== field) return <span className="ml-1 opacity-30">↕</span>;
    return <span className="ml-1">{orderBy === 'asc' ? '↑' : '↓'}</span>;
  };

  const toggleHideInactive = () => {
    const next = !hideInactive;
    setHideInactive(next);
    localStorage.setItem('products_hide_inactive', next ? '1' : '0');
    load(1, search, perPage, sortBy, orderBy, next, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
  };

  const toggleArchivados = () => {
    const next = !showArchivados;
    setShowArchivados(next);
    load(1, search, perPage, sortBy, orderBy, hideInactive, next, filterYear, filterMonth, filterCategoria, filterSucursal);
  };

  const applyDateFilter = (year: string, month: string) => {
    setFilterYear(year);
    setFilterMonth(month);
    load(1, search, perPage, sortBy, orderBy, hideInactive, showArchivados, year, month, filterCategoria, filterSucursal);
  };

  const clearDateFilter = () => {
    setFilterYear('');
    setFilterMonth('');
    load(1, search, perPage, sortBy, orderBy, hideInactive, showArchivados, '', '', filterCategoria, filterSucursal);
  };

  const clearAllFilters = () => {
    setFilterYear('');
    setFilterMonth('');
    setFilterCategoria('');
    setFilterSucursal('');
    load(1, search, perPage, sortBy, orderBy, hideInactive, showArchivados, '', '', '', '');
  };

  const applyCategoria = (cat: string) => {
    setFilterCategoria(cat);
    load(1, search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, cat, filterSucursal);
  };

  const applySucursal = (suc: string) => {
    setFilterSucursal(suc);
    load(1, search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, suc);
  };

  const allSelected = useMemo(() => !!items.length && items.every((p) => selectedIds.has(p.id)), [items, selectedIds]);
  const someSelected = useMemo(() => items.some((p) => selectedIds.has(p.id)), [items, selectedIds]);

  useEffect(() => {
    if (!selectAllRef.current) return;
    selectAllRef.current.indeterminate = !allSelected && someSelected;
  }, [allSelected, someSelected]);

  const totalLabel = useMemo(() => (loading ? '…' : String(total)), [loading, total]);
  const selectedCount = selectedIds.size;

  const renderClp = (raw: string) => {
    const n = Number(raw);
    if (!Number.isFinite(n)) return '-';
    return `$${formatCLP(n)}`;
  };

  const handleArchivar = async (p: ProductItem, archivar: boolean) => {
    const accion = archivar ? 'archivar' : 'restaurar';
    const ok = window.confirm(`¿Seguro que quieres ${accion} "${p.nombre || p.producto_id}"?`);
    if (!ok) return;
    try {
      setLoading(true);
      await apiPost<{ success: boolean }>(`/products/archive/${p.id}/`, { archivar });
      await load(page, search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
      showToast('success', archivar ? 'Producto archivado.' : 'Producto restaurado.');
    } catch (e: any) {
      setError(e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  const hasDateFilter = filterYear !== '' || filterMonth !== '';

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 shadow-lg overflow-hidden">

          {/* ── Encabezado ────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-slate-900">
            <div>
              <h2 className="m-0 text-base font-black text-white">
                {showArchivados ? 'Papelera de productos' : 'Gestión de Productos'}
              </h2>
              <div className="mt-0.5 text-xs text-white/60">
                {loading ? '…' : `${totalLabel} producto${total !== 1 ? 's' : ''}${showArchivados ? ' archivados' : ''}`}
              </div>
            </div>
            {canArchive && (
              <button
                type="button"
                onClick={toggleArchivados}
                className={
                  'inline-flex items-center gap-1.5 rounded-xl border-2 px-3 py-1.5 text-sm font-black shadow transition-colors ' +
                  (showArchivados
                    ? 'border-amber-400 bg-amber-300 text-amber-950'
                    : 'border-white/30 bg-white/10 text-white hover:bg-white/20')
                }
                title={showArchivados ? 'Volver a la lista activa' : 'Ver productos archivados'}
              >
                {showArchivados ? '← Lista activa' : 'Papelera'}
              </button>
            )}
          </div>

          <div className="px-4 py-3 space-y-3">

          {/* ── Barra de acciones ─────────────────────────────────── */}
          <div className="flex flex-wrap items-end gap-4">

            {/* Grupo: Catálogo */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Catálogo</span>
              <div className="flex flex-wrap gap-1">
                {isAdmin && (
                  <a href="/products/categories/" className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow hover:bg-slate-50">
                    Categorías
                  </a>
                )}
                <a
                  href={canAdd ? '/products/create/' : undefined}
                  aria-disabled={!canAdd}
                  title={!canAdd ? 'Sin permiso para crear productos' : undefined}
                  className={
                    'inline-flex items-center justify-center rounded-xl border-2 border-black px-3 py-1.5 text-xs font-bold shadow ' +
                    (canAdd ? 'bg-slate-900 text-white hover:bg-slate-700' : 'bg-white text-slate-400 opacity-40 pointer-events-none')
                  }
                >
                  + Crear
                </a>
                <a
                  href={canAdd ? '/products/upload/' : undefined}
                  aria-disabled={!canAdd}
                  title={!canAdd ? 'Sin permiso para subir productos' : undefined}
                  className={
                    'inline-flex items-center justify-center rounded-xl border-2 border-black px-3 py-1.5 text-xs font-bold shadow ' +
                    (canAdd ? 'bg-white text-slate-900 hover:bg-slate-50' : 'bg-white text-slate-400 opacity-40 pointer-events-none')
                  }
                >
                  ↑ Subir Excel
                </a>
              </div>
            </div>

            {/* Grupo: Exportar */}
            {canExport && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Exportar</span>
                <div className="flex flex-wrap gap-1">
                  <select
                    value={exportSucursalId}
                    onChange={(e) => setExportSucursalId(e.target.value)}
                    className="rounded-xl border-2 border-black bg-white px-2 py-1.5 text-xs text-slate-900 shadow outline-none"
                    aria-label="Sucursal para exportar"
                  >
                    <option value="">Todas las sucursales</option>
                    {sucursales.map((s) => (
                      <option key={s.id} value={String(s.id)}>{s.nombre}</option>
                    ))}
                  </select>
                  <a
                    href={exportSucursalId ? `/products/exportar/excel/?sucursal_id=${exportSucursalId}` : '/products/exportar/excel/'}
                    className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-emerald-100 px-3 py-1.5 text-xs font-bold text-emerald-900 shadow hover:bg-emerald-200"
                    title={exportSucursalId ? `Exportar: ${sucursales.find((s) => String(s.id) === exportSucursalId)?.nombre}` : 'Exportar todos'}
                  >
                    ↓ Excel
                  </a>
                </div>
              </div>
            )}

            {/* Grupo: Stock */}
            {canTransfer && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Stock</span>
                <div className="flex flex-wrap gap-1">
                  <a href="/products/transfer/" className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow hover:bg-slate-50">
                    ⇄ Transferir
                  </a>
                  <a href="/products/stock/adjust/history/" className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow hover:bg-slate-50">
                    Historial ajustes
                  </a>
                </div>
              </div>
            )}

            {/* Grupo: Selección masiva */}
            {(canAssign || canDisable) && (
              <div className="flex flex-col gap-1.5 ml-auto">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                  Selección{selectedCount > 0 ? ` — ${selectedCount} selec.` : ''}
                </span>
                <div className="flex flex-wrap gap-1">
                  {canAssign && (
                    <button
                      type="button"
                      disabled={selectedCount <= 0 || loading || showArchivados}
                      onClick={() => { if (selectedCount > 0) setAssignOpen(true); }}
                      className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow disabled:opacity-40 hover:bg-slate-50"
                    >
                      Asignar stock
                    </button>
                  )}
                  {canDisable && (
                    <button
                      type="button"
                      disabled={selectedCount <= 0 || loading || showArchivados}
                      onClick={async () => {
                        if (selectedCount <= 0) return;
                        const ok = window.confirm(`¿Seguro que quieres deshabilitar ${selectedCount} producto(s)?`);
                        if (!ok) return;
                        try {
                          setLoading(true);
                          setError('');
                          await apiPost<{ success: boolean; deleted: number }>(`/products/bulk-delete/`, {
                            product_ids: Array.from(selectedIds),
                          });
                          const nextPage = selectedCount >= items.length && page > 1 ? Math.max(1, page - 1) : page;
                          await load(nextPage, search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
                        } catch (e: any) {
                          setError(e?.message || 'Error');
                        } finally {
                          setLoading(false);
                        }
                      }}
                      className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-rose-700 shadow disabled:opacity-40 hover:bg-rose-50"
                    >
                      Deshabilitar
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ── Búsqueda ──────────────────────────────────────────── */}
          <div className="flex flex-wrap gap-2 items-center border-t-2 border-black/10 pt-3">
            <input
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  triggerSearch(searchDraft);
                  return;
                }
                if (e.key.length !== 1) return;
                const now = Date.now();
                const burst = scannerBurstRef.current;
                if (!burst.last || now - burst.last > 80) {
                  burst.count = 0;
                  burst.start = now;
                }
                burst.count += 1;
                burst.last = now;
                if (scannerTimerRef.current) window.clearTimeout(scannerTimerRef.current);
                scannerTimerRef.current = window.setTimeout(() => {
                  const current = scannerBurstRef.current;
                  const duration = current.last - current.start;
                  const looksLikeScan = current.count >= 6 && duration <= 700;
                  current.count = 0; current.start = 0; current.last = 0;
                  if (!looksLikeScan) return;
                  triggerSearch(searchDraft);
                }, 140);
              }}
              placeholder="Buscar por nombre, código o código de barras…"
              className="min-w-0 flex-1 rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none"
            />
            <button
              type="button"
              onClick={() => triggerSearch(searchDraft)}
              className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-900 px-4 py-2 text-sm font-black text-white shadow hover:bg-slate-700"
            >
              Buscar
            </button>
            <button
              type="button"
              onClick={toggleHideInactive}
              className={
                'inline-flex items-center justify-center rounded-xl border-2 border-black px-3 py-2 text-sm font-bold shadow transition-colors ' +
                (hideInactive ? 'bg-slate-900 text-white' : 'bg-white text-slate-900 hover:bg-slate-50')
              }
              title={hideInactive ? 'Mostrando solo activos — clic para ver todos' : 'Clic para ocultar deshabilitados'}
            >
              {hideInactive ? 'Solo activos' : 'Todos'}
            </button>
            <select
              value={perPage}
              onChange={(e) => {
                const next = Number(e.target.value || 10);
                const normalized = next === 25 || next === 50 ? next : 10;
                setPerPage(normalized);
                load(1, search, normalized, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
              }}
              aria-label="Elementos por página"
              className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none"
            >
              <option value={10}>10 / pág</option>
              <option value={25}>25 / pág</option>
              <option value={50}>50 / pág</option>
            </select>
          </div>

          {/* ── Filtros ───────────────────────────────────────────── */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Filtros</span>
            {sucursales.length > 0 && (
              <select
                value={filterSucursal}
                onChange={(e) => applySucursal(e.target.value)}
                className={
                  'rounded-xl border-2 border-black bg-white px-2 py-1.5 text-xs text-slate-900 shadow outline-none ' +
                  (filterSucursal ? 'ring-2 ring-slate-900' : '')
                }
                aria-label="Filtrar por sucursal"
              >
                <option value="">Sucursal: todas</option>
                {sucursales.map((s) => (
                  <option key={s.id} value={String(s.id)}>{s.nombre}</option>
                ))}
              </select>
            )}
            {categorias.length > 0 && (
              <select
                value={filterCategoria}
                onChange={(e) => applyCategoria(e.target.value)}
                className={
                  'rounded-xl border-2 border-black bg-white px-2 py-1.5 text-xs text-slate-900 shadow outline-none ' +
                  (filterCategoria ? 'ring-2 ring-slate-900' : '')
                }
                aria-label="Filtrar por categoría"
              >
                <option value="">Categoría: todas</option>
                <option value="sin_categoria">Sin categoría</option>
                {categorias.map((c) => (
                  <option key={c.id} value={String(c.id)}>{c.nombre}</option>
                ))}
              </select>
            )}
            <select
              value={filterYear}
              onChange={(e) => {
                const y = e.target.value;
                applyDateFilter(y, y ? filterMonth : '');
              }}
              className={
                'rounded-xl border-2 border-black bg-white px-2 py-1.5 text-xs text-slate-900 shadow outline-none ' +
                (filterYear ? 'ring-2 ring-slate-900' : '')
              }
              aria-label="Filtrar por año"
            >
              <option value="">Año: todos</option>
              {YEARS.map((y) => <option key={y} value={String(y)}>{y}</option>)}
            </select>
            <select
              value={filterMonth}
              disabled={!filterYear}
              onChange={(e) => applyDateFilter(filterYear, e.target.value)}
              className={
                'rounded-xl border-2 border-black bg-white px-2 py-1.5 text-xs text-slate-900 shadow outline-none disabled:opacity-40 ' +
                (filterMonth ? 'ring-2 ring-slate-900' : '')
              }
              aria-label="Filtrar por mes"
            >
              <option value="">Mes: todos</option>
              {MESES.map((m, i) => <option key={i + 1} value={String(i + 1)}>{m}</option>)}
            </select>
            {(hasDateFilter || filterCategoria || filterSucursal) && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-slate-700 shadow hover:bg-slate-50"
              >
                ✕ Limpiar filtros
              </button>
            )}
          </div>

          </div>{/* /px-4 py-3 */}
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
                        if (!checked) { setSelectedIds(new Set()); return; }
                        setSelectedIds(new Set(items.map((p) => p.id)));
                      }}
                      aria-label="Seleccionar todo"
                    />
                  </th>
                  <th onClick={() => changeSort('nombre')} className="border-b-2 border-black px-3 py-2 text-left font-black cursor-pointer select-none">Nombre{sortIcon('nombre')}</th>
                  <th onClick={() => changeSort('codigo1')} className="border-b-2 border-black px-3 py-2 text-left font-black cursor-pointer select-none">Código{sortIcon('codigo1')}</th>
                  <th className="border-b-2 border-black px-3 py-2 text-right font-black">Stock</th>
                  <th className="border-b-2 border-black px-3 py-2 text-right font-black">Valor</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Categoría</th>
                  <th onClick={() => changeSort('fecha_ingreso')} className="border-b-2 border-black px-3 py-2 text-left font-black cursor-pointer select-none whitespace-nowrap">Fecha ingreso{sortIcon('fecha_ingreso')}</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Estado</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td className="px-3 py-3" colSpan={9}>Cargando…</td></tr>
                ) : items.length ? (
                  items.map((p) => (
                    <tr key={p.id} className={`odd:bg-white/20 ${p.archivado ? 'opacity-70' : ''}`}>
                      <td className="border-b border-black/20 px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(p.id)}
                          onChange={(e) => {
                            const checked = !!e.target.checked;
                            setSelectedIds((prev) => {
                              const next = new Set(prev);
                              if (checked) next.add(p.id); else next.delete(p.id);
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
                      <td className="border-b border-black/20 px-3 py-2">
                        {p.categoria_nombre
                          ? <span className="rounded-md bg-slate-100 border border-slate-300 px-2 py-0.5 text-xs font-bold text-slate-700">{p.categoria_nombre}</span>
                          : <span className="text-slate-400 text-xs">—</span>}
                      </td>
                      <td className="border-b border-black/20 px-3 py-2 whitespace-nowrap text-slate-600 text-xs">
                        {p.fecha_ingreso || <span className="text-slate-400">—</span>}
                      </td>
                      <td className="border-b border-black/20 px-3 py-2">
                        {p.archivado
                          ? <span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-black text-amber-800">Archivado</span>
                          : p.activo
                            ? <span className="text-emerald-700 text-xs font-bold">Activo</span>
                            : <span className="text-slate-500 text-xs">Deshabilitado</span>
                        }
                      </td>
                      <td className="border-b border-black/20 px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          {/* Acción primaria */}
                          {!p.archivado && canEdit && (
                            <a
                              href={`/products/edit/${p.id}/`}
                              className="inline-flex items-center justify-center rounded-lg border-2 border-black bg-slate-900 px-2.5 py-1 text-xs font-bold text-white shadow hover:bg-slate-700"
                            >
                              Editar
                            </a>
                          )}
                          {/* Separador visual si hay acción primaria y secundarias */}
                          {!p.archivado && canEdit && (canDisable || canArchive) && (
                            <div className="h-4 w-px bg-black/20 rounded-full" />
                          )}
                          {/* Habilitar / Deshabilitar */}
                          {!p.archivado && canDisable && (
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
                                  await load(page, search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
                                } catch (e: any) {
                                  setError(e?.message || 'Error');
                                } finally {
                                  setLoading(false);
                                }
                              }}
                              title={p.activo ? 'Deshabilitar producto (oculta del POS)' : 'Habilitar producto'}
                              className={
                                'inline-flex items-center justify-center rounded-lg border-2 border-black px-2.5 py-1 text-xs font-bold shadow ' +
                                (p.activo ? 'bg-white text-slate-700 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-400' : 'bg-slate-100 text-slate-600 hover:bg-slate-200')
                              }
                            >
                              {p.activo ? 'Deshab.' : 'Habilitar'}
                            </button>
                          )}
                          {/* Archivar / Restaurar */}
                          {canArchive && (
                            <button
                              type="button"
                              disabled={loading}
                              onClick={() => handleArchivar(p, !p.archivado)}
                              title={p.archivado ? 'Restaurar a la lista activa' : 'Archivar — oculta de la lista pero conserva historial'}
                              className={
                                'inline-flex items-center justify-center rounded-lg border-2 border-black px-2.5 py-1 text-xs font-bold shadow ' +
                                (p.archivado
                                  ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                                  : 'bg-white text-amber-700 hover:bg-amber-50 hover:border-amber-400')
                              }
                            >
                              {p.archivado ? 'Restaurar' : 'Archivar'}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr><td className="px-3 py-3" colSpan={9}>Sin resultados.</td></tr>
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
                onClick={() => load(Math.max(1, page - 1), search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal)}
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-xs font-black shadow disabled:opacity-50"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={page >= numPages || loading}
                onClick={() => load(Math.min(numPages, page + 1), search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal)}
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
          await load(page, search, perPage, sortBy, orderBy, hideInactive, showArchivados, filterYear, filterMonth, filterCategoria, filterSucursal);
          setSelectedIds(new Set());
          showToast('success', `Asignados: ${assigned_count}. Fallos: ${failures?.length || 0}`);
        }}
      />
    </div>
  );
}
