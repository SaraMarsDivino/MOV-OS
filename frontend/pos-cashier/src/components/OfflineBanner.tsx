type Props = {
  isOffline: boolean;
  pendingCount: number;
  onSync: () => void;
  syncing?: boolean;
};

export default function OfflineBanner({ isOffline, pendingCount, onSync, syncing = false }: Props) {
  if (isOffline) {
    return (
      <div className="flex items-center gap-3 bg-rose-600 text-white px-4 py-2 text-sm font-semibold flex-none">
        <span className="inline-block w-2 h-2 rounded-full bg-white animate-pulse shrink-0" />
        <span>
          Sin conexión — Las ventas se guardan localmente y se sincronizarán al volver la conexión
          {pendingCount > 0 && (
            <span className="ml-2 bg-rose-800 px-2 py-0.5 rounded-full text-xs">
              {pendingCount} {pendingCount === 1 ? 'pendiente' : 'pendientes'}
            </span>
          )}
        </span>
      </div>
    );
  }

  if (pendingCount > 0) {
    return (
      <div className="flex items-center justify-between gap-3 bg-amber-500 text-slate-900 px-4 py-2 text-sm font-semibold flex-none">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-slate-900 shrink-0" />
          <span>
            Conexión restaurada ·{' '}
            <span className="font-black">{pendingCount} {pendingCount === 1 ? 'venta' : 'ventas'}</span>{' '}
            {pendingCount === 1 ? 'pendiente' : 'pendientes'} de sincronizar
          </span>
        </div>
        <button
          type="button"
          onClick={onSync}
          disabled={syncing}
          className="shrink-0 px-3 py-1 rounded-lg bg-slate-900 text-white font-black text-xs disabled:opacity-50 active:scale-95 transition-transform"
        >
          {syncing ? 'Sincronizando...' : 'Sincronizar ahora'}
        </button>
      </div>
    );
  }

  return null;
}
