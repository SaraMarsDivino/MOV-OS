import type { SyncResult } from '../hooks/useConnectionStatus';

type Props = {
  open: boolean;
  results: SyncResult[];
  onClose: () => void;
};

export default function SyncModal({ open, results, onClose }: Props) {
  if (!open) return null;

  const succeeded = results.filter((r) => r.success);
  const failed = results.filter((r) => !r.success);

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute inset-0 p-3 md:p-6 flex items-center justify-center pointer-events-none">
        <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-xl overflow-hidden pointer-events-auto">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
            <div className="font-black text-slate-900 text-base">Sincronización completada</div>
            <div className="text-sm text-slate-600 mt-0.5">
              {succeeded.length > 0 && (
                <span className="text-emerald-700 font-semibold">
                  {succeeded.length} {succeeded.length === 1 ? 'venta sincronizada' : 'ventas sincronizadas'} exitosamente
                </span>
              )}
              {succeeded.length > 0 && failed.length > 0 && ' · '}
              {failed.length > 0 && (
                <span className="text-rose-700 font-semibold">
                  {failed.length} {failed.length === 1 ? 'error' : 'errores'}
                </span>
              )}
            </div>
          </div>

          {failed.length > 0 && (
            <div className="px-4 py-3 border-b border-slate-200">
              <div className="text-sm font-semibold text-rose-700 mb-2">
                {failed.length === 1 ? 'Esta venta requiere atención manual:' : 'Estas ventas requieren atención manual:'}
              </div>
              <ul className="space-y-1 max-h-40 overflow-y-auto">
                {failed.map((r, i) => (
                  <li key={r.key} className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded p-2">
                    <span className="font-semibold">Venta #{i + 1}:</span> {r.error || 'Error desconocido'}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Registra estas ventas manualmente o contacta soporte técnico con los detalles del error.
              </p>
            </div>
          )}

          {succeeded.length > 0 && failed.length === 0 && (
            <div className="px-4 py-3 border-b border-slate-200">
              <p className="text-sm text-slate-600">
                Todas las ventas offline fueron registradas correctamente en el sistema.
              </p>
            </div>
          )}

          <div className="px-4 py-3 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-sky-600 text-white font-black text-sm hover:bg-sky-500 active:scale-95 transition-all"
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
