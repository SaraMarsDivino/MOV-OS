import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

type SucursalItem = {
  id: number;
  nombre: string;
  direccion: string;
  telefono: string;
  activo: boolean;
};

type SucursalesResponse = {
  items: SucursalItem[];
  total: number;
};

export default function SucursalesManagementPage() {
  const [items, setItems] = useState<SucursalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState<Record<number, boolean>>({});
  const [deleting, setDeleting] = useState<Record<number, boolean>>({});

  const fetchItems = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await apiGet<SucursalesResponse>('/sucursales/api/list/');
      setItems(data.items || []);
    } catch (e: any) {
      setError(e?.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchItems(); }, []);

  const handleToggleActivo = async (s: SucursalItem) => {
    if (toggling[s.id]) return;
    setToggling((t) => ({ ...t, [s.id]: true }));
    try {
      await apiPost(`/sucursales/api/${s.id}/toggle-activo/`, {});
      setItems((prev) => prev.map((x) => x.id === s.id ? { ...x, activo: !x.activo } : x));
    } catch (e: any) {
      alert(e?.message || 'Error al cambiar estado.');
    } finally {
      setToggling((t) => ({ ...t, [s.id]: false }));
    }
  };

  const handleDelete = async (s: SucursalItem) => {
    if (deleting[s.id]) return;
    const ok = window.confirm(`¿Eliminar la sucursal "${s.nombre}"?\n\nEsta acción es permanente y solo es posible si no tiene datos asociados.`);
    if (!ok) return;
    setDeleting((d) => ({ ...d, [s.id]: true }));
    try {
      await apiPost(`/sucursales/api/${s.id}/delete/`, {});
      setItems((prev) => prev.filter((x) => x.id !== s.id));
    } catch (e: any) {
      alert(e?.message || 'Error al eliminar.');
    } finally {
      setDeleting((d) => ({ ...d, [s.id]: false }));
    }
  };

  const active = items.filter((s) => s.activo);
  const inactive = items.filter((s) => !s.activo);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div>
            <h2 className="m-0 text-lg font-black text-slate-900">Gestión de Sucursales</h2>
            <div className="mt-1 text-sm text-slate-900/80">
              {active.length} activa{active.length !== 1 ? 's' : ''}
              {inactive.length > 0 && ` · ${inactive.length} deshabilitada${inactive.length !== 1 ? 's' : ''}`}
            </div>
          </div>
          <a
            href="/sucursales/create/"
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-bold text-slate-900 shadow"
          >
            Crear sucursal
          </a>
        </div>

        {error ? (
          <div className="mb-3 rounded-2xl border-2 border-black bg-white p-3 text-sm text-red-700 shadow">{error}</div>
        ) : null}

        <div className="rounded-2xl border-2 border-black bg-slate-300 shadow-lg overflow-hidden">
          <div className="overflow-auto">
            <table className="min-w-full border-collapse text-sm text-slate-900">
              <thead className="bg-slate-200">
                <tr>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Nombre</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Dirección</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Teléfono</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Estado</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="px-3 py-3" colSpan={5}>
                      Cargando…
                    </td>
                  </tr>
                ) : items.length ? (
                  items.map((s) => (
                    <tr key={s.id} className={s.activo ? 'odd:bg-white/20' : 'bg-slate-400/30'}>
                      <td className="border-b border-black/20 px-3 py-2 font-semibold">
                        {s.nombre || '-'}
                      </td>
                      <td className="border-b border-black/20 px-3 py-2">{s.direccion || '-'}</td>
                      <td className="border-b border-black/20 px-3 py-2">{s.telefono || '-'}</td>
                      <td className="border-b border-black/20 px-3 py-2">
                        {s.activo ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-800 border border-emerald-300">
                            Activa
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-slate-200 px-2 py-0.5 text-xs font-bold text-slate-600 border border-slate-400">
                            Deshabilitada
                          </span>
                        )}
                      </td>
                      <td className="border-b border-black/20 px-3 py-2">
                        <div className="flex flex-wrap gap-2">
                          <a
                            href={`/sucursales/edit/${s.id}/`}
                            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-2.5 py-1.5 text-xs font-bold shadow"
                          >
                            Editar
                          </a>
                          <a
                            href={`/sucursales/${s.id}/productos/`}
                            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-2.5 py-1.5 text-xs font-bold shadow"
                          >
                            Ver productos
                          </a>
                          <button
                            onClick={() => handleToggleActivo(s)}
                            disabled={!!toggling[s.id]}
                            className={`inline-flex items-center justify-center rounded-xl border-2 border-black px-2.5 py-1.5 text-xs font-bold shadow disabled:opacity-50 ${
                              s.activo
                                ? 'bg-amber-100 text-amber-900 hover:bg-amber-200'
                                : 'bg-emerald-100 text-emerald-900 hover:bg-emerald-200'
                            }`}
                          >
                            {toggling[s.id] ? '…' : s.activo ? 'Deshabilitar' : 'Reactivar'}
                          </button>
                          <button
                            onClick={() => handleDelete(s)}
                            disabled={!!deleting[s.id]}
                            className="inline-flex items-center justify-center rounded-xl border-2 border-red-700 bg-red-50 px-2.5 py-1.5 text-xs font-bold text-red-700 shadow hover:bg-red-100 disabled:opacity-50"
                          >
                            {deleting[s.id] ? '…' : 'Eliminar'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3" colSpan={5}>
                      No se han creado sucursales aún.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
