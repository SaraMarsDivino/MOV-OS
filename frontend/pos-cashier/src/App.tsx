import { useEffect, useMemo, useRef, useState } from 'react';
import CatalogPanel, { type Product } from './components/CatalogPanel';
import CartPanel, { type CartItemModel } from './components/CartPanel';
import PaymentPanel, { type PaymentMethod, type SaleType, type SplitPayment } from './components/PaymentPanel';
import MobileBottomBar from './components/MobileBottomBar';
import MobileCheckoutDrawer from './components/MobileCheckoutDrawer';

type BootstrapResponse = {
  user: { username: string };
  caja: null | { id: number; sucursal: null | { id: number; nombre: string } };
  has_open_caja: boolean;
  open_caja_url: string;
  cashier_url: string;
};

type ConfirmSaleResponse = {
  success?: boolean;
  mensaje?: string;
  reporte_url?: string;
  venta_id?: number;
  error?: string;
};

type BackendProduct = {
  id: number;
  nombre: string;
  precio_venta: string;
  stock: number;
  permitir_venta_sin_stock: boolean;
  en_sucursal: boolean;
};

type BackendCartItem = {
  producto_id: number;
  nombre: string;
  precio: string;
  cantidad: number;
  stock?: number;
  permitir_venta_sin_stock?: boolean;
};

