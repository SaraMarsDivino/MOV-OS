document.addEventListener("DOMContentLoaded", () => {
    const cerrarCajaBtn = document.getElementById("close-cash-button");
    const confirmarCompraButton = document.getElementById("confirmar-compra");
    const cantidadPagadaInput = document.getElementById("cantidad_pagada");
    const vueltoElement = document.getElementById("vuelto");
    const totalPriceElement = document.getElementById("total-price");
    const cartItemsContainer = document.getElementById("cart-items");
    const searchButton = document.getElementById("product-search-button");
    const searchInput = document.getElementById("product-search-input");
    const resultsList = document.getElementById("product-search-results");
    const barcodeInput = document.getElementById("barcode-input");
    const saleTypeInput = document.getElementById("sale-type");
    const paymentHiddenInput = document.getElementById("payment-method");
    const numeroTransaccionInput = document.getElementById("numero_transaccion");
    const transactionInfoContainer = document.getElementById("transaction-info");
    const bancoInfoContainer = document.getElementById("banco-info");
    const bancoInput = document.getElementById("banco");
    const confirmAndPrintBtn = document.getElementById("confirmAndPrintBtn");
    const confirmModalElement = document.getElementById("confirmPurchaseModal");
    const hasBootstrap = typeof window !== 'undefined' && window.bootstrap && typeof window.bootstrap.Modal === 'function';
    const confirmModal = (hasBootstrap && confirmModalElement) ? new bootstrap.Modal(confirmModalElement) : null;

    // Close cash modal
    const closeCashModalElement = document.getElementById('closeCashModal');
    const closeCashEfectivoInput = document.getElementById('closeCashEfectivoContado');
    const confirmCloseCashBtn = document.getElementById('confirmCloseCashBtn');
    const closeCashExpectedEl = document.getElementById('closeCashExpected');
    const closeCashModal = (hasBootstrap && closeCashModalElement) ? new bootstrap.Modal(closeCashModalElement) : null;

    let tipoVenta = "boleta";
    let formaPago = "efectivo";
    let carrito = new Map();
    let totalCarrito = 0;
    // Simple undo support: store last successful adjustment { productoId, delta }
    let lastAction = null;

    // Leer caja_id expuesto por la plantilla (meta en cashier.html)
    const cajaMeta = document.querySelector('meta[name="current-caja-id"]');
    const cajaId = cajaMeta ? cajaMeta.getAttribute('content') : null;

    // Monto esperado por sistema (solo para mostrar; el backend recalcula al cerrar)
    const cajaExpectedMeta = document.querySelector('meta[name="current-caja-efectivo-expected"]');
    const efectivoExpectedRaw = cajaExpectedMeta ? cajaExpectedMeta.getAttribute('content') : null;

    function formatChileanCurrency(number) {
        return number.toLocaleString("es-CL", { maximumFractionDigits: 0 });
    }

    function escapeHtml(value) {
        const s = String(value ?? "");
        return s
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function showToast(message, type = "success") {
        const toastContainer = document.getElementById("toast-container") || (() => {
            const tc = document.createElement("div");
            tc.id = "toast-container";
            tc.style.position = "fixed";
            tc.style.top = "20px";
            tc.style.right = "20px";
            tc.style.zIndex = "1050";
            document.body.appendChild(tc);
            return tc;
        })();
        const toastId = `toast-${Date.now()}`;
        toastContainer.innerHTML += `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0 show" role="alert">
                <div class="d-flex">
                    <div class="toast-body fs-6">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        const toastElement = document.getElementById(toastId);
        toastElement.addEventListener('hidden.bs.toast', () => {
            try { toastElement.remove(); } catch (e) {}
        }, { once: true });
        new bootstrap.Toast(toastElement, { delay: 2000, autohide: true }).show();
    }

    // Inicializar toasts renderizados por el servidor (mensajes) para que auto-cierren.
    try {
        const existingToasts = document.querySelectorAll('#toast-container .toast');
        existingToasts.forEach((el) => {
            el.addEventListener('hidden.bs.toast', () => {
                try { el.remove(); } catch (e) {}
            }, { once: true });
            new bootstrap.Toast(el, { delay: 2000, autohide: true }).show();
        });
    } catch (e) {
        // no-op
    }

    function getCSRFToken() {
        // Prefer cookie token (required by Django double submit), fallback to meta
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (const part of cookies) {
            const [rawName, ...rest] = part.trim().split('=');
            if (rawName === 'csrftoken') return decodeURIComponent(rest.join('='));
        }
        const meta = document.querySelector('meta[name="csrf-token"], meta[name="csrfmiddlewaretoken"], input[name="csrfmiddlewaretoken"]');
        if (meta && (meta.content || meta.value)) return meta.content || meta.value;
        return "";
    }

    async function refreshCsrfToken() {
        try {
            const resp = await fetch('/reports/refresh-csrf/', { credentials: 'same-origin' });
            if (!resp.ok) return null;
            const j = await resp.json().catch(() => null);
            const token = j && j.csrftoken ? j.csrftoken : null;
            if (token) {
                try { showToast('Sesión sincronizada', 'success'); } catch (e) { console.debug('refresh toast fail', e); }
            }
            return token;
        } catch (e) {
            console.warn('refreshCsrfToken error', e);
            return null;
        }
    }

    async function csrfFetch(input, init = {}, retry = true) {
        init = Object.assign({}, init);
        if (!init.credentials) init.credentials = 'same-origin';
        const method = (init.method || 'GET').toUpperCase();
        if (method !== 'GET') {
            init.headers = init.headers || {};
            // ensure X-CSRFToken exists
            const headerKeys = Object.keys(init.headers).map(k => k.toLowerCase());
            if (!headerKeys.includes('x-csrftoken')) {
                init.headers['X-CSRFToken'] = getCSRFToken();
            }
        }

        let res = await fetch(input, init);
        if (res.status === 403) {
            // try to inspect body to detect CSRF failure
            let text = '';
            try { text = await res.text(); } catch (e) { text = ''; }
            if (isLikelyCSRFFailure(res.status, text) && retry) {
                const token = await refreshCsrfToken();
                if (token) {
                    init.headers = init.headers || {};
                    init.headers['X-CSRFToken'] = token;
                    // retry once with refreshed token
                    return await fetch(input, init);
                }
            }
            // return a Response-like object with the inspected text so callers can handle it
            return new Response(text, { status: res.status, headers: res.headers });
        }
        return res;
    }

    function isLikelyCSRFFailure(status, responseText) {
        if (!status) return false;
        if (status !== 403) return false;
        if (!responseText) return false;
        const t = responseText.toLowerCase();
        return t.includes('csrf') || t.includes('csrf token') || t.includes('csrf verification');
    }

    function handleCSRFFailure() {
        // Informar al usuario y proponer recargar para sincronizar cookies/tokens
        const msg = 'Sesión o token CSRF inválido. Recarga la página para sincronizar tu sesión.';
        try { showToast(msg, 'warning'); } catch (e) { alert(msg); }
        // Preguntar al usuario y forzar recarga si acepta
        if (confirm('Parece que tu sesión cambió o el token CSRF es inválido. ¿Recargar la página para sincronizar?')) {
            try { location.reload(); } catch (e) { window.location.href = window.location.href; }
        }
    }

    function calcularVuelto() {
        if (formaPago === "efectivo") {
            if (cantidadPagadaInput.value.trim() === "") {
                const val = -Math.abs(totalCarrito || 0);
                const abs = Math.abs(Math.round(val));
                vueltoElement.textContent = `-$${formatChileanCurrency(abs)}`;
                // color: negative
                vueltoElement.classList.remove('bg-success','bg-secondary');
                vueltoElement.classList.add('bg-danger');
            } else {
                const pagado = parseFloat(cantidadPagadaInput.value) || 0;
                const calculado = pagado - totalCarrito;
                const abs = Math.abs(Math.round(calculado));
                if (calculado < 0) {
                    vueltoElement.textContent = `-$${formatChileanCurrency(abs)}`;
                    vueltoElement.classList.remove('bg-success','bg-secondary');
                    vueltoElement.classList.add('bg-danger');
                } else if (calculado > 0) {
                    vueltoElement.textContent = `$${formatChileanCurrency(Math.round(calculado))}`;
                    vueltoElement.classList.remove('bg-danger','bg-secondary');
                    vueltoElement.classList.add('bg-success');
                } else {
                    vueltoElement.textContent = `$0`;
                    vueltoElement.classList.remove('bg-danger','bg-success');
                    vueltoElement.classList.add('bg-secondary');
                }
            }
        } else {
            vueltoElement.textContent = "$0";
            vueltoElement.classList.remove('bg-danger','bg-success');
            vueltoElement.classList.add('bg-secondary');
        }
    }
    cantidadPagadaInput.addEventListener("input", calcularVuelto);

    function debounce(func, delay = 300) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func(...args), delay);
        };
    }

    async function safeJsonResponse(res) {
        const ct = res.headers.get('content-type') || '';
        if (!ct.includes('application/json')) return null;
        return res.json().catch(() => null);
    }

    async function searchProducts(query) {
        try {
            const res = await fetch(`/cashier/buscar-producto/?q=${encodeURIComponent(query)}${cajaId ? `&caja_id=${encodeURIComponent(cajaId)}` : ''}`, {
                credentials: "same-origin"
            });
            const data = await safeJsonResponse(res);
            if (!res.ok || !data) {
                showToast("Sesión expirada o respuesta inválida. Recarga la página.", "warning");
                return;
            }
            resultsList.innerHTML = "";
            if (data.productos.length === 0) {
                resultsList.innerHTML = `<li class="list-group-item">No se encontraron productos.</li>`;
                return;
            }
            data.productos.forEach(p => {
                const li = document.createElement("li");
                li.className = "list-group-item d-flex justify-content-between align-items-center";
                const disabled = (p.en_sucursal === false);
                li.innerHTML = `
                    <span>${p.nombre} - $${formatChileanCurrency(parseFloat(p.precio_venta))} <small class="text-muted">(Stock: ${p.stock}${disabled ? ', otra sucursal' : ''})</small></span>
                    <button class="btn btn-success btn-sm" ${disabled ? 'disabled' : ''} data-id="${p.id}" data-nombre="${p.nombre}" data-precio="${p.precio_venta}" data-stock="${p.stock}" data-allow="${p.permitir_venta_sin_stock}">
                        <i class="fas fa-plus"></i>
                    </button>
                `;
                resultsList.appendChild(li);
            });
        } catch (err) {
            console.error(err);
            showToast("Error en la búsqueda.", "danger");
        }
    }
    searchButton.addEventListener("click", debounce(() => {
        const query = searchInput.value.trim();
        if (!query) return showToast("Ingresa un término de búsqueda.", "warning");
        searchProducts(query);
    }));
    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            const query = searchInput.value.trim();
            if (!query) return showToast("Ingresa un término de búsqueda.", "warning");
            searchProducts(query);
        }
    });
    resultsList.addEventListener("click", (e) => {
        const button = e.target.closest("button");
        if (button) {
            const { id, stock, allow } = button.dataset;
            if (String(allow) === "false" && parseInt(stock) <= 0) {
                showToast("Producto agotado en esta sucursal.", "warning");
                return;
            }
            agregarAlCarrito(parseInt(id));
        }
    });

    async function agregarAlCarrito(productoId) {
        try {
            const res = await csrfFetch("/cashier/agregar-al-carrito/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({ producto_id: productoId, caja_id: cajaId })
            });
            const ct = res.headers.get('content-type') || '';
            const text = await res.text();
            console.log("Respuesta del servidor:", text);
            if (!ct.includes('application/json')) {
                // Muestra un snippet útil; típicamente 403 CSRF devuelve HTML
                const snippet = text ? text.substring(0, 200) + '...' : `HTTP ${res.status}`;
                console.error('[cashier] non-json response from /cashier/agregar-al-carrito/', { status: res.status, snippet, full: text });
                if (isLikelyCSRFFailure(res.status, text)) {
                    handleCSRFFailure();
                    return;
                }
                showToast(`Error ${res.status}: ${snippet}`, 'danger');
                return;
            }
            let data;
            try { data = JSON.parse(text); } catch (err) {
                showToast('Respuesta inválida del servidor', 'danger');
                return;
            }
            if (!res.ok || data.error) {
                if (isLikelyCSRFFailure(res.status, text) || (data && data.error && String(data.error).toLowerCase().includes('csrf'))) {
                    handleCSRFFailure();
                    return;
                }
                showToast(data.error || `HTTP ${res.status}`, 'danger');
                return;
            }
            showToast(data.mensaje || "Producto agregado al carrito", "success");
            if (data.carrito) {
                carrito.clear();
                data.carrito.forEach(item => {
                    carrito.set(item.producto_id, {
                        producto_id: item.producto_id,
                        nombre: item.nombre,
                        precio: parseFloat(item.precio),
                        cantidad: item.cantidad,
                        stock: (typeof item.stock !== 'undefined') ? item.stock : undefined,
                        permitir_venta_sin_stock: (typeof item.permitir_venta_sin_stock !== 'undefined') ? item.permitir_venta_sin_stock : true
                    });
                });
                actualizarCarrito();
            }
        } catch (err) {
            console.error("Error en la petición fetch:", err);
            showToast('No se pudo contactar al servidor', 'danger');
        }

    }

    function actualizarCarrito() {
        cartItemsContainer.innerHTML = "";
        totalCarrito = 0;
        if (carrito.size === 0) {
            cartItemsContainer.innerHTML = `<tr><td colspan="4" class="text-center">No hay productos en el carrito.</td></tr>`;
        } else {
            carrito.forEach(({ producto_id, nombre, precio, cantidad }) => {
                const row = document.createElement("tr");
                const safeName = escapeHtml(nombre);
                row.innerHTML = `
                    <td class="align-middle" style="width:100px;"><input type="number" min="1" class="form-control form-control-sm cart-qty qty-input" data-id="${producto_id}" value="${cantidad}"></td>
                    <td class="align-middle cart-product" title="${safeName}">${safeName}</td>
                    <td class="align-middle">$${formatChileanCurrency(cantidad * precio)}</td>
                    <td class="align-middle">
                        <div class="cart-actions" role="group" aria-label="Ajustar cantidad">
                            <button class="btn btn-success btn-sm" data-id="${producto_id}" data-action="inc">+1</button>
                            <button class="btn btn-danger btn-sm" data-id="${producto_id}" data-action="dec">-1</button>
                        </div>
                    </td>
                `;
                cartItemsContainer.appendChild(row);
                totalCarrito += (cantidad * precio);
            });
        }
        totalPriceElement.textContent = `$${formatChileanCurrency(totalCarrito)}`;
        if (["debito", "credito", "transferencia"].includes(formaPago)) {
            cantidadPagadaInput.value = totalCarrito;
        }
        calcularVuelto();
    }

    // Handle clicks for increment/decrement and quantity inputs
    cartItemsContainer.addEventListener("click", (e) => {
        const targetButton = e.target.closest("button");
        if (!targetButton) return;
        const productoId = parseInt(targetButton.dataset.id);
        const action = targetButton.dataset.action;
        if (action === 'inc') {
            ajustarCantidadServidor(productoId, 1);
        } else if (action === 'dec') {
            ajustarCantidadServidor(productoId, -1);
        }
    });

    // Debounced handler for manual qty edits
    cartItemsContainer.addEventListener('input', (e) => {
        const input = e.target.closest('.cart-qty');
        if (!input) return;
        const productoId = parseInt(input.dataset.id);
        const newVal = parseInt(input.value) || 0;
        const current = carrito.get(productoId);
        const oldVal = current ? parseInt(current.cantidad || 0) : 0;
        const delta = newVal - oldVal;
        // If delta is zero, do nothing
        if (delta === 0) return;
        // Debounce per input by storing timer on element
        if (input._debounceTimer) clearTimeout(input._debounceTimer);
        input._debounceTimer = setTimeout(() => {
            // If newVal <= 0, remove item
            const sendDelta = newVal <= 0 ? -oldVal : delta;
            ajustarCantidadServidor(productoId, sendDelta);
        }, 450);
    });

    // Note: multi-delete removed per UI update — no delete-selected handling

    function ajustarCantidadServidor(productoId, delta) {
        // remember candidate to allow undo if server confirms
        const candidate = { productoId: productoId, delta: delta };
        return csrfFetch("/cashier/ajustar-cantidad/", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken()
            },
            body: JSON.stringify({ producto_id: productoId, cantidad: delta, caja_id: cajaId })
        })
        .then(async (res) => {
            const ct = res.headers.get('content-type') || '';
            const text = await res.text();
            let data;
            if (ct.includes('application/json')) {
                try { data = JSON.parse(text); } catch { data = { error: 'Respuesta inválida del servidor' }; }
            } else {
                data = { error: `HTTP ${res.status} - ${text.substring(0, 200)}...` };
            }
            if (!res.ok || data.error) {
                // Detectar fallo CSRF y manejar recarga de sesión
                if (isLikelyCSRFFailure(res.status, text) || (data && data.error && String(data.error).toLowerCase().includes('csrf'))) {
                    handleCSRFFailure();
                    return;
                }
                throw new Error(data.error || `HTTP ${res.status}`);
            }
            carrito.clear();
            (data.carrito || []).forEach(item => {
                carrito.set(item.producto_id, {
                    producto_id: item.producto_id,
                    nombre: item.nombre,
                    precio: parseFloat(item.precio),
                    cantidad: item.cantidad,
                    stock: (typeof item.stock !== 'undefined') ? item.stock : undefined,
                    permitir_venta_sin_stock: (typeof item.permitir_venta_sin_stock !== 'undefined') ? item.permitir_venta_sin_stock : true
                });
            });
            // record last successful action for simple Ctrl+Z undo
            try { lastAction = candidate; } catch (e) { lastAction = null; }
            actualizarCarrito();
        })
        .catch(err => {
            console.error('Error al ajustar cantidad:', err);
            // Si contiene referencia a CSRF, sugerir recarga
            const emsg = err && err.message ? err.message : '';
            if (emsg.toLowerCase().includes('csrf')) {
                handleCSRFFailure();
                return;
            }
            showToast(emsg || 'Error al ajustar cantidad', 'danger');
        });
    }

    document.querySelectorAll("[data-sale-type]").forEach(btn => {
        btn.addEventListener("click", function() {
            document.querySelectorAll("[data-sale-type]").forEach(b => {
                b.classList.remove("btn-primary", "active");
                b.classList.add("btn-outline-primary");
            });
            this.classList.remove("btn-outline-primary");
            this.classList.add("btn-primary", "active");
            saleTypeInput.value = this.getAttribute("data-sale-type");
            tipoVenta = this.getAttribute("data-sale-type");
        });
    });

    document.querySelectorAll("[data-payment-method]").forEach(btn => {
        btn.addEventListener("click", function() {
            document.querySelectorAll("[data-payment-method]").forEach(b => {
                b.classList.remove("btn-primary", "active");
                b.classList.add("btn-outline-primary");
            });
            this.classList.remove("btn-outline-primary");
            this.classList.add("btn-primary", "active");
            if (paymentHiddenInput) paymentHiddenInput.value = this.getAttribute("data-payment-method");
            formaPago = this.getAttribute("data-payment-method");

            if (["debito", "credito", "transferencia"].includes(formaPago)) {
                cantidadPagadaInput.value = totalCarrito;
                cantidadPagadaInput.readOnly = true;
                calcularVuelto();
            } else if (formaPago === "efectivo") {
                cantidadPagadaInput.readOnly = false;
                if (cantidadPagadaInput.value.trim() === "") {
                    calcularVuelto();
                }
            }
            if (["debito", "credito", "transferencia"].includes(formaPago)) {
                transactionInfoContainer.style.display = "block";
            } else {
                transactionInfoContainer.style.display = "none";
                if (numeroTransaccionInput) numeroTransaccionInput.value = "";
                if (bancoInput) bancoInput.value = "";
            }
            if (formaPago === "transferencia") {
                bancoInfoContainer.style.display = "block";
            } else {
                bancoInfoContainer.style.display = "none";
                if (bancoInput) bancoInput.value = "";
            }
            calcularVuelto();
        });
    });

    confirmarCompraButton.addEventListener("click", () => {
        if (carrito.size === 0) {
            showToast("El carrito está vacío", "warning");
            return;
        }
        if (formaPago === "efectivo") {
            const pagado = parseFloat(cantidadPagadaInput.value) || 0;
            if (pagado < totalCarrito) {
                showToast("El monto pagado es insuficiente.", "warning");
                return;
            }
        }
        if ((["debito", "credito", "transferencia"].includes(formaPago)) && !numeroTransaccionInput.value.trim()) {
            showToast("Debe ingresar el número de transacción.", "danger");
            return;
        }
        if (formaPago === "transferencia" && !bancoInput.value.trim()) {
            showToast("Debe ingresar el nombre del banco.", "danger");
            return;
        }
        if (confirmModal) {
            confirmModal.show();
        } else if (confirm("¿Está seguro de la venta?")) {
            confirmAndPrintBtn && confirmAndPrintBtn.click();
        }
    });

    confirmAndPrintBtn.addEventListener("click", async () => {
        try {
            const res = await csrfFetch("/cashier/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken()
                },
                body: JSON.stringify({
                    carrito: Array.from(carrito.values()),
                    tipo_venta: tipoVenta,
                    forma_pago: formaPago,
                    cliente_paga: parseFloat(cantidadPagadaInput.value) || 0,
                    numero_transaccion: (["debito", "credito", "transferencia"].includes(formaPago)) ? numeroTransaccionInput.value.trim() : "",
                    banco: (formaPago === "transferencia") ? bancoInput.value.trim() : "",
                    caja_id: cajaId
                })
            });
            const data = await res.json();
            if (!res.ok || !data.success) {
                showToast(data.error || "Error al confirmar", "danger");
                return;
            }
            showToast("Compra confirmada con éxito", "success");
            carrito.clear();
            actualizarCarrito();
            await csrfFetch("/cashier/limpiar-carrito/", { method: "POST" });
            if (confirmModal) confirmModal.hide();
            // Resetear completamente la UI para la siguiente venta
            try {
                // Limpiar campos de entrada
                if (searchInput) searchInput.value = "";
                if (barcodeInput) barcodeInput.value = "";
                if (cantidadPagadaInput) { cantidadPagadaInput.value = ""; cantidadPagadaInput.readOnly = false; }
                if (numeroTransaccionInput) numeroTransaccionInput.value = "";
                if (bancoInput) bancoInput.value = "";
                // Restablecer forma de pago y tipo de venta a valores por defecto
                tipoVenta = "boleta";
                saleTypeInput.value = "boleta";
                document.querySelectorAll("[data-sale-type]").forEach(b => {
                    b.classList.remove("btn-primary", "active");
                    b.classList.add("btn-outline-primary");
                    if (b.getAttribute("data-sale-type") === "boleta") {
                        b.classList.add("btn-primary", "active");
                    }
                });
                formaPago = "efectivo";
                paymentHiddenInput.value = "efectivo";
                document.querySelectorAll("[data-payment-method]").forEach(b => {
                    b.classList.remove("btn-primary", "active");
                    b.classList.add("btn-outline-primary");
                    if (b.getAttribute("data-payment-method") === "efectivo") {
                        b.classList.add("btn-primary", "active");
                    }
                });
                transactionInfoContainer.style.display = "none";
                bancoInfoContainer.style.display = "none";
                calcularVuelto();
                // Borrar resultados de búsqueda y mensaje de carrito vacío
                if (resultsList) resultsList.innerHTML = "";
                cartItemsContainer.innerHTML = `<tr><td colspan="5" class="text-center">No hay productos en el carrito.</td></tr>`;
                totalPriceElement.textContent = `$0`;
                const mobileTotal = document.getElementById('total-price-mobile');
                if (mobileTotal) mobileTotal.textContent = '0.00';
            } catch (e) { console.warn('No se pudo resetear completamente la UI:', e); }
            // Abrir el reporte en una ventana pequeña (modal) dentro de la vista de cajero
            if (data.reporte_url) {
                try {
                    // Convertir URL de reporte a la URL de embed
                    let embedUrl = data.reporte_url;
                    const matchId = data.reporte_url.match(/\/(\d+)\/?$/);
                    if (matchId) {
                        const ventaId = matchId[1];
                        embedUrl = `/cashier/reporte/embed/${ventaId}/`;
                    }
                    const resp = await fetch(embedUrl, { credentials: "same-origin" });
                    const html = await resp.text();
                    const bodyEl = document.getElementById("saleReportModalBody");
                    bodyEl.innerHTML = html;
                    if (hasBootstrap) {
                        const modal = new bootstrap.Modal(document.getElementById("saleReportModal"));
                        modal.show();
                    }
                    const printBtn = document.getElementById("printSaleReportBtn");
                    if (printBtn) {
                        printBtn.onclick = () => {
                            // Abrir versión térmica de la venta para impresión POS
                            // Convertir URL de reporte a /cashier/print/venta/<id>/
                            const match = data.reporte_url.match(/\/(\d+)\/?$/);
                            if (match) {
                                const ventaId = match[1];
                                window.open(`/cashier/print/venta/${ventaId}/`, '_blank');
                            } else {
                                window.print();
                            }
                        };
                    }
                } catch (e) {
                    console.error("No se pudo cargar el reporte en modal:", e);
                    window.open(data.reporte_url, "_blank");
                }
            }
        } catch (err) {
            console.error("Error al confirmar compra:", err);
            showToast("Error al procesar la compra", "danger");
        }
    });

    if (cerrarCajaBtn) {
        cerrarCajaBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            if (!closeCashModal) {
                showToast('No se pudo abrir el cierre de caja (modal no disponible).', 'danger');
                return;
            }
            try {
                if (closeCashEfectivoInput) closeCashEfectivoInput.value = '';
                if (closeCashExpectedEl) {
                    const n = Number(String(efectivoExpectedRaw ?? '').trim());
                    closeCashExpectedEl.textContent = Number.isFinite(n) ? `$${formatChileanCurrency(Math.round(n))}` : '-';
                }
                closeCashModal.show();
                setTimeout(() => { try { closeCashEfectivoInput && closeCashEfectivoInput.focus(); } catch (e) {} }, 150);
            } catch (err) {
                console.error('Error mostrando closeCashModal:', err);
                showToast('No se pudo abrir el cierre de caja.', 'danger');
            }
        });
    }

    let isClosingCash = false;

    function parseCLPInput(raw) {
        const s = String(raw ?? '').trim();
        if (!s) return NaN;
        // Allow CLP-style inputs like 100.000 or 100.000,00
        // Strategy: keep digits and a single leading minus; treat as integer pesos.
        const cleaned = s
            .replace(/\s+/g, '')
            .replace(/\./g, '')
            .replace(/,/g, '')
            .replace(/[^0-9-]/g, '');
        if (!cleaned || cleaned === '-') return NaN;
        return Number(cleaned);
    }

    async function submitCloseCash() {
        if (isClosingCash) return;
        isClosingCash = true;
        if (confirmCloseCashBtn) confirmCloseCashBtn.disabled = true;
        try {
            const raw = closeCashEfectivoInput ? String(closeCashEfectivoInput.value || '').trim() : '';
            if (!raw) {
                showToast('Ingresa el efectivo contado para cerrar la caja.', 'warning');
                return;
            }

            const num = parseCLPInput(raw);
            if (Number.isNaN(num)) {
                showToast('El efectivo contado debe ser un número.', 'warning');
                return;
            }
            if (num < 0) {
                showToast('El efectivo contado no puede ser negativo.', 'warning');
                return;
            }

            const payload = { caja_id: cajaId };
            payload.efectivo_contado = num;

            const res = await csrfFetch("/cashier/cerrar_caja/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const ct = res.headers.get('content-type') || '';
            const text = await res.text();
            let data;
            if (ct.includes('application/json')) {
                try { data = JSON.parse(text); } catch { data = { error: 'Respuesta inválida del servidor' }; }
            } else {
                data = { error: `HTTP ${res.status} - ${text.substring(0, 200)}...` };
            }

            if (!res.ok && isLikelyCSRFFailure(res.status, text)) {
                handleCSRFFailure();
                return;
            }
            if (data && data.error && String(data.error).toLowerCase().includes('csrf')) {
                handleCSRFFailure();
                return;
            }

            if (data.success) {
                try { closeCashModal && closeCashModal.hide(); } catch (e) {}
                try {
                    const sign = (data && typeof data.descuadre_sign === 'number') ? data.descuadre_sign : null;
                    const label = data && data.descuadre_label ? data.descuadre_label : 'Cierre de caja';
                    const amount = data && data.formatted_descuadre_signed ? data.formatted_descuadre_signed : '';
                    const msg = amount ? `${label}: ${amount}` : 'Caja cerrada exitosamente';
                    const t = (sign === -1) ? 'danger' : (sign === 1 ? 'success' : 'success');
                    showToast(msg, t);
                } catch (e) {
                    showToast("Caja cerrada exitosamente", "success");
                }
                if (data.detalle_url) {
                    window.location.href = data.detalle_url;
                } else {
                    location.reload();
                }
                return;
            }

            showToast((data && data.error) ? data.error : "Error al cerrar la caja", "danger");
        } catch (err) {
            console.error("Error al cerrar la caja:", err);
            showToast("Error al cerrar la caja", "danger");
        } finally {
            isClosingCash = false;
            if (confirmCloseCashBtn) confirmCloseCashBtn.disabled = false;
        }
    }

    if (confirmCloseCashBtn) {
        confirmCloseCashBtn.addEventListener('click', (e) => {
            e.preventDefault();
            submitCloseCash();
        });
    }
    if (closeCashEfectivoInput) {
        closeCashEfectivoInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitCloseCash();
            }
        });
    }

    function forzarCierreCaja(cajaId) {
        if (!confirm("¿Estás seguro de que deseas forzar el cierre de la caja?")) return;
        csrfFetch("/cashier/cerrar_caja/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ caja_id: cajaId, force: true })
        })
        .then(async (response) => {
            const ct = response.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
                const text = await response.text();
                throw new Error(`HTTP ${response.status} - ${text.substring(0, 200)}...`);
            }
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            alert("Caja cerrada correctamente.");
            if (data.detalle_url) window.location.href = data.detalle_url;
        })
        .catch(err => {
            console.error("Error en forzarCierreCaja:", err);
            const emsg = err && err.message ? err.message : '';
            if (emsg.toLowerCase().includes('csrf')) {
                handleCSRFFailure();
                return;
            }
            alert(`Error al cerrar la caja: ${emsg || err}`);
        });
    }

    async function handleBarcodeScan() {
        const barcode = barcodeInput.value.trim();
        if (!barcode) return;
        try {
            const res = await fetch(`/cashier/buscar-producto/?q=${encodeURIComponent(barcode)}${cajaId ? `&caja_id=${encodeURIComponent(cajaId)}` : ''}`, {
                credentials: "same-origin"
            });
            const data = await safeJsonResponse(res);
            if (!res.ok || !data) {
                showToast("Sesión expirada o respuesta inválida. Recarga la página.", "warning");
                return;
            }
            if (data.productos.length > 0) {
                const product = data.productos[0];
                agregarAlCarrito(product.id);
                barcodeInput.value = "";
            } else {
                showToast("Producto no encontrado. Intenta de nuevo.", "warning");
                barcodeInput.value = "";
            }
        } catch (err) {
            console.error(err);
            showToast("Error al buscar producto por código de barras.", "danger");
        }
    }
    barcodeInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handleBarcodeScan();
        }
    });

    if (carrito.size === 0) {
        cantidadPagadaInput.value = "";
        totalPriceElement.textContent = `$0`;
        calcularVuelto();
    }

    // Keyboard shortcuts and undo
    document.addEventListener('keydown', function(e) {
        // F2 -> focus barcode
        if (e.key === 'F2') {
            e.preventDefault();
            if (barcodeInput) barcodeInput.focus();
            return;
        }
        // F3 -> focus search input
        if (e.key === 'F3') {
            e.preventDefault();
            if (searchInput) searchInput.focus();
            return;
        }
        // F4 -> confirm purchase
        if (e.key === 'F4') {
            e.preventDefault();
            if (confirmarCompraButton) confirmarCompraButton.click();
            return;
        }
        // Ctrl+Z -> undo last adjustment
        if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
            e.preventDefault();
            if (lastAction && typeof lastAction.productoId !== 'undefined' && typeof lastAction.delta !== 'undefined') {
                // reverse the last delta
                ajustarCantidadServidor(lastAction.productoId, -lastAction.delta).then(() => {
                    showToast('Acción deshecha', 'info');
                    lastAction = null;
                }).catch(() => { showToast('No se pudo deshacer', 'warning'); });
            } else {
                showToast('Nada que deshacer', 'warning');
            }
        }
    });
});

function mostrarToast(mensaje, tipo = "success") {
    console.log(`Toast (${tipo}): ${mensaje}`);
}