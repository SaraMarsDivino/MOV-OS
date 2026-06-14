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

interface TransferItem {
  product: ProductResult;
  cantidad: string;
  stockOrigen: number | null;
  loadingStock: boolean;
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

function StockPill({ stock, loading, label }: { stock: number | null; loading: boolean; label: string }) {
  if (loading)
    return <span className="inline-block rounded-lg bg-slate-100 text-slate-600 text-xs font-medium px-2.5 py-1">{label}: …</span>;
  if (stock === null)
    return <span className="inline-block rounded-lg bg-slate-100 text-slate-600 text-xs font-medium px-2.5 py-1">{label}: —</span>;
  const bg = stock === 0 ? 'bg-red-100 text-red-800' : stock < 5 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800';
  return (
    <span className={`inline-block rounded-lg text-xs font-bold px-2.5 py-1 ${bg}`}>
      {label}: {stock} u.
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-black text-slate-600 uppercase tracking-widest mb-2">
      {children}
    </p>
  );
}

function ProductSearchBox({ onAdd }: { onAdd: (p: ProductResult) => void }) {
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

  const search = useCallback(
    async (q: string) => {
      if (!q.trim()) { setResults([]); setOpen(false); return; }
      setLoading(true);
      try {
        const r = await fetch(`/products/api/product-search/?q=${encodeURIComponent(q)}`);
        const d = await r.json();
        const items: ProductResult[] = d.items ?? [];
        // Auto-add if exact barcode match (scanner UX)
        if (items.length === 1 && items[0].codigo_barras === q.trim()) {
          onAdd(items[0]);
          setQuery('');
          setResults([]);
          setOpen(false);
          return;
        }
        setResults(items);
        setOpen(items.length > 0);
      } catch {
        setResults([]);
        setOpen(false);
      } finally {
        setLoading(false);
      }
    },
    [onAdd],
  );

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const handleSelect = (p: ProductResult) => {
    onAdd(p);
    setQuery('');
    setResults([]);
    setOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        autoComplete="off"
        className="w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm font-medium text-slate-900 placeholder:text-slate-500 focus:border-slate-900 outline-none"
        placeholder="Escanear código de barras o buscar por nombre…"
        value={query}
        onChange={handleInput}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {loading && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs pointer-events-none">
          Buscando…
        </span>
      )}
      {open && !loading && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border-2 border-slate-300 bg-white shadow-lg overflow-hidden">
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              className="w-full text-left px-3 py-2.5 text-sm hover:bg-slate-100 transition-colors flex items-center gap-2 border-b border-slate-200 last:border-b-0"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleSelect(p)}
            >
              <span className="font-semibold text-slate-900 truncate flex-1">{p.nombre}</span>
              <span className="text-xs text-slate-600 shrink-0 tabular-nums">
                {p.producto_id}
                {p.codigo_barras ? ` · ${p.codigo_barras}` : ''}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TransferStockPage() {
  const ctx = (window as unknown as { __MOVOS_REACT_CONTEXT__?: { sucursales?: Sucursal[] } }).__MOVOS_REACT_CONTEXT__ ?? {};
  const sucursales: Sucursal[] = ctx.sucursales ?? [];

  const fromProduct = new URLSearchParams(window.location.search).get('from_product');
  const backHref = fromProduct ? `/products/edit/${fromProduct}/` : '/products/management/';
  const backLabel = fromProduct ? '← Volver al producto' : '← Volver a productos';
  const historyHref = fromProduct ? `/products/transfer/history/?from_product=${fromProduct}` : '/products/transfer/history/';

  const [origenId, setOrigenId] = useState('');
  const [destinoId, setDestinoId] = useState('');
  const [transferItems, setTransferItems] = useState<TransferItem[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [history, setHistory] = useState<Transfer[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const fetchStockForProduct = useCallback(async (productId: number, sucId: string) => {
    const r = await fetch(`/products/stock/availability/?producto_id=${productId}&sucursal_id=${sucId}`);
    const d = await r.json();
    return (d.cantidad as number) ?? null;
  }, []);

  // Re-fetch stock for all items when origen changes
  useEffect(() => {
    if (!origenId) {
      setTransferItems(prev => prev.map(it => ({ ...it, stockOrigen: null, loadingStock: false })));
      return;
    }
    setTransferItems(prev => prev.map(it => ({ ...it, loadingStock: true })));
    transferItems.forEach(async (it) => {
      try {
        const stock = await fetchStockForProduct(it.product.id, origenId);
        setTransferItems(prev => prev.map(ti =>
          ti.product.id === it.product.id ? { ...ti, stockOrigen: stock, loadingStock: false } : ti
        ));
      } catch {
        setTransferItems(prev => prev.map(ti =>
          ti.product.id === it.product.id ? { ...ti, stockOrigen: null, loadingStock: false } : ti
        ));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origenId]);

  const addProduct = useCallback(async (p: ProductResult) => {
    setTransferItems(prev => {
      if (prev.some(it => it.product.id === p.id)) return prev;
      return [...prev, { product: p, cantidad: '1', stockOrigen: null, loadingStock: !!origenId }];
    });
    if (origenId) {
      try {
        const stock = await fetchStockForProduct(p.id, origenId);
        setTransferItems(prev => prev.map(it =>
          it.product.id === p.id ? { ...it, stockOrigen: stock, loadingStock: false } : it
        ));
      } catch {
        setTransferItems(prev => prev.map(it =>
          it.product.id === p.id ? { ...it, stockOrigen: null, loadingStock: false } : it
        ));
      }
    }
    setError('');
    setSuccess('');
  }, [origenId, fetchStockForProduct]);

  const removeItem = (productId: number) => {
    setTransferItems(prev => prev.filter(it => it.product.id !== productId));
  };

  const updateCantidad = (productId: number, val: string) => {
    setTransferItems(prev => prev.map(it => it.product.id === productId ? { ...it, cantidad: val } : it));
  };

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const r = await fetch('/products/api/transfer/history/?limit=15');
      const d = await r.json();
      setHistory(d.items ?? []);
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const hasErrors = transferItems.some(it => {
    const qty = parseInt(it.cantidad) || 0;
    return qty <= 0 || (it.stockOrigen !== null && qty > it.stockOrigen);
  });

  const canSubmit = transferItems.length > 0 && origenId && destinoId && !hasErrors && !submitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    if (!confirming) { setConfirming(true); return; }
    setConfirming(false);
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      const r = await fetch('/products/api/transfer/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({
          origen_id: parseInt(origenId),
          destino_id: parseInt(destinoId),
          items: transferItems.map(it => ({
            producto_id: it.product.id,
            cantidad: parseInt(it.cantidad),
          })),
        }),
      });
      const d = await r.json();
      if (!r.ok || d.error) {
        setError(d.error ?? 'Error al realizar la transferencia.');
      } else {
        setSuccess(d.message ?? 'Transferencia realizada correctamente.');
        setTransferItems([]);
        loadHistory();
      }
    } catch {
      setError('Error de conexión. Intenta de nuevo.');
    } finally {
      setSubmitting(false);
    }
  };

  const origenNombre = sucursales.find(s => String(s.id) === origenId)?.nombre ?? '';
  const destinoNombre = sucursales.find(s => String(s.id) === destinoId)?.nombre ?? '';

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4 md:p-6">
      {/* Header */}
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

      <div className="mx-auto max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">

        {/* ── LEFT: form ── */}
        <div className="rounded-2xl border-2 border-black bg-white shadow-sm overflow-hidden">
          <div className="bg-slate-900 px-5 py-3">
            <h2 className="text-sm font-bold text-white">Nueva Transferencia</h2>
          </div>

          <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-5">

            {/* ── Ruta ── */}
            <div>
              <SectionLabel>Ruta de transferencia</SectionLabel>
              <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-2">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-700">Origen</label>
                  <select
                    required
                    className="w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm font-medium text-slate-900 focus:border-slate-900 outline-none bg-white"
                    value={origenId}
                    onChange={(e) => setOrigenId(e.target.value)}
                  >
                    <option value="">Seleccione…</option>
                    {sucursales.map((s) => (
                      <option key={s.id} value={s.id}>{s.nombre}</option>
                    ))}
                  </select>
                </div>
                <div className="pt-7 text-slate-700 font-black text-lg">→</div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-700">Destino</label>
                  <select
                    required
                    className="w-full rounded-xl border-2 border-slate-300 px-3 py-2.5 text-sm font-medium text-slate-900 focus:border-slate-900 outline-none bg-white"
                    value={destinoId}
                    onChange={(e) => setDestinoId(e.target.value)}
                  >
                    <option value="">Seleccione…</option>
                    {sucursales.map((s) => (
                      <option key={s.id} value={s.id}>{s.nombre}</option>
                    ))}
                  </select>
                </div>
              </div>
              {origenId && destinoId && origenId === destinoId && (
                <p className="text-xs text-red-700 font-semibold mt-2">El origen y destino no pueden ser iguales.</p>
              )}
            </div>

            <hr className="border-slate-200" />

            {/* ── Agregar producto ── */}
            <div>
              <SectionLabel>Agregar producto</SectionLabel>
              <ProductSearchBox onAdd={addProduct} />
              <p className="text-xs text-slate-600 mt-1.5">
                Busca por nombre, código o escanea el código de barras para agregar a la lista.
              </p>
            </div>

            {/* ── Lista de productos ── */}
            {transferItems.length > 0 && (
              <>
                <hr className="border-slate-200" />
                <div>
                  <SectionLabel>Productos a transferir ({transferItems.length})</SectionLabel>
                  <div className="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1">
                    {transferItems.map((item) => {
                      const qty = parseInt(item.cantidad) || 0;
                      const exceeds = item.stockOrigen !== null && qty > 0 && qty > item.stockOrigen;
                      return (
                        <div
                          key={item.product.id}
                          className={`rounded-xl border-2 p-3 flex flex-col gap-2 ${exceeds ? 'border-red-400 bg-red-50' : 'border-slate-200 bg-slate-50'}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="text-sm font-bold text-slate-900 leading-snug truncate">
                                {item.product.nombre}
                              </p>
                              <p className="text-xs text-slate-600 tabular-nums">
                                {item.product.producto_id}
                                {item.product.codigo_barras ? ` · ${item.product.codigo_barras}` : ''}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => removeItem(item.product.id)}
                              className="text-slate-400 hover:text-red-600 text-xl leading-none shrink-0 transition-colors font-bold"
                              title="Eliminar"
                            >
                              ×
                            </button>
                          </div>
                          <div className="flex items-center gap-3">
                            <StockPill stock={item.stockOrigen} loading={item.loadingStock} label="Disponible en origen" />
                            <div className="flex items-center gap-1.5 ml-auto">
                              <label className="text-xs font-bold text-slate-700 shrink-0">Cantidad:</label>
                              <input
                                type="number"
                                min="1"
                                max={item.stockOrigen !== null ? item.stockOrigen : undefined}
                                value={item.cantidad}
                                onChange={(e) => updateCantidad(item.product.id, e.target.value)}
                                className={`w-20 rounded-lg border-2 px-2 py-1 text-sm font-bold text-slate-900 text-center outline-none ${exceeds ? 'border-red-400 focus:border-red-500' : 'border-slate-300 focus:border-slate-900'}`}
                              />
                            </div>
                          </div>
                          {exceeds && (
                            <p className="text-xs text-red-700 font-semibold">
                              ✕ Supera el stock disponible ({item.stockOrigen} u.)
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            {/* Feedback */}
            {error && (
              <div className="rounded-xl bg-red-50 border-2 border-red-300 text-red-800 text-sm font-medium p-3 leading-snug">
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-xl bg-emerald-50 border-2 border-emerald-300 text-emerald-800 text-sm font-semibold p-3 leading-snug">
                ✓ {success}
              </div>
            )}

            {/* Submit / Confirm */}
            {confirming ? (
              <div className="rounded-xl border-2 border-amber-400 bg-amber-50 p-4 flex flex-col gap-3">
                <p className="text-sm font-bold text-amber-900 text-center">
                  ¿Confirmar transferencia?
                </p>
                <p className="text-xs text-amber-800 text-center">
                  {origenNombre} → {destinoNombre} · {transferItems.length} producto(s)
                </p>
                <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                  {transferItems.map(it => (
                    <div key={it.product.id} className="flex justify-between text-xs text-amber-900 font-medium">
                      <span className="truncate mr-2">{it.product.nombre}</span>
                      <span className="shrink-0 font-black">{it.cantidad} u.</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 mt-1">
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
                    className="flex-1 rounded-xl border-2 border-slate-400 bg-white text-slate-800 font-bold py-2.5 text-sm hover:bg-slate-100 transition-colors"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="submit"
                disabled={!canSubmit || origenId === destinoId}
                className="w-full rounded-xl bg-slate-900 text-white font-bold py-3 text-sm hover:bg-slate-700 disabled:opacity-40 transition-colors"
              >
                {transferItems.length === 0
                  ? 'Agrega productos para transferir'
                  : `Transferir ${transferItems.length} producto(s)`}
              </button>
            )}
          </form>
        </div>

        {/* ── RIGHT: history ── */}
        <div className="rounded-2xl border-2 border-black bg-white shadow-sm overflow-hidden flex flex-col">
          <div className="bg-slate-900 px-5 py-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Historial reciente</h2>
            <a
              href={historyHref}
              className="text-xs text-slate-300 hover:text-white font-semibold transition-colors"
            >
              Ver todo →
            </a>
          </div>

          <div className="p-4 flex flex-col gap-2.5 overflow-y-auto max-h-[480px]">
            {loadingHistory ? (
              <p className="text-sm text-slate-600 text-center py-6">Cargando…</p>
            ) : history.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-2xl mb-1">📦</p>
                <p className="text-sm text-slate-600 font-medium">Sin transferencias registradas</p>
              </div>
            ) : (
              history.map((t) => (
                <div
                  key={t.id}
                  className="rounded-xl border-2 border-slate-200 bg-slate-50 p-3 flex gap-3 items-start"
                >
                  <div className="rounded-lg bg-slate-900 text-white text-xs font-black px-2.5 py-1.5 shrink-0 tabular-nums">
                    {t.cantidad} u.
                  </div>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate leading-snug">
                      {t.producto}
                    </p>
                    <p className="text-xs text-slate-700 font-medium truncate">
                      {t.origen} → {t.destino}
                    </p>
                    <p className="text-xs text-slate-600">
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
