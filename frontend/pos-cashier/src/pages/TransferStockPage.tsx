import React, { useState, useEffect, useCallback, useRef } from 'react';

interface ProductResult {
  id: number;
  nombre: string;
  producto_id: string;
  codigo_barras: string | null;
}

interface Sucursal {
  id: number;
  nombre: string;
}

interface Transfer {
  id: number;
  fecha: string;
  producto: string;
  origen: string;
  destino: string;
  cantidad: number;
  usuario: string | null;
}

function getCsrf(): string {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ?? '';
}

function fmtDate(iso: string): string {
  const dt = new Date(iso);
  return (
    dt.toLocaleDateString('es-CL', { day: '2-digit', month: 'short' }) +
    ' ' +
    dt.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
  );
}

function StockPill({
  stock,
  loading,
  label,
}: {
  stock: number | null;
  loading: boolean;
  label: string;
}) {
  if (loading)
    return (
      <span className="inline-block rounded-lg bg-slate-100 text-slate-400 text-xs font-medium px-2.5 py-1">
        {label}: …
      </span>
    );
  if (stock === null)
    return (
      <span className="inline-block rounded-lg bg-slate-100 text-slate-400 text-xs font-medium px-2.5 py-1">
        {label}: —
      </span>
    );
  const bg =
    stock === 0
      ? 'bg-red-50 text-red-700'
      : stock < 5
        ? 'bg-amber-50 text-amber-700'
        : 'bg-emerald-50 text-emerald-700';
  return (
    <span className={`inline-block rounded-lg text-xs font-semibold px-2.5 py-1 ${bg}`}>
      {label}: {stock} u.
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2">
      {children}
    </p>
  );
}

