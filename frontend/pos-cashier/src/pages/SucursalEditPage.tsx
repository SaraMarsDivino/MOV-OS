import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

const inputCls =
  'w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none';
const labelCls = 'mb-1 block text-sm font-black text-slate-900';

function getCtx() {
  return (window as any).__MOVOS_REACT_CONTEXT__ || {};
}

export default function SucursalEditPage() {
  const ctx = getCtx();
  const id: number = ctx.sucursal_id;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [nombre, setNombre] = useState('');
  const [direccion, setDireccion] = useState('');
  const [telefono, setTelefono] = useState('');
  const [threshold, setThreshold] = useState('0');

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const res = await apiGet<{ item: any }>(`/sucursales/api/${id}/`);
        const s = res.item;
        setNombre(s.nombre || '');
        setDireccion(s.direccion || '');
        setTelefono(s.telefono || '');
        setThreshold(String(s.low_stock_threshold ?? 0));
      } catch (e: any) {
        setError(e?.message || 'Error cargando sucursal');
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const submit = async () => {
    const n = nombre.trim();
    if (!n) { setError('El nombre es obligatorio.'); return; }
    try {
      setSaving(true);
      setError('');
      await apiPost(`/sucursales/api/${id}/update/`, {
        nombre: n,
        direccion: direccion.trim(),
        telefono: telefono.trim(),
        low_stock_threshold: parseInt(threshold) || 0,
      });
      window.location.href = '/sucursales/';
    } catch (e: any) {
      setError(e?.message || 'Error al guardar cambios');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-4 text-slate-900">Cargando…</div>;

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-3xl">

        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div className="flex items-center justify-between gap-3">
            <h2 className="m-0 text-lg font-black text-slate-900">
              Editar Sucursal{nombre ? `: ${nombre}` : ''}
            </h2>
            <a href="/sucursales/"
              className="inline-flex shrink-0 items-center justify-center rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-black text-slate-900 shadow hover:bg-slate-100">
              ← Volver
            </a>
          </div>
        </div>

        {error && (
          <div className="mb-3 rounded-2xl border-2 border-black bg-white p-3 text-sm text-red-700 shadow">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">

          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className="mb-3 text-sm font-black uppercase tracking-wide text-slate-900">Datos principales</h3>
            <div className="mb-3">
              <label className={labelCls}>
                Nombre <span className="text-red-600">*</span>
              </label>
              <input
                className={inputCls}
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
              />
            </div>
            <div>
              <label className={labelCls}>Dirección</label>
              <input
                className={inputCls}
                value={direccion}
                onChange={(e) => setDireccion(e.target.value)}
              />
            </div>
          </div>

          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className="mb-3 text-sm font-black uppercase tracking-wide text-slate-900">Contacto y configuración</h3>
            <div className="mb-3">
              <label className={labelCls}>Teléfono</label>
              <input
                className={inputCls}
                value={telefono}
                onChange={(e) => setTelefono(e.target.value)}
              />
            </div>
            <div>
              <label className={labelCls}>Umbral de stock bajo</label>
              <input
                type="number"
                min="0"
                className={inputCls}
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
              />
              <p className="mt-1 text-xs text-slate-600">0 = usa el umbral global del sistema.</p>
            </div>
          </div>
        </div>

        <div className="mt-3 flex gap-2">
          <button
            onClick={submit}
            disabled={saving}
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-900 px-5 py-2 text-sm font-black text-white shadow disabled:opacity-50"
          >
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </button>
          <a
            href="/sucursales/"
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-5 py-2 text-sm font-black text-slate-900 shadow"
          >
            Cancelar
          </a>
        </div>

      </div>
    </div>
  );
}
