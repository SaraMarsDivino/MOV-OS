import { useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

type UserItem = {
  id: number;
  username: string;
  email: string;
  is_superuser: boolean;
  is_staff: boolean;
  is_active: boolean;
};

type UsersResponse = {
  items: UserItem[];
  total: number;
};

export default function UsersManagementPage() {
  const [items, setItems] = useState<UserItem[]>([]);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError('');
        const data = await apiGet<UsersResponse>('/users/api/users/');
        setItems(data.items || []);
      } catch (e: any) {
        setError(e?.message || 'Error');
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const reload = async () => {
    const data = await apiGet<UsersResponse>('/users/api/users/');
    setItems(data.items || []);
  };

  const total = useMemo(() => items.length, [items]);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-6xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div>
            <h2 className="m-0 text-lg font-black text-slate-900">Gestión de Usuarios</h2>
            <div className="mt-1 text-sm text-slate-900/80">Total: {total}</div>
          </div>
          <a
            href="/users/management/create/"
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-3 py-2 text-sm font-bold text-slate-900 shadow"
          >
            Crear usuario
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
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">ID</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Usuario</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Email</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Rol</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Estado</th>
                  <th className="border-b-2 border-black px-3 py-2 text-left font-black">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="px-3 py-3" colSpan={6}>
                      Cargando…
                    </td>
                  </tr>
                ) : items.length ? (
                  items.map((u) => (
                    <tr key={u.id} className="odd:bg-white/20">
                      <td className="border-b border-black/20 px-3 py-2">{u.id}</td>
                      <td className="border-b border-black/20 px-3 py-2">{u.username}</td>
                      <td className="border-b border-black/20 px-3 py-2">{u.email}</td>
                      <td className="border-b border-black/20 px-3 py-2">
                        {u.is_superuser ? 'Admin' : u.is_staff ? 'Staff' : 'Usuario'}
                      </td>
                      <td className="border-b border-black/20 px-3 py-2">{u.is_active ? 'Activo' : 'Deshabilitado'}</td>
                      <td className="border-b border-black/20 px-3 py-2">
                        <div className="flex flex-wrap gap-2">
                          <a
                            href={`/users/management/edit/${u.id}/`}
                            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-200 px-2.5 py-1.5 text-xs font-bold shadow"
                          >
                            Editar
                          </a>
                          <button
                            type="button"
                            disabled={loading}
                            onClick={async () => {
                              const desired = !u.is_active;
                              const label = desired ? 'habilitar' : 'deshabilitar';
                              const ok = window.confirm(`¿Está seguro que desea ${label} este usuario?`);
                              if (!ok) return;
                              try {
                                setLoading(true);
                                setError('');
                                await apiPost<{ success: boolean; id: number; is_active: boolean }>(
                                  `/users/api/users/${u.id}/set-active/`,
                                  { active: desired },
                                );
                                await reload();
                              } catch (e: any) {
                                setError(e?.message || 'Error');
                              } finally {
                                setLoading(false);
                              }
                            }}
                            className={
                              'inline-flex items-center justify-center rounded-xl border-2 border-black px-2.5 py-1.5 text-xs font-bold shadow ' +
                              (u.is_active ? 'bg-white' : 'bg-slate-200')
                            }
                          >
                            {u.is_active ? 'Deshabilitar' : 'Habilitar'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3" colSpan={6}>
                      Sin usuarios.
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
