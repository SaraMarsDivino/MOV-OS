import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

type SucursalItem = { id: number; nombre: string; display_name?: string };

const inputCls =
  'w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none';
const labelCls = 'mb-1 block text-sm font-black text-slate-900';
const checkRowCls =
  'flex cursor-pointer items-center gap-3 rounded-xl border-2 border-black bg-white px-3 py-2.5 text-sm font-bold text-slate-900 shadow-sm transition-colors hover:bg-slate-100';

function PermCheck({
  checked,
  onChange,
  label,
  desc,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  desc: string;
  disabled?: boolean;
}) {
  return (
    <label
      title={desc}
      className={
        'flex cursor-pointer items-center gap-2 rounded-xl border-2 border-black bg-white px-3 py-2 text-sm font-bold text-slate-900 shadow-sm transition-colors hover:bg-slate-100 ' +
        (disabled ? 'opacity-40 cursor-not-allowed' : '')
      }
    >
      <input
        type="checkbox"
        className="h-4 w-4 flex-shrink-0"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="leading-tight">{label}</span>
    </label>
  );
}

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
  const [sucursales, setSucursales] = useState<SucursalItem[]>([]);
  const [selected, setSelected] = useState<number[]>([]);

  // Permisos
  const [canAdd, setCanAdd] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [canExport, setCanExport] = useState(false);
  const [canDisable, setCanDisable] = useState(false);
  const [canArchive, setCanArchive] = useState(false);
  const [canTransfer, setCanTransfer] = useState(false);
  const [canAssign, setCanAssign] = useState(false);
  const [canView, setCanView] = useState(false);

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
        setCanExport(Boolean(u.can_export_products));
        setCanDisable(Boolean(u.can_disable_products));
        setCanArchive(Boolean(u.can_archive_products));
        setCanTransfer(Boolean(u.can_transfer_stock));
        setCanAssign(Boolean(u.can_assign_stock));
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
        can_export_products: canExport,
        can_disable_products: canDisable,
        can_archive_products: canArchive,
        can_transfer_stock: canTransfer,
        can_assign_stock: canAssign,
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

        {/* Fila superior: datos del usuario */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 mb-3">
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className={labelCls + ' mb-3 uppercase tracking-wide'}>Datos del usuario</h3>
            <div className="mb-3">
              <label className={labelCls}>Nombre de usuario</label>
              <input className={inputCls + ' opacity-60 cursor-not-allowed'} value={username} disabled title="El nombre de usuario no puede modificarse" />
              <p className="mt-1 text-xs text-slate-600">No puede modificarse.</p>
            </div>
            <div className="mb-3">
              <label className={labelCls}>Correo electrónico</label>
              <input type="email" className={inputCls} placeholder="correo@ejemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="mb-3">
              <label className={labelCls}>Nueva contraseña</label>
              <input type="password" className={inputCls} placeholder="Dejar en blanco para no cambiar" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            </div>
            <div>
              <label className={labelCls}>Confirmar nueva contraseña</label>
              <input type="password" className={inputCls} placeholder="Repetir nueva contraseña" value={password2} onChange={(e) => setPassword2(e.target.value)} autoComplete="new-password" />
            </div>
          </div>

          {/* Permisos — columna derecha */}
          <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
            <h3 className={labelCls + ' mb-3 uppercase tracking-wide'}>Privilegios y permisos</h3>

            {/* Administrador — ancho completo, destacado */}
            <label className="mb-3 flex cursor-pointer items-center gap-3 rounded-xl border-2 border-black bg-slate-900 px-3 py-2.5 text-sm font-black text-white shadow-sm transition-colors hover:bg-slate-700">
              <input type="checkbox" className="h-4 w-4 flex-shrink-0" checked={isSuper} onChange={(e) => setIsSuper(e.target.checked)} />
              <span>Administrador <span className="ml-1 text-xs font-normal opacity-70">— acceso total al sistema</span></span>
            </label>

            {isSuper && (
              <p className="mb-2 text-xs text-slate-500 italic">Con Administrador activo, todos los permisos están incluidos.</p>
            )}

            {/* Grilla 2×N de permisos */}
            <div className="grid grid-cols-2 gap-2">
              <div className="col-span-2 mt-1 text-xs font-black uppercase tracking-widest text-slate-500">Catálogo</div>
              <PermCheck checked={canAdd}     onChange={setCanAdd}     disabled={isSuper} label="Crear / subir"      desc="Agregar productos y subir Excel masivo" />
              <PermCheck checked={canEdit}    onChange={setCanEdit}    disabled={isSuper} label="Editar productos"   desc="Modificar nombre, precio, códigos y atributos" />
              <PermCheck checked={canExport}  onChange={setCanExport}  disabled={isSuper} label="Exportar Excel"     desc="Descargar catálogo completo o por sucursal" />
              <PermCheck checked={canDisable} onChange={setCanDisable} disabled={isSuper} label="Habilitar / deshab." desc="Activar o desactivar productos" />
              <PermCheck checked={canArchive} onChange={setCanArchive} disabled={isSuper} label="Archivar / papelera" desc="Archivar y ver papelera de productos" />

              <div className="col-span-2 mt-2 text-xs font-black uppercase tracking-widest text-slate-500">Stock</div>
              <PermCheck checked={canTransfer} onChange={setCanTransfer} disabled={isSuper} label="Transferir stock" desc="Mover unidades entre sucursales" />
              <PermCheck checked={canAssign}   onChange={setCanAssign}   disabled={isSuper} label="Asignar stock"    desc="Asignar stock en masa a sucursales" />

              <div className="col-span-2 mt-2 text-xs font-black uppercase tracking-widest text-slate-500">Reportes</div>
              <PermCheck checked={canView} onChange={setCanView} disabled={isSuper} label="Ver analíticas" desc="Acceso a reportes, historial y estadísticas" />
            </div>
          </div>
        </div>

        {/* Sucursales */}
        <div className="mt-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h3 className={labelCls + ' mb-3 uppercase tracking-wide'}>Sucursales autorizadas</h3>
          {sucursales.length === 0 ? (
            <p className="text-sm text-slate-600">No hay sucursales disponibles.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {sucursales.map((s) => (
                <label
                  key={s.id}
                  className={
                    'flex cursor-pointer items-center gap-2 rounded-xl border-2 px-3 py-2 text-sm font-bold shadow-sm transition-colors ' +
                    (selected.includes(s.id) ? 'border-black bg-slate-900 text-white' : 'border-black bg-white text-slate-900 hover:bg-slate-100')
                  }
                >
                  <input type="checkbox" className="h-4 w-4 flex-shrink-0" checked={selected.includes(s.id)} onChange={() => toggleSucursal(s.id)} />
                  {s.display_name || s.nombre}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="mt-3 flex gap-2">
          <button onClick={submit} disabled={saving} className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-900 px-5 py-2 text-sm font-black text-white shadow disabled:opacity-50">
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </button>
          <a href="/users/management/" className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-5 py-2 text-sm font-black text-slate-900 shadow">
            Cancelar
          </a>
        </div>

      </div>
    </div>
  );
}
