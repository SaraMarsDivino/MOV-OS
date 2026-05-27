import { useEffect, useState } from 'react';
import { apiGet } from '../lib/api';

type SucursalItem = {
  id: number;
  nombre: string;
  direccion: string;
  telefono: string;
};

type SucursalesResponse = {
  items: SucursalItem[];
  total: number;
};

export default function SucursalesManagementPage() {
  const [items, setItems] = useState<SucursalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const run = async () => {
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
    run();
  }, []);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div>
            <h2 className="m-0 text-lg font-black text-slate-900">Gestión de Sucursales</h2>
            <div className="mt-1 text-sm text-slate-900/80">Total: {items.length}</div>
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

        <div className="rounded-2xl border-2 border-black bg-slate-300 shadow-lg">
          <div className="overflow-auto">
            <table className="min-w-full border-collapse text-sm text-slate-900">
              <thead className="bg-slate-200">
                <tr>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Nombre</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Dirección</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Teléfono</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="px-3 py-3" colSpan={4}>
                      Cargando…
                    </td>
                  </tr>
                ) : items.length ? (
                  items.map((s) => (
                    <tr key={s.id} className="odd:bg-white/20">
                      <td className="border-b border-black/20 px-3 py-2">{s.nombre || '-'}</td>
                      <td className="border-b border-black/20 px-3 py-2">{s.direccion || '-'}</td>
                      <td className="border-b border-black/20 px-3 py-2">{s.telefono || '-'}</td>
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
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3" colSpan={4}>
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
