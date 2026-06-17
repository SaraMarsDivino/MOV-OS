import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../lib/api';

type CatItem = { id: number; nombre: string; descripcion: string; product_count: number };

const inputCls = 'w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none';
const labelCls = 'mb-1 block text-sm font-black text-slate-900';

function CatModal({
  initial,
  onSave,
  onClose,
}: {
  initial: CatItem | null;
  onSave: (item: CatItem) => void;
  onClose: () => void;
}) {
  const [nombre, setNombre] = useState(initial?.nombre || '');
  const [descripcion, setDescripcion] = useState(initial?.descripcion || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!nombre.trim()) { setError('El nombre es requerido.'); return; }
    try {
      setSaving(true);
      setError('');
      const url = initial
        ? `/products/api/categories/${initial.id}/update/`
        : '/products/api/categories/create/';
      const res = await apiPost<{ success: boolean; item: CatItem; error?: string }>(url, { nombre, descripcion });
      if (!res.success) { setError(res.error || 'Error'); return; }
      onSave(res.item);
    } catch (e: any) {
      setError(e?.message || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl border-2 border-black bg-slate-200 p-5 shadow-2xl">
        <h3 className="mb-4 text-base font-black text-slate-900">
          {initial ? 'Editar categoría' : 'Nueva categoría'}
        </h3>
        {error && (
          <div className="mb-3 rounded-xl border-2 border-red-400 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}
        <div className="mb-3">
          <label className={labelCls}>Nombre</label>
          <input
            className={inputCls}
            placeholder="ej: Bebidas"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            autoFocus
          />
        </div>
        <div className="mb-4">
          <label className={labelCls}>Descripción <span className="font-normal text-slate-500">(opcional)</span></label>
          <input
            className={inputCls}
            placeholder="ej: Refrescos, jugos y aguas"
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={submit}
            disabled={saving}
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-900 px-4 py-2 text-sm font-black text-white shadow disabled:opacity-50"
          >
            {saving ? 'Guardando…' : initial ? 'Guardar cambios' : 'Crear'}
          </button>
          <button
            onClick={onClose}
            className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-4 py-2 text-sm font-black text-slate-900 shadow"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CategoriesPage() {
  const [items, setItems] = useState<CatItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState<{ open: boolean; item: CatItem | null }>({ open: false, item: null });
  const [deleting, setDeleting] = useState<number | null>(null);
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);

  const showToast = (kind: 'success' | 'error', message: string) => {
    setToast({ kind, message });
    setTimeout(() => setToast(null), 2500);
  };

  const load = async () => {
    try {
      setLoading(true);
      const res = await apiGet<{ items: CatItem[] }>('/products/api/categories/');
      setItems(res.items || []);
    } catch (e: any) {
      setError(e?.message || 'Error cargando categorías');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = (item: CatItem) => {
    setItems((prev) => {
      const idx = prev.findIndex((c) => c.id === item.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], ...item };
        return next.sort((a, b) => a.nombre.localeCompare(b.nombre));
      }
      return [...prev, { ...item, product_count: 0 }].sort((a, b) => a.nombre.localeCompare(b.nombre));
    });
    setModal({ open: false, item: null });
    showToast('success', modal.item ? 'Categoría actualizada.' : 'Categoría creada.');
  };

  const handleDelete = async (cat: CatItem) => {
    const msg = cat.product_count > 0
      ? `¿Eliminar "${cat.nombre}"? Los ${cat.product_count} producto(s) asignados quedarán sin categoría.`
      : `¿Eliminar la categoría "${cat.nombre}"?`;
    if (!window.confirm(msg)) return;
    try {
      setDeleting(cat.id);
      await apiPost(`/products/api/categories/${cat.id}/delete/`, {});
      setItems((prev) => prev.filter((c) => c.id !== cat.id));
      showToast('success', 'Categoría eliminada.');
    } catch (e: any) {
      showToast('error', e?.message || 'Error al eliminar');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-3xl">

        {/* Header */}
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <div>
            <h2 className="m-0 text-lg font-black text-slate-900">Categorías de productos</h2>
            <div className="mt-0.5 text-sm text-slate-600">
              {loading ? '…' : `${items.length} categoría${items.length !== 1 ? 's' : ''}`}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setModal({ open: true, item: null })}
              className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-900 px-4 py-2 text-sm font-black text-white shadow"
            >
              + Nueva categoría
            </button>
            <a
              href="/products/management/"
              className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-white px-4 py-2 text-sm font-black text-slate-900 shadow"
            >
              ← Productos
            </a>
          </div>
        </div>

        {error && (
          <div className="mb-3 rounded-2xl border-2 border-black bg-white p-3 text-sm text-red-700 shadow">{error}</div>
        )}

        {/* Toast */}
        {toast && (
          <div className={`fixed bottom-4 right-4 z-50 rounded-2xl border-2 border-black px-4 py-3 text-sm font-black shadow-2xl ${toast.kind === 'success' ? 'bg-emerald-400 text-slate-900' : 'bg-red-400 text-white'}`}>
            {toast.message}
          </div>
        )}

        {/* Category list */}
        <div className="rounded-2xl border-2 border-black bg-slate-300 shadow-lg overflow-hidden">
          {loading ? (
            <div className="p-6 text-center text-sm text-slate-500">Cargando…</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center">
              <div className="text-sm font-black text-slate-700">No hay categorías aún</div>
              <div className="mt-1 text-xs text-slate-500">Crea tu primera categoría para organizar los productos.</div>
            </div>
          ) : (
            <ul className="divide-y-2 divide-black">
              {items.map((cat) => (
                <li key={cat.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-black text-slate-900 truncate">{cat.nombre}</div>
                    {cat.descripcion && (
                      <div className="mt-0.5 text-xs text-slate-500 truncate">{cat.descripcion}</div>
                    )}
                  </div>
                  <span className="shrink-0 rounded-lg border-2 border-black bg-white px-2 py-0.5 text-xs font-black text-slate-700">
                    {cat.product_count} prod.
                  </span>
                  <button
                    onClick={() => setModal({ open: true, item: cat })}
                    className="shrink-0 rounded-lg border-2 border-black bg-white px-3 py-1.5 text-xs font-black text-slate-900 shadow hover:bg-slate-100"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => handleDelete(cat)}
                    disabled={deleting === cat.id}
                    className="shrink-0 rounded-lg border-2 border-black bg-red-100 px-3 py-1.5 text-xs font-black text-red-700 shadow hover:bg-red-200 disabled:opacity-40"
                  >
                    {deleting === cat.id ? '…' : 'Eliminar'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

      </div>

      {modal.open && (
        <CatModal
          initial={modal.item}
          onSave={handleSave}
          onClose={() => setModal({ open: false, item: null })}
        />
      )}
    </div>
  );
}
