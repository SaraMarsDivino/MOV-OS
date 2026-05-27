import CartPanel, { type CartItemModel } from './CartPanel';
import PaymentPanel, { type PaymentMethod, type SplitPayment, type SaleType } from './PaymentPanel';

type Props = {
  open: boolean;
  onClose: () => void;
  cartItems: CartItemModel[];
  barcodeQuery: string;
  onBarcodeQueryChange: (value: string) => void;
  onBarcodeEnter: () => void;
  onInc: (id: number) => void;
  onDec: (id: number) => void;
  onSetQty: (id: number, qty: number) => void;
  subtotal: number;
  tax: number;
  total: number;
  amountDue: number;

  isMixedPayment: boolean;
  onMixedPaymentChange: (v: boolean) => void;
  paymentMethod: PaymentMethod;
  onPaymentMethodChange: (m: PaymentMethod) => void;
  transactionNumber: string;
  onTransactionNumberChange: (v: string) => void;
  bankName: string;
  onBankNameChange: (v: string) => void;
  paidAmount: string;
  onPaidAmountChange: (v: string) => void;

  noteCreditCode: string;
  onNoteCreditCodeChange: (value: string) => void;
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

export default function MobileCheckoutDrawer({
  open,
  onClose,
  cartItems,
  barcodeQuery,
  onBarcodeQueryChange,
  onBarcodeEnter,
  onInc,
  onDec,
  onSetQty,
  subtotal,
  tax,
  total,
  amountDue,
  isMixedPayment,
  onMixedPaymentChange,
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
  if (!open) return null;

  return (
    <div className="md:hidden fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute inset-0 p-3">
        <div className="h-full rounded-xl border border-slate-200 bg-slate-50 overflow-hidden flex flex-col">
          <div className="p-3 border-b border-slate-200 flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-900">Carrito / Pago</div>
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
              Cerrar
            </button>
          </div>

          <div className="min-h-0 flex-1 grid grid-rows-[1fr_1fr]">
            <div className="min-h-0 overflow-hidden">
              <CartPanel
                items={cartItems}
                barcodeQuery={barcodeQuery}
                onBarcodeQueryChange={onBarcodeQueryChange}
                onBarcodeEnter={onBarcodeEnter}
                onInc={onInc}
                onDec={onDec}
                onSetQty={onSetQty}
                onConfirmPurchase={onConfirmPurchase}
              />
            </div>
            <div className="min-h-0 overflow-hidden border-t border-slate-200">
              <PaymentPanel
                subtotal={subtotal}
                tax={tax}
                total={total}
                amountDue={amountDue}
                isMixedPayment={isMixedPayment}
                showNoteCredit={showNoteCredit}
                paymentMethod={paymentMethod}
                onPaymentMethodChange={onPaymentMethodChange}
                transactionNumber={transactionNumber}
                onTransactionNumberChange={onTransactionNumberChange}
                bankName={bankName}
                onBankNameChange={onBankNameChange}
                paidAmount={paidAmount}
                onPaidAmountChange={onPaidAmountChange}
                noteCreditCode={noteCreditCode}
                onNoteCreditCodeChange={onNoteCreditCodeChange}
                noteCreditSaldo={noteCreditSaldo}
                noteCreditApplied={noteCreditApplied}
                onApplyNoteCredit={onApplyNoteCredit}
                onClearNoteCredit={onClearNoteCredit}
                saleType={saleType}
                onSaleTypeChange={onSaleTypeChange}
                payments={payments}
                onPaymentsChange={onPaymentsChange}
                cashReceived={cashReceived}
                onCashReceivedChange={onCashReceivedChange}
                onConfirmPurchase={onConfirmPurchase}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
