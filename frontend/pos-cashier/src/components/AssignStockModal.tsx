import React, { useEffect, useState } from 'react';
import { apiGet } from '../lib/api';
import { getCsrfToken } from '../lib/csrf';

type Item = { id: number; nombre: string; producto_id: string; stock: number; permitir_venta_sin_stock?: boolean };

type AllowMode = 'inherit' | 'allow' | 'deny';

type AssignStockModalProps = {
  open: boolean;
  items: Item[];
  onClose: () => void;
  onAssigned?: (result: { assigned_count: number; failures: any[] }) => void;
};

export default function AssignStockModal({ open, items, onClose, onAssigned }: AssignStockModalProps) {
  const [sucursales, setSucursales] = useState<Array<{ id: number; nombre: string }>>([]);
  const [sucursalId, setSucursalId] = useState<number | null>(null);
  const [defaultQty, setDefaultQty] = useState<number>(1);
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [allowOverrides, setAllowOverrides] = useState<Record<number, AllowMode>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const data = await apiGet<{ items: { id: number; nombre: string }[] }>('/sucursales/api/list/');
        setSucursales(data.items || []);
        if (data.items && data.items.length) setSucursalId(data.items[0].id);
      } catch (e: any) {
        setError(e?.message || 'Error cargando sucursales');
      }
    })();
  }, [open]);

  useEffect(() => {
    const q: Record<number, number> = {};
    items.forEach((i) => {
      q[i.id] = defaultQty;
    });
    setQuantities(q);
  }, [items, defaultQty]);

  useEffect(() => {
    const next: Record<number, AllowMode> = {};
    items.forEach((i) => {
      next[i.id] = 'inherit';
    });
    setAllowOverrides(next);
  }, [items]);

  if (!open) return null;

  const handleAssign = async () => {
    if (!sucursalId) {
      setError('Seleccione una sucursal');
      return;
    }
    const payload = {
      sucursal_id: sucursalId,
      items: items.map((it) => {
        const mode = allowOverrides[it.id] || 'inherit';
        const allow = mode === 'inherit' ? null : mode === 'allow';
        return {
          codigo: it.producto_id,
          id: it.id,
          cantidad: Number(quantities[it.id] || 0),
          permitir_venta_sin_stock: allow,
        };
      }),
    };
    try {
      setLoading(true);
      setError('');
      const resp = await fetch('/products/bulk-assign/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
          Accept: 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const ct = resp.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        // Avoid auto-redirecting the whole app; show a local error instead.
        throw new Error('Respuesta no válida del servidor (no JSON). ¿Sesión expirada o permisos insuficientes?');
      }

      const res = (await resp.json()) as any;
      if (!resp.ok || !res?.success) {
        throw new Error(res?.error || `HTTP ${resp.status}`);
      }

      if (onAssigned) onAssigned({ assigned_count: res.assigned_count || 0, failures: res.failures || [] });
      onClose();
    } catch (e: any) {
      setError(e?.message || 'Error en la petición');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-w-3xl w-full rounded-2xl border-2 border-black bg-white p-4 shadow-lg">
        <div className="flex items-center justify-between">
          <h3 className="font-black">Asignar stock a sucursal</h3>
          <button onClick={onClose} className="rounded-xl border-2 border-black bg-white px-3 py-1 text-sm font-bold">Cerrar</button>
        </div>
        <div className="mt-3 grid gap-3">
          <div className="flex gap-2">
            <select value={String(sucursalId || '')} onChange={(e) => setSucursalId(Number(e.target.value || 0))} className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900">
              <option value="">-- Seleccione sucursal --</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </select>
            <input type="number" min={0} value={defaultQty} onChange={(e) => setDefaultQty(Number(e.target.value || 0))} className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900" />
            <div className="text-sm text-slate-700 py-2">Cantidad por defecto</div>
          </div>

          <div className="max-h-64 overflow-auto border-2 border-black/10 rounded-lg p-2">
            <table className="min-w-full text-sm">
              <thead>
                <tr>
                  <th className="text-left font-black">Nombre</th>
                  <th className="text-left font-black">Código</th>
                  <th className="text-right font-black">Stock</th>
                  <th className="text-left font-black">Venta sin stock</th>
                  <th className="text-right font-black">Cantidad</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id} className="odd:bg-white/20">
                    <td className="py-2 pr-2">{it.nombre}</td>
                    <td className="py-2 pr-2">{it.producto_id}</td>
                    <td className="py-2 pr-2 text-right">{it.stock}</td>
                    <td className="py-2 pr-2">
                      <select
                        value={allowOverrides[it.id] || 'inherit'}
                        onChange={(e) => {
                          const v = e.target.value as AllowMode;
                          setAllowOverrides((prev) => ({ ...prev, [it.id]: v }));
                        }}
                        className="rounded-xl border-2 border-black bg-white px-2 py-1 text-xs text-slate-900"
                      >
                        <option value="inherit">Usar global ({it.permitir_venta_sin_stock ? 'Si' : 'No'})</option>
                        <option value="allow">Permitir</option>
                        <option value="deny">No permitir</option>
                      </select>
                    </td>
                    <td className="py-2 pr-2 text-right">
                      <input
                        type="number"
                        min={0}
                        value={quantities[it.id] ?? defaultQty}
                        onChange={(e) => {
                          const v = Number(e.target.value || 0);
                          setQuantities((prev) => ({ ...prev, [it.id]: v }));
                        }}
                        className="w-20 rounded-xl border-2 border-black bg-white px-2 py-1 text-sm text-slate-900"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {error ? <div className="text-sm text-red-700">{error}</div> : null}

          <div className="mt-3 flex justify-end gap-2">
            <button onClick={onClose} className="rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-bold">
              Cancelar
            </button>
            <button onClick={handleAssign} disabled={loading} className="rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-black shadow disabled:opacity-50">
              {loading ? 'Enviando…' : 'Asignar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
