type OpenCashConfig = {
  csrfToken: string;
  submitUrl: string;
  sucursales: Array<{ id: number; nombre: string }>;
};

declare global {
  interface Window {
    __MOVOS_OPEN_CASH__?: OpenCashConfig;
  }
}

export default function OpenCashPage() {
  const config = window.__MOVOS_OPEN_CASH__;

  if (!config) {
    return (
      <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
        <div className="mx-auto max-w-3xl rounded-2xl border-2 border-black bg-white p-4 text-sm text-slate-900 shadow">
          No se pudo cargar la configuración de apertura de caja.
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-3xl">
        <div className="rounded-2xl border-2 border-black bg-slate-300 p-4 shadow-lg">
          <h2 className="m-0 text-lg font-black text-slate-900">Abrir Caja</h2>
          <div className="mt-1 text-sm text-slate-900/80">Selecciona sucursal y define efectivo inicial.</div>

          <form method="post" action={config.submitUrl} className="mt-4 space-y-3">
            <input type="hidden" name="csrfmiddlewaretoken" value={config.csrfToken} />

            <div>
              <label htmlFor="sucursal" className="mb-1 block text-sm font-bold text-slate-900">
                Seleccione Sucursal
              </label>
              <select
                id="sucursal"
                name="sucursal"
                defaultValue=""
                className="w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-black outline-none"
                required
              >
                <option value="">-- Seleccione una sucursal --</option>
                {config.sucursales.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="efectivo_inicial" className="mb-1 block text-sm font-bold text-slate-900">
                Efectivo Inicial
              </label>
              <input
                type="text"
                id="efectivo_inicial"
                name="efectivo_inicial"
                defaultValue="0"
                inputMode="numeric"
                placeholder="Ej: 10.000"
                className="w-full rounded-xl border-2 border-black bg-white px-3 py-2 text-sm text-black outline-none"
              />
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="submit"
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-sky-600 px-4 py-2 text-sm font-black text-white shadow"
              >
                Abrir Caja
              </button>
              <a
                href="/logout/"
                className="inline-flex items-center justify-center rounded-xl border-2 border-black bg-slate-500 px-4 py-2 text-sm font-black text-white shadow"
                onClick={(ev) => {
                  if (!window.confirm('¿Está seguro que desea cerrar sesión?')) {
                    ev.preventDefault();
                  }
                }}
              >
                Cerrar Sesión
              </a>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
