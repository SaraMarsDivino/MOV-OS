import { formatCLP } from './utils';

export type PaymentMethod = 'efectivo' | 'debito' | 'credito' | 'transferencia';
export type SaleType = 'boleta' | 'factura';

export type SplitPayment = {
  method: PaymentMethod;
  amount: string;
  transactionNumber: string;
  bankName: string;
};

type Props = {
  subtotal: number;
  tax: number;
  total: number;
  amountDue: number;

  isMixedPayment: boolean;

  // Simple payment mode (legacy-like UX)
  paymentMethod: PaymentMethod;
  onPaymentMethodChange: (m: PaymentMethod) => void;
  transactionNumber: string;
  onTransactionNumberChange: (v: string) => void;
  bankName: string;
  onBankNameChange: (v: string) => void;
  paidAmount: string;
  onPaidAmountChange: (v: string) => void;

  // Mixed payment mode
  noteCreditCode: string;
  onNoteCreditCodeChange: (v: string) => void;
  noteCreditSaldo: number | null;
  noteCreditApplied: number;
  onApplyNoteCredit: () => void;
  onClearNoteCredit: () => void;
  saleType: SaleType;
  onSaleTypeChange: (t: SaleType) => void;
  payments: SplitPayment[];
  onPaymentsChange: (rows: SplitPayment[]) => void;
  cashReceived: string;
  onCashReceivedChange: (v: string) => void;
  onConfirmPurchase: () => void;
  showNoteCredit: boolean;
};

const METHODS: { id: PaymentMethod; label: string }[] = [
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'debito', label: 'Tarjeta de Débito' },
  { id: 'credito', label: 'Tarjeta de Crédito' },
  { id: 'transferencia', label: 'Transferencia' },
];

