import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

type SucursalItem = { id: number; nombre: string; display_name?: string };

const inputCls =
  'w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none';
const labelCls = 'mb-1 block text-sm font-black text-slate-900';
const checkRowCls =
  'flex cursor-pointer items-center gap-3 rounded-xl border-2 border-black bg-white px-3 py-2.5 text-sm font-bold text-slate-900 shadow-sm transition-colors hover:bg-slate-100';

export default function UserEditPage() {
  const path = window.location.pathname || '';
  const parts = path.split('/').filter(Boolean);
  const id = parts[parts.indexOf('edit') + 1];

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [isSuper, setIsSuper] = useState(false);
  const [canAdd, setCanAdd] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [canView, setCanView] = useState(false);
  const [sucursales, setSucursales] = useState<SucursalItem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const [uRes, sRes] = await Promise.all([
          apiGet<any>(`/users/api/users/${id}/`),
          apiGet<{ items: SucursalItem[] }>('/users/api/user-sucursales/'),
        ]);
        const u = uRes.item;
        setUsername(u.username || '');
        setEmail(u.email || '');
        setIsSuper(Boolean(u.is_superuser));
        setCanAdd(Boolean(u.can_add_products));
        setCanEdit(Boolean(u.can_edit_products));
        setCanView(Boolean(u.can_view_analytics));
        setSelected(u.sucursales_autorizadas || []);
        setSucursales(sRes.items || []);
      } catch (e: any) {
        setError(e?.message || 'Error cargando usuario');
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const toggleSucursal = (sid: number) =>
    setSelected((cur) => (cur.includes(sid) ? cur.filter((x) => x !== sid) : [...cur, sid]));

  const submit = async () => {
    if (password && password !== password2) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    try {
      setSaving(true);
      setError('');
      const payload: Record<string, unknown> = {
        email,
        is_superuser: isSuper,
        can_add_products: canAdd,
        can_edit_products: canEdit,
        can_view_analytics: canView,
        sucursales_autorizadas: selected,
      };
      if (password) payload.password = password;
      await apiPost(`/users/api/users/${id}/update/`, payload);
      window.location.href = '/users/management/';
    } catch (e: any) {
      setError(e?.message || 'Error al guardar cambios');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-4 text-slate-900">Cargando…</div>;

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-5xl">

        {/* Header */}
        <div className="mb-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h2 className="m-0 text-lg font-black text-slate-900">
            Editar Usuario{username ? `: ${username}` : ''}
          </h2>
        </div>

        {error && (
          <div className="mb-3 rounded-2xl border-2 border-black bg-white p-3 text-sm text-red-700 shadow">
            {error}
          </div>
        )}

        {/* Grid principal: datos | permisos */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">

          {/* Columna izquierda — Datos del usuario */}
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className="mb-3 text-sm font-black text-slate-900 uppercase tracking-wide">
              Datos del usuario
            </h3>
            <div className="mb-3">
              <label className={labelCls}>Nombre de usuario</label>
              <input
                className={inputCls + ' opacity-60 cursor-not-allowed'}
                value={username}
                disabled
                title="El nombre de usuario no puede modificarse"
              />
              <p className="mt-1 text-xs text-slate-600">El nombre de usuario no puede modificarse.</p>
            </div>
            <div className="mb-3">
              <label className={labelCls}>Correo electrónico</label>
              <input
                type="email"
                className={inputCls}
                placeholder="correo@ejemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="mb-3">
              <label className={labelCls}>Nueva contraseña</label>
              <input
                type="password"
                className={inputCls}
                placeholder="Dejar en blanco para no cambiar"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className={labelCls}>Confirmar nueva contraseña</label>
              <input
                type="password"
                className={inputCls}
                placeholder="Repetir nueva contraseña"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                autoComplete="new-password"
              />
            </div>
          </div>

          {/* Columna derecha — Privilegios */}
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className="mb-3 text-sm font-black text-slate-900 uppercase tracking-wide">
              Privilegios y permisos
            </h3>
            <div className="flex flex-col gap-2">
              <label className={checkRowCls}>
                <input
                  type="checkbox"
                  className="h-4 w-4 flex-shrink-0"
                  checked={isSuper}
                  onChange={(e) => setIsSuper(e.target.checked)}
                />
                <div>
                  <div>Administrador</div>
                  <div className="text-xs font-normal text-slate-600">Acceso total al sistema</div>
                </div>
              </label>
              <label className={checkRowCls}>
                <input
                  type="checkbox"
                  className="h-4 w-4 flex-shrink-0"
                  checked={canAdd}
                  onChange={(e) => setCanAdd(e.target.checked)}
                />
                <div>
                  <div>Crear Productos</div>
                  <div className="text-xs font-normal text-slate-600">Puede agregar nuevos productos</div>
                </div>
              </label>
              <label className={checkRowCls}>
                <input
                  type="checkbox"
                  className="h-4 w-4 flex-shrink-0"
                  checked={canEdit}
                  onChange={(e) => setCanEdit(e.target.checked)}
                />
                <div>
                  <div>Editar Productos</div>
                  <div className="text-xs font-normal text-slate-600">Puede modificar productos existentes</div>
                </div>
              </label>
              <label className={checkRowCls}>
                <input
                  type="checkbox"
                  className="h-4 w-4 flex-shrink-0"
                  checked={canView}
                  onChange={(e) => setCanView(e.target.checked)}
                />
                <div>
                  <div>Ver Analíticas</div>
                  <div className="text-xs font-normal text-slate-600">Acceso a reportes y estadísticas</div>
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* Sucursales autorizadas — ancho completo */}
        <div className="mt-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h3 className="mb-3 text-sm font-black text-slate-900 uppercase tracking-wide">
            Sucursales autorizadas
          </h3>
          {sucursales.length === 0 ? (
            <p className="text-sm text-slate-600">No hay sucursales disponibles.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {sucursales.map((s) => (
                <label
                  key={s.id}
                  className={
                    'flex cursor-pointer items-center gap-2 rounded-xl border-2 px-3 py-2 text-sm font-bold shadow-sm transition-colors ' +
                    (selected.includes(s.id)
                      ? 'border-black bg-slate-900 text-white'
                      : 'border-black bg-white text-slate-900 hover:bg-slate-100')
                  }
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 flex-shrink-0"
                    checked={selected.includes(s.id)}
                    onChange={() => toggleSucursal(s.id)}
                  />
                  {s.display_name || s.nombre}
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Acciones */}
        <div className="mt-3 flex gap-2">
          <button
            onClick={submit}
            disabled={saving}
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-900 px-5 py-2 text-sm font-black text-white shadow disabled:opacity-50"
          >
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </button>
          <a
            href="/users/management/"
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-5 py-2 text-sm font-black text-slate-900 shadow"
          >
            Cancelar
          </a>
        </div>

      </div>
    </div>
  );
}