function ProductSearchBox({
  selectedProduct,
  onSelect,
  onClear,
}: {
  selectedProduct: ProductResult | null;
  onSelect: (p: ProductResult) => void;
  onClear: () => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ProductResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const r = await fetch(`/products/api/product-search/?q=${encodeURIComponent(q)}`);
      const d = await r.json();
      const items: ProductResult[] = d.items ?? [];
      setResults(items);
      setOpen(items.length > 0);
    } catch {
      setResults([]);
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const handleSelect = (p: ProductResult) => {
    onSelect(p);
    setQuery('');
    setResults([]);
    setOpen(false);
  };

  const handleClear = () => {
    onClear();
    setQuery('');
    setResults([]);
    setOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  if (selectedProduct) {
    return (
      <div className="flex items-center gap-2 rounded-xl border-2 border-slate-900 bg-slate-50 px-3 py-2.5">
        <span className="flex-1 text-sm font-semibold text-slate-800 truncate">
          {selectedProduct.nombre}
          <span className="ml-2 text-xs font-normal text-slate-500">
            {selectedProduct.producto_id}
            {selectedProduct.codigo_barras ? ` · ${selectedProduct.codigo_barras}` : ''}
          </span>
        </span>
        <button
          type="button"
          onClick={handleClear}
          className="text-slate-400 hover:text-red-500 text-xl leading-none shrink-0 transition-colors"
          aria-label="Cambiar producto"
          title="Cambiar producto"
        >
          ×
        </button>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        autoComplete="off"
        className="w-full rounded-xl border-2 border-slate-200 px-3 py-2.5 text-sm focus:border-slate-900 outline-none"
        placeholder="Buscar por nombre, código o código de barras…"
        value={query}
        onChange={handleInput}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {loading && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none">
          Buscando…
        </span>
      )}
      {open && !loading && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border-2 border-slate-200 bg-white shadow-lg overflow-hidden">
          {results.length === 0 ? (
            <p className="text-xs text-slate-400 px-3 py-2.5">Sin resultados</p>
          ) : (
            results.map((p) => (
              <button
                key={p.id}
                type="button"
                className="w-full text-left px-3 py-2 text-sm hover:bg-slate-100 transition-colors flex items-center gap-2 border-b border-slate-100 last:border-b-0"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(p)}
              >
                <span className="font-medium text-slate-800 truncate flex-1">{p.nombre}</span>
                <span className="text-xs text-slate-400 shrink-0 tabular-nums">
                  {p.producto_id}
                  {p.codigo_barras ? ` · ${p.codigo_barras}` : ''}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function TransferStockPage() {
  const ctx = (
    window as unknown as {
      __MOVOS_REACT_CONTEXT__?: { sucursales?: Sucursal[] };
    }
  ).__MOVOS_REACT_CONTEXT__ ?? {};
  const sucursales: Sucursal[] = ctx.sucursales ?? [];

  const fromProduct = new URLSearchParams(window.location.search).get('from_product');
  const backHref = fromProduct ? `/products/edit/${fromProduct}/` : '/products/management/';
  const backLabel = fromProduct ? '← Volver al producto' : '← Volver a productos';
  const historyHref = fromProduct
    ? `/products/transfer/history/?from_product=${fromProduct}`
    : '/products/transfer/history/';

  const [selectedProduct, setSelectedProduct] = useState<ProductResult | null>(null);
  const [origenId, setOrigenId] = useState('');
  const [destinoId, setDestinoId] = useState('');
  const [cantidad, setCantidad] = useState('');
  const [stockOrigen, setStockOrigen] = useState<number | null>(null);
  const [stockDestino, setStockDestino] = useState<number | null>(null);
  const [loadingOrigen, setLoadingOrigen] = useState(false);
  const [loadingDestino, setLoadingDestino] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [history, setHistory] = useState<Transfer[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const productoId = selectedProduct ? String(selectedProduct.id) : '';

  const fetchStock = useCallback(
    async (type: 'origen' | 'destino', pId: string, sId: string) => {
      const setStock = type === 'origen' ? setStockOrigen : setStockDestino;
      const setLoading = type === 'origen' ? setLoadingOrigen : setLoadingDestino;
      setLoading(true);
      try {
        const r = await fetch(`/products/stock/availability/?producto_id=${pId}&sucursal_id=${sId}`);
        const d = await r.json();
        setStock(d.cantidad ?? null);
      } catch {
        setStock(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (productoId && origenId) fetchStock('origen', productoId, origenId);
    else setStockOrigen(null);
  }, [productoId, origenId, fetchStock]);

  useEffect(() => {
    if (productoId && destinoId) fetchStock('destino', productoId, destinoId);
    else setStockDestino(null);
  }, [productoId, destinoId, fetchStock]);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const r = await fetch('/products/api/transfer/history/?limit=10');
      const d = await r.json();
      setHistory(d.items ?? []);
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      const r = await fetch('/products/api/transfer/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({
          producto_id: parseInt(productoId),
          origen_id: parseInt(origenId),
          destino_id: parseInt(destinoId),
          cantidad: parseInt(cantidad),
        }),
      });
      const d = await r.json();
      if (!r.ok || d.error) {
        setError(d.error ?? 'Error al realizar la transferencia.');
      } else {
        setSuccess(d.message ?? 'Transferencia realizada correctamente.');
        setStockOrigen(d.nuevo_stock_origen ?? null);
        setStockDestino(d.nuevo_stock_destino ?? null);
        setCantidad('');
        loadHistory();
      }
    } catch {
      setError('Error de conexión. Intenta de nuevo.');
    } finally {
      setSubmitting(false);
    }
  };

  const cantidadNum = parseInt(cantidad) || 0;
  const exceedsStock =
    stockOrigen !== null && cantidadNum > 0 && cantidadNum > stockOrigen;

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4 md:p-6">
      {/* Page header */}
      <div className="mx-auto max-w-5xl mb-5 flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-extrabold text-slate-900 tracking-tight">
          Transferir Stock entre Sucursales
        </h1>
        <a
          href={backHref}
          className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-4 py-2 text-sm font-black text-slate-900 shadow hover:bg-slate-100 transition-colors"
        >
          {backLabel}
        </a>
      </div>

      {/* Two-column grid */}
      <div className="mx-auto max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">

        {/* ── LEFT: form card ── */}
        <div className="rounded-2xl border-2 border-black bg-white shadow-sm overflow-hidden">
          <div className="bg-slate-900 px-5 py-3">
            <h2 className="text-sm font-bold text-white">Nueva Transferencia</h2>
          </div>

          <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-5">
            {/* ── Section 1: Producto ── */}
            <div>
              <SectionLabel>Producto</SectionLabel>
              <ProductSearchBox
                selectedProduct={selectedProduct}
                onSelect={(p) => {
                  setSelectedProduct(p);
                  setError('');
                  setSuccess('');
                  setCantidad('');
                }}
                onClear={() => {
                  setSelectedProduct(null);
                  setStockOrigen(null);
                  setStockDestino(null);
                  setCantidad('');
                  setError('');
                  setSuccess('');
                }}
              />
            </div>

            <hr className="border-slate-100" />

            {/* ── Section 2: Ruta ── */}
            <div>
              <SectionLabel>Ruta de transferencia</SectionLabel>
              <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-2">
                {/* Origen */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-500">Origen</label>
                  <select
                    required
                    className="w-full rounded-xl border-2 border-slate-200 px-3 py-2.5 text-sm focus:border-slate-900 outline-none bg-white"
                    value={origenId}
                    onChange={(e) => setOrigenId(e.target.value)}
                  >
                    <option value="">Seleccione…</option>
                    {sucursales.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.nombre}
                      </option>
                    ))}
                  </select>
                  <StockPill stock={stockOrigen} loading={loadingOrigen} label="Disponible" />
                </div>

                {/* Arrow */}
                <div className="pt-7 text-slate-400 font-bold text-lg">→</div>

                {/* Destino */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-500">Destino</label>
                  <select
                    required
                    className="w-full rounded-xl border-2 border-slate-200 px-3 py-2.5 text-sm focus:border-slate-900 outline-none bg-white"
                    value={destinoId}
                    onChange={(e) => setDestinoId(e.target.value)}
                  >
                    <option value="">Seleccione…</option>
                    {sucursales.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.nombre}
                      </option>
                    ))}
                  </select>
                  <StockPill stock={stockDestino} loading={loadingDestino} label="Stock actual" />
                </div>
              </div>
            </div>

            <hr className="border-slate-100" />

            {/* ── Section 3: Cantidad ── */}
            <div>
              <SectionLabel>Cantidad a transferir</SectionLabel>
              <input
                type="number"
                min="1"
                max={stockOrigen !== null ? stockOrigen : undefined}
                required
                className={`w-full rounded-xl border-2 px-3 py-2.5 text-sm outline-none ${
                  exceedsStock
                    ? 'border-red-400 focus:border-red-500'
                    : 'border-slate-200 focus:border-slate-900'
                }`}
                placeholder={stockOrigen !== null ? `Máx. ${stockOrigen}` : 'Ej: 10'}
                value={cantidad}
                onChange={(e) => setCantidad(e.target.value)}
              />
              {stockOrigen !== null && !exceedsStock && cantidadNum === 0 && (
                <p className="text-xs text-slate-400 mt-1.5">
                  Stock disponible en origen: {stockOrigen} u.
                </p>
              )}
              {exceedsStock && (
                <p className="text-xs text-red-600 mt-1.5 font-medium">
                  ✕ Supera el stock disponible en origen ({stockOrigen} u.)
                </p>
              )}
            </div>

            {/* Feedback */}
            {error && (
              <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm p-3 leading-snug">
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm p-3 leading-snug">
                ✓ {success}
              </div>
            )}

            {/* Submit / Confirm */}
            {confirming ? (
              <div className="rounded-xl border-2 border-amber-400 bg-amber-50 p-4 flex flex-col gap-3">
                <p className="text-sm font-semibold text-amber-800 text-center">
                  ¿Está seguro que desea transferir{' '}
                  <span className="font-black">{cantidad} u.</span> de{' '}
                  <span className="font-black">{selectedProduct?.nombre}</span>?
                </p>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 rounded-xl bg-slate-900 text-white font-bold py-2.5 text-sm hover:bg-slate-700 disabled:opacity-50 transition-colors"
                  >
                    {submitting ? 'Transfiriendo…' : 'Sí, transferir'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(false)}
                    className="flex-1 rounded-xl border-2 border-slate-300 bg-white text-slate-700 font-bold py-2.5 text-sm hover:bg-slate-100 transition-colors"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="submit"
                disabled={submitting || exceedsStock || !selectedProduct}
                className="w-full rounded-xl bg-slate-900 text-white font-bold py-3 text-sm hover:bg-slate-700 disabled:opacity-50 transition-colors"
              >
                Transferir
              </button>
            )}
          </form>
        </div>

        {/* ── RIGHT: history card ── */}
        <div className="rounded-2xl border-2 border-black bg-white shadow-sm overflow-hidden flex flex-col">
          <div className="bg-slate-900 px-5 py-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Historial reciente</h2>
            <a
              href={historyHref}
              className="text-xs text-slate-300 hover:text-white font-medium transition-colors"
            >
              Ver todo →
            </a>
          </div>

          <div className="p-4 flex flex-col gap-2.5 overflow-y-auto flex-1">
            {loadingHistory ? (
              <p className="text-sm text-slate-400 text-center py-6">Cargando…</p>
            ) : history.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-2xl mb-1">📦</p>
                <p className="text-sm text-slate-400">Sin transferencias registradas</p>
              </div>
            ) : (
              history.map((t) => (
                <div
                  key={t.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-3 flex gap-3 items-start"
                >
                  <div className="rounded-lg bg-slate-900 text-white text-xs font-bold px-2.5 py-1.5 shrink-0 tabular-nums">
                    {t.cantidad} u.
                  </div>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate leading-snug">
                      {t.producto}
                    </p>
                    <p className="text-xs text-slate-500 truncate">
                      {t.origen} → {t.destino}
                    </p>
                    <p className="text-xs text-slate-400">
                      {fmtDate(t.fecha)}
                      {t.usuario ? ` · ${t.usuario}` : ''}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
