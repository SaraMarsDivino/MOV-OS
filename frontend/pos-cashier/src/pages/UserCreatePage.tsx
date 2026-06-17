import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

type SucursalItem = { id: number; nombre: string; display_name?: string };

const inputCls =
  'w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none';
const labelCls = 'mb-1 block text-sm font-black text-slate-900';
const checkRowCls =
  'flex cursor-pointer items-center gap-3 rounded-xl border-2 border-black bg-white px-3 py-2.5 text-sm font-bold text-slate-900 shadow-sm transition-colors hover:bg-slate-100';

export default function UserCreatePage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [isSuper, setIsSuper] = useState(false);
  const [canAdd, setCanAdd] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [canExport, setCanExport] = useState(false);
  const [canDisable, setCanDisable] = useState(false);
  const [canArchive, setCanArchive] = useState(false);
  const [canTransfer, setCanTransfer] = useState(false);
  const [canAssign, setCanAssign] = useState(false);
  const [canView, setCanView] = useState(false);
  const [sucursales, setSucursales] = useState<SucursalItem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const sRes = await apiGet<{ items: SucursalItem[] }>('/users/api/user-sucursales/');
        setSucursales(sRes.items || []);
      } catch (e: any) {
        setError(e?.message || 'Error cargando sucursales');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toggleSucursal = (sid: number) =>
    setSelected((cur) => (cur.includes(sid) ? cur.filter((x) => x !== sid) : [...cur, sid]));

  const submit = async () => {
    if (!username.trim()) { setError('El nombre de usuario es requerido.'); return; }
    if (!password.trim()) { setError('La contraseña es requerida.'); return; }
    try {
      setSaving(true);
      setError('');
      await apiPost('/users/api/users/create/', {
        username,
        password,
        email,
        is_superuser: isSuper,
        can_add_products: canAdd,
        can_edit_products: canEdit,
        can_export_products: canExport,
        can_disable_products: canDisable,
        can_archive_products: canArchive,
        can_transfer_stock: canTransfer,
        can_assign_stock: canAssign,
        can_view_analytics: canView,
        sucursales_autorizadas: selected,
      });
      window.location.href = '/users/management/';
    } catch (e: any) {
      setError(e?.message || 'Error al crear usuario');
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
          <h2 className="m-0 text-lg font-black text-slate-900">Crear Usuario</h2>
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
                className={inputCls}
                placeholder="ej: juan.perez"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="mb-3">
              <label className={labelCls}>Contraseña</label>
              <input
                type="password"
                className={inputCls}
                placeholder="Mínimo 6 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div>
              <label className={labelCls}>Correo electrónico</label>
              <input
                type="email"
                className={inputCls}
                placeholder="correo@ejemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          {/* Columna derecha — Privilegios */}
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className="mb-3 text-sm font-black text-slate-900 uppercase tracking-wide">Privilegios y permisos</h3>

            {/* Administrador — destacado */}
            <label className="mb-3 flex cursor-pointer items-center gap-3 rounded-xl border-2 border-black bg-slate-900 px-3 py-2.5 text-sm font-black text-white shadow-sm transition-colors hover:bg-slate-700">
              <input type="checkbox" className="h-4 w-4 flex-shrink-0" checked={isSuper} onChange={(e) => setIsSuper(e.target.checked)} />
              <span>Administrador <span className="ml-1 text-xs font-normal opacity-70">— acceso total al sistema</span></span>
            </label>

            {isSuper && (
              <p className="mb-2 text-xs text-slate-500 italic">Con Administrador activo, todos los permisos están incluidos.</p>
            )}

            {/* Grilla 2×N */}
            <div className="grid grid-cols-2 gap-2">
              <div className="col-span-2 mt-1 text-xs font-black uppercase tracking-widest text-slate-500">Catálogo</div>
              {([
                [canAdd,     setCanAdd,     'Crear / subir',       'Agregar productos y subir Excel masivo'],
                [canEdit,    setCanEdit,    'Editar productos',    'Modificar nombre, precio, códigos y atributos'],
                [canExport,  setCanExport,  'Exportar Excel',      'Descargar catálogo completo o por sucursal'],
                [canDisable, setCanDisable, 'Habilitar / deshab.', 'Activar o desactivar productos'],
                [canArchive, setCanArchive, 'Archivar / papelera', 'Archivar y ver papelera de productos'],
              ] as const).map(([val, setter, lbl, desc]) => (
                <label key={lbl} title={desc} className={checkRowCls + ' py-2 ' + (isSuper ? 'opacity-40 cursor-not-allowed' : '')}>
                  <input type="checkbox" className="h-4 w-4 flex-shrink-0" checked={val} disabled={isSuper} onChange={(e) => setter(e.target.checked)} />
                  <span className="text-sm leading-tight">{lbl}</span>
                </label>
              ))}

              <div className="col-span-2 mt-2 text-xs font-black uppercase tracking-widest text-slate-500">Stock</div>
              {([
                [canTransfer, setCanTransfer, 'Transferir stock', 'Mover unidades entre sucursales'],
                [canAssign,   setCanAssign,   'Asignar stock',    'Asignar stock en masa a sucursales'],
              ] as const).map(([val, setter, lbl, desc]) => (
                <label key={lbl} title={desc} className={checkRowCls + ' py-2 ' + (isSuper ? 'opacity-40 cursor-not-allowed' : '')}>
                  <input type="checkbox" className="h-4 w-4 flex-shrink-0" checked={val} disabled={isSuper} onChange={(e) => setter(e.target.checked)} />
                  <span className="text-sm leading-tight">{lbl}</span>
                </label>
              ))}

              <div className="col-span-2 mt-2 text-xs font-black uppercase tracking-widest text-slate-500">Reportes</div>
              <label title="Acceso a reportes, historial de ventas y estadísticas" className={checkRowCls + ' py-2 ' + (isSuper ? 'opacity-40 cursor-not-allowed' : '')}>
                <input type="checkbox" className="h-4 w-4 flex-shrink-0" checked={canView} disabled={isSuper} onChange={(e) => setCanView(e.target.checked)} />
                <span className="text-sm leading-tight">Ver analíticas</span>
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
            {saving ? 'Creando…' : 'Crear usuario'}
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