export default function App() {
  const [searchDraft, setSearchDraft] = useState<string>('');
  const [searchedQuery, setSearchedQuery] = useState<string>('');
  const [hasSearched, setHasSearched] = useState(false);
  const [barcodeQuery, setBarcodeQuery] = useState<string>('');
  const [cartItems, setCartItems] = useState<CartItemModel[]>([]);
  const [isMixedPayment, setIsMixedPayment] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('efectivo');
  const [transactionNumber, setTransactionNumber] = useState('');
  const [bankName, setBankName] = useState('');
  const [paidAmount, setPaidAmount] = useState('');

  const [payments, setPayments] = useState<SplitPayment[]>([]);
  const [saleType, setSaleType] = useState<SaleType>('boleta');
  const [cashReceived, setCashReceived] = useState('');
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  const [noteCreditCode, setNoteCreditCode] = useState('');
  const [noteCreditSaldo, setNoteCreditSaldo] = useState<number | null>(null);
  const [noteCreditLoading, setNoteCreditLoading] = useState(false);
  const [showNoteCreditSection, setShowNoteCreditSection] = useState(false);

  const [username, setUsername] = useState<string>('');
  const [sucursalName, setSucursalName] = useState<string>('');
  const [hasOpenCaja, setHasOpenCaja] = useState<boolean>(true);
  const [bootstrapDone, setBootstrapDone] = useState<boolean>(false);

  const [saleReportOpen, setSaleReportOpen] = useState(false);
  const [saleReportVentaId, setSaleReportVentaId] = useState<number | null>(null);
  const saleReportFrameRef = useRef<HTMLIFrameElement | null>(null);

  const [printPromptOpen, setPrintPromptOpen] = useState(false);
  const [printPromptVentaId, setPrintPromptVentaId] = useState<number | null>(null);

  const filteredProducts = useMemo(() => {
    // products are loaded from backend on-demand; this memo is kept for UI compatibility
    return [] as Product[];
  }, [searchedQuery, hasSearched]);

  const [products, setProducts] = useState<Product[]>([]);

  const subtotal = useMemo(() => {
    return cartItems.reduce((acc, it) => acc + it.qty * it.unitPrice, 0);
  }, [cartItems]);

  // UI-only placeholder for tax logic
  const tax = 0;
  const total = subtotal + tax;

  const noteCreditApplied = useMemo(() => {
    if (noteCreditSaldo === null) return 0;
    const usable = Math.max(0, noteCreditSaldo);
    return Math.min(usable, total);
  }, [noteCreditSaldo, total]);

  const amountDue = useMemo(() => {
    return Math.max(0, total - noteCreditApplied);
  }, [total, noteCreditApplied]);

  const resetSaleUi = () => {
    setSearchDraft('');
    setSearchedQuery('');
    setHasSearched(false);
    setProducts([]);
    setBarcodeQuery('');

    setIsMixedPayment(false);
    setPaymentMethod('efectivo');
    setTransactionNumber('');
    setBankName('');
    setPaidAmount('');

    setPayments([]);
    setCashReceived('');

    setNoteCreditCode('');
    setNoteCreditSaldo(null);
  };

  const parseAmount = (v: string) => {
    const n = Number(String(v || '').replace(/[^0-9]/g, ''));
    return Number.isFinite(n) ? n : 0;
  };

  useEffect(() => {
    // Keep payment rows aligned with the remaining amount due (after note credit).
    // Only applies to the mixed-payment UI.
    if (!isMixedPayment) return;
    if (amountDue <= 0) {
      setPayments([]);
      setCashReceived('');
      return;
    }

    setPayments((prev) => {
      if (!prev.length) {
        return [{ method: 'efectivo', amount: String(Math.round(amountDue)), transactionNumber: '', bankName: '' }];
      }
      if (prev.length === 1) {
        return [{ ...prev[0], amount: String(Math.round(amountDue)) }];
      }
      const sumExceptLast = prev.slice(0, -1).reduce((acc, p) => acc + parseAmount(p.amount), 0);
      const remainder = Math.max(0, Math.round(amountDue - sumExceptLast));
      const last = prev[prev.length - 1];
      return [...prev.slice(0, -1), { ...last, amount: String(remainder) }];
    });
  }, [amountDue, isMixedPayment]);

  useEffect(() => {
    // Simple mode UX: cash paid amount defaults to total due.
    if (isMixedPayment) return;
    if (amountDue <= 0) {
      setPaidAmount('');
      return;
    }
    if (paymentMethod === 'efectivo') {
      setPaidAmount(String(Math.round(amountDue)));
    } else {
      setPaidAmount('');
    }
  }, [amountDue, isMixedPayment, paymentMethod]);

  const onMixedPaymentChange = (next: boolean) => {
    if (next) {
      if (amountDue <= 0) return;
      const row: SplitPayment = {
        method: paymentMethod,
        amount: String(Math.round(amountDue)),
        transactionNumber: paymentMethod === 'efectivo' ? '' : transactionNumber,
        bankName: paymentMethod === 'transferencia' ? bankName : '',
      };
      setPayments([row]);
      setCashReceived(paymentMethod === 'efectivo' ? (paidAmount.trim() ? paidAmount : String(Math.round(amountDue))) : '');
      setIsMixedPayment(true);
      return;
    }

    // Switching back to simple mode (best-effort: keep first payment row as the single method)
    const first = payments[0];
    if (first) {
      setPaymentMethod(first.method);
      if (first.method === 'efectivo') {
        setPaidAmount(cashReceived.trim() ? cashReceived : first.amount);
        setTransactionNumber('');
        setBankName('');
      } else {
        setPaidAmount('');
        setTransactionNumber(first.transactionNumber || '');
        setBankName(first.method === 'transferencia' ? first.bankName || '' : '');
      }
    }
    setPayments([]);
    setCashReceived('');
    setIsMixedPayment(false);
  };

  const applyNoteCredit = async () => {
    const code = noteCreditCode.trim();
    if (!code) {
      // eslint-disable-next-line no-alert
      alert('Ingrese un código de nota de crédito');
      return;
    }

    setNoteCreditLoading(true);
    try {
      const res = await csrfFetchJson('/cashier/api/nota-credito/validar/', {
        method: 'POST',
        body: JSON.stringify({ codigo: code }),
      });

      if (!res.ok || !res.json?.ok) {
        // eslint-disable-next-line no-alert
        alert(res.json?.error || 'No se pudo validar la nota de crédito');
        setNoteCreditSaldo(null);
        return;
      }

      setNoteCreditSaldo(Number(res.json.saldo || 0));
    } catch {
      // eslint-disable-next-line no-alert
      alert('Error validando la nota de crédito');
      setNoteCreditSaldo(null);
    } finally {
      setNoteCreditLoading(false);
    }
  };

  const clearNoteCredit = () => {
    setNoteCreditCode('');
    setNoteCreditSaldo(null);
  };

  useEffect(() => {
    // Bootstrap from Django (user/caja/sucursal + CSRF cookie)
    const run = async () => {
      try {
        const res = await fetch('/cashier/api/bootstrap/', { credentials: 'include' });
        const ct = res.headers.get('content-type') || '';
        if (!ct.includes('application/json')) {
          // Likely redirected to login; hard-navigate to backend login.
          window.location.href = '/login/';
          return;
        }
        const data = (await res.json()) as BootstrapResponse;
        setUsername(data.user?.username || '');
        setHasOpenCaja(Boolean(data.has_open_caja));
        setSucursalName(data.caja?.sucursal?.nombre || '');
        setBootstrapDone(true);

        if (!data.has_open_caja) {
          window.location.href = data.open_caja_url || '/cashier/abrir-caja/';
          return;
        }

        const cartRes = await fetch('/cashier/listar-carrito/', { credentials: 'include' });
        const cartJson = await cartRes.json().catch(() => null);
        if (cartJson && Array.isArray(cartJson.carrito)) {
          setCartItems(mapBackendCartToUi(cartJson.carrito as BackendCartItem[]));
        }
      } catch {
        // If backend isn't running yet, keep UI usable.
        setBootstrapDone(true);
      }
    };
    void run();
  }, []);

  const onAddProduct = async (product: Product) => {
    if (!product.allowSaleWithoutStock && product.stock <= 0) {
      // eslint-disable-next-line no-alert
      alert(`El producto '${product.name}' no tiene suficiente stock. Disponible: ${product.stock}.`);
      return;
    }
    const res = await csrfFetchJson('/cashier/agregar-al-carrito/', {
      method: 'POST',
      body: JSON.stringify({ producto_id: product.id }),
    });
    if (res.ok && res.json && Array.isArray(res.json.carrito)) {
      setCartItems(mapBackendCartToUi(res.json.carrito as BackendCartItem[]));
      return;
    }
    if (!res.ok) {
      // eslint-disable-next-line no-alert
      alert(res.json?.error || 'No se pudo agregar el producto al carrito');
    }
  };

  const onSearch = () => {
    const q = searchDraft.trim();
    setHasSearched(true);
    setSearchedQuery(q);
    if (!q) {
      setProducts([]);
      return;
    }
    void (async () => {
      const res = await fetch(`/cashier/buscar-producto/?q=${encodeURIComponent(q)}`, {
        credentials: 'include',
      });
      const ct = res.headers.get('content-type') || '';
      if (looksLikeSessionExpired(res.status, ct)) {
        window.location.href = '/login/';
        return;
      }
      if (!res.ok || !ct.includes('application/json')) {
        // eslint-disable-next-line no-alert
        alert('Sesion expirada o respuesta invalida. Recarga la pagina.');
        return;
      }
      const data = (await res.json().catch(() => null)) as null | { productos: BackendProduct[] };
      if (!data || !Array.isArray(data.productos)) {
        setProducts([]);
        return;
      }
      setProducts(
        data.productos.map((p) => ({
          id: p.id,
          name: p.nombre,
          price: Number(p.precio_venta || 0),
          stock: p.stock,
          allowSaleWithoutStock: Boolean(p.permitir_venta_sin_stock),
          inSucursal: Boolean(p.en_sucursal),
        })),
      );
    })();
  };

  const onBarcodeEnter = () => {
    const q = barcodeQuery.trim();
    if (!q) return;
    void (async () => {
      try {
        const res = await fetch(`/cashier/buscar-producto/?q=${encodeURIComponent(q)}`, { credentials: 'include' });
        const ct = res.headers.get('content-type') || '';
        if (looksLikeSessionExpired(res.status, ct)) {
          window.location.href = '/login/';
          return;
        }
        if (!res.ok || !ct.includes('application/json')) {
          // eslint-disable-next-line no-alert
          alert('Sesion expirada o respuesta invalida. Recarga la pagina.');
          return;
        }
        const data = (await res.json().catch(() => null)) as null | { productos: BackendProduct[] };
        if (data && Array.isArray(data.productos) && data.productos.length > 0) {
          const p = data.productos[0];
          await onAddProduct({
            id: p.id,
            name: p.nombre,
            price: Number(p.precio_venta || 0),
            stock: p.stock,
            allowSaleWithoutStock: Boolean(p.permitir_venta_sin_stock),
            inSucursal: Boolean(p.en_sucursal),
          });
        }
      } finally {
        setBarcodeQuery('');
      }
    })();
  };

  const adjustQty = async (productId: number, delta: number) => {
    const res = await csrfFetchJson('/cashier/ajustar-cantidad/', {
      method: 'POST',
      body: JSON.stringify({ producto_id: productId, cantidad: delta }),
    });
    if (res.ok && res.json && Array.isArray(res.json.carrito)) {
      setCartItems(mapBackendCartToUi(res.json.carrito as BackendCartItem[]));
      return;
    }
    if (!res.ok) {
      // eslint-disable-next-line no-alert
      alert(res.json?.error || 'No se pudo ajustar la cantidad');
    }
  };

  const onInc = (id: number) => {
    const item = cartItems.find((x) => x.id === id);
    if (item && !item.allowSaleWithoutStock && item.qty >= item.stock) {
      // eslint-disable-next-line no-alert
      alert(`El producto '${item.name}' no tiene suficiente stock. Disponible: ${item.stock}.`);
      return;
    }
    void adjustQty(id, 1);
  };

  const onDec = (id: number) => {
    void adjustQty(id, -1);
  };

  const onSetQty = (id: number, qty: number) => {
    const current = cartItems.find((x) => x.id === id)?.qty ?? 0;
    const item = cartItems.find((x) => x.id === id);
    if (item && !item.allowSaleWithoutStock) {
      if (item.stock <= 0) {
        // eslint-disable-next-line no-alert
        alert(`El producto '${item.name}' no tiene suficiente stock. Disponible: ${item.stock}.`);
        return;
      }
      if (qty > item.stock) {
        // eslint-disable-next-line no-alert
        alert(`El producto '${item.name}' no tiene suficiente stock. Disponible: ${item.stock}.`);
        qty = item.stock;
      }
    }
    const delta = qty - current;
    if (delta === 0) return;
    void adjustQty(id, delta);
  };

  const onConfirmPurchase = async () => {
    if (!window.confirm('¿Desea confirmar la compra?')) return;

    if (cartItems.length === 0) {
      // eslint-disable-next-line no-alert
      alert('No hay productos en el carrito');
      return;
    }

    if (amountDue <= 0) {
      // Fully paid by note credit
      if (noteCreditSaldo === null || !noteCreditCode.trim()) {
        // eslint-disable-next-line no-alert
        alert('Debe aplicar una nota de crédito para completar el pago');
        return;
      }
    } else {
      if (!isMixedPayment) {
        if (paymentMethod === 'efectivo') {
          const paid = Number(paidAmount || 0);
          if (!Number.isFinite(paid) || paid < amountDue) {
            // eslint-disable-next-line no-alert
            alert('El efectivo entregado debe ser mayor o igual al total a pagar');
            return;
          }
        } else {
          if (!transactionNumber.trim()) {
            // eslint-disable-next-line no-alert
            alert('Ingrese el número de transacción');
            return;
          }
          if (paymentMethod === 'transferencia' && !bankName.trim()) {
            // eslint-disable-next-line no-alert
            alert('Ingrese el banco');
            return;
          }
        }
      } else {
        if (payments.length === 0) {
          // eslint-disable-next-line no-alert
          alert('Debe ingresar al menos un pago');
          return;
        }

        const methods = payments.map((p) => p.method);
        if (new Set(methods).size !== methods.length) {
          // eslint-disable-next-line no-alert
          alert('No se permite repetir métodos de pago');
          return;
        }

        const cashRows = payments.filter((p) => p.method === 'efectivo');
        if (cashRows.length > 1) {
          // eslint-disable-next-line no-alert
          alert('Solo se permite un pago en efectivo');
          return;
        }

        const sumPayments = payments.reduce((acc, p) => acc + parseAmount(p.amount), 0);
        if (sumPayments !== Math.round(amountDue)) {
          // eslint-disable-next-line no-alert
          alert('La suma de pagos debe ser exactamente igual al total a pagar');
          return;
        }

        for (const p of payments) {
          const a = parseAmount(p.amount);
          if (a <= 0) {
            // eslint-disable-next-line no-alert
            alert('Todos los pagos deben tener un monto mayor a 0');
            return;
          }
          if (p.method !== 'efectivo') {
            if (!p.transactionNumber.trim()) {
              // eslint-disable-next-line no-alert
              alert('Ingrese el número de transacción');
              return;
            }
            if (p.method === 'transferencia' && !p.bankName.trim()) {
              // eslint-disable-next-line no-alert
              alert('Ingrese el banco');
              return;
            }
          }
        }

        const cashPortion = cashRows.length ? parseAmount(cashRows[0].amount) : 0;
        if (cashPortion > 0) {
          const paid = Number(cashReceived || 0);
          if (!Number.isFinite(paid) || paid < cashPortion) {
            // eslint-disable-next-line no-alert
            alert('El efectivo entregado debe ser mayor o igual al monto en efectivo');
            return;
          }
        }
      }
    }

    const payload: Record<string, unknown> = {
      carrito: cartItems.map((it) => ({ producto_id: it.id, cantidad: it.qty })),
      tipo_venta: saleType,
    };

    if (amountDue <= 0 && noteCreditSaldo !== null) {
      payload.forma_pago = 'nota_credito';
      payload.cliente_paga = 0;
      payload.numero_transaccion = noteCreditCode.trim();
      payload.banco = '';
    } else if (!isMixedPayment) {
      payload.forma_pago = paymentMethod;
      payload.cliente_paga = paymentMethod === 'efectivo' ? Number(paidAmount || 0) : amountDue;
      payload.numero_transaccion = paymentMethod === 'efectivo' ? '' : transactionNumber.trim();
      payload.banco = paymentMethod === 'transferencia' ? bankName.trim() : '';

      if (noteCreditSaldo !== null && noteCreditCode.trim()) {
        payload.nota_credito_codigo = noteCreditCode.trim();
      }
    } else {
      const pagos = payments.map((p) => ({
        metodo: p.method,
        monto: parseAmount(p.amount),
        numero_transaccion: p.method === 'efectivo' ? '' : p.transactionNumber,
        banco: p.method === 'transferencia' ? p.bankName : '',
      }));
      payload.pagos = pagos;
      payload.forma_pago = pagos.length === 1 ? pagos[0].metodo : 'mixto';
      const cashRow = payments.find((p) => p.method === 'efectivo');
      payload.cliente_paga = cashRow ? Number(cashReceived || 0) : 0;
      payload.numero_transaccion = '';
      payload.banco = '';

      if (noteCreditSaldo !== null && noteCreditCode.trim()) {
        payload.nota_credito_codigo = noteCreditCode.trim();
      }
    }

    const res = await csrfFetchJson('/cashier/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      // Keep minimal UI feedback: alert like legacy
      // eslint-disable-next-line no-alert
      alert(res.json?.error || 'Error al confirmar la compra');
      return;
    }

    const saleRes = (res.json || {}) as ConfirmSaleResponse;

    // Clear session cart + UI (leave cashier visible and clean)
    await csrfFetchJson('/cashier/limpiar-carrito/', { method: 'POST', body: JSON.stringify({}) });
    setCartItems([]);
    resetSaleUi();

    const ventaId =
      typeof saleRes.venta_id === 'number'
        ? saleRes.venta_id
        : typeof saleRes.reporte_url === 'string'
          ? parseVentaIdFromUrl(saleRes.reporte_url)
          : null;

    if (ventaId) {
      // Evitamos window.confirm porque el navegador fuerza botones “Aceptar/Cancelar”.
      setPrintPromptVentaId(ventaId);
      setPrintPromptOpen(true);
    }
  };

  const onCloseCash = async () => {
    const raw = window.prompt('Ingresa el efectivo contado para cerrar la caja:');
    if (raw === null) return;
    const efectivo = raw.trim();

    const res = await csrfFetchJson('/cashier/cerrar_caja/', {
      method: 'POST',
      body: JSON.stringify({ efectivo_contado: efectivo }),
    });

    if (!res.ok) {
      // eslint-disable-next-line no-alert
      alert(res.json?.error || 'Error al cerrar la caja');
      return;
    }
    if (res.json?.detalle_url) {
      window.location.href = res.json.detalle_url as string;
    }
  };

  return (
    <div className="h-full min-h-0 overflow-hidden bg-slate-200 text-slate-900 flex flex-col">
      <header className="px-4 py-2 border-b border-slate-300 bg-slate-200 flex-none">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-base font-black tracking-wide text-sky-700 leading-tight truncate">
              Bienvenido, {username}
            </div>
            <div className="text-sm text-slate-600 leading-tight">Modo Cajero</div>
            <div className="mt-1 inline-flex rounded-full bg-slate-100 border border-slate-200 px-3 py-1 text-sm font-semibold text-slate-700">
              Sucursal: {sucursalName}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <a
              href="/cashier/historial-ventas/"
              className="min-h-[44px] px-4 rounded-lg bg-slate-300 text-slate-950 font-black inline-flex items-center"
            >
              Historial
            </a>
            <button
              type="button"
              disabled={amountDue <= 0}
              onClick={() => onMixedPaymentChange(!isMixedPayment)}
              className={
                'min-h-[44px] px-4 rounded-lg font-black ' +
                (amountDue <= 0
                  ? 'bg-slate-100 text-slate-400'
                  : isMixedPayment
                    ? 'bg-sky-600 text-white'
                    : 'bg-slate-300 text-slate-950')
              }
              title={isMixedPayment ? 'Volver a pago simple' : 'Pagar con más de un método'}
            >
              {isMixedPayment ? 'Pago simple' : 'Pago mixto'}
            </button>
            <button
              type="button"
              disabled={amountDue <= 0}
              onClick={() => setShowNoteCreditSection(!showNoteCreditSection)}
              className={
                'min-h-[44px] px-4 rounded-lg font-black ' +
                (amountDue <= 0
                  ? 'bg-slate-100 text-slate-400'
                  : showNoteCreditSection
                    ? 'bg-sky-600 text-white'
                    : 'bg-slate-300 text-slate-950')
              }
              title={showNoteCreditSection ? 'Ocultar nota de crédito' : 'Mostrar nota de crédito'}
            >
              {showNoteCreditSection ? 'Ocultar nota' : 'Nota de crédito'}
            </button>
            <button
              type="button"
              onClick={onCloseCash}
              className="min-h-[44px] px-4 rounded-lg bg-amber-400 text-slate-950 font-black"
            >
              Cerrar Caja
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-hidden">
        <div
          className={
            'h-full grid gap-3 p-3 ' +
            // Tablet/desktop: 3 secciones (Buscar / Carrito / Pago)
            'md:grid-cols-[3fr_2fr_360px] lg:grid-cols-[1fr_1fr_420px]'
          }
        >
          {/* Área A: Catálogo */}
          <section className="min-h-0 rounded-xl border-2 border-slate-950 bg-slate-300 shadow-xl overflow-hidden">
            <CatalogPanel
              searchQuery={searchDraft}
              onSearchQueryChange={setSearchDraft}
              hasSearched={hasSearched}
              onSearch={onSearch}
              products={products}
              onAddProduct={onAddProduct}
            />
          </section>

          {/* Área B (md+): Carrito */}
          <section className="hidden md:flex min-h-0 rounded-xl border-2 border-slate-950 bg-slate-300 shadow-xl overflow-hidden">
            <CartPanel
              items={cartItems}
              barcodeQuery={barcodeQuery}
              onBarcodeQueryChange={setBarcodeQuery}
              onBarcodeEnter={onBarcodeEnter}
              onInc={onInc}
              onDec={onDec}
              onSetQty={onSetQty}
              onConfirmPurchase={onConfirmPurchase}
            />
          </section>

          {/* Área C (md+): Pago */}
          <section className="hidden md:flex min-h-0 rounded-xl border-2 border-slate-950 bg-slate-300 shadow-xl overflow-hidden">
            <PaymentPanel
              subtotal={subtotal}
              tax={tax}
              total={total}
              amountDue={amountDue}
              isMixedPayment={isMixedPayment}
              showNoteCredit={showNoteCreditSection}
              paymentMethod={paymentMethod}
              onPaymentMethodChange={setPaymentMethod}
              transactionNumber={transactionNumber}
              onTransactionNumberChange={setTransactionNumber}
              bankName={bankName}
              onBankNameChange={setBankName}
              paidAmount={paidAmount}
              onPaidAmountChange={setPaidAmount}
              noteCreditCode={noteCreditCode}
              onNoteCreditCodeChange={(v) => {
                setNoteCreditCode(v);
                setNoteCreditSaldo(null);
              }}
              noteCreditSaldo={noteCreditSaldo}
              noteCreditApplied={noteCreditApplied}
              onApplyNoteCredit={applyNoteCredit}
              onClearNoteCredit={clearNoteCredit}
              saleType={saleType}
              onSaleTypeChange={setSaleType}
              payments={payments}
              onPaymentsChange={setPayments}
              cashReceived={cashReceived}
              onCashReceivedChange={setCashReceived}
              onConfirmPurchase={onConfirmPurchase}
            />
          </section>
        </div>

        <MobileBottomBar
          total={total}
          isOpen={isMobileDrawerOpen}
          onOpen={() => setIsMobileDrawerOpen(true)}
        />

        <MobileCheckoutDrawer
          open={isMobileDrawerOpen}
          onClose={() => setIsMobileDrawerOpen(false)}
          cartItems={cartItems}
          barcodeQuery={barcodeQuery}
          onBarcodeQueryChange={setBarcodeQuery}
          onBarcodeEnter={onBarcodeEnter}
          onInc={onInc}
          onDec={onDec}
          onSetQty={onSetQty}
          subtotal={subtotal}
          tax={tax}
          total={total}
          amountDue={amountDue}
          isMixedPayment={isMixedPayment}
          onMixedPaymentChange={onMixedPaymentChange}
          paymentMethod={paymentMethod}
          onPaymentMethodChange={setPaymentMethod}
          transactionNumber={transactionNumber}
          onTransactionNumberChange={setTransactionNumber}
          bankName={bankName}
          onBankNameChange={setBankName}
          paidAmount={paidAmount}
          onPaidAmountChange={setPaidAmount}
          noteCreditCode={noteCreditCode}
          onNoteCreditCodeChange={(v) => {
            setNoteCreditCode(v);
            setNoteCreditSaldo(null);
          }}
          noteCreditSaldo={noteCreditSaldo}
          noteCreditApplied={noteCreditApplied}
          onApplyNoteCredit={applyNoteCredit}
          onClearNoteCredit={clearNoteCredit}
          saleType={saleType}
          onSaleTypeChange={setSaleType}
          payments={payments}
          onPaymentsChange={setPayments}
          cashReceived={cashReceived}
          onCashReceivedChange={setCashReceived}
          onConfirmPurchase={onConfirmPurchase}
            showNoteCredit={showNoteCreditSection}
        />
      </main>

      {saleReportOpen && saleReportVentaId ? (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/60" onClick={() => setSaleReportOpen(false)} />

          <div className="absolute inset-0 p-3 md:p-6 flex items-center justify-center">
            <div className="w-full max-w-4xl h-[85vh] rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden flex flex-col">
              <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-slate-200 flex-none">
                <div className="min-w-0">
                  <div className="font-black text-slate-900 truncate">Detalle de Venta #{saleReportVentaId}</div>
                  <div className="text-sm text-slate-600">Impresión del detalle</div>
                </div>
                <button
                  type="button"
                  onClick={() => setSaleReportOpen(false)}
                  className="px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 font-semibold"
                >
                  Cerrar
                </button>
              </div>

              <div className="flex-1 min-h-0 bg-white">
                <iframe
                  title={`Detalle de venta ${saleReportVentaId}`}
                  src={`/cashier/reporte/embed/${saleReportVentaId}/`}
                  className="w-full h-full"
                  ref={saleReportFrameRef}
                />
              </div>

              <div className="px-4 py-3 border-t border-slate-200 flex-none flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setSaleReportOpen(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 font-semibold"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  onClick={() => {
                    try {
                      // Imprimir usando la boleta térmica dedicada (evita cortes por tablas anchas)
                      window.open(`/cashier/print/venta/${saleReportVentaId}/`, '_blank', 'noopener,noreferrer');
                    } catch {
                      // eslint-disable-next-line no-alert
                      alert('No se pudo iniciar la impresión');
                    }
                  }}
                  className="px-4 py-2 rounded-lg bg-sky-600 text-white font-black"
                >
                  Imprimir Detalle
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {printPromptOpen && printPromptVentaId ? (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => {
              setPrintPromptOpen(false);
              setPrintPromptVentaId(null);
            }}
          />

          <div className="absolute inset-0 p-3 md:p-6 flex items-center justify-center">
            <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-200">
                <div className="font-black text-slate-900">Imprimir detalle</div>
                <div className="text-sm text-slate-600">¿Desea imprimir el detalle de la venta?</div>
              </div>

              <div className="px-4 py-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPrintPromptOpen(false);
                    setPrintPromptVentaId(null);
                  }}
                  className="px-4 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 font-bold"
                >
                  No
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const ventaId = printPromptVentaId;
                    setPrintPromptOpen(false);
                    setPrintPromptVentaId(null);
                    setSaleReportVentaId(ventaId);
                    setSaleReportOpen(true);
                  }}
                  className="px-4 py-2 rounded-lg bg-sky-600 text-white font-black"
                >
                  Sí
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function parseVentaIdFromUrl(url: string): number | null {
  // Expected patterns:
  //  - /cashier/reporte/123/
  //  - /cashier/reporte/123/?...
  const m = url.match(/\/reporte\/(\d+)\//);
  if (!m) return null;
  const id = Number(m[1]);
  return Number.isFinite(id) ? id : null;
}

function getCookie(name: string): string {
  // If multiple cookies share the same name (e.g., different paths), browsers can
  // send more than one value. Django's cookie parsing will effectively use the
  // last one, so we mirror that behavior to avoid CSRF mismatches.
  const raw = document.cookie || '';
  if (!raw) return '';

  let lastValue = '';
  for (const part of raw.split(';')) {
    const cookie = part.trim();
    if (!cookie) continue;
    const eq = cookie.indexOf('=');
    if (eq <= 0) continue;
    const key = cookie.slice(0, eq);
    if (key !== name) continue;
    lastValue = cookie.slice(eq + 1);
  }
  return lastValue ? decodeURIComponent(lastValue) : '';
}

function looksLikeSessionExpired(status: number, ct: string): boolean {
  if (status === 401 || status === 403) return true;
  // Django often serves login/forbidden pages as HTML when auth/session is gone.
  return ct.includes('text/html');
}

async function csrfFetchJson(
  url: string,
  init: { method?: string; body?: string; headers?: Record<string, string> } = {},
): Promise<{ ok: boolean; status: number; json: any }>
{
  const method = (init.method || 'GET').toUpperCase();

  const doRequest = async (): Promise<{ ok: boolean; status: number; json: any; ct: string }> => {
    const headers: Record<string, string> = {
      ...(init.headers || {}),
    };
    if (method !== 'GET') {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
      headers['X-CSRFToken'] = headers['X-CSRFToken'] || getCookie('csrftoken');
      headers['X-Requested-With'] = headers['X-Requested-With'] || 'XMLHttpRequest';
    }

    const res = await fetch(url, {
      method,
      body: init.body,
      headers,
      credentials: 'include',
    });
    const ct = res.headers.get('content-type') || '';
    if (looksLikeSessionExpired(res.status, ct)) {
      window.location.href = '/login/';
      return { ok: false, status: res.status, json: null, ct };
    }
    const json = ct.includes('application/json') ? await res.json().catch(() => null) : null;
    return { ok: res.ok && ct.includes('application/json'), status: res.status, json, ct };
  };

  const ensureCsrfCookie = async () => {
    try {
      await fetch('/cashier/api/bootstrap/', { credentials: 'include' });
    } catch {
      // ignore
    }
  };

  // If we're about to POST but the CSRF cookie isn't present yet, bootstrap first.
  if (method !== 'GET' && !getCookie('csrftoken')) {
    await ensureCsrfCookie();
  }

  const first = await doRequest();

  // If CSRF failed, Django often returns an HTML 403 page (non-JSON). Retry once after bootstrap.
  if (method !== 'GET' && first.status === 403 && !first.ct.includes('application/json')) {
    await ensureCsrfCookie();
    const second = await doRequest();
    return { ok: second.ok && second.ct.includes('application/json'), status: second.status, json: second.json };
  }

  return { ok: first.ok && first.ct.includes('application/json'), status: first.status, json: first.json };
}

function mapBackendCartToUi(items: BackendCartItem[]): CartItemModel[] {
  return items.map((it) => ({
    id: Number(it.producto_id),
    name: it.nombre,
    qty: Number(it.cantidad || 0),
    unitPrice: Number(it.precio || 0),
    stock: Number(it.stock ?? 0),
    allowSaleWithoutStock: Boolean(it.permitir_venta_sin_stock),
  }));
}
