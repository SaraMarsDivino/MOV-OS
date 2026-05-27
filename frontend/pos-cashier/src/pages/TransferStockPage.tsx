import React, { useState, useEffect, useCallback } from 'react';

interface Product {
  id: number;
  nombre: string;
  producto_id: string;
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

function StockBadge({ stock, loading, label }: { stock: number | null; loading: boolean; label: string }) {
  if (loading) return <span className="text-xs text-slate-400">{label}: …</span>;
  if (stock === null) return <span className="text-xs text-slate-400">{label}: —</span>;
  const color =
    stock === 0 ? 'text-red-600' : stock < 5 ? 'text-amber-600' : 'text-emerald-600';
  return (
    <span className={`text-xs font-semibold ${color}`}>
      {label}: {stock} unid.
    </span>
  );
}

export default function TransferStockPage() {
  const ctx = (window as unknown as { __MOVOS_REACT_CONTEXT__?: { products?: Product[]; sucursales?: Sucursal[] } }).__MOVOS_REACT_CONTEXT__ ?? {};
  const products: Product[] = ctx.products ?? [];
  const sucursales: Sucursal[] = ctx.sucursales ?? [];

  const [productoId, setProductoId] = useState('');
  const [origenId, setOrigenId] = useState('');
  const [destinoId, setDestinoId] = useState('');
  const [cantidad, setCantidad] = useState('');
  const [stockOrigen, setStockOrigen] = useState<number | null>(null);
  const [stockDestino, setStockDestino] = useState<number | null>(null);
  const [loadingOrigen, setLoadingOrigen] = useState(false);
  const [loadingDestino, setLoadingDestino] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [history, setHistory] = useState<Transfer[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const fetchStock = useCallback(async (type: 'origen' | 'destino', pId: string, sId: string) => {
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
  }, []);

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
        setSuccess(d.message ?? 'Transferencia realizada.');
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

  const selectedProduct = products.find((p) => String(p.id) === productoId);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      {/* Header */}
      <div className="mx-auto max-w-5xl mb-4 flex items-center gap-3 flex-wrap">
        <a
          href="/products/management/"
          className="text-sm font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1"
        >
          ← Volver a Productos
        </a>
        <span className="text-slate-400 hidden sm:inline">|</span>
        <h1 className="text-xl font-bold text-slate-900">Transferir Stock entre Sucursales</h1>
      </div>

      {/* 2-column grid */}
      <div className="mx-auto max-w-5xl grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-4">

        {/* Left card: form */}
        <div className="rounded-2xl border-2 border-black bg-white p-5 shadow">
          <h2 className="text-base font-bold text-slate-900 mb-4">Nueva Transferencia</h2>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Producto */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                Producto *
              </label>
              <select
                required
                className="w-full rounded-xl border-2 border-slate-200 p-2.5 text-sm focus:border-slate-900 outline-none bg-white"
                value={productoId}
                onChange={(e) => setProductoId(e.target.value)}
              >
                <option value="">Seleccione un producto</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre} — {p.producto_id}
                  </option>
                ))}
              </select>
              {selectedProduct && (
                <p className="text-xs text-slate-400 mt-1">Código: {selectedProduct.producto_id}</p>
              )}
            </div>

            {/* Origen + Destino */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                  Origen *
                </label>
                <select
                  required
                  className="w-full rounded-xl border-2 border-slate-200 p-2.5 text-sm focus:border-slate-900 outline-none bg-white"
                  value={origenId}
                  onChange={(e) => setOrigenId(e.target.value)}
                >
                  <option value="">Seleccione</option>
                  {sucursales.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nombre}
                    </option>
                  ))}
                </select>
                <div className="mt-1.5">
                  <StockBadge stock={stockOrigen} loading={loadingOrigen} label="Disponible" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                  Destino *
                </label>
                <select
                  required
                  className="w-full rounded-xl border-2 border-slate-200 p-2.5 text-sm focus:border-slate-900 outline-none bg-white"
                  value={destinoId}
                  onChange={(e) => setDestinoId(e.target.value)}
                >
                  <option value="">Seleccione</option>
                  {sucursales.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nombre}
                    </option>
                  ))}
                </select>
                <div className="mt-1.5">
                  <StockBadge stock={stockDestino} loading={loadingDestino} label="Stock actual" />
                </div>
              </div>
            </div>

            {/* Cantidad */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                Cantidad *
              </label>
              <input
                type="number"
                min="1"
                required
                className="w-full rounded-xl border-2 border-slate-200 p-2.5 text-sm focus:border-slate-900 outline-none"
                placeholder="Ej: 10"
                value={cantidad}
                onChange={(e) => setCantidad(e.target.value)}
              />
              {stockOrigen !== null && cantidad && parseInt(cantidad) > stockOrigen && (
                <p className="text-xs text-amber-600 mt-1">
                  La cantidad supera el stock disponible ({stockOrigen} unid.)
                </p>
              )}
            </div>

            {/* Feedback */}
            {error && (
              <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm p-3">
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm p-3">
                {success}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-slate-900 text-white font-semibold py-2.5 text-sm hover:bg-slate-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Transfiriendo…' : 'Transferir'}
            </button>
          </form>
        </div>

        {/* Right card: recent history */}
        <div className="rounded-2xl border-2 border-black bg-white p-5 shadow flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-slate-900">Historial reciente</h2>
            <a
              href="/products/transfer/history/"
              className="text-xs text-slate-500 hover:text-slate-900 font-medium"
            >
              Ver todo →
            </a>
          </div>

          {loadingHistory ? (
            <div className="text-sm text-slate-400">Cargando…</div>
          ) : history.length === 0 ? (
            <div className="text-sm text-slate-400">Sin transferencias registradas.</div>
          ) : (
            <div className="flex flex-col gap-2 overflow-y-auto">
              {history.map((t) => (
                <div
                  key={t.id}
                  className="rounded-xl bg-slate-50 border border-slate-200 p-3 flex flex-col gap-0.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-slate-800 text-xs leading-snug">{t.producto}</span>
                    <span className="text-xs font-bold bg-slate-900 text-white rounded-full px-2 py-0.5 shrink-0">
                      {t.cantidad} u.
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    {t.origen} → {t.destino}
                  </div>
                  <div className="text-xs text-slate-400">
                    {fmtDate(t.fecha)}
                    {t.usuario ? ` · ${t.usuario}` : ''}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