export default function PaymentPanel({
  subtotal,
  tax,
  total,
  amountDue,

  isMixedPayment,

  paymentMethod,
  onPaymentMethodChange,
  transactionNumber,
  onTransactionNumberChange,
  bankName,
  onBankNameChange,
  paidAmount,
  onPaidAmountChange,

  noteCreditCode,
  onNoteCreditCodeChange,
  noteCreditSaldo,
  noteCreditApplied,
  onApplyNoteCredit,
  onClearNoteCredit,
  saleType,
  onSaleTypeChange,
  payments,
  onPaymentsChange,
  cashReceived,
  onCashReceivedChange,
  onConfirmPurchase,
  showNoteCredit,
}: Props) {
  const parseAmount = (v: string) => {
    const n = Number(String(v || '').replace(/[^0-9]/g, ''));
    return Number.isFinite(n) ? n : 0;
  };

  const totalPayments = isMixedPayment ? payments.reduce((acc, p) => acc + parseAmount(p.amount), 0) : 0;
  const remaining = isMixedPayment ? Math.round(amountDue - totalPayments) : 0;

  const cashPortion = isMixedPayment
    ? payments.reduce((acc, p) => acc + (p.method === 'efectivo' ? parseAmount(p.amount) : 0), 0)
    : paymentMethod === 'efectivo'
      ? Math.round(amountDue)
      : 0;

  const cashPaid = isMixedPayment
    ? cashReceived.trim() === ''
      ? null
      : Number(cashReceived)
    : paidAmount.trim() === ''
      ? null
      : Number(paidAmount);

  const change = cashPortion > 0 ? (cashPaid === null ? -cashPortion : cashPaid - cashPortion) : 0;
  const changeAbs = Math.abs(Math.round(change));
  const changeLabel = change < 0 ? `-$${formatCLP(changeAbs)}` : `$${formatCLP(changeAbs)}`;
  const changeTone = change < 0 ? 'bg-rose-500 text-white' : change > 0 ? 'bg-emerald-400 text-slate-950' : 'bg-slate-200 text-slate-700';

  const remainingTone = remaining === 0 ? 'bg-emerald-400 text-slate-950' : remaining > 0 ? 'bg-amber-300 text-slate-950' : 'bg-rose-500 text-white';
  const remainingLabel = remaining === 0 ? 'Cuadrado' : remaining > 0 ? 'Faltan' : 'Sobra';

  const usedMethods = new Set(payments.map((p) => p.method));
  const availableMethods = METHODS.map((m) => m.id).filter((m) => !usedMethods.has(m));

  const updateRow = (idx: number, patch: Partial<SplitPayment>) => {
    const next = payments.map((p, i) => (i === idx ? { ...p, ...patch } : p));
    onPaymentsChange(next);
  };

  const removeRow = (idx: number) => {
    const next = payments.filter((_, i) => i !== idx);
    onPaymentsChange(next.length ? next : []);
  };

  const addRow = () => {
    if (!availableMethods.length) return;
    const method = availableMethods[0];
    const next: SplitPayment[] = [...payments, { method, amount: '', transactionNumber: '', bankName: '' }];
    onPaymentsChange(next);
  };

  return (
    <div className="h-full w-full min-w-0 flex flex-col min-h-0 overflow-hidden bg-slate-300">
      <div className="flex-none shrink-0 p-3 border-b-2 border-slate-400 bg-slate-200">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-900 normal-case tracking-normal">
            Opciones de pago
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 bg-slate-300">
        {/* Tipo de Venta */}
        <div>
          <div className="text-xs font-semibold text-slate-700">Tipo de Venta</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => onSaleTypeChange('boleta')}
              className={
                'min-h-[44px] rounded-lg border text-sm font-extrabold ' +
                (saleType === 'boleta'
                  ? 'bg-sky-600 text-white border-sky-600'
                  : 'bg-white text-slate-900 border-slate-300')
              }
            >
              Boleta Electrónica
            </button>
            <button
              type="button"
              onClick={() => onSaleTypeChange('factura')}
              className={
                'min-h-[44px] rounded-lg border text-sm font-extrabold ' +
                (saleType === 'factura'
                  ? 'bg-sky-600 text-white border-sky-600'
                  : 'bg-white text-slate-900 border-slate-300')
              }
            >
              Factura Electrónica
            </button>
          </div>
        </div>

        {/* Pago simple (UX legacy) */}
        {!isMixedPayment ? (
          <>
            <div className="mt-2">
              <div className="text-xs font-semibold text-slate-700">Forma de Pago</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {METHODS.map((m) => {
                  const active = m.id === paymentMethod;
                  const disabled = amountDue <= 0;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => !disabled && onPaymentMethodChange(m.id)}
                      className={
                        'min-h-[56px] rounded-lg border text-sm font-extrabold ' +
                        (disabled
                          ? 'bg-slate-100 text-slate-400 border-slate-200'
                          : active
                            ? 'bg-sky-600 text-white border-sky-600'
                            : 'bg-white text-slate-900 border-slate-300')
                      }
                      disabled={disabled}
                    >
                      {m.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {amountDue > 0 && paymentMethod !== 'efectivo' ? (
              <div className="mt-2 rounded-lg border-2 border-slate-400 bg-slate-200 p-2">
                <div className="flex items-center gap-2">
                  <div className="text-xs font-semibold text-slate-700 shrink-0">Transacción</div>
                  <div className={"grid gap-2 flex-1 " + (paymentMethod === 'transferencia' ? 'grid-cols-2' : 'grid-cols-1')}>
                    <input
                      value={transactionNumber}
                      onChange={(e) => onTransactionNumberChange(e.target.value)}
                      placeholder="N°"
                      className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                    />
                    {paymentMethod === 'transferencia' ? (
                      <input
                        value={bankName}
                        onChange={(e) => onBankNameChange(e.target.value)}
                        placeholder="Banco"
                        className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                      />
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}

        {/* Pagos mixtos (solo cuando el usuario lo activa) */}
        {isMixedPayment ? (
          <div className="mt-2">
            <div className="text-xs font-semibold text-slate-700">Pagos</div>

            <div className="mt-2 space-y-2">
              {payments.map((p, idx) => {
                const isCash = p.method === 'efectivo';
                const showTx = !isCash;
                const showBank = p.method === 'transferencia';

                const methodUsedElsewhere = (m: PaymentMethod) => payments.some((x, i) => i !== idx && x.method === m);

                return (
                  <div key={idx} className="rounded-lg border-2 border-slate-400 bg-slate-200 p-2">
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={p.method}
                        disabled={amountDue <= 0}
                        onChange={(e) => {
                          const nextMethod = e.target.value as PaymentMethod;
                          if (methodUsedElsewhere(nextMethod)) return;
                          updateRow(idx, { method: nextMethod });
                          if (nextMethod === 'efectivo' && cashReceived.trim() === '') {
                            onCashReceivedChange(p.amount || '');
                          }
                        }}
                        className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                      >
                        {METHODS.map((m) => (
                          <option key={m.id} value={m.id} disabled={methodUsedElsewhere(m.id)}>
                            {m.label}
                          </option>
                        ))}
                      </select>

                      <input
                        value={p.amount}
                        disabled={amountDue <= 0}
                        onChange={(e) => {
                          updateRow(idx, { amount: e.target.value });
                          if (p.method === 'efectivo' && cashReceived.trim() === '') {
                            onCashReceivedChange(e.target.value);
                          }
                        }}
                        placeholder="Monto"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                      />
                    </div>

                    {showTx ? (
                      <div className={"mt-2 grid gap-2 " + (showBank ? 'grid-cols-2' : 'grid-cols-1')}>
                        <input
                          value={p.transactionNumber}
                          onChange={(e) => updateRow(idx, { transactionNumber: e.target.value })}
                          placeholder="N° Transacción"
                          className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                        />
                        {showBank ? (
                          <input
                            value={p.bankName}
                            onChange={(e) => updateRow(idx, { bankName: e.target.value })}
                            placeholder="Banco"
                            className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                          />
                        ) : null}
                      </div>
                    ) : null}

                    {payments.length > 1 ? (
                      <div className="mt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => removeRow(idx)}
                          className="min-h-[36px] px-3 rounded-lg border border-slate-300 bg-white text-slate-700 font-extrabold"
                        >
                          Quitar
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}

              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={addRow}
                  disabled={amountDue <= 0 || availableMethods.length === 0}
                  className={
                    'min-h-[40px] px-3 rounded-lg font-black ' +
                    (amountDue <= 0 || availableMethods.length === 0
                      ? 'bg-slate-100 text-slate-400'
                      : 'bg-sky-600 text-white')
                  }
                >
                  Agregar método
                </button>
                <div className={'min-h-[40px] px-3 rounded-lg font-extrabold flex items-center ' + remainingTone}>
                  {remainingLabel}: ${formatCLP(Math.abs(remaining))}
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {/* Nota de crédito (al final) - visible only when toggled from header */}
        {showNoteCredit ? (
          <div className="mt-2">
            <div className="text-xs font-semibold text-slate-700">Nota de crédito (opcional)</div>
            <div className="mt-2 rounded-lg border-2 border-slate-400 bg-slate-200 p-2">
              <div className="flex items-center gap-2">
                <input
                  value={noteCreditCode}
                  onChange={(e) => onNoteCreditCodeChange(e.target.value)}
                  placeholder="Código (ej: NC123...)"
                  className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
                />
                {noteCreditSaldo !== null && noteCreditApplied > 0 ? (
                  <button
                    type="button"
                    onClick={onClearNoteCredit}
                    className="min-h-[40px] px-3 rounded-lg border border-slate-300 bg-white text-slate-700 font-extrabold"
                  >
                    Quitar
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={onApplyNoteCredit}
                    className="min-h-[40px] px-3 rounded-lg bg-sky-600 text-white font-black"
                  >
                    Aplicar
                  </button>
                )}
              </div>

              {noteCreditSaldo !== null && noteCreditApplied > 0 ? (
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-md bg-white border border-slate-300 px-2 py-2">
                    <div className="text-slate-500 font-semibold">Saldo</div>
                    <div className="text-slate-900 font-black">${formatCLP(Math.round(noteCreditSaldo))}</div>
                  </div>
                  <div className="rounded-md bg-white border border-slate-300 px-2 py-2">
                    <div className="text-slate-500 font-semibold">Se aplica</div>
                    <div className="text-slate-900 font-black">-${formatCLP(Math.round(noteCreditApplied))}</div>
                  </div>
                  <div className="rounded-md bg-white border border-slate-300 px-2 py-2">
                    <div className="text-slate-500 font-semibold">A pagar</div>
                    <div className="text-slate-900 font-black">${formatCLP(Math.round(amountDue))}</div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      {/* Footer: Cantidad pagada / Vuelto (sin mostrar Total en el panel de pago) */}
      <div className="flex-none shrink-0 p-3 border-t-2 border-slate-400 bg-slate-200">
        <div className="grid grid-cols-2 gap-2">
          {!isMixedPayment && paymentMethod === 'efectivo' && amountDue > 0 ? (
            <>
              <div>
                <div className="text-xs font-semibold text-slate-700">Cantidad Pagada</div>
                <input
                  value={paidAmount}
                  onChange={(e) => onPaidAmountChange(e.target.value)}
                  placeholder="Ingrese la cantidad"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  className="mt-2 w-full rounded-lg border px-3 py-2 text-sm outline-none bg-white border-slate-300 focus:border-sky-500 text-slate-900"
                />
              </div>
              <div>
                <div className="text-xs font-semibold text-slate-700">Vuelto</div>
                <div
                  className={
                    'mt-2 flex min-h-[40px] w-full items-center justify-center rounded-lg font-extrabold ' +
                    changeTone
                  }
                >
                  {changeLabel}
                </div>
              </div>
            </>
          ) : (
            <div className="col-span-2">
              <div className="text-xs font-semibold text-slate-700">{isMixedPayment ? 'Total a Pagar' : 'Cantidad Pagada'}</div>
              <div className="mt-2 flex min-h-[40px] w-full items-center justify-center rounded-lg font-extrabold bg-slate-200 text-slate-900">
                ${formatCLP(Math.round(amountDue))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
