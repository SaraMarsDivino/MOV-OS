import { formatCLP } from './utils';

export type CartItemModel = {
  id: number;
  name: string;
  qty: number;
  unitPrice: number;
  stock: number;
  allowSaleWithoutStock: boolean;
};

type Props = {
  items: CartItemModel[];
  barcodeQuery: string;
  onBarcodeQueryChange: (value: string) => void;
  onBarcodeEnter: () => void;
  onInc: (id: number) => void;
  onDec: (id: number) => void;
  onSetQty: (id: number, qty: number) => void;
  onConfirmPurchase: () => void;
};

export default function CartPanel({ items, barcodeQuery, onBarcodeQueryChange, onBarcodeEnter, onInc, onDec, onSetQty, onConfirmPurchase }: Props) {
  const total = items.reduce((acc, it) => acc + it.qty * it.unitPrice, 0);

  return (
    <div className="h-full w-full flex flex-col min-h-0 overflow-hidden bg-slate-300">
      <div className="flex-none shrink-0 p-3 border-b-2 border-slate-400 bg-slate-200">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-900 normal-case tracking-normal">
            Carrito de compras
          </div>
          <div className="text-xs text-slate-500">{items.length} ítems</div>
        </div>

        <div className="mt-2">
          <input
            value={barcodeQuery}
            onChange={(e) => onBarcodeQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onBarcodeEnter();
            }}
            placeholder="Código de barras / SKU"
            className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
            aria-label="Ingresar código de barras"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
        <table className="w-full text-sm table-fixed">
          <thead className="sticky top-0 bg-slate-200 border-b-2 border-slate-400">
            <tr>
              <th className="text-left px-3 py-2 text-xs font-bold text-slate-700 w-[90px]">Cant.</th>
              <th className="text-left px-3 py-2 text-xs font-bold text-slate-700">Producto</th>
              <th className="text-left px-3 py-2 text-xs font-bold text-slate-700 w-[110px]">Total</th>
              <th className="text-right px-3 py-2 text-xs font-bold text-slate-700 w-[120px]">Acción</th>
            </tr>
          </thead>
          <tbody className="divide-y-2 divide-slate-400">
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-3 text-slate-500 text-sm">
                  No hay productos en el carrito.
                </td>
              </tr>
            ) : (
              items.map((it) => (
                <tr key={it.id} className="hover:bg-slate-200">
                  <td className="px-3 py-2 align-middle">
                    <input
                      type="number"
                      min={1}
                      max={it.allowSaleWithoutStock ? undefined : it.stock}
                      value={it.qty}
                      onChange={(e) => onSetQty(it.id, Number(e.target.value || 1))}
                      className="w-[64px] rounded-md bg-white border border-slate-300 px-2 py-1 text-sm font-semibold text-center"
                    />
                  </td>
                  <td className="px-3 py-2 align-middle">
                    <div className="min-w-0 font-semibold whitespace-normal break-words leading-snug" title={it.name}>
                      {it.name}
                    </div>
                    <div className="text-xs text-slate-500">${formatCLP(it.unitPrice)} c/u</div>
                  </td>
                  <td className="px-3 py-2 align-middle font-extrabold text-slate-900">${formatCLP(it.qty * it.unitPrice)}</td>
                  <td className="px-3 py-2 align-middle">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => onInc(it.id)}
                        disabled={!it.allowSaleWithoutStock && it.qty >= it.stock}
                        className="min-h-[36px] min-w-[44px] rounded-md bg-emerald-400 text-slate-950 font-black"
                      >
                        +1
                      </button>
                      <button
                        type="button"
                        onClick={() => onDec(it.id)}
                        className="min-h-[36px] min-w-[44px] rounded-md bg-rose-500 text-white font-black"
                      >
                        -1
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex-none shrink-0 p-3 border-t-2 border-slate-400 bg-slate-200">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs text-slate-500">Total</div>
            <div className="text-lg font-extrabold text-slate-900 truncate">${formatCLP(total)}</div>
          </div>
          <button
            type="button"
            onClick={onConfirmPurchase}
            className="inline-flex min-h-[44px] px-4 rounded-lg bg-emerald-400 text-slate-950 font-black items-center justify-center text-center"
          >
            Confirmar Compra
          </button>
        </div>
      </div>
    </div>
  );
}
